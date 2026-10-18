from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-insecure-secret-change-me-before-deploying"
OLD_DEV_SECRETS = {"dev-insecure-change-me"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SYNAPTO_", env_file=".env", extra="ignore", populate_by_name=True)

    env: str = "development"
    version: str = "0.6.0"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "sqlite:///./synapto.db"

    # auth
    jwt_secret: str = DEV_SECRET
    jwt_expire_minutes: int = 60 * 24 * 7

    # cloud providers (credentials come from the environment or encrypted per-user storage; never from the browser)
    deepseek_api_key: str | None = Field(default=None, validation_alias=AliasChoices("DEEPSEEK_API_KEY", "SYNAPTO_DEEPSEEK_API_KEY"))
    gemini_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "SYNAPTO_GEMINI_API_KEY"))
    encryption_key: str | None = None     # Fernet key for stored user API keys; auto-created in data_dir if unset
    deepseek_base_url: str = "https://api.deepseek.com"
    # Model IDs change often. These defaults were checked against the providers' docs on 2026-10-13;
    # `deepseek-chat`/`deepseek-reasoner` and `gemini-1.5-pro`/`gemini-2.0-flash` have been retired.
    deepseek_chat_model: str = "deepseek-flash"       # used with thinking disabled (fast)
    deepseek_reasoner_model: str = "deepseek-flash"   # used with thinking enabled; "deepseek-v4-pro" is the stronger option
    deepseek_reasoning_effort: str = "high"           # low | high | max
    gemini_pro_model: str = "gemini-3.1-pro-preview"
    gemini_flash_model: str = "gemini-3.5-flash"

    # routing
    auto_order: list[str] = ["deepseek:chat", "gemini:pro", "gemini:flash"]  # Ollama is always last
    route_reasoning: bool = True          # Auto may choose the reasoner for clearly hard maths/logic prompts
    fallback_default: bool = True         # per-request override from the Settings toggle
    local_fallback: bool = True           # allow falling back to a (slow) local Ollama model
    provider_max_retries: int = 1         # retries per provider for rate limits, timeouts and outages (no infinite retries)
    provider_retry_backoff_s: float = 0.5
    provider_connect_timeout_s: float = 10.0
    provider_first_token_timeout_s: float = 45.0
    provider_stall_timeout_s: float = 30.0
    provider_total_timeout_s: float = 120.0

    # local inference
    ollama_url: str = "http://127.0.0.1:11434"
    runtime_timeout_s: float = 2.0
    chat_model: str = "llama3.2"
    num_ctx: int = 8192

    # storage + uploads
    data_dir: str = "./data"
    max_doc_bytes: int = 25 * 1024 * 1024
    max_image_bytes: int = 10 * 1024 * 1024
    max_audio_bytes: int = 25 * 1024 * 1024

    # prompt / retrieval (RAG)
    history_limit: int = 20
    embed_model: str = "bge-m3"          # multilingual; "nomic-embed-text" is a lighter English-centric option
    chunk_size: int = 1000                # characters
    chunk_overlap: int = 150
    retrieval_top_k: int = 6
    retrieval_char_budget: int = 7000     # max characters of sources placed in the prompt

    # agent guardrails
    agent_max_turns: int = 8              # model decisions per task (tool calls + final + format retries)
    agent_max_tool_calls: int = 6
    agent_tool_timeout_s: float = 20.0
    agent_llm_timeout_s: float = 90.0

    # optional integrations (all disabled until configured)
    searxng_url: str | None = None        # e.g. http://127.0.0.1:8080 (self-hosted SearXNG, JSON format enabled)
    imagegen_url: str | None = None       # e.g. http://127.0.0.1:7860 (Stable Diffusion WebUI started with --api)
    whisper_model: str = "small"          # faster-whisper model size

    @model_validator(mode="after")
    def _require_real_secret(self) -> "Settings":
        if self.env != "development" and self.jwt_secret in ({DEV_SECRET} | OLD_DEV_SECRETS):
            raise ValueError("SYNAPTO_JWT_SECRET must be set when SYNAPTO_ENV is not 'development'")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
