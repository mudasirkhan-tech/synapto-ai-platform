from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Document, User
from app.schemas import DocumentOut
from app.services import storage
from app.services.files import IMAGE_EXT, classify, sniff_image
from app.services.ingest import ingest_document, reembed_document

router = APIRouter(prefix="/documents", tags=["documents"])


def owned_document(db: Session, user: User, document_id: str) -> Document:
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.user_id == user.id))
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("", response_model=DocumentOut)
async def upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    scope: str = Form("library"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if scope not in {"library", "chat"}:
        raise HTTPException(422, "scope must be 'library' or 'chat'")
    name = Path(file.filename or "upload").name[:200] or "upload"
    kind = classify(name)
    if kind is None:
        raise HTTPException(415, "Unsupported file type. Use PDF, DOCX, TXT, MD, CSV, JSON, or an image (PNG, JPG, WEBP, GIF).")
    if kind == "image" and scope != "chat":
        raise HTTPException(415, "Images can only be attached to chat messages.")

    limit = settings.max_image_bytes if kind == "image" else settings.max_doc_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {limit // (1024 * 1024)} MB")

    ext = Path(name).suffix.lower()
    doc = Document(user_id=user.id, scope=scope, kind=kind, filename=name, size_bytes=len(data))
    if kind == "image":
        if not sniff_image(data, ext):
            raise HTTPException(422, "This file is not a valid image.")
        doc.mime = IMAGE_EXT[ext]
        doc.status = "ready"
        db.add(doc)
        db.flush()
        doc.storage_path = storage.save_bytes(settings, user.id, doc.id, ext, data)
        db.commit()
        return doc

    doc.status = "processing"
    db.add(doc)
    db.commit()
    background.add_task(ingest_document, doc.id, name, data, settings)  # parse + chunk + embed off the request path
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(
    scope: str = "library", user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    stmt = select(Document).where(Document.user_id == user.id, Document.scope == scope).order_by(Document.created_at.desc())
    return list(db.scalars(stmt.limit(200)))


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return owned_document(db, user, document_id)


@router.get("/{document_id}/file")
def get_file(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    doc = owned_document(db, user, document_id)
    if doc.kind != "image" or not doc.storage_path:
        raise HTTPException(404, "No stored file for this document")
    try:
        path = storage.abs_path(settings, doc.storage_path)
    except ValueError:
        raise HTTPException(404, "File not found")
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type=doc.mime or "application/octet-stream", headers={"X-Content-Type-Options": "nosniff"})


@router.post("/{document_id}/reindex", response_model=DocumentOut)
def reindex(
    document_id: str,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    doc = owned_document(db, user, document_id)
    if doc.kind != "document" or doc.status != "ready":
        raise HTTPException(409, "Only processed documents can be re-indexed")
    background.add_task(reembed_document, doc.id, settings)
    return doc


@router.delete("/{document_id}", status_code=204)
def delete(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    doc = owned_document(db, user, document_id)
    if doc.message_id is not None:
        raise HTTPException(409, "This file belongs to a chat message. Delete the conversation to remove it.")
    path = doc.storage_path
    db.delete(doc)
    db.commit()
    storage.remove(settings, path)
