# Ética, privacidad y aspectos legales

Scamly ayuda a un comprador a detectar señales de riesgo en un anuncio concreto. Estas son las
reglas que sigue y las decisiones que se han tomado a sabiendas. Esto no es asesoramiento
legal: si el proyecto se publicara en la Chrome Web Store, habría que revisarlo.

## Qué datos se tratan

- **Solo el anuncio que el usuario abre**, y solo cuando pulsa el icono: título, descripción,
  precio, categoría, estado, envío, número de fotos y los datos públicos del vendedor que
  muestra la página (antigüedad, nº de valoraciones, media, ventas). Nunca el nombre del
  vendedor, ni fotos, ni cookies o datos del usuario.
- **Anuncios similares**: solo título y precio, sin vendedores ni identificadores.
- **El backend no guarda los anuncios.** La única persistencia es una caché SQLite de 24 h con
  el hash del texto y las citas que el LLM encontró en él.
- **Antes de enviar el texto a un LLM** se sustituyen teléfonos y emails por `[TELEFONO]` y
  `[EMAIL]`. Los planes gratuitos de algunos proveedores pueden usar las peticiones para
  entrenar o revisarlas personas; por eso no se les envían datos personales.
- **Secretos** (claves de API) solo en `.env`, que está en `.gitignore`.
- **Dataset de evaluación**: anuncios sintéticos con teléfonos y emails ficticios
  (`600 000 000`, `@example.com`); un test lo comprueba. Además, un split `real` con 66 anuncios
  reales anonimizados (ver abajo).

## Sin acusaciones

El panel habla de **"señales de riesgo"**, nunca de "este vendedor es un estafador". Un falso
positivo puede perjudicar a un vendedor honrado, así que:

- Cada motivo muestra su evidencia, para que el usuario juzgue.
- Los atenuantes (buen historial, envío protegido) se muestran igual que los riesgos.
- El panel indica cuándo faltan datos y la fiabilidad del análisis.
- Un precio bajo pesa menos si el producto tiene desgaste o defectos declarados.

## Decisión consciente: búsqueda de anuncios similares

Para comparar el precio con el mismo producto, la extensión hace **una búsqueda por análisis**:

- En **Wallapop** usa la API interna que usa la propia web
  (`api.wallapop.com/api/v3/search/section`), que no está documentada.
- En **Vinted** descarga la página de búsqueda normal (`/catalog`).

Esto **va contra las condiciones de uso** de ambas webs, que prohíben el acceso automatizado, y
puede dejar de funcionar o bloquearse sin aviso. Es una decisión del autor para un proyecto
personal, con estos límites:

- Una sola búsqueda, iniciada por el usuario con un clic, desde su propia pestaña.
- Nada de rastreo en bucle, de recorrer listados ni de guardar resultados.
- Si la búsqueda falla, el análisis sigue con una tabla de precios de referencia.

Si el proyecto dejara de ser personal, esta función habría que retirarla o sustituirla por un
acuerdo o una fuente autorizada.

## Decisión consciente: dataset de anuncios reales

Para medir el detector fuera de los datos inventados, el 2026-11-26 se recogieron **66 anuncios
reales** (una búsqueda por producto en cada web, 6 anuncios de cada una) con un recolector de
desarrollo (`extension/dev/collector.ts`) que no forma parte de la extensión. Carga los anuncios
de uno en uno y con pausa, con el mismo extractor que usa la extensión. Como la búsqueda de
similares, **va contra las condiciones de uso** de Wallapop y Vinted.

Antes de guardarlos, `scripts/import_real.py` los anonimiza: el ID del anuncio se sustituye por
un hash, los teléfonos y emails por `[TELEFONO]` y `[EMAIL]`, se elimina la URL y del vendedor
solo quedan recuentos y medias (valoraciones, ventas, antigüedad). Se conservan el título, la
descripción, el precio y los títulos y precios de anuncios similares, porque son lo que el
detector analiza; buscando el texto podría encontrarse el anuncio original. Las etiquetas
(sospechoso o legítimo) son una propuesta sin verificar: no afirman que ningún vendedor concreto
sea un estafador. Si alguien reconoce un anuncio suyo y quiere que se retire, basta con abrir un
issue.

## Permisos mínimos

`manifest.json` pide solo `activeTab` y `scripting`, sin dominios ni `<all_urls>`. La extensión
no puede leer ninguna página hasta que el usuario pulsa el icono en ella. El texto del anuncio
se pinta con `textContent` para evitar XSS. El backend solo acepta peticiones (CORS) de la
extensión y de `localhost`.

## RGPD

En la v1 no hay cuentas ni se guardan datos personales. Si en el futuro hubiera cuentas, reportes
de usuarios o una lista negra colaborativa (v3), haría falta una política de privacidad, una base
legal para el tratamiento y un procedimiento para corregir o borrar datos.
