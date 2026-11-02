from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def ps5_listing() -> dict[str, Any]:
    """Invented PS5 listing from the API contract in CLAUDE.md."""
    return {
        "platform": "wallapop",
        "listing_id": "abc123",
        "title": "PS5 nueva precintada",
        "description": "Me voy del país, solo Bizum, escríbeme por WhatsApp",
        "price_eur": 180,
        "category": "consolas",
        "seller": {
            "account_age_days": 3,
            "ratings_count": 0,
            "ratings_avg": None,
            "sales_count": 0,
        },
        "shipping_available": False,
        "image_count": 2,
    }
