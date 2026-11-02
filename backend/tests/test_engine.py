import math
import random

import pytest

from app.rules.loader import ScoringConfig, load_scoring_config
from app.scoring.engine import combine, level_for
from app.signals.base import SignalKind, SignalResult

CONFIG: ScoringConfig = load_scoring_config()
TOTAL_RISK_WEIGHT = 150  # sum of signal weights in scoring.yaml


def risk(name: str, points: float, weight: float = 100, confidence: float = 1.0) -> SignalResult:
    return _signal(name, "risk", weight, points / (weight * confidence), confidence)


def mitigator(name: str, reduction: float) -> SignalResult:
    return _signal(name, "mitigator", 1.0, reduction, 1.0)


def _signal(
    name: str, kind: SignalKind, weight: float, intensity: float, confidence: float
) -> SignalResult:
    return SignalResult(name, kind, weight, intensity, confidence, f"msg {name}", f"ev {name}")


# --- aggregation ----------------------------------------------------------------


def test_no_signals_is_zero_and_green() -> None:
    score = combine([], [], CONFIG)

    assert score.risk_score == 0
    assert score.level == "verde"
    assert score.reasons == []


@pytest.mark.parametrize(
    ("points", "expected"),
    [([40], 40), ([50, 50], 75), ([100, 30], 100), ([30, 30, 30], 66), ([0, 0], 0)],
)
def test_risk_signals_combine_with_noisy_or(points: list[float], expected: int) -> None:
    signals = [risk(f"s{i}", p) for i, p in enumerate(points)]

    assert combine(signals, [], CONFIG).risk_score == expected


def test_mitigators_reduce_multiplicatively() -> None:
    signals = [risk("a", 80), mitigator("m1", 0.25), mitigator("m2", 0.5)]

    assert combine(signals, [], CONFIG).risk_score == 30  # 80 * 0.75 * 0.5


def test_score_is_always_between_0_and_100() -> None:
    rng = random.Random(42)
    for _ in range(500):
        signals = [risk(f"r{i}", rng.uniform(0, 100)) for i in range(rng.randint(0, 8))]
        signals += [mitigator(f"m{i}", rng.uniform(0, 1)) for i in range(rng.randint(0, 3))]

        score = combine(signals, [], CONFIG)

        assert 0 <= score.risk_score <= 100
        assert 0 <= score.confidence <= 1


def test_adding_a_risk_signal_never_lowers_the_score() -> None:
    rng = random.Random(7)
    for _ in range(200):
        base = [risk(f"r{i}", rng.uniform(0, 60)) for i in range(rng.randint(0, 5))]
        extra = risk("extra", rng.uniform(0, 60))

        assert (
            combine([*base, extra], [], CONFIG).risk_score >= combine(base, [], CONFIG).risk_score
        )


def test_adding_a_mitigator_never_raises_the_score() -> None:
    rng = random.Random(9)
    for _ in range(200):
        base = [risk(f"r{i}", rng.uniform(0, 60)) for i in range(rng.randint(1, 5))]
        extra = mitigator("m", rng.uniform(0, 1))

        assert (
            combine([*base, extra], [], CONFIG).risk_score <= combine(base, [], CONFIG).risk_score
        )


# --- traffic light ----------------------------------------------------------------


AMARILLO, ROJO = CONFIG.levels.amarillo, CONFIG.levels.rojo


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (0, "verde"),
        (AMARILLO - 1, "verde"),
        (AMARILLO, "amarillo"),
        (ROJO - 1, "amarillo"),
        (ROJO, "rojo"),
        (100, "rojo"),
    ],
)
def test_level_thresholds(score: int, level: str) -> None:
    assert level_for(score, CONFIG.levels) == level


# --- reasons ------------------------------------------------------------------------


def test_reasons_are_sorted_by_points_and_small_ones_hidden() -> None:
    signals = [risk("low", 10), risk("high", 40), risk("tiny", 2.9), risk("mid", 20)]

    reasons = combine(signals, [], CONFIG).reasons

    assert [r.signal for r in reasons] == ["high", "mid", "low"]


def test_mitigator_reasons_show_negative_points_after_risks() -> None:
    signals = [risk("a", 50), mitigator("buen_vendedor", 0.2), mitigator("nada", 0.0)]

    reasons = combine(signals, [], CONFIG).reasons

    assert [r.signal for r in reasons] == ["a", "buen_vendedor"]
    assert math.isclose(reasons[1].points, -10.0)  # removes 20 % of 50 points


def test_reason_values_are_rounded() -> None:
    reason = combine([risk("a", 13.5726, weight=15)], [], CONFIG).reasons[0]

    assert reason.points == 13.6
    assert reason.intensity == 0.9


# --- confidence -----------------------------------------------------------------------


def test_confidence_is_share_of_trusted_signal_weight() -> None:
    signals = [
        risk("precio_anomalo", 0, weight=40, confidence=1.0),
        risk("pago_fuera_app", 0, weight=40, confidence=0.5),
    ]

    score = combine(signals, ["cuenta_nueva"], CONFIG)

    assert math.isclose(score.confidence, (40 * 1.0 + 40 * 0.5) / TOTAL_RISK_WEIGHT, abs_tol=0.01)


def test_unavailable_signals_are_reported_and_lower_confidence() -> None:
    full = combine([risk("precio_anomalo", 10, weight=40)], [], CONFIG)
    partial = combine([risk("precio_anomalo", 10, weight=40)], ["cuenta_nueva"], CONFIG)

    assert partial.unavailable_signals == ["cuenta_nueva"]
    assert partial.confidence == full.confidence  # only evaluated signals add confidence
