"""Shared types and helpers for signals.

Every signal is a pure function: it takes the listing plus its rule config and returns a
SignalResult, or None when the data it needs is not visible (the signal is then unavailable).
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

SignalKind = Literal["risk", "mitigator"]

ORDINAL_MARKS = frozenset("ªº")


@dataclass(frozen=True, slots=True)
class SignalResult:
    signal: str
    kind: SignalKind
    # risk: max points (0-100); mitigator: max fraction of the risk removed (0-1)
    weight: float
    intensity: float  # how strongly the signal is present, 0-1
    confidence: float  # how much we trust the measurement, 0-1
    message: str  # Spanish, shown to the user
    evidence: str  # the concrete data that justifies the message

    @property
    def points(self) -> float:
        return self.weight * self.intensity * self.confidence


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalize(text: str) -> str:
    """Lowercase and strip accents, keeping the same length so match spans map back.
    Ordinal marks become spaces: "AirPods Pro 2ª" must read as "airpods pro 2"."""
    chars = []
    for char in text:
        if char in ORDINAL_MARKS:
            chars.append(" ")
            continue
        decomposed = unicodedata.normalize("NFKD", char)
        stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
        chars.append(stripped if len(stripped) == 1 else char)
    return "".join(chars)


def contains_phrase(normalized_text: str, phrase: str) -> bool:
    """Whole-word match of `phrase` inside text already passed through normalize()."""
    return re.search(rf"\b{re.escape(normalize(phrase))}\b", normalized_text) is not None


def format_eur(amount: float) -> str:
    if amount == int(amount):
        return f"{int(amount)} €"
    return f"{amount:.2f} €".replace(".", ",")
