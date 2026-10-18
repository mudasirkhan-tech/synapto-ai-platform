"""Shared interface for model providers. Adapters normalise each vendor's request/stream format to this."""
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from app.config import Settings

ErrorKind = Literal["auth", "billing", "rate_limit", "timeout", "unavailable", "not_found", "bad_request", "unknown"]


class ProviderError(Exception):
    """A user-presentable provider failure. `message` never contains credentials."""

    def __init__(self, kind: ErrorKind, message: str, *, provider: str = "", status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.provider = provider
        self.status = status

    @property
    def retryable(self) -> bool:
        return self.kind in {"rate_limit", "timeout", "unavailable"}


@dataclass
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    def as_dict(self) -> dict:
        return {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens}


@dataclass
class Chunk:
    text: str = ""
    usage: Usage | None = None
    thinking: bool = False  # the model is reasoning; its chain of thought is deliberately never shown or stored


@dataclass
class Completion:
    text: str
    usage: Usage | None = None
    provider: str = ""
    model: str = ""


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str                      # provider-side model id
    slot: str                       # stable handle used in API/UI ("chat", "reasoner", "pro", "flash", or the Ollama name)
    label: str
    thinking: bool | None = None    # DeepSeek: explicit thinking toggle
    vision: bool | None = None      # None = unknown
    tags: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        return f"{self.provider}:{self.slot}"


@dataclass
class CallContext:
    api_key: str | None
    settings: Settings


class Provider(Protocol):
    id: str
    label: str
    cloud: bool

    def stream(self, ctx: CallContext, spec: ModelSpec, messages: list[dict]) -> AsyncIterator[Chunk]: ...

    async def complete(self, ctx: CallContext, spec: ModelSpec, messages: list[dict], json_mode: bool) -> Completion: ...

    async def list_remote_models(self, ctx: CallContext) -> set[str]: ...

    async def test(self, ctx: CallContext) -> tuple[bool, str]: ...
