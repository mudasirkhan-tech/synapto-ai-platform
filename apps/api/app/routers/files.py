from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Attachment, User
from app.schemas import AttachmentOut
from app.services.files import FileRejected, extract_text

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=AttachmentOut)
async def upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    name = Path(file.filename or "upload").name[:200] or "upload"
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File is larger than {settings.max_upload_bytes // (1024 * 1024)} MB")
    try:
        text = await run_in_threadpool(extract_text, name, data)
    except FileRejected as exc:
        raise HTTPException(exc.status, exc.message) from exc
    att = Attachment(user_id=user.id, filename=name, text=text, char_count=len(text))
    db.add(att)
    db.commit()
    return att


@router.delete("/{attachment_id}", status_code=204, response_class=Response)
def remove(attachment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    att = db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id, Attachment.user_id == user.id, Attachment.message_id.is_(None)
        )
    )
    if att is None:
        raise HTTPException(404, "Attachment not found")
    db.delete(att)
    db.commit()
    return Response(status_code=204)
