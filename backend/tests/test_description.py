import math

import pytest

from app.rules.loader import ShortDescriptionConfig
from app.signals.description import short_description_signal
from tests.factories import make_listing

CONFIG = ShortDescriptionConfig(weight=15, full_risk_words=5, no_risk_words=30)


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("", 1.0),
        ("Precio fijo. Envío por la app.", 1 - 1 / 25),  # 6 words
        ("uno dos tres cuatro cinco", 1.0),  # at full_risk_words
        (" ".join(["palabra"] * 30), 0.0),  # at no_risk_words
        (" ".join(["palabra"] * 80), 0.0),
    ],
)
def test_intensity_decreases_linearly_with_words(description: str, expected: float) -> None:
    result = short_description_signal(make_listing(description=description), CONFIG)

    assert math.isclose(result.intensity, expected)
    assert result.signal == "descripcion_pobre"
    assert result.kind == "risk"


def test_message_and_evidence() -> None:
    result = short_description_signal(
        make_listing(description="Precio fijo. Envío por la app."), CONFIG
    )

    assert result.message == "La descripción es muy corta"
    assert result.evidence == "6 palabras"


def test_longer_descriptions_never_add_risk() -> None:
    words = ["el", "producto", "está", "en", "buen", "estado", "y", "funciona", "bien"]
    intensities = [
        short_description_signal(make_listing(description=" ".join(words * n)), CONFIG).intensity
        for n in range(6)
    ]

    assert intensities == sorted(intensities, reverse=True)
