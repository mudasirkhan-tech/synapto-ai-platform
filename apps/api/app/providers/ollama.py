"""Local Ollama adapter: wraps the existing llm.py functions so Ollama behaves like any other provider."""
from collections.abc import AsyncIterator

from app.providers.base import CallContext, Chunk, Completion, ModelSpec, ProviderError
from app.services import llm
from app.services.runtime import probe_ollama

ID = "ollama"


def _to_ollama(m: dict) -> dict:
    out = {"role": m["role"], "content": m["content"]}
    if m.get("images"):
        out["images"] = [i["data"] for i in m["images"]]  # Ollama takes raw base64 strings
    return out


def _wrap(exc: llm.LLMError) -> ProviderError:
    text = str(exc)
    if "not installed" in text:
        kind = "not_found"
    elif "too long" in text:
        kind = "timeout"
    else:
        kind = "unavailable"
    return ProviderError(kind, text, provider=ID)


class OllamaProvider:
    id = ID
    label = "Local · Ollama"
    cloud = False

    async def stream(self, ctx: CallContext, spec: ModelSpec, messages: list[dict]) -> AsyncIterator[Chunk]:
        try:
            async for token in llm.stream_chat(ctx.settings.ollama_url, spec.model, [_to_ollama(m) for m in messages], ctx.settings.num_ctx):
                yield Chunk(text=token)
        except llm.LLMError as exc:
            raise _wrap(exc) from exc

    async def complete(self, ctx: CallContext, spec: ModelSpec, messages: list[dict], json_mode: bool) -> Completion:
        try:
            if json_mode:
                text = await llm.chat_json(ctx.settings.ollama_url, spec.model, [_to_ollama(m) for m in messages],
                                           ctx.settings.num_ctx, ctx.settings.agent_llm_timeout_s)
            else:
                text = "".join([t async for t in llm.stream_chat(ctx.settings.ollama_url, spec.model, [_to_ollama(m) for m in messages], ctx.settings.num_ctx)])
        except llm.LLMError as exc:
            raise _wrap(exc) from exc
        return Completion(text, None, ID, spec.model)

    async def list_remote_models(self, ctx: CallContext) -> set[str]:
        runtime = await probe_ollama(ctx.settings.ollama_url, ctx.settings.runtime_timeout_s, ctx.settings.chat_model)
        if not runtime.reachable:
            raise ProviderError("unavailable", f"Cannot reach Ollama at {ctx.settings.ollama_url}.", provider=ID)
        return {m.name for m in runtime.models}

    async def test(self, ctx: CallContext) -> tuple[bool, str]:
        try:
            names = await self.list_remote_models(ctx)
        except ProviderError as exc:
            return False, exc.message
        return True, f"Ollama is running with {len(names)} model(s)."
