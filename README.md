# $BROKERS · La bolsa de amigos

MVP de mercado especulativo en tiempo real para grupos de amigos. Cada persona cotiza como un ticker (`$SAMU`, `$LUCIA`, ...), el grupo crea retos positivos y el resto apuesta monedas virtuales `$BROK` a que se cumplen (`CONFIO`) o no (`NI_DE_BROMA`).

La interfaz es una webapp mobile-first con estética Bloomberg Terminal / Robinhood dark, servida por Flask. No hay React, Node, npm ni base de datos externa: Flask sirve la API y `static/index.html`, y el estado se guarda en `db.json`.

---

## Funcionalidades

- Varios grupos por usuario: piso, clase, etc.
- Activos, retos, noticias, ranking y **cartera independiente por grupo**.
- Registro sin contraseña: alias + ticker automático `$ALIAS` en cada grupo.
- Retos formulados en positivo (`Ser capaz de...`).
- Motor de precios LMSR de Hanson.
- Apuestas `SI` / `NO`, aceptación del protagonista y liquidación.
- Filtro CNMV con IA y fallback local.
- Oráculo visual con **cámara en directo** (sin galería), sello temporal y evaluación con hora del servidor.
- VAR / impugnación con contra-foto para el protagonista.
- Invitaciones por QR o código de grupo.
- PWA instalable con manifest e iconos.

---

## Stack

- Python 3 + Flask
- HTML + Tailwind CSS (CDN) + Chart.js (CDN) + Vanilla JS
- `google-genai` para CNMV y oráculo visual
- Persistencia JSON atómica en `db.json`

---

## Estructura

```text
BROKERS/
├── app.py                  # API Flask, motor LMSR, grupos y liquidación
├── ai_service.py           # CNMV, titulares y oráculo visual
├── static/
│   ├── index.html          # UI completa (HTML + Tailwind + JS inline)
│   ├── manifest.webmanifest
│   ├── icons/              # Iconos PWA y logo
│   └── uploads/            # Capturas de evidencias (ignoradas por Git)
├── tests/
│   └── test_smoke.py       # Tests de API, grupos, saldos y cámara
├── scripts/
│   └── local_https.sh      # HTTPS local para usar la cámara desde el móvil
├── db.example.json         # Estado inicial vacío
├── .env.example            # Variables de entorno de ejemplo
├── pytest.ini
├── requirements.txt
└── requirements-dev.txt
```

`db.json`, `.env`, las capturas y los certificados locales están fuera de Git.

---

## Arranque rápido

```bash
git clone git@github.com:samuelminambres/BROKERS.git
cd BROKERS

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env y añade GEMINI_API_KEY
python app.py
```

Abre **http://localhost:5000**.

Si no existe `db.json`, la app crea un estado vacío. Para partir del ejemplo:

```bash
cp db.example.json db.json
```

### Variables de entorno

| Variable | Uso |
|---|---|
| `GEMINI_API_KEY` | Clave de Google AI Studio. Obligatoria para IA real. |
| `GEMINI_MODEL` | Modelo de texto/CNMV. Por defecto `gemini-3.5-flash-lite`. |
| `GEMINI_VISION_MODEL` | Modelo del oráculo. Por defecto `gemini-3.5-flash`. |
| `GEMINI_TITULARES` | `1` activa titulares con IA; por defecto usa el banco local. |

La cuota gratuita de Gemini es por proyecto/API key. Si aparece `429`, crea una key nueva en un proyecto nuevo. El oráculo devuelve `503` si no hay cuota, para no aprobar fotos a ciegas.

---

## Cámara en el móvil: HTTPS local

`getUserMedia` exige HTTPS (o `localhost`). Para usar la cámara desde un móvil en la misma Wi-Fi:

```bash
# Terminal 1: app HTTP para servir el CA
python app.py

# Terminal 2: HTTPS local
./scripts/local_https.sh
```

El script genera un CA local, imprime la URL y deja el CA en:

```text
http://TU_IP_LOCAL:5000/static/rootCA.crt
```

Instala ese CA en el móvil como certificado de confianza y abre:

```text
https://TU_IP_LOCAL:5443
```

- iPhone: Ajustes > General > VPN y gestión de dispositivos > instalar; después Ajustes > General > Información > Ajustes de confianza de certificados > activar `BROKERS Local CA`.
- Android: Ajustes > Seguridad > Cifrado y credenciales > Instalar un certificado > CA.

