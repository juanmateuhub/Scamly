"""Run every signal on a listing and score it."""

from datetime import datetime

from app import __version__
from app.models.listing import Analysis, Listing, PriceCheck
from app.rules.loader import PhraseRules, ReferencePrices, ScoringConfig
from app.scoring.engine import combine
from app.signals.base import SignalResult
from app.signals.consistency import model_mismatch_signal
from app.signals.description import short_description_signal
from app.signals.price import price_signal
from app.signals.seller import (
    account_age_signal,
    bad_ratings_signal,
    history_signal,
    seller_reputation_mitigator,
)
from app.signals.shipping import shipping_mitigator
from app.signals.text_llm import LlmFindings, combine_text_signals, generic_text_signal
from app.signals.text_rules import text_rule_signals


def analyze_listing(
    listing: Listing,
    config: ScoringConfig,
    phrases: PhraseRules,
    reference: ReferencePrices,
    llm_findings: LlmFindings | None,
    now: datetime,
) -> Analysis:
    """Score a listing. `llm_findings` is None when the LLM is disabled or failed (plan B)."""
    signals, mitigators = config.signals, config.mitigators
    short_description = short_description_signal(listing, signals.descripcion_pobre)
    optional: dict[str, SignalResult | None] = {
        "precio_anomalo": price_signal(listing, reference, signals.precio_anomalo),
        "modelo_distinto": model_mismatch_signal(listing, reference, signals.modelo_distinto),
        "cuenta_nueva": account_age_signal(listing, signals.cuenta_nueva),
        "sin_historial": history_signal(listing, signals.sin_historial),
        "malas_valoraciones": bad_ratings_signal(listing, signals.malas_valoraciones),
        "vendedor_con_historial": seller_reputation_mitigator(
            listing, mitigators.vendedor_con_historial
        ),
        "texto_generico": generic_text_signal(
            llm_findings, signals.texto_generico, short_description.intensity
        ),
    }
    rule_results = text_rule_signals(
        listing, phrases, signals.text_weights(), config.text_confidence.regex
    )
    results = [r for r in optional.values() if r is not None]
    results += combine_text_signals(rule_results, llm_findings, config.text_confidence)
    results.append(short_description)
    results.append(shipping_mitigator(listing, mitigators.envio_protegido))
    unavailable = [name for name, result in optional.items() if result is None]

    score = combine(results, unavailable, config)
    price = optional["precio_anomalo"]
    return Analysis(
        risk_score=score.risk_score,
        level=score.level,
        confidence=score.confidence,
        reasons=score.reasons,
        price_check=PriceCheck(message=price.message, evidence=price.evidence) if price else None,
        unavailable_signals=score.unavailable_signals,
        text_analysis="basico" if llm_findings is None else "llm",
        analyzed_at=now,
        version=__version__,
    )
