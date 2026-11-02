import math

import pytest

from app.rules.loader import (
    PriceConfig,
    ReferencePrices,
    ReferenceProduct,
    load_reference_prices,
    load_scoring_config,
)
from app.signals.base import SignalResult
from app.signals.price import price_signal
from tests.factories import make_listing

CONFIG = PriceConfig(
    weight=40,
    ratio_no_risk=0.75,
    ratio_max_risk=0.25,
    confidence_product=1.0,
    confidence_category=0.6,
)

REFERENCE = ReferencePrices(
    skip_words=["funda", "busco"],
    defect_phrases=["para piezas", "pantalla rota", "no carga"],
    products=[
        ReferenceProduct(
            name="PS5", category="consolas", price_eur=500, aliases=["ps5", "playstation 5"]
        ),
        ReferenceProduct(
            name="iPhone 15 Pro",
            category="moviles",
            price_eur=700,
            aliases=["iphone 15 pro"],
            exclude=["max"],
        ),
        ReferenceProduct(
            name="iPhone 15",
            category="moviles",
            price_eur=500,
            aliases=["iphone 15"],
            exclude=["pro", "plus"],
        ),
    ],
    categories={"zapatillas": 80},
)


def signal_for(
    title: str, price: float, category: str | None = None, description: str = ""
) -> SignalResult | None:
    listing = make_listing(title=title, price_eur=price, category=category, description=description)
    return price_signal(listing, REFERENCE, CONFIG)


@pytest.mark.parametrize(
    ("price", "expected_intensity"),
    [
        (500, 0.0),  # at reference price
        (375, 0.0),  # ratio 0.75: no risk yet
        (250, 0.5),  # ratio 0.50: halfway
        (180, 0.78),  # ratio 0.36: PS5 example from CLAUDE.md
        (125, 1.0),  # ratio 0.25: full risk
        (0, 1.0),  # free
        (900, 0.0),  # above reference
    ],
)
def test_intensity_is_linear_between_thresholds(price: float, expected_intensity: float) -> None:
    result = signal_for("PS5 nueva", price)

    assert result is not None
    assert math.isclose(result.intensity, expected_intensity, abs_tol=1e-9)


def test_ps5_example_points_message_and_evidence() -> None:
    result = signal_for("PS5 nueva precintada", 180)

    assert result is not None
    assert result.signal == "precio_anomalo"
    assert result.kind == "risk"
    assert result.confidence == 1.0
    assert math.isclose(result.points, 31.2)
    assert result.message == "Precio un 64 % por debajo de lo habitual"
    assert result.evidence == "180 € frente a 500 € (PS5)"


def test_intensity_never_decreases_when_price_drops() -> None:
    intensities = []
    for price in range(600, -1, -5):
        result = signal_for("PS5", price)
        assert result is not None
        intensities.append(result.intensity)

    assert intensities == sorted(intensities)


def test_matching_ignores_case_and_accents() -> None:
    result = signal_for("Vendo PLAYSTATION 5 con mandos", 200)

    assert result is not None
    assert result.confidence == 1.0


def test_unknown_product_returns_none() -> None:
    assert signal_for("Bicicleta de montaña", 50) is None


@pytest.mark.parametrize("title", ["Funda para PS5", "PS5 para piezas", "Busco PS5"])
def test_skip_words_explain_low_price(title: str) -> None:
    assert signal_for(title, 20) is None


def test_product_exclude_picks_the_specific_model() -> None:
    pro = signal_for("iPhone 15 Pro 256GB", 350)
    base = signal_for("iPhone 15 128GB", 350)

    assert pro is not None
    assert base is not None
    assert pro.evidence.endswith("(iPhone 15 Pro)")
    assert base.evidence.endswith("(iPhone 15)")


def test_excluded_variant_without_own_entry_is_not_matched() -> None:
    assert signal_for("iPhone 15 Pro Max", 300) is None


def test_alias_must_match_whole_words() -> None:
    assert signal_for("Cable PS50", 5) is None


def test_category_fallback_has_lower_confidence() -> None:
    result = signal_for("Zapatillas running", 20, category="Zapatillas")

    assert result is not None
    assert result.confidence == 0.6
    assert result.evidence == "20 € frente a 80 € (categoría zapatillas)"


def test_decimal_prices_use_spanish_format() -> None:
    result = signal_for("PS5", 179.99)

    assert result is not None
    assert result.evidence.startswith("179,99 € frente a 500 €")


def test_fair_price_message() -> None:
    result = signal_for("PS5", 520)

    assert result is not None
    assert result.message == "Precio en línea con lo habitual"


@pytest.mark.parametrize(
    "description", ["Pantalla rota, el resto funciona", "Uno de los auriculares no carga bien"]
)
def test_defects_in_the_description_explain_low_price(description: str) -> None:
    assert signal_for("iPhone 15 128GB", 150, description=description) is None


def test_accessory_words_in_the_description_do_not_hide_the_price() -> None:
    # A scammer writing "con funda de regalo" must not switch the price signal off.
    result = signal_for("iPhone 15 128GB", 150, description="Con funda de regalo, solo bizum")

    assert result is not None
    assert result.intensity > 0


def test_product_exclude_phrases_skip_games_packs() -> None:
    reference = ReferencePrices(
        products=[
            ReferenceProduct(
                name="PS5",
                category="consolas",
                price_eur=400,
                aliases=["ps5"],
                exclude=["juegos ps5", "juegos para ps5"],
            )
        ]
    )
    pack = make_listing(title="Pack 3 juegos PS5", price_eur=60)
    bundle = make_listing(title="PS5 + 2 juegos", price_eur=150)

    assert price_signal(pack, reference, CONFIG) is None
    assert price_signal(bundle, reference, CONFIG) is not None


def test_shipped_rule_files_are_valid() -> None:
    reference = load_reference_prices()
    config = load_scoring_config()

    assert len(reference.products) >= 10
    assert (
        config.signals.precio_anomalo.ratio_no_risk > config.signals.precio_anomalo.ratio_max_risk
    )
