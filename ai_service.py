import os
import json
import random
import re
import time
from dotenv import load_dotenv

# Cargar automáticamente variables de entorno desde .env si existe
load_dotenv()

# Intento de importar el SDK oficial google-genai
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
VISION_MODEL_NAME = os.environ.get("GEMINI_VISION_MODEL", "gemini-3.5-flash")


def _get_genai_client():
    """Obtiene el cliente genai si la API key está disponible y el paquete instalado."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not GENAI_AVAILABLE or not api_key:
        return None
    try:
        return genai.Client(
            api_key=api_key,
            # Corta la llamada si la red se cuelga para que el fallback offline responda.
            http_options=types.HttpOptions(timeout=12000),
        )
    except Exception:
        return None


def _generar_contenido(client, contents, config=None, modelo=None, modelos=None):
    """Llama a Gemini con el modelo rápido elegido y un fallback opcional."""
    candidatos = modelos or [modelo or MODEL_NAME]
    ultimo_error = None
    for modelo_actual in candidatos:
        if not modelo_actual:
            continue
        try:
            return client.models.generate_content(
                model=modelo_actual,
                contents=contents,
                config=config
            )
        except Exception as e:
            ultimo_error = e
            print(f"[IA] Fallo {modelo_actual}: {str(e)[:300]}")
            continue
    raise ultimo_error or RuntimeError("Todos los modelos de Gemini fallaron.")


def _extraer_json(raw_text: str) -> dict:
    """Extrae y decodifica un objeto JSON de una respuesta de texto de forma segura."""
    texto = raw_text.strip()
    texto = re.sub(r"^```(?:json)?\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto)
    match = re.search(r"(\{.*\})", texto, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(texto)


def validar_reto_cnmv(creador: str, ticker: str, reto: str) -> dict:
    """
    Evalúa si un reto es físicamente posible y verificable en foto según las normas de la CNMV IA.
    Si es absurdo, lo rechaza y penaliza con -10 $BROK.
    Si está formulado en negativo, lo reescribe en positivo ("Ser capaz de...").
    """
    client = _get_genai_client()
    
    if client:
        try:
            prompt = f"""
Eres el inspector jefe de la CNMV de $BROKERS (mercado especulativo de amigos universitarios).
Analiza este reto propuesto por el usuario '{creador}' para el ticker '{ticker}':
Reto propuesto: "{reto}"

Reglas:
1. Absurdo / Físicamente imposible / Ilegal / Peligroso / Incomprobable en foto (ej: "ir a la Antártida hoy", "comprar Apple", "volar"):
   - valido: false
   - motivo: Explicación sarcástica y cómica de por qué la CNMV tumba el mercado.
   - penalizacion: 10.0
2. Si es posible y comprobable con una foto o selfie:
   - valido: true
   - Si está redactado en negativo ("no suspender", "no llegar tarde"), reescríbelo siempre en positivo: "Ser capaz de llegar puntual", "Ser capaz de aprobar".
   - Si no empieza con "Ser capaz de...", añade ese prefijo o dale formato de reto alcanzable.
   - pregunta_final: Texto del reto en positivo.
   - comentario: Comentario breve y cínico de auditor financiero.

