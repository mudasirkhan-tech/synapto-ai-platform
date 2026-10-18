from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import ModelEntry, ModelsOut
from app.services import credentials
from app.services.catalog import build_catalog
from app.services.runtime import model_tags

router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelsOut)
async def list_models(user: User = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    keys = credentials.resolve_keys(db, user.id, settings)
    groups, auto, ollama_models = await build_catalog(keys, settings)
    legacy = [ModelEntry(name=m.name, size_bytes=m.size_bytes, tags=model_tags(m.name, None)) for m in ollama_models
              if "embed" not in m.name.lower() and "bge-" not in m.name.lower()]
    names = [m.name for m in legacy]
    configured = next((n for n in names if n == settings.chat_model or n.startswith(f"{settings.chat_model}:")), None)
    return ModelsOut(default=configured or (names[0] if names else settings.chat_model), reachable=bool(ollama_models) or any(g.id == "ollama" and g.status == "ok" for g in groups),
                     models=legacy, groups=groups, auto=auto)
