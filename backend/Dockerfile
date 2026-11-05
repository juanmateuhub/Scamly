# Scamly backend. Build from the repo root (it needs data/ as well):
#   docker compose build    or    docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The app finds its files relative to the repo layout (app/config.py -> ../..), so keep it:
# /srv/backend (code) and /srv/data (reference prices).
WORKDIR /srv/backend

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY data/reference_prices.yaml /srv/data/reference_prices.yaml

# Editable install: runtime dependencies only, and app/ stays at /srv/backend/app.
RUN pip install -e . \
    && useradd --create-home --uid 10001 scamly \
    && mkdir -p /srv/backend/.cache \
    && chown -R scamly:scamly /srv/backend/.cache

USER scamly

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
