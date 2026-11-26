import re

from app.models.listing import Listing
from app.rules.loader import ModelMismatchConfig, ReferencePrices, ReferenceProduct
from app.signals.base import SignalResult, contains_phrase, normalize

SIGNAL = "modelo_distinto"
_CLAUSE_BREAK = re.compile(r"[.,;:!?¡¿\n]")


def _product_in(text: str, reference: ReferencePrices) -> ReferenceProduct | None:
    """First (most specific) table product named in already normalized text."""
    for product in reference.products:
        if any(contains_phrase(text, alias) for alias in product.aliases) and not any(
            contains_phrase(text, word) for word in product.exclude
        ):
            return product
    return None


def model_mismatch_signal(
    listing: Listing, reference: ReferencePrices, config: ModelMismatchConfig
) -> SignalResult | None:
    """The description promises a higher model than the title ("PS5 Slim" / "PS5 Pro").

    Only a model listed BEFORE the title's in the table counts (more specific or newer): a
    description that is just less specific ("Nintendo Switch" for a Switch 2) is not a
    contradiction. Clauses that explain the mention ("me compré el 16 Pro") are skipped.
    None when the title names no table product.
    """
    title_product = _product_in(normalize(listing.title), reference)
    if title_product is None:
        return None
    rank = reference.products.index(title_product)

    found = None
    for clause in _CLAUSE_BREAK.split(normalize(listing.description)):
        if any(re.search(pattern, clause) for pattern in config.exemptions):
            continue
        product = _product_in(clause, reference)
        if (
            product is not None
            and product.category == title_product.category
            and reference.products.index(product) < rank
        ):
            found = product
            break

    return SignalResult(
        signal=SIGNAL,
        kind="risk",
        weight=config.weight,
        intensity=1.0 if found else 0.0,
        confidence=config.confidence,
        message="El título y la descripción hablan de modelos distintos",
        evidence=f"título: {title_product.name} · descripción: {found.name}" if found else "",
    )
