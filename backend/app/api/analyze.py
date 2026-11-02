from datetime import UTC, datetime

from fastapi import APIRouter

from app import __version__
from app.models.listing import Analysis, Listing

router = APIRouter()


@router.post("/analyze")
def analyze(listing: Listing) -> Analysis:
    # Placeholder until the scoring engine is wired in (phase 4).
    return Analysis(
        risk_score=0,
        level="verde",
        confidence=0.0,
        reasons=[],
        unavailable_signals=[],
        text_analysis="basico",
        analyzed_at=datetime.now(UTC),
        version=__version__,
    )
