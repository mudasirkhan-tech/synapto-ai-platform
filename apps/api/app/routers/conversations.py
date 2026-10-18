import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Conversation, Document, Message, User, utcnow
from app.schemas import AttachmentRef, ConversationOut, ConversationPatch, MessageOut, SourceOut
from app.services import storage

router = APIRouter(prefix="/conversations", tags=["conversations"])


def owned_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
    conv = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return conv


def _stored_paths(db: Session, condition) -> list[str]:
    stmt = select(Document.storage_path).join(Message, Document.message_id == Message.id).where(condition, Document.storage_path.is_not(None))
    return list(db.scalars(stmt))


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


def _sources(raw: str | None) -> list[SourceOut]:
    try:
        return [SourceOut(**item) for item in json.loads(raw)] if raw else []
    except (ValueError, TypeError):
        return []


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = owned_conversation(db, user, conversation_id)
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .options(selectinload(Message.documents))
        .order_by(Message.id)
    )
    return [
        MessageOut(
            id=m.id, role=m.role, content=m.content, model=m.model, provider=m.provider, finish=m.finish,
            sources=_sources(m.sources_json),
            attachments=[AttachmentRef(id=d.id, filename=d.filename, kind=d.kind) for d in m.documents],
        )
        for m in rows
    ]


@router.get("/export")
def export_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    convs = db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.created_at)
        .options(selectinload(Conversation.messages))
    )
    return {
        "exported_at": utcnow().isoformat(),
        "conversations": [
            {
                "id": c.id, "title": c.title, "created_at": c.created_at.isoformat(),
                "messages": [{"role": m.role, "content": m.content, "model": m.model, "created_at": m.created_at.isoformat()} for m in c.messages],
            }
            for c in convs
        ],
    }


@router.patch("/{conversation_id}", response_model=ConversationOut)
def rename(
    conversation_id: str,
    body: ConversationPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = owned_conversation(db, user, conversation_id)
    conv.title = body.title.strip()[:200] or conv.title
    conv.updated_at = utcnow()
    db.commit()
    return conv


@router.delete("/{conversation_id}", status_code=204, response_class=Response)
def delete(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    conv = owned_conversation(db, user, conversation_id)
    paths = _stored_paths(db, Message.conversation_id == conv.id)
    db.delete(conv)
    db.commit()
    for path in paths:
        storage.remove(settings, path)
    return Response(status_code=204)


@router.delete("", status_code=204, response_class=Response)
def delete_all(user: User = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    paths = _stored_paths(db, Message.conversation_id.in_(select(Conversation.id).where(Conversation.user_id == user.id)))
    for conv in db.scalars(select(Conversation).where(Conversation.user_id == user.id)):
        db.delete(conv)
    db.commit()
    for path in paths:
        storage.remove(settings, path)
    return Response(status_code=204)
