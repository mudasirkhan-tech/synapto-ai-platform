"""Background ingestion: parse -> chunk -> store -> embed. Runs in a worker thread."""
from sqlalchemy import select

from app import db as dbmod
from app.config import Settings
from app.models import Document, DocumentChunk
from app.services import embeddings
from app.services.chunking import chunk_sections
from app.services.files import FileRejected, parse_document


def _embed_rows(rows: list[DocumentChunk], settings: Settings) -> str | None:
    """Embeds in place. Returns a warning (and leaves embeddings empty) if the embedding model is unavailable."""
    try:
        vectors = embeddings.embed_texts(settings.ollama_url, settings.embed_model, [r.text for r in rows])
    except embeddings.EmbedError as exc:
        return f"Keyword search only. {exc}"
    for row, vec in zip(rows, vectors):
        row.embedding = embeddings.to_blob(vec)
    return None


def ingest_document(document_id: str, filename: str, data: bytes, settings: Settings) -> None:
    with dbmod.SessionLocal() as db:
        try:
            doc = db.get(Document, document_id)
            if doc is None:
                return
            chunks = chunk_sections(parse_document(filename, data), settings.chunk_size, settings.chunk_overlap)
            rows = [
                DocumentChunk(document_id=doc.id, user_id=doc.user_id, ordinal=i, page=page, text=text)
                for i, (page, text) in enumerate(chunks)
            ]
            db.add_all(rows)
            doc.chunk_count = len(rows)
            doc.char_count = sum(len(r.text) for r in rows)
            warning = _embed_rows(rows, settings)
            doc.embedded = warning is None
            doc.embed_model = None if warning else settings.embed_model
            doc.error = warning
            doc.status = "ready"
            db.commit()
        except Exception as exc:
            db.rollback()
            doc = db.get(Document, document_id)
            if doc is not None:
                doc.status = "failed"
                doc.error = exc.message if isinstance(exc, FileRejected) else "Could not process this file."
                db.commit()


def reembed_document(document_id: str, settings: Settings) -> None:
    with dbmod.SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        rows = list(
            db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.ordinal))
        )
        warning = _embed_rows(rows, settings) if rows else "No text to index."
        doc.embedded = warning is None
        doc.embed_model = None if warning else settings.embed_model
        doc.error = warning
        db.commit()
