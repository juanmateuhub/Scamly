from fastapi import FastAPI

from app import __version__
from app.api.analyze import router as analyze_router

app = FastAPI(title="Scamly API", version=__version__)
app.include_router(analyze_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
