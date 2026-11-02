import math

from app.models.listing import Listing
from app.rules.loader import (
    AccountAgeConfig,
    BadRatingsConfig,
    HistoryConfig,
    SellerReputationConfig,
)
from app.signals.base import SignalResult, clamp


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def account_age_signal(listing: Listing, config: AccountAgeConfig) -> SignalResult | None:
    days = listing.seller.account_age_days
    if days is None:
        return None
    age = _plural(days, "día", "días")
    return SignalResult(
        signal="cuenta_nueva",
        kind="risk",
        weight=config.weight,
        intensity=math.exp(-days / config.decay_days),
        confidence=1.0,
        message=f"La cuenta se creó hace {age}",
        evidence=age,
    )


def history_signal(listing: Listing, config: HistoryConfig) -> SignalResult | None:
    ratings = listing.seller.ratings_count
    sales = listing.seller.sales_count
    if ratings is None and sales is None:
        return None

    activity = (ratings or 0) + (sales or 0)
    parts = []
    if ratings is not None:
        parts.append(_plural(ratings, "valoración", "valoraciones"))
    if sales is not None:
        parts.append(_plural(sales, "venta", "ventas"))

    return SignalResult(
        signal="sin_historial",
        kind="risk",
        weight=config.weight,
        intensity=1 / (1 + activity / config.half_count),
        confidence=1.0,
        message="El vendedor apenas tiene valoraciones",
        evidence=", ".join(parts),
    )


def _ratings_evidence(count: int, avg: float) -> str:
    avg_text = f"{avg:.1f}".replace(".", ",")
    return f"{_plural(count, 'valoración', 'valoraciones')}, media {avg_text}"


def bad_ratings_signal(listing: Listing, config: BadRatingsConfig) -> SignalResult | None:
    count = listing.seller.ratings_count
    avg = listing.seller.ratings_avg
    if not count or avg is None:
        return None

    volume = min(1.0, count / config.full_count)
    badness = clamp((config.avg_ok - avg) / (config.avg_ok - config.avg_bad))
    return SignalResult(
        signal="malas_valoraciones",
        kind="risk",
        weight=config.weight,
        intensity=volume * badness,
        confidence=1.0,
        message="El vendedor tiene malas valoraciones",
        evidence=_ratings_evidence(count, avg),
    )


def seller_reputation_mitigator(
    listing: Listing, config: SellerReputationConfig
) -> SignalResult | None:
    count = listing.seller.ratings_count
    avg = listing.seller.ratings_avg
    if count is None or avg is None:
        return None

    volume = min(1.0, count / config.full_count)
    quality = clamp((avg - config.avg_floor) / (config.avg_ceiling - config.avg_floor))

    return SignalResult(
        signal="vendedor_con_historial",
        kind="mitigator",
        weight=config.max_reduction,
        intensity=volume * quality,
        confidence=1.0,
        message="Vendedor con buen historial",
        evidence=_ratings_evidence(count, avg),
    )
