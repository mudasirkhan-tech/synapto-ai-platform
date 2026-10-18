"""Scriptable fake providers so routing and chat tests never touch the network."""
from app.providers.base import Chunk, Completion, ProviderError, Usage


class FakeProvider:
    def __init__(self, pid: str, cloud: bool, script=None):
        self.id, self.label, self.cloud = pid, {"deepseek": "DeepSeek", "gemini": "Google Gemini", "ollama": "Local · Ollama"}[pid], cloud
        self.script = list(script or [])  # one entry per call: a list of str | Chunk | ProviderError
        self.calls = 0
        self.seen_messages: list[list[dict]] = []

    async def stream(self, ctx, spec, messages):
        self.calls += 1
        self.seen_messages.append(messages)
        step = self.script.pop(0) if self.script else ["ok"]
        for item in step:
            if isinstance(item, ProviderError):
                raise item
            yield Chunk(text=item) if isinstance(item, str) else item
        yield Chunk(usage=Usage(3, 4))

    async def complete(self, ctx, spec, messages, json_mode):
        self.calls += 1
        step = self.script.pop(0) if self.script else ["ok"]
        if isinstance(step[0], ProviderError):
            raise step[0]
        return Completion("".join(s for s in step if isinstance(s, str)), None, self.id, spec.model)

    async def list_remote_models(self, ctx):
        return set()

    async def test(self, ctx):
        return True, "ok"


def err(kind, message="boom", pid="deepseek"):
    return ProviderError(kind, message, provider=pid)


def install(monkeypatch, **providers):
    """Replace the provider lookup used by the router with fakes (pid -> FakeProvider)."""
    from app.services import routing

    monkeypatch.setattr(routing, "get_provider", lambda pid: providers[pid])
