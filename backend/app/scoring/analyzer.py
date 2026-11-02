"""Run every signal on a listing and score it."""

from datetime import datetime

from app import __version__
from app.models.listing import Analysis, Listing
from app.rules.loader import PhraseRules, ReferencePrices, ScoringConfig
from app.scoring.engine import combine
from app.signals.base import SignalResult
from app.signals.price import price_signal
from app.signals.seller import account_age_signal, history_signal, seller_reputation_mitigator
from app.signals.shipping import shipping_mitigator
from app.signals.text_rules import text_rule_signals


def analyze_listing(
    listing: Listing,
    config: ScoringConfig,
    phrases: PhraseRules,
    reference: ReferencePrices,
    now: datetime,
) -> Analysis:
    signals, mitigators = config.signals, config.mitigators
    optional: dict[str, SignalResult | None] = {
        "precio_anomalo": price_signal(listing, reference, signals.precio_anomalo),
        "cuenta_nueva": account_age_signal(listing, signals.cuenta_nueva),
        "sin_historial": history_signal(listing, signals.sin_historial),
        "vendedor_con_historial": seller_reputation_mitigator(
            listing, mitigators.vendedor_con_historial
        ),
        # LLM-only signal, wired in phase 5.
        "texto_generico": None,
    }
    results = [r for r in optional.values() if r is not None]
    results += text_rule_signals(
        listing, phrases, signals.text_weights(), config.text_confidence.regex
    )
    results.append(shipping_mitigator(listing, mitigators.envio_protegido))
    unavailable = [name for name, result in optional.items() if result is None]

    score = combine(results, unavailable, config)
    return Analysis(
        risk_score=score.risk_score,
        level=score.level,
        confidence=score.confidence,
        reasons=score.reasons,
        unavailable_signals=score.unavailable_signals,
        text_analysis="basico",
        analyzed_at=now,
        version=__version__,
    )
