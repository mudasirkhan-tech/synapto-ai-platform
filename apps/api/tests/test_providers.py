"""Adapter tests. DeepSeek runs against httpx.MockTransport (real code path, no network). Gemini uses an injected fake client."""
import asyncio
import json
import types

import httpx
import pytest

from app.config import Settings
from app.providers import deepseek, gemini
from app.providers.base import CallContext, ModelSpec, ProviderError
from app.services import routing
from app.services.credentials import redact

KEY = "sk-test-0123456789abcdef"
SETTINGS = Settings(deepseek_api_key=None, gemini_api_key=None)
CHAT = routing.cloud_specs(SETTINGS)["deepseek:chat"]
REASONER = routing.cloud_specs(SETTINGS)["deepseek:reasoner"]
CTX = CallContext(KEY, SETTINGS)


def sse(*events: dict | str) -> bytes:
    lines = [f"data: {e if isinstance(e, str) else json.dumps(e)}\n\n" for e in events]
    return ("".join(lines)).encode()


def use_transport(monkeypatch, handler):
    monkeypatch.setattr(deepseek, "TRANSPORT", httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


async def collect(agen):
    return [c async for c in agen]


def test_deepseek_streaming_request_and_parsing(monkeypatch):
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        body = sse(
            {"choices": [{"delta": {"reasoning_content": "private thoughts"}}]},
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
            "[DONE]",
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    use_transport(monkeypatch, handler)
    chunks = run(collect(deepseek.DeepSeekProvider().stream(CTX, CHAT, [{"role": "user", "content": "hi"}])))

    assert "".join(c.text for c in chunks) == "Hello"
    assert any(c.thinking for c in chunks) and all("private thoughts" not in c.text for c in chunks)  # reasoning never exposed
    assert [c.usage.completion_tokens for c in chunks if c.usage] == [2]
    assert seen["url"].endswith("/chat/completions") and seen["auth"] == f"Bearer {KEY}"
    assert seen["body"]["stream"] is True and seen["body"]["thinking"] == {"type": "disabled"}
    assert seen["body"]["model"] == SETTINGS.deepseek_chat_model and seen["body"]["stream_options"] == {"include_usage": True}


def test_deepseek_reasoner_enables_thinking_and_json_mode(monkeypatch):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}', "reasoning_content": "x"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    use_transport(monkeypatch, handler)
    done = run(deepseek.DeepSeekProvider().complete(CTX, REASONER, [{"role": "user", "content": "json please"}], True))
    assert done.text == '{"ok": true}'
    assert seen["body"]["thinking"] == {"type": "enabled"} and seen["body"]["reasoning_effort"] == SETTINGS.deepseek_reasoning_effort
    assert seen["body"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status,kind,retryable", [(401, "auth", False), (402, "billing", False), (404, "not_found", False),
                                                   (429, "rate_limit", True), (503, "unavailable", True), (400, "bad_request", False)])
def test_deepseek_error_mapping_never_leaks_the_key(monkeypatch, status, kind, retryable):
    use_transport(monkeypatch, lambda r: httpx.Response(status, json={"error": {"message": f"bad token {KEY}"}}))
    with pytest.raises(ProviderError) as info:
        run(collect(deepseek.DeepSeekProvider().stream(CTX, CHAT, [{"role": "user", "content": "hi"}])))
    assert info.value.kind == kind and info.value.retryable is retryable
    assert KEY not in info.value.message


def test_deepseek_timeout_and_connection_errors(monkeypatch):
    def boom(request):
        raise httpx.ReadTimeout("slow", request=request)

    use_transport(monkeypatch, boom)
    with pytest.raises(ProviderError) as info:
        run(collect(deepseek.DeepSeekProvider().stream(CTX, CHAT, [{"role": "user", "content": "hi"}])))
    assert info.value.kind == "timeout"

    def refuse(request):
        raise httpx.ConnectError("no route", request=request)

    use_transport(monkeypatch, refuse)
    with pytest.raises(ProviderError) as info:
        run(deepseek.DeepSeekProvider().complete(CTX, CHAT, [{"role": "user", "content": "hi"}], False))
    assert info.value.kind == "unavailable"


