from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from environment variables or the repo-root .env file."""

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    llm_provider: Literal["ollama", "gemini"] = "ollama"
    llm_timeout_s: float = 8.0
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    gemini_api_key: str = ""
    gemini_model: str = ""
    extension_id: str = ""


settings = Settings()
