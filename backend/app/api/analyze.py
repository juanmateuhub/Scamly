from datetime import UTC, datetime

from fastapi import APIRouter

from app.models.listing import Analysis, Listing
from app.rules.loader import load_phrase_rules, load_reference_prices, load_scoring_config
from app.scoring.analyzer import analyze_listing

router = APIRouter()


@router.post("/analyze")
def analyze(listing: Listing) -> Analysis:
    return analyze_listing(
        listing,
        config=load_scoring_config(),
        phrases=load_phrase_rules(),
        reference=load_reference_prices(),
        now=datetime.now(UTC),
    )
