"""Builds the <sources> context for a chat turn: document retrieval + optional web search."""
from dataclasses import dataclass, field

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Document, Message
from app.schemas import WebResult
from app.services import embeddings, retrieval
from app.services.prompt import format_sources


@dataclass
class TurnContext:
    block: str | None = None
    sources: list[dict] = field(default_factory=list)


async def build_context(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    query: str,
    use_knowledge: bool,
    web_results: list[WebResult],
    settings: Settings,
) -> TurnContext:
    # Scope = documents attached in this conversation (+ the user's library when asked). Always owner-filtered.
    doc_ids = set(
        db.scalars(
            select(Document.id)
            .join(Message, Document.message_id == Message.id)
            .where(Message.conversation_id == conversation_id, Document.user_id == user_id,
                   Document.kind == "document", Document.status == "ready")
        )
    )
    if use_knowledge:
        doc_ids |= set(
            db.scalars(
                select(Document.id).where(
                    Document.user_id == user_id, Document.scope == "library",
                    Document.kind == "document", Document.status == "ready",
                )
            )
        )

    items: list[tuple[str, str]] = []
    sources: list[dict] = []

    if doc_ids:
        query_vec = None
        try:
            vecs = await run_in_threadpool(embeddings.embed_texts, settings.ollama_url, settings.embed_model, [query])
            query_vec = embeddings.normalise(vecs[0])
        except embeddings.EmbedError:
            pass  # fall back to keyword-only retrieval
        hits = retrieval.retrieve(
            db, user_id, sorted(doc_ids), query, query_vec,
            k=settings.retrieval_top_k, small_doc_chars=settings.retrieval_char_budget,
        )
        for h in hits:
            label = f"{h.filename} (page {h.page})" if h.page else h.filename
            items.append((label, h.text))
            sources.append({"title": h.filename, "kind": "document", "document_id": h.document_id,
                            "page": h.page, "url": None, "snippet": h.text[:200]})

    for r in web_results:
        items.append((f"{r.title} — {r.url}", r.snippet))
        sources.append({"title": r.title, "kind": "web", "document_id": None, "page": None, "url": r.url, "snippet": r.snippet[:200]})

    block, kept = format_sources(items, settings.retrieval_char_budget)
    sources = sources[:kept]  # only sources that actually made it into the prompt are cited
    for n, s in enumerate(sources, start=1):
        s["n"] = n
    return TurnContext(block=block or None, sources=sources)
