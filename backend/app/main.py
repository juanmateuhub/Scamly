from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.analyze import router as analyze_router
from app.config import settings

# Any Chrome extension ID (32 letters a-p). Only used when EXTENSION_ID is not configured.
ANY_EXTENSION = r"chrome-extension://[a-p]{32}"
LOCALHOST = r"http://(localhost|127\.0\.0\.1)(:\d+)?"


def cors_options(extension_id: str) -> dict[str, Any]:
    """CORS limited to the Scamly extension (or any extension in development) and localhost."""
    extension = f"chrome-extension://{extension_id}" if extension_id else ANY_EXTENSION
    return {
        "allow_origin_regex": rf"^({extension}|{LOCALHOST})$",
        "allow_methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"],
        # Chrome's Private Network Access: requests to localhost need an explicit opt-in.
        # It only applies to the origins allowed above.
        "allow_private_network": True,
    }


app = FastAPI(title="Scamly API", version=__version__)
app.add_middleware(CORSMiddleware, **cors_options(settings.extension_id))
app.include_router(analyze_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
