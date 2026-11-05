import math

import pytest

from app.rules.loader import TextSignalConfig, TextSignalName, load_phrase_rules
from app.signals.base import SignalResult
from app.signals.text_rules import combine_strengths, normalize, text_rule_signals
from tests.factories import make_listing

WEIGHTS: dict[TextSignalName, TextSignalConfig] = {
    "pago_fuera_app": TextSignalConfig(weight=40),
    "contacto_externo": TextSignalConfig(weight=25),
    "urgencia": TextSignalConfig(weight=10),
}
REGEX_CONFIDENCE = 0.8
RULES = load_phrase_rules()


def analyze(description: str, title: str = "Vendo artículo") -> dict[str, SignalResult]:
    listing = make_listing(title=title, description=description)
    results = text_rule_signals(listing, RULES, WEIGHTS, REGEX_CONFIDENCE)
    return {r.signal: r for r in results}


# --- helpers ------------------------------------------------------------------


def test_normalize_keeps_length_and_strips_accents() -> None:
    text = "Escríbeme por WhatsApp, ¡ÚLTIMO día!"

    normalized = normalize(text)

    assert normalized == "escribeme por whatsapp, ¡ultimo dia!"
    assert len(normalized) == len(text)


@pytest.mark.parametrize(
    ("strengths", "expected"),
    [([], 0.0), ([1.0], 1.0), ([0.5], 0.5), ([0.5, 0.4], 0.7), ([0.5, 0.5, 0.5], 0.875)],
)
def test_combine_strengths_is_noisy_or(strengths: list[float], expected: float) -> None:
    assert math.isclose(combine_strengths(strengths), expected)


# --- detection ------------------------------------------------------------------


def test_returns_one_result_per_text_signal() -> None:
    results = analyze("")

    assert set(results) == {"pago_fuera_app", "contacto_externo", "urgencia"}
    assert all(r.intensity == 0 for r in results.values())


def test_ps5_example() -> None:
    results = analyze("Me voy del país, solo Bizum, escríbeme por WhatsApp")

    pago = results["pago_fuera_app"]
    contacto = results["contacto_externo"]
    urgencia = results["urgencia"]
    assert pago.intensity == 1.0
    assert pago.confidence == REGEX_CONFIDENCE
    assert pago.evidence == "solo Bizum"
    assert pago.message == "Pide pagar fuera de la plataforma, sin protección"
    assert contacto.intensity == 1.0
    assert contacto.evidence == "escríbeme por WhatsApp"
    assert urgencia.intensity == 1.0
    assert urgencia.evidence == "Me voy del país"


def test_overlapping_phrases_count_once() -> None:
    # "escríbeme por WhatsApp" also contains the weaker "WhatsApp" pattern.
    results = analyze("escríbeme por WhatsApp")

    assert results["contacto_externo"].evidence == "escríbeme por WhatsApp"


def test_independent_weak_phrases_combine() -> None:
    weak = analyze("acepto bizum")["pago_fuera_app"]
    combined = analyze("acepto bizum o transferencia")["pago_fuera_app"]

    assert 0 < weak.intensity < 1
    assert combined.intensity > weak.intensity
    assert combined.intensity < 1


@pytest.mark.parametrize(
    "text",
    [
        "No acepto bizum, solo pago por la app",
        "Nada de transferencias",
        "Sin bizum ni transferencia",
        "Un poco rayado por fuera",
    ],
)
def test_negations_and_innocent_phrases_do_not_trigger_payment(text: str) -> None:
    assert analyze(text)["pago_fuera_app"].intensity == 0


def test_negation_only_applies_within_the_same_clause() -> None:
    result = analyze("No tiene golpes, solo bizum")["pago_fuera_app"]

    assert result.intensity == 1.0


@pytest.mark.parametrize(
    "text",
    ["Llámame al 612 345 678", "Mi móvil: +34 612345678", "contacto: vendedor.ps5@gmail.com"],
)
def test_contact_details_are_detected(text: str) -> None:
    assert analyze(text)["contacto_externo"].intensity == 1.0


def test_prices_are_not_phone_numbers() -> None:
    assert analyze("Precio 450 euros, comprada en 2024")["contacto_externo"].intensity == 0


@pytest.mark.parametrize(
    "text", ["El primero que pague se lo lleva", "Urge vender hoy mismo", "Me voy de España"]
)
def test_urgency_is_detected(text: str) -> None:
    assert analyze(text)["urgencia"].intensity > 0


def test_title_is_analyzed_too() -> None:
    results = analyze("", title="iPhone 15 solo bizum")

    assert results["pago_fuera_app"].intensity == 1.0


def test_points_combine_weight_intensity_and_confidence() -> None:
    result = analyze("solo bizum")["pago_fuera_app"]

    assert math.isclose(result.points, 40 * 1.0 * 0.8)


def test_shipped_phrase_rules_are_valid() -> None:
    assert set(RULES.signals) == {"pago_fuera_app", "contacto_externo", "urgencia"}
    assert all(phrases for phrases in RULES.signals.values())


# --- in-person payment is not "outside the platform" ----------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Pago por bizum en mano al recoger",
        "Entrega en mano en Zaragoza, pago con Bizum al recogerla.",
        "Recoger en Sevilla, pago en efectivo o bizum al recoger",
        "Bizum cuando lo recojas en persona",
    ],
)
def test_payment_on_pickup_in_person_does_not_count(text: str) -> None:
    assert analyze(text)["pago_fuera_app"].intensity == 0


def test_in_person_exemption_only_applies_to_the_same_clause() -> None:
    result = analyze("Solo bizum por adelantado; se puede ver en mano")["pago_fuera_app"]

    assert result.intensity == 1.0


# --- seller abroad with own courier: pay first, receive never --------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Estoy fuera de España por trabajo, mi agencia de transporte te la entrega tras el pago.",
        "Te lo envío cuando me hagas el ingreso",
        "Mi empresa de mensajería se lo lleva después del pago",
    ],
)
def test_pay_first_own_courier_is_detected(text: str) -> None:
    assert analyze(text)["pago_fuera_app"].intensity >= 0.8
