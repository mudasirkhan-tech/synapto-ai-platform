"""Google Gemini through the official `google-genai` SDK (imported lazily)."""
import asyncio
import base64
from collections.abc import AsyncIterator

from app.providers.base import CallContext, Chunk, Completion, ModelSpec, ProviderError, Usage
from app.services.credentials import redact

ID = "gemini"


def _make_client(ctx: CallContext):  # module-level so tests can substitute a fake
    from google import genai
    from google.genai import types

    timeout_ms = int(ctx.settings.provider_total_timeout_s * 1000)
    return genai.Client(api_key=ctx.api_key, http_options=types.HttpOptions(timeout=timeout_ms))


def map_exception(exc: Exception) -> ProviderError:
    code = getattr(exc, "code", None)
    text = redact(str(getattr(exc, "message", "") or exc))[:200]
    if isinstance(code, int):
        if code in (401, 403) or (code == 400 and ("API key" in text or "API_KEY" in text)):
            return ProviderError("auth", "Gemini rejected the API key. Check it in Settings → API keys.", provider=ID, status=code)
        if code == 404:
            return ProviderError("not_found", "Gemini doesn't offer this model ID to your account (it may be retired). Change it in the server configuration.", provider=ID, status=code)
        if code == 429:
            return ProviderError("rate_limit", "Gemini rate limit or quota reached.", provider=ID, status=code)
        if code >= 500:
            return ProviderError("unavailable", "Gemini is temporarily unavailable.", provider=ID, status=code)
        return ProviderError("bad_request", f"Gemini rejected the request ({code}). {text}".strip(), provider=ID, status=code)
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in type(exc).__name__.lower():
        return ProviderError("timeout", "Gemini did not respond in time.", provider=ID)
    if isinstance(exc, (ConnectionError, OSError)) or "connect" in type(exc).__name__.lower():
        return ProviderError("unavailable", "Could not reach Gemini.", provider=ID)
    return ProviderError("unknown", "The Gemini request failed.", provider=ID)


def _convert(messages: list[dict]):
    from google.genai import types

    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    contents: list = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "model" if m["role"] == "assistant" else "user"
        parts = [types.Part.from_text(text=m["content"])]
        for img in m.get("images") or []:
            parts.append(types.Part.from_bytes(data=base64.b64decode(img["data"]), mime_type=img["mime"]))
        if contents and contents[-1].role == role:  # Gemini expects alternating turns
            contents[-1].parts.extend(parts)
        else:
            contents.append(types.Content(role=role, parts=parts))
    return system, contents


def _usage(chunk) -> Usage | None:
    um = getattr(chunk, "usage_metadata", None)
    if um is None:
        return None
    return Usage(getattr(um, "prompt_token_count", None), getattr(um, "candidates_token_count", None))


def _text(chunk) -> str:
    try:
        return chunk.text or ""
    except (ValueError, AttributeError):  # chunk without text parts
        return ""


def _blocked(chunk) -> bool:
    feedback = getattr(chunk, "prompt_feedback", None)
    return bool(feedback and getattr(feedback, "block_reason", None))


async def _close(client) -> None:
    try:
        await client.aio.aclose()
    except Exception:
        pass


class GeminiProvider:
    id = ID
    label = "Google Gemini"
    cloud = True

    def _config(self, system: str, json_mode: bool):
        from google.genai import types

        kwargs: dict = {"temperature": 0.2 if json_mode else 0.7}
        if system:
            kwargs["system_instruction"] = system
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**kwargs)

    async def stream(self, ctx: CallContext, spec: ModelSpec, messages: list[dict]) -> AsyncIterator[Chunk]:
        client = _make_client(ctx)
        usage: Usage | None = None
        try:
            system, contents = _convert(messages)
            stream = await client.aio.models.generate_content_stream(model=spec.model, contents=contents, config=self._config(system, False))
            async for chunk in stream:
                if _blocked(chunk):
                    raise ProviderError("bad_request", "Gemini blocked this prompt for safety reasons.", provider=ID)
                text = _text(chunk)
                if text:
                    yield Chunk(text=text)
                usage = _usage(chunk) or usage
            if usage:
                yield Chunk(usage=usage)
        except ProviderError:
            raise
        except Exception as exc:
            raise map_exception(exc) from exc
        finally:
            await _close(client)

    async def complete(self, ctx: CallContext, spec: ModelSpec, messages: list[dict], json_mode: bool) -> Completion:
        client = _make_client(ctx)
        try:
            system, contents = _convert(messages)
            res = await client.aio.models.generate_content(model=spec.model, contents=contents, config=self._config(system, json_mode))
            return Completion(_text(res), _usage(res), ID, spec.model)
        except ProviderError:
            raise
        except Exception as exc:
            raise map_exception(exc) from exc
        finally:
            await _close(client)

    async def list_remote_models(self, ctx: CallContext) -> set[str]:
        client = _make_client(ctx)
        names: set[str] = set()
        try:
            async for model in await client.aio.models.list():
                names.add(str(model.name).removeprefix("models/"))
                if len(names) >= 500:
                    break
            return names
        except Exception as exc:
            raise map_exception(exc) from exc
        finally:
            await _close(client)

    async def test(self, ctx: CallContext) -> tuple[bool, str]:
        try:
            names = await self.list_remote_models(ctx)
        except ProviderError as exc:
            return False, exc.message
        return True, f"Connected. {len(names)} model(s) available to this key."
