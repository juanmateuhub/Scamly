"""Minimal client for any OpenAI-compatible chat completions API (OpenRouter, Ollama, Groq...)."""

from typing import Any, Protocol

import httpx


class LLMError(Exception):
    """The LLM could not give a usable answer (network, timeout, HTTP error, bad payload)."""


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> str:
        """Return the raw JSON text answered by the model, or raise LLMError."""
        ...


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        timeout_s: float,
        http: httpx.Client | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}", "X-Title": "Scamly"}
        self._timeout = timeout_s
        self._http = http or httpx.Client()

    def complete_json(self, system: str, user: str) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._http.post(
                self._url, headers=self._headers, json=payload, timeout=self._timeout
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
            raise LLMError(f"{type(error).__name__}: {error}") from error
        if not isinstance(content, str):
            raise LLMError("response content is not text")
        return content
