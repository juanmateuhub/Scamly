from typing import Any

from app.models.listing import Listing

BASE_LISTING: dict[str, Any] = {
    "platform": "wallapop",
    "listing_id": "test-1",
    "title": "Producto de prueba",
    "description": "",
    "price_eur": 100,
    "category": None,
    "seller": {},
    "shipping_available": False,
    "image_count": 3,
}


def make_listing(**overrides: Any) -> Listing:
    return Listing.model_validate({**BASE_LISTING, **overrides})
