from app.models.listing import Listing
from app.rules.loader import PriceConfig, ReferencePrices
from app.signals.base import SignalResult, clamp, contains_phrase, format_eur, normalize

SIGNAL = "precio_anomalo"


def find_reference(
    listing: Listing, reference: ReferencePrices, config: PriceConfig
) -> tuple[float, float, str] | None:
    """Return (reference price, confidence, label) for the listing, or None if unknown."""
    title = normalize(listing.title)
    full_text = normalize(f"{listing.title}\n{listing.description}")
    if any(contains_phrase(title, word) for word in reference.skip_words) or any(
        contains_phrase(full_text, phrase) for phrase in reference.defect_phrases
    ):
        return None

    for product in reference.products:
        if any(contains_phrase(title, alias) for alias in product.aliases) and not any(
            contains_phrase(title, word) for word in product.exclude
        ):
            return product.price_eur, config.confidence_product, product.name

    if listing.category is not None:
        category = normalize(listing.category)
        for name, price in reference.categories.items():
            if normalize(name) == category:
                return price, config.confidence_category, f"categoría {category}"

    return None


def price_signal(
    listing: Listing, reference: ReferencePrices, config: PriceConfig
) -> SignalResult | None:
    match = find_reference(listing, reference, config)
    if match is None:
        return None
    reference_price, confidence, label = match

    ratio = listing.price_eur / reference_price
    intensity = clamp(
        (config.ratio_no_risk - ratio) / (config.ratio_no_risk - config.ratio_max_risk)
    )
    below_pct = round((1 - ratio) * 100)
    message = (
        f"Precio un {below_pct} % por debajo de lo habitual"
        if below_pct > 0
        else "Precio en línea con lo habitual"
    )
    evidence = f"{format_eur(listing.price_eur)} frente a {format_eur(reference_price)} ({label})"

    return SignalResult(
        signal=SIGNAL,
        kind="risk",
        weight=config.weight,
        intensity=intensity,
        confidence=confidence,
        message=message,
        evidence=evidence,
    )