def test_deepseek_models_and_connection_test(monkeypatch):
    use_transport(monkeypatch, lambda r: httpx.Response(200, json={"data": [{"id": "deepseek-flash"}, {"id": "deepseek-v4-pro"}]}))
    ok, message = run(deepseek.DeepSeekProvider().test(CTX))
    assert ok and "2 model" in message
    use_transport(monkeypatch, lambda r: httpx.Response(401, json={}))
    ok, message = run(deepseek.DeepSeekProvider().test(CTX))
    assert not ok and "rejected" in message


def test_deepseek_images_use_openai_content_blocks():
    msg = deepseek._to_openai({"role": "user", "content": "what is this?", "images": [{"mime": "image/png", "data": "QUJD"}]})
    assert msg["content"][1]["image_url"]["url"] == "data:image/png;base64,QUJD"


# ---------------- Gemini (fake SDK client) ----------------
class FakeChunk:
    def __init__(self, text, usage=None):
        self.text, self.usage_metadata, self.prompt_feedback = text, usage, None


class FakeApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


class FakeModels:
    def __init__(self, chunks=(), error=None, names=()):
        self.chunks, self.error, self.names, self.kwargs = chunks, error, names, None

    async def generate_content_stream(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error

        async def gen():
            for c in self.chunks:
                yield c
        return gen()

    async def generate_content(self, **kwargs):
        if self.error:
            raise self.error
        return FakeChunk("".join(c.text for c in self.chunks))

    async def list(self):
        async def gen():
            for n in self.names:
                yield types.SimpleNamespace(name=f"models/{n}")
        return gen()


class FakeClient:
    def __init__(self, models):
        self.aio = types.SimpleNamespace(models=models, aclose=self._aclose)
        self.closed = False

    async def _aclose(self):
        self.closed = True


def gem_ctx():
    return CallContext("AIzaFakeKeyFakeKeyFakeKey123456", SETTINGS)


def test_gemini_streaming_usage_and_cleanup(monkeypatch):
    usage = types.SimpleNamespace(prompt_token_count=7, candidates_token_count=3)
    models = FakeModels([FakeChunk("Hi "), FakeChunk("there", usage)])
    client = FakeClient(models)
    monkeypatch.setattr(gemini, "_make_client", lambda ctx: client)
    spec = routing.cloud_specs(SETTINGS)["gemini:pro"]
    chunks = run(collect(gemini.GeminiProvider().stream(gem_ctx(), spec, [
        {"role": "system", "content": "be brief"}, {"role": "user", "content": "hello"}, {"role": "assistant", "content": "yo"}, {"role": "user", "content": "again"}])))
    assert "".join(c.text for c in chunks) == "Hi there" and chunks[-1].usage.prompt_tokens == 7
    assert models.kwargs["model"] == SETTINGS.gemini_pro_model and client.closed
    assert [c.role for c in models.kwargs["contents"]] == ["user", "model", "user"]  # system prompt moved to system_instruction


@pytest.mark.parametrize("code,message,kind", [(401, "x", "auth"), (400, "API key not valid", "auth"), (404, "x", "not_found"),
                                                (429, "quota", "rate_limit"), (503, "x", "unavailable"), (400, "bad", "bad_request")])
def test_gemini_error_mapping(monkeypatch, code, message, kind):
    monkeypatch.setattr(gemini, "_make_client", lambda ctx: FakeClient(FakeModels(error=FakeApiError(code, message))))
    spec = routing.cloud_specs(SETTINGS)["gemini:flash"]
    with pytest.raises(ProviderError) as info:
        run(collect(gemini.GeminiProvider().stream(gem_ctx(), spec, [{"role": "user", "content": "hi"}])))
    assert info.value.kind == kind


def test_gemini_model_listing_and_connection_test(monkeypatch):
    monkeypatch.setattr(gemini, "_make_client", lambda ctx: FakeClient(FakeModels(names=["gemini-3.5-flash", "gemini-3.1-pro-preview"])))
    assert run(gemini.GeminiProvider().list_remote_models(gem_ctx())) == {"gemini-3.5-flash", "gemini-3.1-pro-preview"}
    ok, message = run(gemini.GeminiProvider().test(gem_ctx()))
    assert ok and "2 model" in message


def test_redaction_scrubs_key_shaped_strings():
    text = f"Authorization: Bearer abcdefghijklmnop1234 key={KEY} g=AIza{'x' * 30}"
    cleaned = redact(text)
    assert KEY not in cleaned and "AIza" not in cleaned and "abcdefghijklmnop1234" not in cleaned
