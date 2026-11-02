"""Text signals from Spanish phrase rules (works without the LLM; plan B in phase 5)."""

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache

from app.models.listing import Listing
from app.rules.loader import Phrase, PhraseRules, TextSignalConfig, TextSignalName
from app.signals.base import SignalResult, normalize

__all__ = ["combine_strengths", "find_phrases", "normalize", "text_rule_signals"]

MESSAGES: dict[TextSignalName, str] = {
    "pago_fuera_app": "Pide pagar fuera de la plataforma, sin protección",
    "contacto_externo": "Intenta llevar la conversación fuera de la app",
    "urgencia": "Mete prisa, táctica típica de estafa",
}

_CLAUSE_BREAK = re.compile(r"[.,;:!?¡¿\n]")
_WORD = re.compile(r"\w+")
_NEGATION_WINDOW = 3  # words before a match that can negate it


@dataclass(frozen=True, slots=True)
class PhraseMatch:
    start: int
    end: int
    strength: float
    excerpt: str  # original text, with its case and accents


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def _is_negated(normalized: str, start: int, negations: frozenset[str]) -> bool:
    clause = _CLAUSE_BREAK.split(normalized[:start])[-1]
    preceding = _WORD.findall(clause)[-_NEGATION_WINDOW:]
    return any(word in negations for word in preceding)


def find_phrases(
    text: str, phrases: Iterable[Phrase], negations: frozenset[str]
) -> list[PhraseMatch]:
    """Non-overlapping, non-negated matches, strongest first."""
    normalized = normalize(text)
    candidates = [
        PhraseMatch(m.start(), m.end(), phrase.strength, text[m.start() : m.end()])
        for phrase in phrases
        for m in _compile(phrase.pattern).finditer(normalized)
        if not _is_negated(normalized, m.start(), negations)
    ]
    candidates.sort(key=lambda m: (-m.strength, m.start))

    kept: list[PhraseMatch] = []
    for match in candidates:
        if all(match.end <= k.start or match.start >= k.end for k in kept):
            kept.append(match)
    return kept


def combine_strengths(strengths: Iterable[float]) -> float:
    """Noisy-OR: independent pieces of evidence reinforce each other with diminishing returns."""
    return 1 - math.prod(1 - s for s in strengths)


def text_rule_signals(
    listing: Listing,
    rules: PhraseRules,
    weights: Mapping[TextSignalName, TextSignalConfig],
    confidence: float,
) -> list[SignalResult]:
    text = f"{listing.title}\n{listing.description}"
    results = []
    for name, config in weights.items():
        matches = find_phrases(text, rules.signals.get(name, []), rules.negations)
        excerpts = list(dict.fromkeys(m.excerpt for m in matches))
        results.append(
            SignalResult(
                signal=name,
                kind="risk",
                weight=config.weight,
                intensity=combine_strengths(m.strength for m in matches),
                confidence=confidence,
                message=MESSAGES[name],
                evidence=" · ".join(excerpts),
            )
        )
    return results
