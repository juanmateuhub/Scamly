from fastapi import FastAPI

from app import __version__

app = FastAPI(title="Scamly API", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
