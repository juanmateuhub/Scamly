from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import settings
from app.llm.cache import FindingsCache
from app.llm.client import OpenAICompatibleClient
from app.llm.service import LlmTextService
from app.models.listing import Analysis, Listing
from app.rules.loader import load_phrase_rules, load_reference_prices, load_scoring_config
from app.scoring.analyzer import analyze_listing

router = APIRouter()


@lru_cache
def get_llm_service() -> LlmTextService | None:
    """The LLM service, or None when no API key is configured (rules only)."""
    if not settings.llm_enabled:
        return None
    client = OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key.get_secret_value(),
        timeout_s=settings.llm_timeout_s,
        fallback_models=settings.llm_fallback_list,
        disable_reasoning=settings.llm_disable_reasoning,
    )
    cache = FindingsCache(settings.cache_path, ttl=timedelta(hours=settings.cache_ttl_hours))
    return LlmTextService(client, cache, model_id=settings.llm_model)


@router.post("/analyze")
def analyze(
    listing: Listing,
    llm: Annotated[LlmTextService | None, Depends(get_llm_service)],
) -> Analysis:
    now = datetime.now(UTC)
    return analyze_listing(
        listing,
        config=load_scoring_config(),
        phrases=load_phrase_rules(),
        reference=load_reference_prices(),
        llm_findings=llm.findings_for(listing, now) if llm else None,
        now=now,
    )
