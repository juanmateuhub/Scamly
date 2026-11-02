"""Combine signal results into the final score (see "Agregación" in CLAUDE.md).

risk_raw = 100 * (1 - prod(1 - p_i / 100))   over risk signals
risk     = risk_raw * prod(1 - m_j)          over mitigators
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.listing import Reason, RiskLevel
from app.rules.loader import LevelsConfig, ScoringConfig
from app.signals.base import SignalResult, clamp


@dataclass(frozen=True, slots=True)
class Score:
    risk_score: int
    level: RiskLevel
    confidence: float
    reasons: list[Reason]
    unavailable_signals: list[str]


def level_for(score: int, levels: LevelsConfig) -> RiskLevel:
    if score >= levels.rojo:
        return "rojo"
    if score >= levels.amarillo:
        return "amarillo"
    return "verde"


def _reason(result: SignalResult, points: float) -> Reason:
    return Reason(
        signal=result.signal,
        points=round(points, 1),
        intensity=round(result.intensity, 2),
        confidence=round(result.confidence, 2),
        message=result.message,
        evidence=result.evidence,
    )


def combine(
    results: Sequence[SignalResult], unavailable: Sequence[str], config: ScoringConfig
) -> Score:
    risks = [r for r in results if r.kind == "risk"]
    mitigators = [r for r in results if r.kind == "mitigator"]

    risk_raw = 100 * (1 - math.prod(1 - clamp(r.points / 100) for r in risks))
    risk = risk_raw * math.prod(1 - clamp(m.points) for m in mitigators)
    risk_score = round(clamp(risk, 0, 100))

    risk_reasons = sorted(
        (_reason(r, r.points) for r in risks if r.points >= config.min_reason_points),
        key=lambda reason: reason.points,
        reverse=True,
    )
    # Each mitigator is shown with the points it would remove from the raw risk on its own.
    mitigator_reasons = sorted(
        (
            _reason(m, -risk_raw * m.points)
            for m in mitigators
            if m.points >= config.min_mitigator_reduction
        ),
        key=lambda reason: reason.points,
    )

    trusted_weight = sum(r.weight * r.confidence for r in risks)
    confidence = clamp(trusted_weight / config.total_risk_weight())

    return Score(
        risk_score=risk_score,
        level=level_for(risk_score, config.levels),
        confidence=round(confidence, 2),
        reasons=risk_reasons + mitigator_reasons,
        unavailable_signals=list(unavailable),
    )
