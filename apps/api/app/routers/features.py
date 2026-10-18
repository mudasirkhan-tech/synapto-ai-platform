"""Voice (speech-to-text), web search, image generation, calculator tools and capability reporting."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Document, User
from app.schemas import CalcIn, ConvertIn, DocumentOut, ImageGenIn, SearchIn, WebResult
from app.services import imagegen, storage, tools, voice
from app.services.runtime import probe_ollama
from app.services.search import SearchError, web_search

router = APIRouter(tags=["features"])

VOICE_SETUP = "Install local speech-to-text: `uv sync --extra voice` (downloads a Whisper model on first use), then restart the API."
SEARCH_SETUP = "Run a self-hosted SearXNG with JSON output enabled and set SYNAPTO_SEARXNG_URL (e.g. http://127.0.0.1:8080)."
IMAGE_SETUP = "Run Stable Diffusion WebUI (AUTOMATIC1111/Forge) with --api and set SYNAPTO_IMAGEGEN_URL (e.g. http://127.0.0.1:7860)."


@router.get("/capabilities")
async def capabilities(_: User = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    runtime = await probe_ollama(settings.ollama_url, settings.runtime_timeout_s, settings.embed_model)
    return {
        "embeddings": {
            "model": settings.embed_model,
            "installed": runtime.model_ready if runtime.reachable else None,
            "setup": f"ollama pull {settings.embed_model}",
        },
        "voice": {"available": voice.available(), "engine": f"faster-whisper ({settings.whisper_model})", "setup": VOICE_SETUP},
        "web_search": {"available": bool(settings.searxng_url), "engine": "SearXNG", "setup": SEARCH_SETUP},
        "image_generation": {"available": bool(settings.imagegen_url), "engine": "Stable Diffusion WebUI API", "setup": IMAGE_SETUP},
    }


@router.post("/voice/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str | None = Form(None),
    _: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    if not voice.available():
        raise HTTPException(501, f"Speech-to-text isn't installed. {VOICE_SETUP}")
    if language is not None and not (1 <= len(language) <= 8 and language.replace("-", "").isalpha()):
        raise HTTPException(422, "Invalid language code")
    data = await audio.read(settings.max_audio_bytes + 1)
    if len(data) > settings.max_audio_bytes:
        raise HTTPException(413, "Audio file is too large")
    if not data:
        raise HTTPException(422, "The recording is empty")
    try:
        text, detected = await run_in_threadpool(voice.transcribe, data, settings.whisper_model, language)
    except Exception as exc:
        raise HTTPException(422, "Could not transcribe this audio.") from exc
    return {"text": text, "language": detected}


@router.post("/search", response_model=list[WebResult])
async def search(body: SearchIn, _: User = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    if not settings.searxng_url:
        raise HTTPException(501, f"Web search isn't configured. {SEARCH_SETUP}")
    try:
        return await web_search(settings.searxng_url, body.query, limit=8)
    except SearchError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/images/generate", response_model=DocumentOut)
async def generate_image(
    body: ImageGenIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.imagegen_url:
        raise HTTPException(501, f"Image generation isn't configured. {IMAGE_SETUP}")
    try:
        png = await imagegen.txt2img(settings.imagegen_url, body.prompt, body.negative_prompt, body.width, body.height, body.steps)
    except imagegen.ImageGenError as exc:
        raise HTTPException(502, str(exc)) from exc
    name = (" ".join(body.prompt.split())[:40] or "image") + ".png"
    doc = Document(user_id=user.id, scope="generated", kind="image", filename=name, mime="image/png",
                   size_bytes=len(png), status="ready")
    db.add(doc)
    db.flush()
    doc.storage_path = storage.save_bytes(settings, user.id, doc.id, ".png", png)
    db.commit()
    return doc


@router.get("/images", response_model=list[DocumentOut])
def list_generated(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Document).where(Document.user_id == user.id, Document.scope == "generated").order_by(Document.created_at.desc())
    return list(db.scalars(stmt.limit(100)))


@router.post("/tools/calculate")
def calculate(body: CalcIn, _: User = Depends(get_current_user)):
    try:
        return {"result": tools.evaluate(body.expression)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/tools/units")
def units(_: User = Depends(get_current_user)):
    return tools.unit_catalog()


@router.post("/tools/convert")
def convert(body: ConvertIn, _: User = Depends(get_current_user)):
    try:
        return {"result": tools.convert(body.value, body.from_unit, body.to_unit)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