Los certificados quedan en `.local-tls/` y no se suben al repositorio. Si cambia la IP, borra `.local-tls/` y vuelve a ejecutar el script.

> El túnel gratuito de `localhost.run` sirve para una prueba rápida, pero no es estable para una presentación. Para acceso remoto usa un túnel de pago/ngrok con token o despliega la app en un host HTTPS.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Los tests usan una base temporal y IA offline, así que no tocan `db.json`. Cubren:

- Matemáticas LMSR.
- Fallback de CNMV.
- Varios grupos con tickers aislados.
- Saldo independiente por grupo.
- Aceptación del protagonista y bloqueo de auto-apuestas.
- Captura de cámara reciente y resolución.

Resultado esperado: **4 passed**.

---

## API

Base: `/api`.

| Método | Ruta | Body / params |
|---|---|---|
| `GET` | `/estado?usuario=<alias>&grupo=<id>` | Devuelve grupos, grupo actual, amigos, mercados, noticias y ranking. |
| `POST` | `/usuarios` | `{ "usuario": "samu", "nombre": "Samu" }` |
| `POST` | `/grupos` | `{ "usuario": "samu", "nombre": "Piso" }` |
| `POST` | `/grupos/unirse` | `{ "usuario": "samu", "codigo": "4A9C2F" }` |
| `POST` | `/amigos` | `{ "ticker": "$LUCIA", "nombre": "Lucía", "grupo": "grp_..." }` |
| `POST` | `/mercados` | `{ "creador": "samu", "ticker": "$LUCIA", "pregunta": "Ser capaz de...", "grupo": "grp_..." }` |
| `POST` | `/mercados/<id>/aceptar` | `{ "usuario": "lucia" }` |
| `POST` | `/mercados/<id>/apostar` | `{ "usuario": "samu", "tipo": "SI"\|"NO", "cantidad": 25 }` |
| `POST` | `/mercados/<id>/resolver` | `multipart/form-data`: `usuario`, `imagen`, `captura_ts` (epoch ms), `origen="camara"`, `es_impugnacion` |
| `POST` | `/reset` | Borra grupos, cuentas, retos y noticias. |

### Reglas de grupo y saldo

- Un usuario puede pertenecer a varios grupos.
- Al crear/unirse a un grupo se crea su ticker `$ALIAS` en ese grupo.
- La cartera es independiente por grupo: empezar en un grupo nuevo da `1.000 $BROK` en ese grupo.
- El ranking y las apuestas solo usan miembros del grupo.
- Un miembro del grupo no puede apostar en un reto del que es protagonista.

### Oráculo visual

- La cámara se captura con `getUserMedia`; no hay selector de galería.
- El navegador dibuja un sello `EN VIVO · fecha/hora` en la captura.
- El backend exige `origen=camara` y una captura de menos de 2 minutos.
- Gemini recibe la hora del servidor, la hora de captura y la fecha de creación del reto.
- Si la prueba es ambigua, antigua, una pantalla, un meme o no demuestra el reto, el veredicto es `NO`.
- Sin cuota o sin conexión, el oráculo responde `503`; no inventa un `SI`.

---

## Modelo de datos

`db.json` contiene:

```json
{
  "grupos": [
    {
      "id": "grp_...",
      "nombre": "Piso",
      "codigo": "4A9C2F",
      "creador": "samu",
      "miembros": ["samu"],
      "saldos": { "samu": 1000.0 },
      "creado": "2026-10-22"
    }
  ],
  "amigos": [
    {
      "ticker": "$SAMU",
      "nombre": "Samu",
      "descripcion": "...",
      "cotizacion": 50.0,
      "grupo": "grp_..."
    }
  ],
  "usuarios": {
    "samu": { "nombre": "Samu" }
  },
  "mercados": [],
  "noticias": []
}
```

El archivo se escribe de forma atómica después de cada mutación. No se versiona el estado real de la demo.

---

## Notas y límites

- No hay login con contraseña: el alias identifica al broker en el navegador. No se permite cambiar de broker desde la interfaz.
- La app no maneja dinero real.
- La IA depende de internet y de la cuota del proyecto de Google AI Studio.
- El túnel gratuito no es una buena opción para la demo final.
- `static/uploads/` puede crecer con capturas; está ignorado por Git.

---

## Convenciones

Las reglas de arquitectura, negocio y API están en `AGENTS.md`. Cualquier cambio estructural debe respetar esas reglas o actualizarlas de forma explícita.
