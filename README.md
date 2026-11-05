# Scamly

[![CI](https://github.com/juanmateuhub/Scamly/actions/workflows/ci.yml/badge.svg)](https://github.com/juanmateuhub/Scamly/actions/workflows/ci.yml)

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

## Probar la extensión

1. Arranca el backend: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload`.
2. Compila la extensión: `cd extension && npm install && npm run build`.
3. En Chrome abre `chrome://extensions`, activa **Modo de desarrollador**, pulsa
   **Cargar descomprimida** y elige la carpeta `extension/dist`.
4. Abre un anuncio de Wallapop o Vinted y pulsa el icono de Scamly.

Opcional: copia el ID que muestra Chrome en `EXTENSION_ID` del `.env` para que el backend
solo acepte peticiones de tu extensión.

## Licencia

MIT
