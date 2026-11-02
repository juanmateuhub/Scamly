# Scamly

Extensión de Chrome que, al abrir un anuncio de Wallapop o Vinted España, muestra una
puntuación de riesgo de estafa de 0 a 100 y explica en español los motivos.

> En desarrollo (v0.1.0). Instalación, arquitectura y métricas se completarán al cerrar la v1.

## Estructura

- `backend/`: API FastAPI que calcula la nota (`GET /health`, `POST /analyze`).
- `extension/`: extensión Chrome Manifest V3 en TypeScript.
- `data/`: precios de referencia y dataset de evaluación.
- `docs/`: arquitectura y ética.

## Desarrollo rápido

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev]"
pytest -q
```

```bash
cd extension
npm install
npm test
```

## Licencia

MIT
