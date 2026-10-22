# AGENTS.md - $BROKERS (La Bolsa de Amigos)

## 1. Contexto y Visión del Proyecto
Estamos construyendo un MVP para una hackathon de 7 horas. "$BROKERS" es un mercado de valores especulativo en tiempo real para grupos de amigos universitarios con estética "Bloomberg Terminal / Robinhood Dark Mode".
- Los amigos cotizan en bolsa mediante un Ticker (`$SAMU`, `$MITO`, etc.).
- Un usuario puede pertenecer a varios grupos (piso, clase, etc.). Cada grupo tiene sus propios activos, retos y ranking.
- Los usuarios abren "Contratos Flash" sobre retos cotidianos de un amigo.
- El resto invierte monedas virtuales (`$BROK`) pulsando `CONFIO` (LONG 📈) o `NI_DE_BROMA` (SHORT 📉).

## 2. Reglas de Arquitectura Estrictas (PROHIBIDO SALTARSE)
- **Stack:** Backend en Python (`Flask`) sirviendo la API y los estáticos en el mismo puerto (`5000`). Frontend en `static/index.html` usando **Tailwind CSS (CDN)**, **Chart.js (CDN)** y **Vanilla JS**.
- **PROHIBIDO:** No usar React, Node, npm, Webpack, bases de datos SQL externas ni sistemas de login con contraseña.
- **Estado y Persistencia:** Diccionario global en memoria (`db`) con guardado/lectura automática en un archivo local `db.json` tras cada mutación para no perder datos al recargar Flask.
- **Rutas Relativas:** En el frontend, TODAS las peticiones `fetch` deben usar rutas relativas (`fetch('/api/...')`), nunca `localhost`, para que funcione directamente al exponerlo por túnel QR (`cloudflared`/`ngrok`).
- **IA SDK:** Usar exclusivamente `google-genai` (nuevo SDK oficial: `from google import genai`). Texto/CNMV: `gemini-3.5-flash-lite`. Visión/oráculo: `gemini-flash-lite-latest`. Los titulares usan el banco local por defecto para ahorrar cuota; `GEMINI_TITULARES=1` los activa con IA. El oráculo offline nunca inventa un veredicto y devuelve error 503.

## 3. Reglas de Negocio y Matemáticas (Teoría de Juegos)
1. **Separación de métricas y grupos:**
   - `saldo` (Monedas `$BROK`): Cartera independiente de cada usuario **dentro de cada grupo** (empieza en `1000.0` por grupo). Determina el ranking de ese grupo.
   - `cotizacion` (`0.0¢` a `100.0¢`): Probabilidad/fiabilidad actual de un amigo o contrato.
   - Cada grupo aísla sus activos, contratos, noticias, ranking y cartera. Un usuario puede estar en varios grupos y cada miembro tiene su ticker `$ALIAS` dentro de cada grupo.
   - Cada navegador mantiene un único broker (alias). No existe selector para encarnar a otro miembro del ranking.
2. **Motor de Precios LMSR (Hanson):**
   - Liquidez constante `B = 100.0`.
   - Todo mercado nace con liquidez semilla del Banco Central: `q_si = 50.0`, `q_no = 50.0`.
   - Precio instantáneo (`CONFIO`): `round((exp(q_si/B) / (exp(q_si/B) + exp(q_no/B))) * 100, 2)`.
3. **Polaridad Positiva ("Reto a lograr"):**
   - Todos los contratos son retos positivos ("Ser capaz de..."). El botón verde es `CONFIO` (`SI`) y el rojo es `NI_DE_BROMA` (`NO`).
   - El mercado nace pendiente: el protagonista debe aceptar el reto antes de que se permitan apuestas.
   - El protagonista no puede apostar en su propio mercado (ni `SI` ni `NO`).
4. **Liquidación y Incentivos Dinámicos del Protagonista:**
   - Bote de usuarios reales: `bote_si = q_si - 50`, `bote_no = q_no - 50`.
   - Si gana `SI` (Cumplió el reto):
     - **Prima del Protagonista (Short Squeeze):** Cobra `+0.30 * bote_no` (más un bono base de `+25` del Banco Central).
     - Los inversores del `SI` recuperan su inversión + se reparten proporcionalmente el `0.70 * bote_no` restante (más `25` de la semilla).
   - Si gana `NO` (Falló el reto):
     - **Multa al Protagonista:** Pierde `-0.20 * bote_si` de su saldo.
     - Los inversores del `NO` recuperan su inversión + se reparten proporcionalmente `bote_si` + la multa cobrada al protagonista.
5. **Seguridad y Antifraude:**
   - **CNMV IA:** Al crear un reto, Gemini evalúa si es físicamente posible y verificable en foto. Si es absurdo (ej. "ir a la Antártida hoy"), devuelve HTTP 400 con motivo cómico y resta `-10 $BROK` al creador. Si está formulado en negativo ("llegar tarde"), lo reescribe en positivo ("llegar puntual").
   - **Oráculo Visual + VAR (Impugnación):** Solo se admite una captura de cámara en directo (`getUserMedia`), con `captura_ts` reciente y `origen=camara`; prohibido el selector de galería. Gemini Vision recibe la hora del servidor, la hora de captura y la fecha del reto. Si gana `NO`, el mercado permite "Impugnar con Contra-Foto (VAR)" al protagonista; si se acepta, se revierte a `SI` y se embarga el doble al tramposo.

## 4. Contrato Estricto de API (Backend <-> Frontend)
- `GET /api/estado?usuario=<alias>&grupo=<id>` -> Devuelve `{ grupos, grupo_actual, amigos, mercados, noticias, ranking }` del grupo indicado.
- `POST /api/usuarios` -> Body: `{ usuario, nombre }` (registra el alias y le asigna 1.000 $BROK)
- `POST /api/grupos` -> Body: `{ usuario, nombre }` (crea el grupo y su ticker `$ALIAS`; devuelve `grupo` con `id` y `codigo`)
- `POST /api/grupos/unirse` -> Body: `{ usuario, codigo }` (añade al usuario y su ticker al grupo)
- `POST /api/amigos` -> Body: `{ ticker, nombre, grupo }`
- `POST /api/mercados` -> Body: `{ creador, ticker, pregunta, grupo }` (Pasa por filtro CNMV IA)
- `POST /api/mercados/<id>/aceptar` -> Body: `{ usuario }` (Solo el protagonista; abre el mercado)
- `POST /api/mercados/<id>/apostar` -> Body: `{ usuario, tipo: "SI"|"NO", cantidad: float }`
- `POST /api/mercados/<id>/resolver` -> `multipart/form-data` con `usuario`, `imagen` (captura de cámara), `captura_ts` (epoch ms), `origen="camara"` y `es_impugnacion` ("true"|"false").
- `POST /api/reset` -> Borra todos los grupos, cuentas, retos y noticias (estado vacío).

## 5. Diseño de `static/index.html` (Obligatorio)
- Toda creación o edición de `static/index.html` se hace con la skill global `design-taste-frontend` (cargarla antes de tocar el archivo).
- Si la skill choca con la sección 2 o con la estética Bloomberg Terminal dark, gana este AGENTS.md.