Responde ÚNICAMENTE en formato JSON plano sin bloques markdown:
{{"valido": bool, "motivo": str, "penalizacion": float, "pregunta_final": str, "reescrito": bool, "comentario": str}}
"""
            config = types.GenerateContentConfig(response_mime_type="application/json") if GENAI_AVAILABLE else None
            response = _generar_contenido(client, contents=prompt, config=config)
            return _extraer_json(response.text)
        except Exception:
            pass

    # FALLBACK INTELIGENTE (Sin conexión / Sin API KEY)
    texto_lower = reto.lower().strip()
    import unicodedata
    texto_sin_tildes = ''.join(
        c for c in unicodedata.normalize('NFD', texto_lower)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Detección heurística de retos absurdos
    palabras_prohibidas = [
        "antartida", "marte", "luna", "elon musk", "millonario", "nuclear",
        "asesinar", "morir", "volar", "jupiter", "saturno", "pentagono", "atracar"
    ]
    if any(p in texto_sin_tildes for p in palabras_prohibidas):
        return {
            "valido": False,
            "motivo": f"CNMV IA rechaza el contrato: {reto}. Nivel de delirio financiero no admitido en este parqué.",
            "penalizacion": 10.0,
            "pregunta_final": "",
            "reescrito": False,
            "comentario": "Operación cancelada por riesgo sistémico de pitorreo."
        }
    
    # Corrección de polaridad negativa -> positiva
    reescrito = False
    pregunta_final = reto
    if "no llegar tarde" in texto_lower or "llegar tarde" in texto_lower:
        pregunta_final = "Ser capaz de llegar puntual y antes de que pase lista"
        reescrito = True
    elif "no suspender" in texto_lower or "suspender" in texto_lower:
        pregunta_final = "Ser capaz de aprobar el examen sin recurrir a la desesperación"
        reescrito = True
    elif not texto_lower.startswith("ser capaz de"):
        pregunta_final = f"Ser capaz de {reto[0].lower() + reto[1:] if len(reto) > 1 else reto}"
        reescrito = True

    return {
        "valido": True,
        "motivo": "",
        "penalizacion": 0.0,
        "pregunta_final": pregunta_final,
        "reescrito": reescrito,
        "comentario": "Aprobado por la CNMV (Modo Offline / Tasa de emisión 0 $BROK)."
    }


def generar_titular_wallstreet(evento_tipo: str, datos: dict) -> str:
    """
    Genera un titular satírico sensacionalista estilo Bloomberg / Wall Street Journal.
    Por defecto usa el banco local para no gastar cuota ni alargar la creación de retos.
    Actívalo con GEMINI_TITULARES=1.
    """
    usar_ia = os.environ.get("GEMINI_TITULARES", "0").strip() == "1"
    client = _get_genai_client() if usar_ia else None
    ticker = datos.get("ticker", "$AMIGO")
    usuario = datos.get("usuario", "Un trader")
    cantidad = datos.get("cantidad", 0)
    pregunta = datos.get("pregunta", "")

    if client:
        try:
            prompt = f"""
Escribe UN SOLO titular satírico urgente (máximo 14 palabras) estilo Bloomberg Terminal o Wall Street Journal para un mercado de apuestas entre amigos universitarios.
Evento: {evento_tipo}
Ticker implicado: {ticker}
Usuario: {usuario}
Cantidad: {cantidad} $BROK
Contexto reto: {pregunta}

Ejemplo: "PÁNICO EN EL PARQUÉ: $SAMU se desploma un 40% tras sonar su despertador por tercera vez."
Devuelve solo el titular entre mayúsculas y minúsculas sin comillas adicionales.
"""
            response = _generar_contenido(client, contents=prompt)
            return response.text.strip().replace('"', '')
        except Exception:
            pass

    # BANCO DE FALLBACKS REALISTAS Y SARCÁSTICOS
    if evento_tipo == "nuevo_mercado":
        titulares = [
            f"OFERTA PÚBLICA: {ticker} sale a bolsa con el contrato: '{pregunta[:45]}...'",
            f"ALERTA FINANCIERA: La CNMV aprueba emisión de alto riesgo para {ticker}.",
            f"NUEVO DERIVADO: Los analistas recomiendan cautela con la última promesa de {ticker}."
        ]
    elif evento_tipo == "apuesta":
        tipo = datos.get("tipo", "CONFIO")
        verbo = "apuesta fuerte al ALZA por" if tipo == "SI" else "pone en CORTO y duda de"
        titulares = [
            f"VOLUMEN RÉCORD: {usuario} {verbo} {ticker} con {cantidad:.0f} $BROK.",
            f"MOVIMIENTO BALLENA: Inyección de capital en {ticker}. La cotización se tambalea.",
            f"ESPECULACIÓN BRUTAL: El parqué reacciona a la entrada de {usuario} en {ticker}."
        ]
    elif evento_tipo == "resolucion":
        veredicto = datos.get("veredicto", "SI")
        if veredicto == "SI":
            titulares = [
                f"SHORT SQUEEZE HISTÓRICO: {ticker} cumple su promesa y aniquila a los bajistas.",
                f"DIVIDENDO EXTRAORDINARIO: Fuerte subida en {ticker} tras verificación del Oráculo IA.",
                f"RALLY ALCISTA: {ticker} silencia a los escépticos y deja sin blanca a media clase."
            ]
        else:
            titulares = [
                f"CRAC BURSÁTIL: {ticker} fracasa estrepitosamente; los cortos celebran con champán.",
                f"DEFAULT TOTAL: El Oráculo sentencia a {ticker}. Pérdidas millonarias en el parqué.",
                f"DESPLOME HISTÓRICO: {ticker} no cumple y la CNMV le embarga la dignidad."
            ]
    elif evento_tipo == "var":
        titulares = [
            f"TENSIÓN EN EL VAR: Impugnación aceptada en {ticker}. Multa doble al informante falso.",
            f"GIRO DRAMÁTICO EN LA CNMV: La contra-prueba de {ticker} desata el caos entre los inversores."
        ]
    else:
        titulares = [
            f"MERCADOS LATERALES: Rumores de resaca masiva afectan al rendimiento de {ticker}.",
            f"INFLACIÓN DE PROMESAS: El Banco Central de $BROKERS vigila las cotizaciones."
        ]
    
    return random.choice(titulares)


def evaluar_oraculo_visual(imagen_bytes: bytes, mime_type: str, reto: str, es_impugnacion: bool = False,
                            hora_actual: str = None, captura_ts: float = None, reto_creado: str = None) -> dict:
    """
    Usa Gemini Vision para evaluar si una captura de cámara demuestra el reto.
    La hora del servidor, la hora de captura y la antigüedad del reto forman parte de la sentencia.
    Si no se puede verificar, el fallback rechaza la prueba; nunca aprueba a ciegas.
    """
    from datetime import datetime

    client = _get_genai_client()
    hora_captura = "desconocida"
    if captura_ts:
        try:
            hora_captura = datetime.fromtimestamp(float(captura_ts) / 1000).isoformat(timespec="seconds")
        except (ValueError, OSError, TypeError):
            pass

    if client and imagen_bytes:
        try:
            prompt = f"""
