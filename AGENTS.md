# AGENTS.md - $BROKERS (La Bolsa de Amigos)

## 1. Contexto y Visión del Proyecto
Estamos construyendo un MVP para una hackathon de 7 horas. "$BROKERS" es un mercado de valores especulativo en tiempo real para grupos de amigos universitarios con estética "Bloomberg Terminal / Robinhood Dark Mode".
- Los amigos cotizan en bolsa mediante un Ticker (`$SAMU`, `$MITO`, etc.).
- Los usuarios abren "Contratos Flash" sobre retos cotidianos de un amigo.
- El resto invierte monedas virtuales (`$BROK`) pulsando `CONFIO` (LONG 📈) o `NI_DE_BROMA` (SHORT 📉).

## 2. Reglas de Arquitectura Estrictas (PROHIBIDO SALTARSE)
- **Stack:** Backend en Python (`Flask`) sirviendo la API y los estáticos en el mismo puerto (`5000`). Frontend en `static/index.html` usando **Tailwind CSS (CDN)**, **Chart.js (CDN)** y **Vanilla JS**.
- **PROHIBIDO:** No usar React, Node, npm, Webpack, bases de datos SQL externas ni sistemas de login con contraseña.
- **Estado y Persistencia:** Diccionario global en memoria (`db`) con guardado/lectura automática en un archivo local `db.json` tras cada mutación para no perder datos al recargar Flask.
- **Rutas Relativas:** En el frontend, TODAS las peticiones `fetch` deben usar rutas relativas (`fetch('/api/...')`), nunca `localhost`, para que funcione directamente al exponerlo por túnel QR (`cloudflared`/`ngrok`).
- **IA SDK:** Usar exclusivamente `google-genai` (nuevo SDK oficial: `from google import genai`) con el modelo `gemini-2.5-flash`. Tener siempre un *fallback* (try/except) por si falla la API o no hay internet, devolviendo respuestas sarcásticas predefinidas para que la demo nunca se rompa.

## 3. Reglas de Negocio y Matemáticas (Teoría de Juegos)
1. **Separación de métricas:**
   - `saldo` (Monedas `$BROK`): Cartera del usuario (todos empiezan con `1000.0`). Determina el Ranking de Ricos.
   - `cotizacion` (`0.0¢` a `100.0¢`): Probabilidad/fiabilidad actual de un amigo o contrato.
2. **Motor de Precios LMSR (Hanson):**
   - Liquidez constante `B = 100.0`.
   - Todo mercado nace con liquidez semilla del Banco Central: `q_si = 50.0`, `q_no = 50.0`.
   - Precio instantáneo (`CONFIO`): `round((exp(q_si/B) / (exp(q_si/B) + exp(q_no/B))) * 100, 2)`.
3. **Polaridad Positiva ("Reto a lograr"):**
   - Todos los contratos son retos positivos ("Ser capaz de..."). El botón verde es `CONFIO` (`SI`) y el rojo es `NI_DE_BROMA` (`NO`).
   - El protagonista del reto NO puede apostar `NO` en su propio mercado.
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
   - **Oráculo Visual + VAR (Impugnación):** Al subir foto de resolución, Gemini Vision decide si se cumplió (`SI`/`NO`). Si gana `NO`, el mercado permite pulsar "Impugnar con Contra-Foto (VAR)": si el protagonista sube un selfie demostrando presencia, se revierte a `SI` y se embarga el doble de lo apostado al tramposo que subió la primera foto falsa.

## 4. Contrato Estricto de API (Backend <-> Frontend)
- `GET /api/estado` -> Devuelve `{ amigos: [...], mercados: [...], noticias: [...], ranking: [...] }`
- `POST /api/amigos` -> Body: `{ ticker, nombre }`
- `POST /api/mercados` -> Body: `{ creador, ticker, pregunta }` (Pasa por filtro CNMV IA)
- `POST /api/mercados/<id>/apostar` -> Body: `{ usuario, tipo: "SI"|"NO", cantidad: float }`
- `POST /api/mercados/<id>/resolver` -> `multipart/form-data` con `usuario`, `imagen` (File) y `es_impugnacion` ("true"|"false").
- `POST /api/reset` -> Reinicia el estado a los valores de demostración iniciales.
