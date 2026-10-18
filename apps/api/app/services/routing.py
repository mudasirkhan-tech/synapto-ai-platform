"""Model routing: selection parsing, cloud-first plan, retries, fallback, and the normalised event stream."""
import asyncio
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.config import Settings
from app.providers import PROVIDERS, get_provider
from app.providers.base import CallContext, Completion, ModelSpec, ProviderError

REASONING_HINTS = re.compile(
    r"\b(prove|proof|derive|theorem|puzzle|riddle|logic problem|time complexity|optimal solution|mathematical|equation)\b", re.I
)


def cloud_specs(settings: Settings) -> dict[str, ModelSpec]:
    specs = [
        ModelSpec("deepseek", settings.deepseek_chat_model, "chat", "DeepSeek Chat", thinking=False, vision=True, tags=("fast",)),
        ModelSpec("deepseek", settings.deepseek_reasoner_model, "reasoner", "DeepSeek Reasoner", thinking=True, vision=True, tags=("reasoning",)),
        ModelSpec("gemini", settings.gemini_pro_model, "pro", "Gemini Pro", vision=True, tags=("pro",)),
        ModelSpec("gemini", settings.gemini_flash_model, "flash", "Gemini Flash", vision=True, tags=("fast",)),
    ]
    return {s.ref: s for s in specs}


def ollama_spec(name: str, vision: bool | None = None) -> ModelSpec:
    return ModelSpec("ollama", name, name, name, vision=vision, tags=("local",))


@dataclass
class Selection:
    auto: bool
    spec: ModelSpec | None = None


def parse_selection(value: str | None, settings: Settings) -> Selection:
    """'auto' | 'deepseek:chat' | 'gemini:pro' | 'ollama:<name>' | '<bare ollama name>' (legacy clients)."""
    if not value or value == "auto":
        return Selection(True)
    prefix, _, rest = value.partition(":")
    if prefix in PROVIDERS and rest:
        if prefix == "ollama":
            return Selection(False, ollama_spec(rest))
        spec = cloud_specs(settings).get(value)
        if spec is None:
            raise ValueError(f"Unknown model '{value}'")
        return Selection(False, spec)
    return Selection(False, ollama_spec(value))


def needs_reasoning(text: str) -> bool:
    return len(text) >= 50 and bool(REASONING_HINTS.search(text))


@dataclass
class RoutePlan:
    candidates: list[ModelSpec]
    auto: bool
    fallback: bool
    notes: list[str] = field(default_factory=list)


def auto_candidates(settings: Settings, keys: dict[str, str], query: str = "") -> tuple[list[ModelSpec], list[str]]:
    specs = cloud_specs(settings)
    out: list[ModelSpec] = []
    if settings.route_reasoning and keys.get("deepseek") and needs_reasoning(query):
        out.append(specs["deepseek:reasoner"])
    for ref in settings.auto_order:
        spec = specs.get(ref)
        if spec and keys.get(spec.provider) and spec not in out:
            out.append(spec)
    notes: list[str] = []
    if not out:
        notes.append("No cloud API key is configured, so Synapto is using a local model, which can be slow. Add a DeepSeek or Gemini key in Settings → API keys.")
    if settings.local_fallback or not out:
        out.append(ollama_spec(settings.chat_model))
    return out, notes


def build_plan(
    selection: Selection,
    settings: Settings,
    keys: dict[str, str],
    *,
    query: str = "",
    needs_vision: bool = False,
    fallback: bool | None = None,
) -> RoutePlan:
    fb = settings.fallback_default if fallback is None else fallback
    auto, notes = auto_candidates(settings, keys, query)
    if selection.auto:
        candidates = auto
    else:  # manual choice always goes first; fallbacks follow only if enabled
        assert selection.spec is not None
        candidates = [selection.spec] + [s for s in auto if s.ref != selection.spec.ref]
        notes = []
    if needs_vision:
        candidates = [s for s in candidates if s.vision is not False]
    return RoutePlan(candidates, selection.auto, fb, notes)


def _fallback_ok(err: ProviderError, auto: bool) -> bool:
    if err.kind in {"rate_limit", "timeout", "unavailable"}:
        return True
    # Credential/model problems are configuration errors: only skipped in Auto, never hidden for a manual pick.
    return auto and err.kind in {"auth", "billing", "not_found"}


def _summary(failures: list[tuple[ModelSpec, ProviderError]]) -> str:
    if len(failures) == 1:
        return failures[0][1].message
    return "No provider could answer. " + " ".join(f"{s.label}: {e.message}" for s, e in failures)


async def _guard(gen: AsyncIterator, settings: Settings, label: str) -> AsyncIterator:
    """Adds first-token and stall timeouts to any provider stream and always closes it."""
    it = gen.__aiter__()
    timeout = settings.provider_first_token_timeout_s
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(it.__anext__(), timeout)
            except StopAsyncIteration:
                return
            except asyncio.TimeoutError:
                raise ProviderError("timeout", f"{label} did not respond in time.") from None
            timeout = settings.provider_stall_timeout_s
            yield chunk
    finally:
        aclose = getattr(it, "aclose", None)
        if aclose is not None:
            try:
                await aclose()
            except Exception:
                pass


