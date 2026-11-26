from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.analyze import get_llm_service, limiter
from app.llm.cache import FindingsCache
from app.llm.service import LlmTextService
from app.main import app
from tests.fakes import FakeLLM


@pytest.fixture(autouse=True)
def reset_rate_limit() -> None:
    """Every test starts with a fresh per-IP quota (all test requests share one IP)."""
    limiter.reset()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """API client with the LLM disabled (rules only), so tests never call a real API."""
    app.dependency_overrides[get_llm_service] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_llm(tmp_path: Path) -> Iterator[tuple[TestClient, FakeLLM]]:
    """API client backed by a fake LLM; set `fake.reply` before posting."""
    fake = FakeLLM()
    service = LlmTextService(fake, FindingsCache(tmp_path / "c.db", timedelta(hours=24)), "fake")
    app.dependency_overrides[get_llm_service] = lambda: service
    yield TestClient(app), fake
    app.dependency_overrides.clear()


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
