from typing import Any

import pytest
from fastapi.testclient import TestClient


def test_ps5_example_is_red_with_explained_reasons(
    client: TestClient, ps5_listing: dict[str, Any]
) -> None:
    response = client.post("/analyze", json=ps5_listing)

    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "rojo"
    assert body["risk_score"] >= 60
    signals = [r["signal"] for r in body["reasons"]]
    assert signals[0] == "pago_fuera_app"
    assert set(signals) == {
        "pago_fuera_app",
        "precio_anomalo",
        "contacto_externo",
        "cuenta_nueva",
        "sin_historial",
        "urgencia",
        "descripcion_pobre",
    }
    points = [r["points"] for r in body["reasons"]]
    assert points == sorted(points, reverse=True)
    assert body["text_analysis"] == "basico"
    assert body["version"] == "0.1.0"
    assert 0 < body["confidence"] <= 1
    assert "analyzed_at" in body


def test_honest_listing_is_green(client: TestClient, ps5_listing: dict[str, Any]) -> None:
    ps5_listing.update(
        title="PS5 slim con dos mandos",
        description="Con factura y caja original. Envío por la app o en mano.",
        price_eur=390,
        shipping_available=True,
        seller={
            "account_age_days": 900,
            "ratings_count": 85,
            "ratings_avg": 4.9,
            "sales_count": 70,
        },
    )

    body = client.post("/analyze", json=ps5_listing).json()

    assert body["level"] == "verde"
    assert {"vendedor_con_historial", "envio_protegido"} <= {r["signal"] for r in body["reasons"]}


def test_unknown_product_reports_unavailable_price(
    client: TestClient, ps5_listing: dict[str, Any]
) -> None:
    ps5_listing.update(title="Bicicleta de montaña", description="", seller={})

    body = client.post("/analyze", json=ps5_listing).json()

    assert set(body["unavailable_signals"]) >= {
        "precio_anomalo",
        "cuenta_nueva",
        "sin_historial",
        "vendedor_con_historial",
    }


def test_analyze_accepts_missing_seller_data(
    client: TestClient, ps5_listing: dict[str, Any]
) -> None:
    ps5_listing["seller"] = {}
    ps5_listing["category"] = None

    response = client.post("/analyze", json=ps5_listing)

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price_eur", -1),
        ("platform", "ebay"),
        ("description", "a" * 5001),
        ("title", "a" * 5001),
        ("image_count", -1),
        ("listing_id", ""),
    ],
)
def test_analyze_rejects_invalid_fields(
    client: TestClient, ps5_listing: dict[str, Any], field: str, value: Any
) -> None:
    ps5_listing[field] = value

    response = client.post("/analyze", json=ps5_listing)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("account_age_days", -1),
        ("ratings_count", -1),
        ("ratings_avg", 5.1),
        ("sales_count", -1),
    ],
)
def test_analyze_rejects_invalid_seller_fields(
    client: TestClient, ps5_listing: dict[str, Any], field: str, value: Any
) -> None:
    ps5_listing["seller"][field] = value

    response = client.post("/analyze", json=ps5_listing)

    assert response.status_code == 422


def test_analyze_accepts_description_at_limit(
    client: TestClient, ps5_listing: dict[str, Any]
) -> None:
    ps5_listing["description"] = "a" * 5000

    response = client.post("/analyze", json=ps5_listing)

    assert response.status_code == 200


def test_analyze_rejects_unknown_fields(client: TestClient, ps5_listing: dict[str, Any]) -> None:
    ps5_listing["cookies"] = "session=123"

    response = client.post("/analyze", json=ps5_listing)

    assert response.status_code == 422


def test_analyze_rejects_missing_required_field(
    client: TestClient, ps5_listing: dict[str, Any]
) -> None:
    del ps5_listing["price_eur"]

    response = client.post("/analyze", json=ps5_listing)

    assert response.status_code == 422


def test_comparables_are_validated(client: TestClient, ps5_listing: dict[str, Any]) -> None:
    ps5_listing["comparables"] = [{"title": "PS5", "price_eur": -5}]

    assert client.post("/analyze", json=ps5_listing).status_code == 422


def test_comparables_are_limited(client: TestClient, ps5_listing: dict[str, Any]) -> None:
    ps5_listing["comparables"] = [{"title": "PS5", "price_eur": 400}] * 61

    assert client.post("/analyze", json=ps5_listing).status_code == 422


def test_price_check_is_reported_even_when_the_price_is_normal(
    client: TestClient, ps5_listing: dict[str, Any]
) -> None:
    ps5_listing.update(
        title="iPhone 17",
        price_eur=720,
        comparables=[
            {"title": "iPhone 17 256GB", "price_eur": p} for p in (680, 700, 720, 750, 780)
        ],
    )

    body = client.post("/analyze", json=ps5_listing).json()

    assert "precio_anomalo" not in {r["signal"] for r in body["reasons"]}
    assert body["price_check"] == {
        "message": "Precio en línea con lo habitual",
        "evidence": "720 € frente a 720 € (mediana de 5 anuncios similares)",
    }


def test_price_check_is_null_without_reference(
    client: TestClient, ps5_listing: dict[str, Any]
) -> None:
    ps5_listing.update(title="Bicicleta de montaña")

    assert client.post("/analyze", json=ps5_listing).json()["price_check"] is None