def _status(spec: ModelSpec, phase: str, message: str) -> dict:
    return {"type": "status", "phase": phase, "provider": spec.provider, "model": spec.model, "label": spec.label, "message": message}


async def route_stream(
    plan: RoutePlan, messages: list[dict], *, settings: Settings, keys: dict[str, str], announce: bool = True
) -> AsyncIterator[dict]:
    """Yields normalised events: status | token | fallback | error | finished. Never switches provider once text has started."""
    failures: list[tuple[ModelSpec, ProviderError]] = []
    fell_back = False
    for i, spec in enumerate(plan.candidates):
        provider = get_provider(spec.provider)
        key = keys.get(spec.provider)
        if announce:
            msg = f"Connecting to {provider.label}..." if provider.cloud else f"Loading local model {spec.model} (may be slow)..."
            yield _status(spec, "connecting", msg)
        err: ProviderError | None = None
        if provider.cloud and not key:
            err = ProviderError("auth", f"{provider.label} API key is missing. Add it in Settings → API keys.", provider=spec.provider)
        else:
            attempts = 0
            while True:
                started, announced_thinking, usage = False, False, None
                t0 = time.perf_counter()
                first_ms: int | None = None
                try:
                    async for chunk in _guard(provider.stream(CallContext(key, settings), spec, messages), settings, provider.label):
                        if chunk.usage:
                            usage = chunk.usage
                        if chunk.thinking and not announced_thinking:
                            announced_thinking = True
                            yield _status(spec, "thinking", f"{spec.label} is reasoning...")
                        if chunk.text:
                            if first_ms is None:
                                first_ms = round((time.perf_counter() - t0) * 1000)
                            started = True
                            yield {"type": "token", "text": chunk.text}
                    yield {
                        "type": "finished", "provider": spec.provider, "model": spec.model, "label": spec.label,
                        "latency_ms": round((time.perf_counter() - t0) * 1000), "first_token_ms": first_ms,
                        "usage": usage.as_dict() if usage else None, "fallback_used": fell_back,
                    }
                    return
                except ProviderError as exc:
                    if started:  # a provider failing mid-answer is reported, not silently replaced
                        yield {"type": "error", "kind": exc.kind, "provider": spec.provider,
                               "message": f"{provider.label} stopped mid-answer: {exc.message} The reply above is incomplete."}
                        return
                    if exc.retryable and attempts < settings.provider_max_retries:
                        attempts += 1
                        yield _status(spec, "retry", f"{provider.label}: {exc.message} Retrying...")
                        await asyncio.sleep(settings.provider_retry_backoff_s * attempts)
                        continue
                    err = exc
                    break
        failures.append((spec, err))
        nxt = plan.candidates[i + 1] if i + 1 < len(plan.candidates) else None
        if nxt is not None and plan.fallback and _fallback_ok(err, plan.auto):
            fell_back = True
            slow = nxt.provider == "ollama"
            yield {
                "type": "fallback", "from": spec.label, "to": nxt.label, "reason": err.message, "slow": slow,
                "message": f"{provider.label} failed: {err.message} Switching to {nxt.label}" + (" (local, may be much slower)." if slow else "."),
            }
            continue
        break
    last = failures[-1][1]
    yield {"type": "error", "kind": last.kind, "provider": failures[-1][0].provider, "message": _summary(failures)}


async def complete(
    plan: RoutePlan, messages: list[dict], *, settings: Settings, keys: dict[str, str], json_mode: bool = False
) -> Completion:
    """Non-streaming call with the same retry/fallback policy. Raises ProviderError when every allowed provider fails."""
    failures: list[tuple[ModelSpec, ProviderError]] = []
    for i, spec in enumerate(plan.candidates):
        provider = get_provider(spec.provider)
        key = keys.get(spec.provider)
        err: ProviderError | None = None
        if provider.cloud and not key:
            err = ProviderError("auth", f"{provider.label} API key is missing. Add it in Settings → API keys.", provider=spec.provider)
        else:
            attempts = 0
            while True:
                try:
                    return await asyncio.wait_for(
                        provider.complete(CallContext(key, settings), spec, messages, json_mode), settings.provider_total_timeout_s
                    )
                except asyncio.TimeoutError:
                    exc = ProviderError("timeout", f"{provider.label} did not respond in time.", provider=spec.provider)
                except ProviderError as e:
                    exc = e
                if exc.retryable and attempts < settings.provider_max_retries:
                    attempts += 1
                    await asyncio.sleep(settings.provider_retry_backoff_s * attempts)
                    continue
                err = exc
                break
        failures.append((spec, err))
        has_next = i + 1 < len(plan.candidates)
        if has_next and plan.fallback and _fallback_ok(err, plan.auto):
            continue
        break
    raise ProviderError(failures[-1][1].kind, _summary(failures), provider=failures[-1][0].provider)
