"""Pydantic schemas for the POST /analyze contract (see "Contrato de la API" in CLAUDE.md)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_TEXT_LENGTH = 5000

Platform = Literal["wallapop", "vinted"]
RiskLevel = Literal["verde", "amarillo", "rojo"]
TextAnalysis = Literal["llm", "basico"]

Text = Annotated[str, Field(max_length=MAX_TEXT_LENGTH)]
Unit = Annotated[float, Field(ge=0, le=1)]
Count = Annotated[int, Field(ge=0)]


class _StrictModel(BaseModel):
    # Reject unknown fields so the extension cannot send anything beyond the listing data.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Seller(_StrictModel):
    """Seller data visible on the listing page. Missing values mean "not visible"."""

    account_age_days: Count | None = None
    ratings_count: Count | None = None
    ratings_avg: Annotated[float, Field(ge=0, le=5)] | None = None
    sales_count: Count | None = None


class Listing(_StrictModel):
    platform: Platform
    listing_id: Annotated[str, Field(min_length=1, max_length=100)]
    title: Text
    description: Text = ""
    price_eur: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    category: Annotated[str, Field(max_length=100)] | None = None
    seller: Seller = Field(default_factory=Seller)
    shipping_available: bool = False
    image_count: Count = 0


class Reason(BaseModel):
    signal: str
    # Risk signals add points; mitigators show the points they remove as a negative number.
    points: Annotated[float, Field(ge=-100, le=100)]
    intensity: Unit
    confidence: Unit
    message: str
    evidence: str


class Analysis(BaseModel):
    risk_score: Annotated[int, Field(ge=0, le=100)]
    level: RiskLevel
    confidence: Unit
    reasons: list[Reason]
    unavailable_signals: list[str]
    text_analysis: TextAnalysis
    analyzed_at: datetime
    version: str
