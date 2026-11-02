import hashlib
from datetime import datetime

from app.llm.cache import FindingsCache
from app.llm.client import LLMClient
from app.models.listing import Listing
from app.signals.text_llm import LlmFindings, analyze_text_with_llm


class LlmTextService:
    """LLM text analysis with a cache, so each listing costs at most one request per TTL."""

    def __init__(self, client: LLMClient, cache: FindingsCache, model_id: str) -> None:
        self._client = client
        self._cache = cache
        self._model_id = model_id

    def _key(self, listing: Listing) -> str:
        parts = (self._model_id, listing.platform, listing.listing_id, listing.title)
        text = "\0".join((*parts, listing.description))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def findings_for(self, listing: Listing, now: datetime) -> LlmFindings | None:
        key = self._key(listing)
        cached = self._cache.get(key, now)
        if cached is not None:
            return cached
        findings = analyze_text_with_llm(listing, self._client)
        if findings is not None:  # failures are not cached, the next request retries
            self._cache.put(key, findings, now)
        return findings
