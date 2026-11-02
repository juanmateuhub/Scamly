import json
from typing import Any

from app.llm.client import LLMError


class FakeLLM:
    """LLM test double: returns a canned reply (or raises) and records the prompts."""

    def __init__(self, reply: dict[str, Any] | str | None = None, *, fail: bool = False) -> None:
        self.reply = reply if reply is not None else {}
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.fail:
            raise LLMError("simulated failure")
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


def detected(quote: str) -> dict[str, Any]:
    return {"detectado": True, "cita": quote}


NOT_DETECTED: dict[str, Any] = {"detectado": False, "cita": None}
