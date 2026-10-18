"""Probes the local inference runtime. Reports facts only — never fabricates status."""
import asyncio
import time

import httpx
from pydantic import BaseModel


class ModelInfo(BaseModel):
    name: str
    size_bytes: int | None = None


class RuntimeStatus(BaseModel):
    provider: str = "ollama"
    base_url: str
    reachable: bool
    version: str | None = None
    latency_ms: int | None = None
    models: list[ModelInfo] = []
    required_model: str
    model_ready: bool = False
    error: str | None = None


def _has_model(models: list[ModelInfo], wanted: str) -> bool:
    return any(m.name == wanted or m.name.startswith(f"{wanted}:") for m in models)


async def probe_ollama(base_url: str, timeout_s: float, required_model: str) -> RuntimeStatus:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout_s) as client:
            version_res = await client.get("/api/version")
            version_res.raise_for_status()
            tags_res = await client.get("/api/tags")
            tags_res.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        return RuntimeStatus(
            base_url=base_url,
            reachable=False,
            required_model=required_model,
            error=f"{type(exc).__name__}: runtime not reachable",
        )

    models = [
        ModelInfo(name=m.get("name", "unknown"), size_bytes=m.get("size"))
        for m in tags_res.json().get("models", [])
    ]
    return RuntimeStatus(
        base_url=base_url,
        reachable=True,
        version=version_res.json().get("version"),
        latency_ms=round((time.perf_counter() - started) * 1000),
        models=models,
        required_model=required_model,
        model_ready=_has_model(models, required_model),
    )


VISION_HINTS = ("vision", "llava", "moondream", "minicpm-v", "bakllava", "gemma3", "qwen2.5vl", "qwen2-vl")


async def get_capabilities(base_url: str, model: str, timeout_s: float = 3.0) -> set[str] | None:
    """Capabilities Ollama reports for a model (e.g. {"completion", "vision"}); None when unknown."""
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout_s) as client:
            res = await client.post("/api/show", json={"model": model})
            res.raise_for_status()
            caps = res.json().get("capabilities")
    except (httpx.HTTPError, ValueError):
        caps = None
    if isinstance(caps, list):
        return {str(c) for c in caps}
    return {"vision"} if any(h in model.lower() for h in VISION_HINTS) else None


def model_tags(name: str, caps: set[str] | None) -> list[str]:
    lower = name.lower()
    tags = []
    if (caps and "vision" in caps) or any(h in lower for h in VISION_HINTS):
        tags.append("vision")
    if "coder" in lower or "codellama" in lower or "codegemma" in lower:
        tags.append("code")
    if lower.startswith(("qwen2.5", "qwen3", "aya", "gemma2", "gemma3", "llama3.1", "mistral-nemo")) and "coder" not in lower:
        tags.append("multilingual")
    return tags


async def capabilities_for(base_url: str, names: list[str], timeout_s: float = 3.0) -> dict[str, set[str] | None]:
    results = await asyncio.gather(*(get_capabilities(base_url, n, timeout_s) for n in names[:30]))
    return dict(zip(names[:30], results))
