"""Conversation titles. Uses the same provider as the answer, so a local chat never sends its first message to the cloud."""
import asyncio

from app.config import Settings
from app.providers.base import ProviderError
from app.services import llm, routing

PROMPT = (
    "Write a short title (3 to 6 words) for a chat that begins with the message below. "
    "Reply with only the title, in the same language as the message: no quotes, no trailing punctuation.\n\nMessage:\n{text}"
)


async def generate(settings: Settings, keys: dict[str, str], first_message: str, provider: str, model: str) -> str | None:
    if provider == "ollama":
        spec = routing.ollama_spec(model)
    else:
        slot = "chat" if provider == "deepseek" else "flash"
        spec = routing.cloud_specs(settings).get(f"{provider}:{slot}")
        if spec is None or not keys.get(provider):
            return None
    plan = routing.RoutePlan([spec], auto=False, fallback=False)
    try:
        result = await asyncio.wait_for(
            routing.complete(plan, [{"role": "user", "content": PROMPT.format(text=first_message[:600])}], settings=settings, keys=keys),
            timeout=25.0,
        )
    except (ProviderError, asyncio.TimeoutError):
        return None
    return llm.clean_title(result.text)
