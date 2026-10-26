# $BROKERS · La bolsa de amigos

MVP de mercado especulativo en tiempo real para grupos de amigos. Cada persona cotiza como un ticker (`$ANA`, `$LUIS`, ...), el grupo crea retos positivos y el resto apuesta monedas virtuales `$BROK` a que se cumplen (`CONFIO`) o no (`NI_DE_BROMA`).

La interfaz es una webapp mobile-first con estética Bloomberg Terminal / Robinhood dark, servida por Flask. No hay React, Node, npm ni base de datos externa: Flask sirve la API y `static/index.html`, y el estado se guarda en `db.json`.

---

## Resumen

`$BROKERS` convierte cada grupo de amigos en una bolsa privada: cada miembro cotiza, se lanzan retos y se apuesta `$BROK` con `CONFIO` o `NI DE BROMA` mientras un motor LMSR mueve el precio. La IA valida retos y resuelve capturas con VAR. El MVP es virtual; la Fase 2 con dinero real, KYC, licencia y límites es una hoja de ruta.

---

## Qué hace

1. Un usuario crea o se une a varios grupos mediante un código.
2. Cada grupo tiene sus propios activos, retos, noticias, ranking y cartera.
3. Al entrar en un grupo, el alias del usuario se convierte en el ticker `$ALIAS`.
4. El grupo crea retos positivos (`Ser capaz de...`).
5. El protagonista acepta el reto; hasta entonces nadie puede apostar.
6. Los miembros apuestan `CONFIO` o `NI_DE_BROMA`.
7. El protagonista sube una captura de cámara en directo cuando lo cumple.
8. El oráculo visual evalúa la prueba y la hora; el VAR permite impugnar un `NO`.

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

## Tecnologías

| Capa | Tecnología | Uso |
|---|---|---|
| Backend | Python 3 + Flask | API, rutas, liquidación y servidor de estáticos. |
| Frontend | HTML + Tailwind CSS (CDN) | Interfaz mobile-first, sin build step. |
| Frontend | Vanilla JS | Estado, navegación, cámara, gráficos y fetch relativo. |
| Gráficos | Chart.js (CDN) | Evolución de precios del contrato. |
| IA | `google-genai` | Validación CNMV y oráculo visual multimodal. |
| Precios | LMSR de Hanson | Probabilidad y precio del contrato. |
| Persistencia | JSON atómico (`db.json`) | Estado local sin base de datos externa. |
| PWA | Web App Manifest | Instalación y iconos. |
| Cámara | `getUserMedia` + Canvas | Captura en directo, sin galería. |
| Tests | pytest | API, grupos, saldos, cámara y fallback IA. |

---

## Estructura

```text
BROKERS/
├── backend/
│   ├── __init__.py
│   ├── app.py              # API Flask, motor LMSR, grupos y liquidación
│   └── ai_service.py       # CNMV, titulares y oráculo visual
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
git clone <URL_DEL_REPOSITORIO>
cd BROKERS

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env y añade GEMINI_API_KEY
python -m backend.app
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
python -m backend.app

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
| `POST` | `/usuarios` | `{ "usuario": "ana", "nombre": "Ana" }` |
| `POST` | `/grupos` | `{ "usuario": "ana", "nombre": "Piso" }` |
| `POST` | `/grupos/unirse` | `{ "usuario": "ana", "codigo": "4A9C2F" }` |
| `POST` | `/amigos` | `{ "ticker": "$LUIS", "nombre": "Luis", "grupo": "grp_..." }` |
| `POST` | `/mercados` | `{ "creador": "ana", "ticker": "$LUIS", "pregunta": "Ser capaz de...", "grupo": "grp_..." }` |
| `POST` | `/mercados/<id>/aceptar` | `{ "usuario": "luis" }` |
| `POST` | `/mercados/<id>/apostar` | `{ "usuario": "ana", "tipo": "SI"\|"NO", "cantidad": 25 }` |
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
      "creador": "ana",
      "miembros": ["ana"],
      "saldos": { "ana": 1000.0 },
      "creado": "2026-10-22"
    }
  ],
  "amigos": [
    {
      "ticker": "$LUIS",
      "nombre": "Luis",
      "descripcion": "...",
      "cotizacion": 50.0,
      "grupo": "grp_..."
    }
  ],
  "usuarios": {
    "ana": { "nombre": "Ana" }
  },
  "mercados": [],
  "noticias": []
}
```

El archivo se escribe de forma atómica después de cada mutación. No se versiona el estado real.

---

## Decisiones de diseño

- **Es un MVP virtual:** no hay dinero real, depósitos ni retiradas. La Fase 2 con dinero real, KYC, licencia y límites es una hoja de ruta, no una funcionalidad implementada.
- **Cada grupo es una economía independiente:** activos, retos, noticias, ranking y cartera por grupo. El mismo usuario puede estar en “Piso” o “Clase” sin mezclar saldos.
- **El motor de precios es LMSR de Hanson:** el precio no lo fija una persona; se mueve con la liquidez de las apuestas.
- **La IA tiene dos papeles:** la CNMV valida que el reto sea posible/verificable y el oráculo visual evalúa la prueba.
- **La prueba debe ser en directo:** cámara obligatoria, sin galería, sello temporal y ventana de captura de 2 minutos.
- **El VAR es una segunda capa:** si el oráculo da `NO`, el protagonista puede impugnar con una contra-foto.
- **La app funciona sin login:** el alias identifica al broker; no se puede cambiar de broker desde la UI. Es una decisión de MVP, no autenticación fuerte.
- **La app se ejecuta en local o por HTTPS local:** no requiere build ni servicios externos salvo la API de Gemini.
- **La IA puede fallar por cuota:** el backend usa fallback en CNMV y devuelve `503` en el oráculo si no puede verificar; nunca aprueba una foto a ciegas.

---

## Roadmap

### Fase 1 — MVP (actual)

- Grupos múltiples, tickers automáticos y carteras por grupo.
- Retos, LMSR, apuestas, aceptación, oráculo visual y VAR.
- PWA mobile-first y persistencia JSON.
- IA con fallback y ejecución local/HTTPS.

### Fase 2 — Modo Adultos 18+

- Dinero real con proveedor regulado.
- KYC/AML, verificación de edad y geolocalización.
- Licencia, límites de gasto, autoexclusión y juego responsable.
- Contabilidad auditable, custodia de fondos y resolución de disputas.
- Moderación de retos y evidencias, consentimiento de imagen y privacidad.

> El Modo Adultos 18+ no está implementado en este repositorio.

---

## Notas y límites

- No hay login con contraseña: el alias identifica al broker en el navegador. No se permite cambiar de broker desde la interfaz.
- La app no maneja dinero real.
- La IA depende de internet y de la cuota del proyecto de Google AI Studio.
- `static/uploads/` puede crecer con capturas; está ignorado por Git.

---

## Convenciones

Las reglas de arquitectura, negocio y API están en `AGENTS.md`. Cualquier cambio estructural debe respetar esas reglas o actualizarlas de forma explícita.
