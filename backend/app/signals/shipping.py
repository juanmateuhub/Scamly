from app.models.listing import Listing
from app.rules.loader import ShippingConfig
from app.signals.base import SignalResult


def shipping_mitigator(listing: Listing, config: ShippingConfig) -> SignalResult:
    return SignalResult(
        signal="envio_protegido",
        kind="mitigator",
        weight=config.max_reduction,
        intensity=1.0 if listing.shipping_available else 0.0,
        confidence=1.0,
        message="Ofrece envío con protección de la app",
        evidence="Envío disponible" if listing.shipping_available else "Sin envío",
    )
