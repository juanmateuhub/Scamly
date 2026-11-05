# Arquitectura

Scamly tiene dos piezas: una **extensión de Chrome** que solo lee y muestra, y un **backend
FastAPI** donde vive toda la lógica de riesgo. Así la lógica se prueba con tests y se cambia
sin publicar otra versión de la extensión.

## Flujo de un análisis

1. El usuario abre un anuncio y pulsa el icono. El popup (`extension/src/panel/`) inyecta
   `content.js` en esa pestaña con `chrome.scripting` (permiso `activeTab`).
2. El content script lee el anuncio:
   - **Wallapop** (`src/content/wallapop.ts`): `script#__NEXT_DATA__` → `item` (título,
     descripción, precio, categoría, estado, envío, fotos) e `itemSeller` (fecha de registro,
     nº de valoraciones, media, ventas).
   - **Vinted** (`src/content/vinted.ts`): JSON-LD `Product`, valoración de la página y estado.
   Si `__NEXT_DATA__` es de otra página (navegación sin recargar), pide recargar.
3. Hace **una búsqueda** del mismo producto (Wallapop: marca + modelo estructurados y misma
   categoría final; Vinted: página `/catalog`) y se queda con título y precio de hasta 40.
4. El popup envía todo a `POST http://localhost:8000/analyze`.
5. El backend valida con Pydantic (`app/models/listing.py`), calcula las señales, las combina y
   devuelve nota, nivel, motivos, `price_check` y fiabilidad.
6. El popup lo pinta con `textContent` (`src/panel/render.ts`).

## Backend

```
backend/app/
├── main.py              # FastAPI, CORS (extensión + localhost), /health
├── config.py            # ajustes desde .env (proveedor LLM, caché)
├── api/analyze.py       # POST /analyze
├── models/listing.py    # contrato de entrada y salida
├── rules/               # scoring.yaml (pesos), phrases_es.yaml (frases), loader.py
├── signals/             # una función pura por señal
│   ├── price.py         # anuncios similares → tabla → categoría; estado del producto
│   ├── seller.py        # cuenta nueva, sin historial, malas valoraciones, buen historial
│   ├── description.py   # descripción pobre
│   ├── shipping.py      # envío protegido (atenuante)
│   ├── text_rules.py    # frases en español (plan B)
│   └── text_llm.py      # LLM: prompt, verificación de citas, combinación con reglas
├── scoring/engine.py    # noisy-OR, atenuantes, semáforo, motivos, fiabilidad
├── scoring/analyzer.py  # ejecuta todas las señales sobre un anuncio
└── llm/                 # cliente compatible con OpenAI, caché SQLite, servicio
```

Datos: `data/reference_prices.yaml` (precios de respaldo, variantes, estados, desgaste) y
`data/eval/listings.jsonl` (dataset de evaluación).

## Señales y motor

Cada señal devuelve `intensity` (cuánto se cumple, 0–1), `confidence` (cuánto nos fiamos, 0–1)
y `weight` (puntos máximos). Su aportación es `p = weight · intensity · confidence`. Si falta
el dato, la señal no se aplica y aparece en `unavailable_signals`.

```
riesgo_bruto = 100 · (1 − Π (1 − p_i / 100))     # señales de riesgo, noisy-OR
riesgo       = riesgo_bruto · Π (1 − m_j)         # atenuantes
```

Semáforo: verde < 20, amarillo 20–34, rojo ≥ 35 (calibrado en el split `dev`). Las fórmulas de
cada señal y su justificación están en [`CLAUDE.md`](../CLAUDE.md).

## LLM

- Un único cliente para cualquier API compatible con OpenAI (Groq, OpenRouter, Ollama…),
  elegido en `.env`. Temperatura 0, modo JSON, timeout de 8 s.
- El LLM **solo clasifica** cuatro señales de texto; una detección cuenta solo si su cita
  aparece en el anuncio, y nunca puede bajar lo que detectaron las reglas.
- Caché SQLite de 24 h por hash del texto y de la versión del prompt. Si falla, se usan las
  reglas (`text_analysis: "basico"`).

## Calidad

- Backend: ruff, mypy estricto, pytest con cobertura ≥ 80 %.
- Extensión: TypeScript strict, Vitest con HTML y JSON de ejemplo en `tests/fixtures`.
- CI en GitHub Actions en cada push a `main` y en cada pull request.
- `scripts/evaluate.py`: precisión, recall, F1 y matriz de confusión, solo reglas frente a
  reglas + LLM.
