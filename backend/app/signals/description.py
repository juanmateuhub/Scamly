import re

from app.models.listing import Listing
from app.rules.loader import ShortDescriptionConfig
from app.signals.base import SignalResult, clamp

_WORD = re.compile(r"\w+")


def short_description_signal(listing: Listing, config: ShortDescriptionConfig) -> SignalResult:
    """Very short descriptions give the buyer nothing to check (works without the LLM)."""
    words = len(_WORD.findall(listing.description))
    span = config.no_risk_words - config.full_risk_words
    return SignalResult(
        signal="descripcion_pobre",
        kind="risk",
        weight=config.weight,
        intensity=clamp((config.no_risk_words - words) / span),
        confidence=1.0,
        message="La descripción es muy corta",
        evidence=f"{words} palabra" if words == 1 else f"{words} palabras",
    )
