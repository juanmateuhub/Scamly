import pytest

from app.rules.loader import ModelMismatchConfig, ReferencePrices, ReferenceProduct
from app.signals.base import SignalResult
from app.signals.consistency import model_mismatch_signal
from tests.factories import make_listing

CONFIG = ModelMismatchConfig(
    weight=15, confidence=0.8, exemptions=[r"\b(?:compr\w*|compatible|funda)\b"]
)
REFERENCE = ReferencePrices(
    products=[
        ReferenceProduct(name="PS5 Pro", category="consolas", price_eur=650, aliases=["ps5 pro"]),
        ReferenceProduct(name="PS5", category="consolas", price_eur=400, aliases=["ps5"]),
        ReferenceProduct(
            name="iPhone 16", category="moviles", price_eur=500, aliases=["iphone 16"]
        ),
    ]
)


def mismatch(title: str, description: str) -> SignalResult | None:
    listing = make_listing(title=title, description=description)
    return model_mismatch_signal(listing, REFERENCE, CONFIG)


def test_description_promising_a_higher_model_is_flagged() -> None:
    result = mismatch("PS5 Slim", "picture of Sony PlayStation 5 Pro. Es la PS5 Pro de 2 TB")

    assert result is not None
    assert result.intensity == 1.0
    assert result.points == pytest.approx(15 * 0.8)
    assert result.evidence == "título: PS5 · descripción: PS5 Pro"


def test_a_less_specific_description_is_not_a_contradiction() -> None:
    result = mismatch("PS5 Pro 2TB", "Consola PS5 en perfecto estado")

    assert result is not None
    assert result.intensity == 0


@pytest.mark.parametrize(
    "description",
    [
        "La vendo porque me compré la PS5 Pro",
        "Mando compatible con PS5 Pro",
        "Con funda de PS5 Pro",
    ],
)
def test_explained_mentions_of_another_model_are_ignored(description: str) -> None:
    result = mismatch("PS5 Slim", description)

    assert result is not None
    assert result.intensity == 0


def test_other_categories_are_ignored() -> None:
    result = mismatch("iPhone 16", "Se lo cambio a alguien por una PS5 Pro")

    assert result is not None
    assert result.intensity == 0


def test_unknown_title_product_is_not_applicable() -> None:
    assert mismatch("Cámara Sony A7 IV", "Mejor que la PS5 Pro") is None
