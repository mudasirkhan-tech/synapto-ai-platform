"""DeepSeek via its OpenAI-compatible HTTP API (plain httpx: no extra SDK needed)."""
import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import CallContext, Chunk, Completion, ModelSpec, ProviderError, Usage
from app.services.credentials import redact

ID = "deepseek"
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests inject httpx.MockTransport here


def _client(ctx: CallContext, timeout: httpx.Timeout) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=ctx.settings.deepseek_base_url, timeout=timeout, transport=TRANSPORT)


def map_error(status: int, body: bytes | str = b"") -> ProviderError:
    detail = ""
    try:
        data = json.loads(body)
        detail = str(data.get("error", {}).get("message", ""))[:200]
    except (ValueError, AttributeError, TypeError):
        pass
    detail = redact(detail)
    if status in (401, 403):
        return ProviderError("auth", "DeepSeek rejected the API key. Check it in Settings → API keys.", provider=ID, status=status)
    if status == 402:
        return ProviderError("billing", "DeepSeek reports insufficient balance. Top up your DeepSeek account.", provider=ID, status=status)
    if status == 404:
        return ProviderError("not_found", "DeepSeek doesn't offer this model ID (it may have been retired). Change it in the server configuration.", provider=ID, status=status)
    if status == 429:
        return ProviderError("rate_limit", "DeepSeek rate limit reached.", provider=ID, status=status)
    if status >= 500:
        return ProviderError("unavailable", "DeepSeek is temporarily unavailable.", provider=ID, status=status)
    return ProviderError("bad_request", f"DeepSeek rejected the request ({status}). {detail}".strip(), provider=ID, status=status)


def _to_openai(m: dict) -> dict:
    images = m.get("images") or []
    if m["role"] == "user" and images:
        blocks: list[dict] = [{"type": "text", "text": m["content"]}]
        blocks += [{"type": "image_url", "image_url": {"url": f"data:{i['mime']};base64,{i['data']}"}} for i in images]
        return {"role": "user", "content": blocks}
    return {"role": m["role"], "content": m["content"]}


def _usage(obj: dict | None) -> Usage | None:
    if not obj:
        return None
    return Usage(obj.get("prompt_tokens"), obj.get("completion_tokens"))


def _wrap(exc: Exception) -> ProviderError:
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError("timeout", "DeepSeek did not respond in time.", provider=ID)
    return ProviderError("unavailable", "Could not reach DeepSeek.", provider=ID)


class DeepSeekProvider:
    id = ID
    label = "DeepSeek"
    cloud = True

    @staticmethod
    def _headers(ctx: CallContext) -> dict:
        return {"Authorization": f"Bearer {ctx.api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _timeout(ctx: CallContext) -> httpx.Timeout:
        s = ctx.settings
        return httpx.Timeout(s.provider_connect_timeout_s, read=s.provider_first_token_timeout_s, write=15.0, pool=10.0)

    def _payload(self, ctx: CallContext, spec: ModelSpec, messages: list[dict], *, stream: bool, json_mode: bool) -> dict:
        payload: dict = {"model": spec.model, "messages": [_to_openai(m) for m in messages], "stream": stream}
        if spec.thinking is True:
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = ctx.settings.deepseek_reasoning_effort
        elif spec.thinking is False:
            payload["thinking"] = {"type": "disabled"}
            payload["temperature"] = 0.2 if json_mode else 0.7
        if stream:
            payload["stream_options"] = {"include_usage": True}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def stream(self, ctx: CallContext, spec: ModelSpec, messages: list[dict]) -> AsyncIterator[Chunk]:
        payload = self._payload(ctx, spec, messages, stream=True, json_mode=False)
        try:
            async with _client(ctx, self._timeout(ctx)) as client:
                async with client.stream("POST", "/chat/completions", json=payload, headers=self._headers(ctx)) as res:
                    if res.status_code >= 400:
                        raise map_error(res.status_code, await res.aread())
                    async for line in res.aiter_lines():
                        if not line.startswith("data:"):
                            continue  # blank lines and ": keep-alive" comments
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError as exc:
                            raise ProviderError("unavailable", "DeepSeek sent an unreadable stream.", provider=ID) from exc
                        if obj.get("usage"):
                            yield Chunk(usage=_usage(obj["usage"]))
                        for choice in obj.get("choices") or []:
                            delta = choice.get("delta") or {}
                            if delta.get("reasoning_content"):
                                yield Chunk(thinking=True)  # signal only; the reasoning text is dropped on purpose
                            if delta.get("content"):
                                yield Chunk(text=delta["content"])
        except ProviderError:
            raise
        except httpx.HTTPError as exc:
            raise _wrap(exc) from exc

    async def complete(self, ctx: CallContext, spec: ModelSpec, messages: list[dict], json_mode: bool) -> Completion:
        payload = self._payload(ctx, spec, messages, stream=False, json_mode=json_mode)
        try:
            async with _client(ctx, httpx.Timeout(ctx.settings.provider_total_timeout_s, connect=ctx.settings.provider_connect_timeout_s)) as client:
                res = await client.post("/chat/completions", json=payload, headers=self._headers(ctx))
            if res.status_code >= 400:
                raise map_error(res.status_code, res.content)
            data = res.json()
            return Completion(str(data["choices"][0]["message"].get("content") or ""), _usage(data.get("usage")), ID, spec.model)
        except ProviderError:
            raise
        except httpx.HTTPError as exc:
            raise _wrap(exc) from exc
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError("unavailable", "DeepSeek returned an unusable response.", provider=ID) from exc

    async def list_remote_models(self, ctx: CallContext) -> set[str]:
        try:
            async with _client(ctx, httpx.Timeout(10.0)) as client:
                res = await client.get("/models", headers=self._headers(ctx))
            if res.status_code >= 400:
                raise map_error(res.status_code, res.content)
            return {str(m["id"]) for m in res.json().get("data", [])}
        except ProviderError:
            raise
        except httpx.HTTPError as exc:
            raise _wrap(exc) from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError("unavailable", "DeepSeek returned an unusable model list.", provider=ID) from exc

    async def test(self, ctx: CallContext) -> tuple[bool, str]:
        try:
            models = await self.list_remote_models(ctx)
        except ProviderError as exc:
            return False, exc.message
        return True, f"Connected. {len(models)} model(s) available to this key."
