import math

import pytest

from app.rules.loader import (
    ComparablesConfig,
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
    comparables=ComparablesConfig(min_count=5, full_count=15, max_confidence=0.9),
    condition_factors={
        "nuevo": 1.0,
        "como_nuevo": 1.0,
        "buen_estado": 0.85,
        "aceptable": 0.6,
        "danado": 0.3,
        "desconocido": 0.85,
    },
)

REFERENCE = ReferencePrices(
    skip_words=["funda", "busco"],
    variant_words=["pro", "max", "plus", "digital"],
    conditions={
        "sin abrir": "nuevo",
        "como nuevo": "como_nuevo",
        "muy bueno": "como_nuevo",
        "en buen estado": "buen_estado",
        "satisfactorio": "aceptable",
        "lo ha dado todo": "danado",
    },
    wear_phrases=["arañazos", "rayado", "desgaste"],
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
    title: str,
    price: float,
    category: str | None = None,
    description: str = "",
    condition: str | None = "Como nuevo",
) -> SignalResult | None:
    listing = make_listing(
        title=title,
        price_eur=price,
        category=category,
        description=description,
        condition=condition,
    )
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
    assert result.evidence == "180 € frente a 500 € (PS5) · estado: como nuevo"


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
    assert "(iPhone 15 Pro)" in pro.evidence
    assert "(iPhone 15)" in base.evidence


def test_excluded_variant_without_own_entry_is_not_matched() -> None:
    assert signal_for("iPhone 15 Pro Max", 300) is None


def test_alias_must_match_whole_words() -> None:
    assert signal_for("Cable PS50", 5) is None


def test_category_fallback_has_lower_confidence() -> None:
    result = signal_for("Zapatillas running", 20, category="Zapatillas")

    assert result is not None
    assert result.confidence == 0.6
    assert result.evidence == "20 € frente a 80 € (categoría zapatillas) · estado: como nuevo"


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


# --- comparables: the same product listed right now --------------------------------


def comparables(*prices: float, title: str = "iPhone 17 256GB") -> list[dict[str, object]]:
    return [{"title": title, "price_eur": price} for price in prices]


def comparable_signal(
    title: str, price: float, items: list[dict[str, object]]
) -> SignalResult | None:
    listing = make_listing(title=title, price_eur=price, comparables=items, condition="Como nuevo")
    return price_signal(listing, REFERENCE, CONFIG)


def test_median_of_comparables_is_the_reference() -> None:
    items = comparables(600, 650, 700, 720, 750, 800, 900)

    result = comparable_signal("iPhone 17", 350, items)

    assert result is not None
    assert result.evidence.startswith("350 € frente a 720 € (mediana de 7 anuncios similares)")
    assert math.isclose(result.intensity, (0.75 - 350 / 720) / 0.5)


def test_comparables_win_over_the_reference_table() -> None:
    # The table says 500 for "iPhone 15"; live listings say 300.
    result = comparable_signal("iPhone 15", 280, comparables(*[300] * 6, title="iPhone 15 128GB"))

    assert result is not None
    assert "(mediana de 6 anuncios similares)" in result.evidence
    assert result.intensity == 0


def test_too_few_comparables_fall_back_to_the_table() -> None:
    result = comparable_signal("iPhone 15", 250, comparables(300, 310, title="iPhone 15"))

    assert result is not None
    assert result.evidence.startswith("250 € frente a 500 € (iPhone 15)")


def test_too_few_comparables_and_unknown_product_returns_none() -> None:
    assert comparable_signal("Cámara Sony A7 IV", 400, comparables(1200, 1300)) is None


def test_other_variants_accessories_and_defects_are_ignored() -> None:
    items = [
        *comparables(700, 710, 720, 730, 740),
        *comparables(1100, 1150, title="iPhone 17 Pro 256GB"),  # other variant
        *comparables(1300, title="iPhone 17 Pro Max"),
        *comparables(10, 12, title="Funda iPhone 17"),  # accessory
        *comparables(150, title="iPhone 17 pantalla rota"),  # defect
        *comparables(0, title="iPhone 17"),  # no price
    ]

    result = comparable_signal("iPhone 17", 700, items)

    assert result is not None
    assert result.evidence.startswith("700 € frente a 720 € (mediana de 5 anuncios similares)")


def test_a_pro_listing_only_compares_with_pro_listings() -> None:
    items = [
        *comparables(700, 710, 720, 730, 740),
        *comparables(*[1100] * 5, title="iPhone 17 Pro"),
    ]

    result = comparable_signal("iPhone 17 Pro 256GB", 1000, items)

    assert result is not None
    assert "frente a 1100 € (mediana de 5 anuncios similares)" in result.evidence


@pytest.mark.parametrize(
    ("prices", "expected"),
    [
        ([700] * 15, 0.9),  # many, identical prices: max confidence
        ([700] * 5, 0.9 * 5 / 15),  # few comparables
    ],
)
def test_confidence_grows_with_count(prices: list[float], expected: float) -> None:
    result = comparable_signal("iPhone 17", 300, comparables(*prices))

    assert result is not None
    assert math.isclose(result.confidence, expected)


def test_scattered_prices_lower_the_confidence() -> None:
    tight = comparable_signal("iPhone 17", 300, comparables(*[690, 700, 710] * 5))
    scattered = comparable_signal("iPhone 17", 300, comparables(*[200, 700, 1400] * 5))

    assert tight is not None
    assert scattered is not None
    assert scattered.confidence < tight.confidence


# --- condition: a worn item may be cheap for a good reason ---------------------------------


@pytest.mark.parametrize(
    ("condition", "factor", "label"),
    [
        ("Sin abrir", 1.0, "nuevo"),
        ("Como nuevo", 1.0, "como nuevo"),
        ("Muy bueno", 1.0, "como nuevo"),  # Vinted
        ("En buen estado", 0.85, "buen estado"),
        ("Satisfactorio", 0.6, "aceptable"),
        ("Lo ha dado todo", 0.3, "dañado"),
        (None, 0.85, None),
        ("Texto desconocido", 0.85, None),
    ],
)
def test_condition_scales_the_price_signal(
    condition: str | None, factor: float, label: str | None
) -> None:
    result = signal_for("PS5", 125, condition=condition)  # full intensity at ratio 0.25

    assert result is not None
    assert math.isclose(result.intensity, factor)
    if label:
        assert result.evidence.endswith(f"· estado: {label}")
    else:
        assert "estado" not in result.evidence


def test_wear_in_the_description_lowers_the_condition() -> None:
    result = signal_for("PS5", 125, description="Tiene algunos arañazos en la carcasa")

    assert result is not None
    assert math.isclose(result.intensity, 0.6)
    assert result.evidence.endswith("· estado: con desgaste («arañazos»)")


def test_wear_never_improves_a_worse_condition() -> None:
    result = signal_for("PS5", 125, condition="Lo ha dado todo", description="algo rayado")

    assert result is not None
    assert math.isclose(result.intensity, 0.3)
