from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import settings


def test_analyze_is_limited_per_ip(
    client: TestClient, ps5_listing: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit", "3/minute")

    statuses = [client.post("/analyze", json=ps5_listing).status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]
    assert "Espera un minuto" in client.post("/analyze", json=ps5_listing).json()["detail"]


def test_health_is_not_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit", "1/minute")

    statuses = [client.get("/health").status_code for _ in range(3)]

    assert statuses == [200, 200, 200]


def test_rate_limited_response_keeps_cors_headers(
    client: TestClient, ps5_listing: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The extension must be able to read the 429 to show "espera un minuto"."""
    monkeypatch.setattr(settings, "rate_limit", "1/minute")
    origin = {"Origin": "http://localhost:5173"}
    client.post("/analyze", json=ps5_listing, headers=origin)

    response = client.post("/analyze", json=ps5_listing, headers=origin)

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
