import math

import pytest

from app.rules.loader import (
    AccountAgeConfig,
    BadRatingsConfig,
    HistoryConfig,
    SellerReputationConfig,
    ShippingConfig,
)
from app.signals.seller import (
    account_age_signal,
    bad_ratings_signal,
    history_signal,
    seller_reputation_mitigator,
)
from app.signals.shipping import shipping_mitigator
from tests.factories import make_listing

AGE = AccountAgeConfig(weight=15, decay_days=30)
HISTORY = HistoryConfig(weight=10, half_count=3)
REPUTATION = SellerReputationConfig(
    max_reduction=0.30, full_count=50, avg_floor=4.0, avg_ceiling=5.0
)
SHIPPING = ShippingConfig(max_reduction=0.15)
BAD = BadRatingsConfig(weight=20, full_count=10, avg_ok=3.5, avg_bad=2.0)


# --- account age -------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "expected"),
    [(0, 1.0), (3, math.exp(-0.1)), (30, math.exp(-1)), (90, math.exp(-3))],
)
def test_account_age_decays_exponentially(days: int, expected: float) -> None:
    result = account_age_signal(make_listing(seller={"account_age_days": days}), AGE)

    assert result is not None
    assert math.isclose(result.intensity, expected)
    assert result.signal == "cuenta_nueva"


def test_account_age_message_matches_example() -> None:
    result = account_age_signal(make_listing(seller={"account_age_days": 3}), AGE)

    assert result is not None
    assert result.message == "La cuenta se creó hace 3 días"
    assert math.isclose(result.points, 13.57, abs_tol=0.01)


def test_account_age_singular_day() -> None:
    result = account_age_signal(make_listing(seller={"account_age_days": 1}), AGE)

    assert result is not None
    assert result.message == "La cuenta se creó hace 1 día"


def test_account_age_unknown_returns_none() -> None:
    assert account_age_signal(make_listing(seller={}), AGE) is None


def test_older_account_never_increases_risk() -> None:
    intensities = [
        account_age_signal(make_listing(seller={"account_age_days": d}), AGE).intensity  # type: ignore[union-attr]
        for d in range(0, 400, 7)
    ]

    assert intensities == sorted(intensities, reverse=True)


# --- history -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("ratings", "sales", "expected"),
    [(0, 0, 1.0), (3, 0, 0.5), (0, 3, 0.5), (2, 1, 0.5), (27, 0, 0.1)],
)
def test_history_intensity(ratings: int, sales: int, expected: float) -> None:
    listing = make_listing(seller={"ratings_count": ratings, "sales_count": sales})
    result = history_signal(listing, HISTORY)

    assert result is not None
    assert math.isclose(result.intensity, expected)


def test_history_without_any_activity_message() -> None:
    listing = make_listing(seller={"ratings_count": 0, "sales_count": 0})
    result = history_signal(listing, HISTORY)

    assert result is not None
    assert result.message == "El vendedor apenas tiene valoraciones"
    assert result.evidence == "0 valoraciones, 0 ventas"


def test_history_with_one_count_missing_uses_the_other() -> None:
    result = history_signal(make_listing(seller={"ratings_count": 3}), HISTORY)

    assert result is not None
    assert math.isclose(result.intensity, 0.5)
    assert result.evidence == "3 valoraciones"


def test_history_unknown_returns_none() -> None:
    assert history_signal(make_listing(seller={}), HISTORY) is None


# --- seller reputation (mitigator) --------------------------------------------


@pytest.mark.parametrize(
    ("count", "avg", "expected"),
    [
        (50, 5.0, 1.0),
        (100, 5.0, 1.0),
        (25, 4.5, 0.25),
        (50, 4.0, 0.0),
        (50, 3.0, 0.0),
        (0, 5.0, 0.0),
    ],
)
def test_reputation_intensity(count: int, avg: float, expected: float) -> None:
    listing = make_listing(seller={"ratings_count": count, "ratings_avg": avg})
    result = seller_reputation_mitigator(listing, REPUTATION)

    assert result is not None
    assert result.kind == "mitigator"
    assert math.isclose(result.intensity, expected)
    assert math.isclose(result.points, 0.30 * expected)


def test_reputation_needs_count_and_average() -> None:
    assert (
        seller_reputation_mitigator(make_listing(seller={"ratings_count": 80}), REPUTATION) is None
    )
    assert (
        seller_reputation_mitigator(make_listing(seller={"ratings_avg": 4.9}), REPUTATION) is None
    )


def test_reputation_evidence() -> None:
    listing = make_listing(seller={"ratings_count": 120, "ratings_avg": 4.8})
    result = seller_reputation_mitigator(listing, REPUTATION)

    assert result is not None
    assert result.message == "Vendedor con buen historial"
    assert result.evidence == "120 valoraciones, media 4,8"


# --- shipping (mitigator) -------------------------------------------------------


def test_shipping_available_mitigates() -> None:
    result = shipping_mitigator(make_listing(shipping_available=True), SHIPPING)

    assert result.kind == "mitigator"
    assert result.intensity == 1.0
    assert math.isclose(result.points, 0.15)
    assert result.message == "Ofrece envío con protección de la app"


def test_shipping_not_available_does_not_mitigate() -> None:
    result = shipping_mitigator(make_listing(shipping_available=False), SHIPPING)

    assert result.intensity == 0.0


# --- bad ratings ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "avg", "expected"),
    [
        (10, 2.0, 1.0),  # enough ratings, very bad average
        (40, 1.5, 1.0),
        (10, 2.75, 0.5),  # halfway between avg_bad and avg_ok
        (5, 2.0, 0.5),  # few ratings: less evidence
        (10, 3.5, 0.0),  # acceptable average
        (50, 4.8, 0.0),
    ],
)
def test_bad_ratings_intensity(count: int, avg: float, expected: float) -> None:
    listing = make_listing(seller={"ratings_count": count, "ratings_avg": avg})
    result = bad_ratings_signal(listing, BAD)

    assert result is not None
    assert result.kind == "risk"
    assert result.signal == "malas_valoraciones"
    assert math.isclose(result.intensity, expected)


def test_bad_ratings_message_and_evidence() -> None:
    listing = make_listing(seller={"ratings_count": 12, "ratings_avg": 2.4})
    result = bad_ratings_signal(listing, BAD)

    assert result is not None
    assert result.message == "El vendedor tiene malas valoraciones"
    assert result.evidence == "12 valoraciones, media 2,4"


def test_bad_ratings_unknown_returns_none() -> None:
    assert bad_ratings_signal(make_listing(seller={"ratings_count": 0}), BAD) is None
