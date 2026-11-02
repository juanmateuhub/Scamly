import statistics

from app.models.listing import Listing
from app.rules.loader import CONDITION_ORDER, ConditionLevel, PriceConfig, ReferencePrices
from app.signals.base import SignalResult, clamp, contains_phrase, format_eur, normalize

SIGNAL = "precio_anomalo"


def _explains_low_price(title: str, text: str, reference: ReferencePrices) -> bool:
    """Accessory title (not the product itself) or a declared defect; both normalized."""
    return any(contains_phrase(title, word) for word in reference.skip_words) or any(
        contains_phrase(text, phrase) for phrase in reference.defect_phrases
    )


def _variants(normalized_title: str, reference: ReferencePrices) -> frozenset[str]:
    return frozenset(w for w in reference.variant_words if contains_phrase(normalized_title, w))


CONDITION_LABELS: dict[ConditionLevel, str] = {
    "nuevo": "nuevo",
    "como_nuevo": "como nuevo",
    "buen_estado": "buen estado",
    "aceptable": "aceptable",
    "danado": "dañado",
}


def assess_condition(
    listing: Listing, reference: ReferencePrices
) -> tuple[ConditionLevel | None, str | None]:
    """(level, label) from the platform condition, worsened by wear named in the description."""
    levels = {normalize(text).strip(): level for text, level in reference.conditions.items()}
    level = levels.get(normalize(listing.condition or "").strip())
    label = CONDITION_LABELS[level] if level else None

    text = normalize(f"{listing.title}\n{listing.description}")
    wear = next((p for p in reference.wear_phrases if contains_phrase(text, p)), None)
    if wear is not None:
        worn: ConditionLevel = "aceptable"
        if level is None or CONDITION_ORDER.index(level) < CONDITION_ORDER.index(worn):
            level, label = worn, f"con desgaste («{wear}»)"
    return level, label


def comparable_reference(
    listing: Listing, reference: ReferencePrices, config: PriceConfig
) -> tuple[float, float, str] | None:
    """Median price of the same product listed now, or None if there are too few."""
    variants = _variants(normalize(listing.title), reference)
    prices = []
    for comparable in listing.comparables:
        title = normalize(comparable.title)
        if (
            comparable.price_eur > 0
            and not _explains_low_price(title, title, reference)
            and _variants(title, reference) == variants
        ):
            prices.append(comparable.price_eur)

    settings = config.comparables
    if len(prices) < settings.min_count:
        return None
    median = statistics.median(prices)
    q1, _, q3 = statistics.quantiles(prices, n=4)
    spread = clamp(1 - (q3 - q1) / median)
    confidence = settings.max_confidence * min(1.0, len(prices) / settings.full_count) * spread
    return median, confidence, f"mediana de {len(prices)} anuncios similares"


def find_reference(
    listing: Listing, reference: ReferencePrices, config: PriceConfig
) -> tuple[float, float, str] | None:
    """Return (reference price, confidence, label) for the listing, or None if unknown.

    Order: similar listings found now, then the reference table, then a category average.
    """
    title = normalize(listing.title)
    full_text = normalize(f"{listing.title}\n{listing.description}")
    if _explains_low_price(title, full_text, reference):
        return None

    live = comparable_reference(listing, reference, config)
    if live is not None:
        return live

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

    level, condition_label = assess_condition(listing, reference)
    condition_factor = config.condition_factors[level or "desconocido"]

    ratio = listing.price_eur / reference_price
    intensity = condition_factor * clamp(
        (config.ratio_no_risk - ratio) / (config.ratio_no_risk - config.ratio_max_risk)
    )
    below_pct = round((1 - ratio) * 100)
    message = (
        f"Precio un {below_pct} % por debajo de lo habitual"
        if below_pct > 0
        else "Precio en línea con lo habitual"
    )
    evidence = f"{format_eur(listing.price_eur)} frente a {format_eur(reference_price)} ({label})"
    if condition_label:
        evidence += f" · estado: {condition_label}"

    return SignalResult(
        signal=SIGNAL,
        kind="risk",
        weight=config.weight,
        intensity=intensity,
        confidence=confidence,
        message=message,
        evidence=evidence,
    )
