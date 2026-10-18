from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.services.runtime import RuntimeStatus, probe_ollama

router = APIRouter(tags=["system"])


class ApiInfo(BaseModel):
    status: str
    version: str
    env: str


class SystemStatus(BaseModel):
    api: ApiInfo
    mode: str
    runtime: RuntimeStatus


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "version": settings.version}


@router.get("/status", response_model=SystemStatus)
async def status(settings: Settings = Depends(get_settings)) -> SystemStatus:
    runtime = await probe_ollama(settings.ollama_url, settings.runtime_timeout_s, settings.chat_model)
    return SystemStatus(
        api=ApiInfo(status="ok", version=settings.version, env=settings.env),
        mode="local-only",
        runtime=runtime,
    )
