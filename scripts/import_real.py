"""Add real listings collected with extension/dev/collector.ts to the evaluation dataset.

Usage (from the repo root, with the backend virtualenv):
    backend/.venv/Scripts/python scripts/import_real.py ~/Downloads/scamly-real-*.json

Anonymisation before anything is written: the platform's listing ID becomes a hash
(no link back to the listing), phones and emails in every text become [TELEFONO] and
[EMAIL], and the URL is dropped. Seller data is already only counts and averages. Listings
are stored in the "real" split with label "sin_revisar" until the author labels them.
"""

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.evaluation import DATASET_PATH, EvalItem, load_dataset
from app.models.listing import Listing
from app.signals.text_llm import redact


def anonymize(listing: dict[str, Any]) -> Listing:
    """The listing without anything that identifies the seller or the listing itself."""
    key = f"{listing['platform']}:{listing['listing_id']}".encode()
    data = {
        **listing,
        "listing_id": "real-" + hashlib.sha256(key).hexdigest()[:12],
        "title": redact(listing["title"]),
        "description": redact(listing.get("description", "")),
        "comparables": [
            {"title": redact(c["title"]), "price_eur": c["price_eur"]}
            for c in listing.get("comparables", [])
        ],
    }
    return Listing.model_validate(data)


def new_items(collected: list[dict[str, Any]], existing: list[EvalItem]) -> list[EvalItem]:
    """Successful extractions not already in the dataset, numbered after the last r-id."""
    known = {item.listing.listing_id for item in existing}
    numbers = [int(i.id[1:]) for i in existing if i.id.startswith("r") and i.id[1:].isdigit()]
    next_number = max(numbers, default=0) + 1
    items = []
    for entry in collected:
        if not entry.get("ok"):
            continue
        listing = anonymize(entry["listing"])
        if listing.listing_id in known:
            continue
        known.add(listing.listing_id)
        items.append(
            EvalItem(
                id=f"r{next_number:03d}",
                label="sin_revisar",
                split="real",
                notes="",
                source=f"real: {listing.platform}, recogido el {date.today()}, anonimizado",
                listing=listing,
            )
        )
        next_number += 1
    return items


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("files", nargs="+", type=Path, help="JSON files from the collector")
    args = parser.parse_args()

    collected = [e for f in args.files for e in json.loads(f.read_text(encoding="utf-8"))]
    items = new_items(collected, load_dataset())
    with DATASET_PATH.open("a", encoding="utf-8", newline="\n") as file:
        for item in items:
            row = item.model_dump(mode="json", exclude_none=True)  # same style as the other lines
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    failed = sum(1 for e in collected if not e.get("ok"))
    print(f"{len(items)} anuncios añadidos al split real ({failed} sin datos, resto duplicados)")


if __name__ == "__main__":
    main()
