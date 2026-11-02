from typing import Any

import pytest
from fastapi.testclient import TestClient


def test_analyze_accepts_valid_listing(client: TestClient, ps5_listing: dict[str, Any]) -> None:
    response = client.post("/analyze", json=ps5_listing)

    assert response.status_code == 200
    body = response.json()
    assert body["risk_score"] == 0
    assert body["level"] == "verde"
    assert body["reasons"] == []
    assert body["version"] == "0.1.0"
    assert 0 <= body["confidence"] <= 1
    assert body["text_analysis"] in {"llm", "basico"}
    assert "analyzed_at" in body


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
