import importlib.util
from types import ModuleType
from typing import Any

import pytest

from app.config import REPO_ROOT
from app.evaluation import EvalItem


@pytest.fixture(scope="module")
def importer() -> ModuleType:
    path = REPO_ROOT / "scripts" / "import_real.py"
    spec = importlib.util.spec_from_file_location("import_real", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collected(listing_id: str = "10976327067", **changes: Any) -> dict[str, Any]:
    listing = {
        "platform": "vinted",
        "listing_id": listing_id,
        "title": "PS5 Slim",
        "description": "Escríbeme al 612 345 678 o a ana.garcia@gmail.com",
        "price_eur": 350,
        "seller": {"ratings_count": 14, "ratings_avg": 4.8},
        "shipping_available": True,
        "comparables": [{"title": "PS5 llama al 698765432", "price_eur": 400}],
        **changes,
    }
    return {"url": f"https://www.vinted.es/items/{listing_id}", "ok": True, "listing": listing}


def test_anonymize_hides_ids_phones_and_emails(importer: ModuleType) -> None:
    listing = importer.anonymize(collected()["listing"])

    assert listing.listing_id.startswith("real-")
    assert "10976327067" not in listing.model_dump_json()
    assert listing.description == "Escríbeme al [TELEFONO] o a [EMAIL]"
    assert listing.comparables[0].title == "PS5 llama al [TELEFONO]"


def test_new_items_skip_failures_and_duplicates(importer: ModuleType) -> None:
    first: list[EvalItem] = importer.new_items([collected("1")], [])
    batch = [collected("1"), collected("2"), {"url": "x", "ok": False, "error": "timeout"}]

    items: list[EvalItem] = importer.new_items(batch, first)

    assert [item.id for item in first] == ["r001"]
    assert [item.id for item in items] == ["r002"]
    assert items[0].split == "real"
    assert items[0].label == "sin_revisar"
    assert not items[0].is_labeled
