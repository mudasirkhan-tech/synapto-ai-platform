from app.providers.base import Provider
from app.providers.deepseek import DeepSeekProvider
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider

PROVIDERS: dict[str, Provider] = {p.id: p for p in (DeepSeekProvider(), GeminiProvider(), OllamaProvider())}  # type: ignore[misc]
CLOUD_IDS = [p.id for p in PROVIDERS.values() if p.cloud]


def get_provider(provider_id: str) -> Provider:
    return PROVIDERS[provider_id]
