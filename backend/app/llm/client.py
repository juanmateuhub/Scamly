"""Minimal client for any OpenAI-compatible chat completions API (OpenRouter, Ollama, Groq...)."""

import logging
from collections.abc import Sequence
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)


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
        fallback_models: Sequence[str] = (),
        disable_reasoning: bool = False,
        reasoning_effort: str = "",
        http: httpx.Client | None = None,
    ) -> None:
        # Groq-style `reasoning_effort` ("none", "low"...); empty means not sent.
        self._reasoning_effort = reasoning_effort
        # OpenRouter: skip "thinking" tokens; a classification does not need them and they
        # multiply latency (measured ~12 s -> ~2 s median on Nemotron).
        self._disable_reasoning = disable_reasoning
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        # OpenRouter tries these in order when `model` is unavailable (e.g. rate-limited upstream).
        self._fallback_models = list(fallback_models)
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
        if self._fallback_models:
            payload["models"] = [self._model, *self._fallback_models]
        if self._disable_reasoning:
            payload["reasoning"] = {"enabled": False}
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        try:
            response = self._http.post(
                self._url, headers=self._headers, json=payload, timeout=self._timeout
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
            raise LLMError(f"{type(error).__name__}: {error}") from error
        if not isinstance(content, str):
            raise LLMError("response content is not text")
        logger.info("LLM answered with model %s", body.get("model", self._model))
        return content
