from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings, read from environment variables or the repo-root .env file."""

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Any OpenAI-compatible chat completions API (OpenRouter, Ollama /v1, Groq, Mistral...).
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "google/gemma-4-31b-it:free"
    llm_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("LLM_API_KEY", "OPENROUTER_API_KEY")
    )
    llm_timeout_s: float = 8.0
    # Comma-separated OpenRouter fallbacks, tried in order if the primary model is unavailable.
    llm_fallback_models: str = "nvidia/nemotron-3.5-super-vl:free,google/gemma-4-26b-a4b-it:free"
    # OpenRouter only: ask models not to spend tokens "thinking" (much lower latency).
    llm_disable_reasoning: bool = True

    # LLM findings cache (hash of the listing text -> verified quotes), never full texts.
    cache_path: Path = REPO_ROOT / "backend" / ".cache" / "scamly.db"
    cache_ttl_hours: float = 24.0

    extension_id: str = ""

    @property
    def llm_fallback_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.get_secret_value())


settings = Settings()
