"""Model catalog for the selector: what exists, what is actually usable right now, and what Auto would pick."""
import hashlib
import time

from app.config import Settings
from app.providers import CLOUD_IDS, PROVIDERS
from app.providers.base import CallContext, ProviderError
from app.schemas import AutoInfo, CatalogGroup, CatalogModel
from app.services import routing
from app.services.runtime import capabilities_for, model_tags, probe_ollama

TTL_S = 120.0
_cache: dict[tuple[str, str], tuple[float, tuple[str, set[str]]]] = {}
USABLE = {"ready", "unverified"}


def clear_cache() -> None:
    _cache.clear()


async def verify(provider_id: str, key: str, settings: Settings) -> tuple[str, set[str]]:
    """(status, remote model ids): status is ok | auth_error | billing | unverified (e.g. network trouble)."""
    ck = (provider_id, hashlib.sha256(key.encode()).hexdigest()[:16])
    hit = _cache.get(ck)
    if hit and time.monotonic() - hit[0] < TTL_S:
        return hit[1]
    try:
        models = await PROVIDERS[provider_id].list_remote_models(CallContext(key, settings))
        result: tuple[str, set[str]] = ("ok", models)
    except ProviderError as exc:
        result = ("auth_error" if exc.kind == "auth" else "billing" if exc.kind == "billing" else "unverified", set())
    _cache[ck] = (time.monotonic(), result)
    return result


async def build_catalog(keys: dict[str, str], settings: Settings) -> tuple[list[CatalogGroup], AutoInfo, list]:
    specs = routing.cloud_specs(settings)
    groups: list[CatalogGroup] = []

    for pid in CLOUD_IDS:
        provider = PROVIDERS[pid]
        key = keys.get(pid)
        status, remote = ("no_key", set()) if not key else await verify(pid, key, settings)
        detail = {
            "no_key": "No API key. Add one in Settings → API keys.",
            "auth_error": "The API key was rejected.",
            "billing": "The provider reports insufficient balance.",
            "unverified": "Could not verify model availability right now.",
            "ok": "Connected.",
        }[status]
        models: list[CatalogModel] = []
        for spec in (s for s in specs.values() if s.provider == pid):
            if status == "no_key":
                state, note = "needs_key", "Needs an API key"
            elif status in {"auth_error", "billing"}:
                state, note = status, detail
            elif status == "unverified":
                state, note = "unverified", "Availability not verified"
            elif spec.model in remote:
                state, note = "ready", ""
            else:
                state, note = "unavailable", f"'{spec.model}' isn't offered to this API account (retired or no access). Change it in the server configuration."
            models.append(CatalogModel(ref=spec.ref, label=spec.label, model_id=spec.model, state=state, detail=note, tags=list(spec.tags), vision=spec.vision))
        groups.append(CatalogGroup(id=pid, label=provider.label.upper(), cloud=True, status=status, detail=detail, models=models))

    runtime = await probe_ollama(settings.ollama_url, settings.runtime_timeout_s, settings.chat_model)
    local_models: list[CatalogModel] = []
    if runtime.reachable and runtime.models:
        caps = await capabilities_for(settings.ollama_url, [m.name for m in runtime.models])
        for m in runtime.models:
            if "embed" in m.name.lower() or "bge-" in m.name.lower():
                continue
            tags = model_tags(m.name, caps.get(m.name))
            local_models.append(CatalogModel(ref=f"ollama:{m.name}", label=m.name, model_id=m.name, state="ready", tags=tags, vision="vision" in tags or None))
    groups.append(CatalogGroup(
        id="ollama", label="LOCAL — OLLAMA", cloud=False,
        status="ok" if runtime.reachable else "unreachable",
        detail="Runs on this computer (slow on CPU)." if runtime.reachable else f"Ollama isn't reachable at {settings.ollama_url}.",
        models=local_models,
    ))

    state_of = {m.ref: m.state for g in groups for m in g.models}
    local_ok = any(m.model_id == settings.chat_model or m.model_id.startswith(f"{settings.chat_model}:") for m in local_models)
    order, note = [], ""
    candidates, _ = routing.auto_candidates(settings, keys)
    for spec in candidates:
        usable = local_ok if spec.provider == "ollama" else state_of.get(spec.ref) in USABLE
        if usable:
            order.append(spec)
    first = order[0] if order else None
    if first is None:
        note = "Nothing is available right now. Add an API key or start Ollama."
    elif first.provider == "ollama":
        note = "No cloud key is working, so Auto uses the local model (slow)."
    auto = AutoInfo(ref=first.ref if first else None, label=first.label if first else "Unavailable", order=[s.ref for s in order], note=note)
    return groups, auto, runtime.models