Eres el Oráculo Visual de $BROKERS (mercado de apuestas de retos entre amigos universitarios).
Reto a verificar: "{reto}"
¿Es impugnación de VAR por parte del protagonista?: {"SÍ (Contra-foto de prueba en directo)" if es_impugnacion else "NO (Primera prueba)"}
Hora actual del servidor: {hora_actual or "desconocida"}
Hora declarada de la captura: {hora_captura}
Reto creado: {reto_creado or "desconocido"}
La imagen DEBE ser una captura de cámara en directo. No es válida una foto de galería, captura de pantalla, meme, logo, imagen de stock o collage.
La app añade un sello "EN VIVO · fecha/hora" en la parte inferior de la captura. Si el sello no aparece o su hora no es coherente con la hora actual, responde "NO".

Criterio estricto:
1. Solo responde "SI" si la imagen muestra de forma clara y directa el cumplimiento del reto en el momento actual.
2. Ten en cuenta la hora actual y la hora de captura: si el reto depende de una hora o contexto temporal y la evidencia no es coherente con ese momento, responde "NO".
3. Si parece una imagen antigua, de pantalla, descargada, editada o sin relación directa con el reto, responde "NO".
4. Si hay dudas o la prueba es ambigua, responde "NO" con confianza baja.
5. Sé riguroso pero divertido en la explicación; menciona explícitamente la comprobación temporal.

Devuelve ÚNICAMENTE un JSON sin bloques markdown:
{{"cumplido": bool, "veredicto": "SI" o "NO", "confianza": float_entre_0_y_1, "explicacion": "Frase lapidaria explicando el veredicto visual y temporal"}}
"""
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM
            ) if GENAI_AVAILABLE else None
            part = types.Part.from_bytes(data=imagen_bytes, mime_type=mime_type or "image/jpeg")
            ultimo_error = None
            for intento in range(2):
                try:
                    response = _generar_contenido(
                        client,
                        contents=[part, prompt],
                        config=config,
                        modelos=[VISION_MODEL_NAME, "gemini-3.6-flash"]
                    )
                    return _extraer_json(response.text)
                except Exception as e:
                    ultimo_error = e
                    if intento == 0:
                        time.sleep(0.8)
            print(f"[IA] Visión no disponible: {str(ultimo_error)[:300]}")
        except Exception:
            pass

    # Si no hay conexión con el Oráculo, no se inventa un veredicto.
    return {
        "error": "Oráculo sin conexión: no se pudo verificar la captura en directo. Inténtalo de nuevo.",
        "cumplido": False,
        "veredicto": None,
        "confianza": 0.0,
        "explicacion": "No hay sentencia visual disponible."
    }
