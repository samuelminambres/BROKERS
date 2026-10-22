import os
import math
import time
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Cargar automáticamente variables de entorno desde .env si existe
load_dotenv()

import ai_service

app = Flask(__name__, static_folder="static")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(__file__), "db.json")

# Constante de liquidez LMSR de Hanson
B_LIQUIDEZ = 100.0


def calcular_precio_lmsr(q_si: float, q_no: float) -> float:
    """
    Calcula el precio instantáneo del 'CONFIO' (SI) en centavos (0.0¢ - 100.0¢)
    mediante el Market Maker Logarítmico de Hanson.
    """
    exp_si = math.exp(q_si / B_LIQUIDEZ)
    exp_no = math.exp(q_no / B_LIQUIDEZ)
    precio = (exp_si / (exp_si + exp_no)) * 100.0
    return round(precio, 2)


def get_semilla_demo():
    """Genera el estado demo inicial hilarante para la hackathon."""
    return {
        "amigos": [
            {
                "ticker": "$SAMU",
                "nombre": "Samu",
                "descripcion": "Trader de sueños y promesas matutinas al gym.",
                "cotizacion": 53.74
            },
            {
                "ticker": "$MITO",
                "nombre": "Mito",
                "descripcion": "Accionista mayoritario de Deliveroo y Glovo.",
                "cotizacion": 42.56
            },
            {
                "ticker": "$LUCAS",
                "nombre": "Lucas",
                "descripcion": "Deja las prácticas de la universidad para las 23:58.",
                "cotizacion": 50.00
            }
        ],
        "usuarios": {
            "samu": {"nombre": "Samu", "saldo": 1000.0},
            "mito": {"nombre": "Mito", "saldo": 1000.0},
            "lucas": {"nombre": "Lucas", "saldo": 1000.0},
            "tiburontrader": {"nombre": "El Lobo de la Uni", "saldo": 1250.0}
        },
        "mercados": [
            {
                "id": "mkt_1",
                "ticker": "$SAMU",
                "creador": "mito",
                "pregunta": "Ser capaz de ir al gimnasio a las 7:30 AM sin pulsar 'posponer alarma'",
                "estado": "ABIERTO",  # ABIERTO | RESUELTO
                "ganador": None,      # "SI" | "NO"
                "q_si": 65.0,
                "q_no": 50.0,
                "precio_si": 53.74,
                "bote_si": 15.0,
                "bote_no": 0.0,
                "total_apostado": 15.0,
                "apuestas": [
                    {"usuario": "tiburontrader", "tipo": "SI", "cantidad": 15.0, "timestamp": time.time()}
                ],
                "resolucion": None,
                "impugnado": False,
                "tramposo": None,
                "historial_precios": [
                    {"t": "09:00", "p": 50.0},
                    {"t": "10:15", "p": 53.74}
                ]
            },
            {
                "id": "mkt_2",
                "ticker": "$MITO",
                "creador": "samu",
                "pregunta": "Ser capaz de cocinar en casa hoy en vez de pedir hamburguesas por Glovo",
                "estado": "ABIERTO",
                "ganador": None,
                "q_si": 50.0,
                "q_no": 80.0,
                "precio_si": 42.56,
                "bote_si": 0.0,
                "bote_no": 30.0,
                "total_apostado": 30.0,
                "apuestas": [
                    {"usuario": "lucas", "tipo": "NO", "cantidad": 30.0, "timestamp": time.time()}
                ],
                "resolucion": None,
                "impugnado": False,
                "tramposo": None,
                "historial_precios": [
                    {"t": "09:30", "p": 50.0},
                    {"t": "11:00", "p": 42.56}
                ]
            }
        ],
        "noticias": [
            {
                "id": "not_1",
                "titular": "APERTURA DEL PARQUÉ: Los bajistas toman posiciones ante la alarma de $SAMU.",
                "hora": "09:05",
                "ticker": "$SAMU"
            },
            {
                "id": "not_2",
                "titular": "MOVIMIENTO BALLENA: El Lobo de la Uni inyecta capital esperando un milagro fitness.",
                "hora": "10:20",
                "ticker": "$SAMU"
            },
            {
                "id": "not_3",
                "titular": "GLOVO ADVANCE: El mercado descuenta una pizza cuatro quesos en la cartera de $MITO.",
                "hora": "11:15",
                "ticker": "$MITO"
            }
        ]
    }


def cargar_db():
    """Lee el estado persistente desde db.json o lo inicializa con los datos semilla."""
    if not os.path.exists(DB_PATH):
        db = get_semilla_demo()
        guardar_db(db)
        return db
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        db = get_semilla_demo()
        guardar_db(db)
        return db


def guardar_db(db):
    """Escribe de manera atómica el diccionario db en db.json tras cada mutación."""
    temp_path = f"{DB_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, DB_PATH)


def asegurar_usuario(db, usuario_id: str, nombre: str = None):
    """Garantiza que el usuario exista en el balance con 1000.0 $BROK de capital inicial."""
    uid = usuario_id.strip().lower()
    if uid not in db["usuarios"]:
        db["usuarios"][uid] = {
            "nombre": nombre or usuario_id.strip(),
            "saldo": 1000.0
        }
    return uid


# ==========================================
# RUTAS DE INTERFAZ Y ESTÁTICOS
# ==========================================

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


# ==========================================
# RUTAS DEL CONTRATO DE API ESTRICTO
# ==========================================

@app.route("/api/estado", methods=["GET"])
def api_estado():
    """
    Devuelve el estado completo del mercado:
    { amigos: [...], mercados: [...], noticias: [...], ranking: [...] }
    """
    db = cargar_db()

    # Calcular ranking ordenado por saldo de mayor a menor
    ranking = []
    for uid, data in db.get("usuarios", {}).items():
        ranking.append({
            "usuario": uid,
            "nombre": data.get("nombre", uid),
            "saldo": round(data.get("saldo", 0.0), 2)
        })
    ranking.sort(key=lambda x: x["saldo"], reverse=True)

    # Actualizar cotización actual de cada amigo con base en sus mercados
    cotizaciones_amigos = {a["ticker"]: a.get("cotizacion", 50.0) for a in db["amigos"]}
    mercados_abiertos = {m["ticker"] for m in db["mercados"] if m["estado"] == "ABIERTO"}

    for m in db["mercados"]:
        ticker = m["ticker"]
        if m["estado"] == "ABIERTO":
            # Si hay mercado abierto, manda el precio spot actual
            cotizaciones_amigos[ticker] = m["precio_si"]
        elif ticker not in mercados_abiertos and m["estado"] == "RESUELTO":
            # Si no hay mercado abierto, refleja el resultado del último mercado resuelto
            cotizaciones_amigos[ticker] = 100.0 if m.get("ganador") == "SI" else 0.0

    for a in db["amigos"]:
        if a["ticker"] in cotizaciones_amigos:
            a["cotizacion"] = cotizaciones_amigos[a["ticker"]]

    return jsonify({
        "amigos": db.get("amigos", []),
        "mercados": db.get("mercados", []),
        "noticias": db.get("noticias", []),
        "ranking": ranking
    })


@app.route("/api/amigos", methods=["POST"])
def api_crear_amigo():
    """
    Crea un nuevo amigo para cotizar en bolsa.
    Body: { ticker, nombre, descripcion (opcional) }
    """
    db = cargar_db()
    data = request.get_json() or {}
    
    ticker_raw = data.get("ticker", "").strip().upper()
    nombre = data.get("nombre", "").strip()
    descripcion = data.get("descripcion", "Nuevo activo especulativo de alta volatilidad.").strip()

    if not ticker_raw or not nombre:
        return jsonify({"error": "Ticker y nombre son obligatorios"}), 400

    ticker = ticker_raw if ticker_raw.startswith("$") else f"${ticker_raw}"

    # Comprobar si ya existe
    if any(a["ticker"] == ticker for a in db["amigos"]):
        return jsonify({"error": f"El ticker {ticker} ya cotiza en bolsa"}), 400

    nuevo_amigo = {
        "ticker": ticker,
        "nombre": nombre,
        "descripcion": descripcion,
        "cotizacion": 50.0
    }
    db["amigos"].append(nuevo_amigo)

    # Crear usuario automáticamente
    uid = ticker.replace("$", "").lower()
    asegurar_usuario(db, uid, nombre)

    # Noticia de OPV
    titular = f"SALIDA A BOLSA: {ticker} debuta en el parqué con una cotización base de 50.0¢."
    db["noticias"].insert(0, {
        "id": f"not_{uuid.uuid4().hex[:6]}",
        "titular": titular,
        "hora": datetime.now().strftime("%H:%M"),
        "ticker": ticker
    })

    guardar_db(db)
    return jsonify({"mensaje": "Amigo registrado con éxito", "amigo": nuevo_amigo}), 201


@app.route("/api/mercados", methods=["POST"])
def api_crear_mercado():
    """
    Crea un nuevo contrato flash.
    Pasa obligatoriamente por el filtro de la CNMV IA.
    Body: { creador, ticker, pregunta }
    """
    db = cargar_db()
    data = request.get_json() or {}
    
    creador = data.get("creador", "").strip().lower()
    ticker = data.get("ticker", "").strip().upper()
    pregunta = data.get("pregunta", "").strip()

    if not creador or not ticker or not pregunta:
        return jsonify({"error": "creador, ticker y pregunta son obligatorios"}), 400

    asegurar_usuario(db, creador)

    # 1. Filtro CNMV IA
    analisis = ai_service.validar_reto_cnmv(creador, ticker, pregunta)
    if not analisis.get("valido", False):
        penalizacion = analisis.get("penalizacion", 10.0)
        db["usuarios"][creador]["saldo"] = max(0.0, db["usuarios"][creador]["saldo"] - penalizacion)
        
        # Registrar noticia de sanción
        db["noticias"].insert(0, {
            "id": f"not_{uuid.uuid4().hex[:6]}",
            "titular": f"SANCIÓN CNMV: {creador} multado con -{penalizacion:.0f} $BROK por intentar colocar un contrato delirante en {ticker}.",
            "hora": datetime.now().strftime("%H:%M"),
            "ticker": ticker
        })
        guardar_db(db)
        
        return jsonify({
            "error": "Contrato rechazado por la CNMV",
            "motivo": analisis.get("motivo", "Reto físicamente imposible o no verificable."),
            "penalizacion": penalizacion,
            "saldo_actual": db["usuarios"][creador]["saldo"]
        }), 400

    pregunta_final = analisis.get("pregunta_final") or pregunta

    # 2. Creación del Mercado con Liquidez Semilla Hanson
    precio_inicial = calcular_precio_lmsr(50.0, 50.0)  # 50.0¢
    hora_actual = datetime.now().strftime("%H:%M")

    nuevo_mercado = {
        "id": f"mkt_{uuid.uuid4().hex[:8]}",
        "ticker": ticker,
        "creador": creador,
        "pregunta": pregunta_final,
        "estado": "ABIERTO",
        "ganador": None,
        "q_si": 50.0,
        "q_no": 50.0,
        "precio_si": precio_inicial,
        "bote_si": 0.0,
        "bote_no": 0.0,
        "total_apostado": 0.0,
        "apuestas": [],
        "resolucion": None,
        "impugnado": False,
        "tramposo": None,
        "historial_precios": [
            {"t": hora_actual, "p": precio_inicial}
        ]
    }
    db["mercados"].insert(0, nuevo_mercado)

    # 3. Noticia con IA
    titular = ai_service.generar_titular_wallstreet("nuevo_mercado", {
        "ticker": ticker,
        "usuario": creador,
        "pregunta": pregunta_final
    })
    db["noticias"].insert(0, {
        "id": f"not_{uuid.uuid4().hex[:6]}",
        "titular": titular,
        "hora": hora_actual,
        "ticker": ticker
    })

    guardar_db(db)
    return jsonify({
        "mensaje": "Mercado creado y validado por la CNMV",
        "mercado": nuevo_mercado,
        "analisis_cnmv": analisis
    }), 201


@app.route("/api/mercados/<mercado_id>/apostar", methods=["POST"])
def api_apostar(mercado_id):
    """
    Ejecuta una apuesta LMSR sobre un mercado abierto.
    Body: { usuario, tipo: "SI"|"NO", cantidad: float }
    """
    db = cargar_db()
    data = request.get_json() or {}

    usuario = data.get("usuario", "").strip().lower()
    tipo = data.get("tipo", "").strip().upper()
    try:
        cantidad = float(data.get("cantidad", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "La cantidad debe ser un número positivo"}), 400

    if not usuario or tipo not in ["SI", "NO"] or cantidad <= 0:
        return jsonify({"error": "Parámetros inválidos (usuario, tipo SI/NO, cantidad > 0)"}), 400

    mercado = next((m for m in db["mercados"] if m["id"] == mercado_id), None)
    if not mercado:
        return jsonify({"error": "Mercado no encontrado"}), 404

    if mercado["estado"] != "ABIERTO":
        return jsonify({"error": "El mercado ya está cerrado o resuelto"}), 400

    asegurar_usuario(db, usuario)

    # REGLA 3: El protagonista del reto NO puede apostar NO en su propio mercado
    protagonista_ticker = mercado["ticker"].replace("$", "").lower()
    amigo_obj = next((a for a in db["amigos"] if a["ticker"] == mercado["ticker"]), None)
    nombres_protagonista = {protagonista_ticker}
    if amigo_obj and "nombre" in amigo_obj:
        nombres_protagonista.add(amigo_obj["nombre"].strip().lower())

    if (usuario in nombres_protagonista) and tipo == "NO":
        return jsonify({
            "error": "Fraude detectado: El protagonista del reto tiene prohibido apostar NI_DE_BROMA (NO) contra sí mismo."
        }), 400

    # Comprobación de saldo
    saldo_usuario = db["usuarios"][usuario]["saldo"]
    if saldo_usuario < cantidad:
        return jsonify({
            "error": f"Saldo insuficiente. Tienes {saldo_usuario:.2f} $BROK disponibles."
        }), 400

    # Descontar saldo al inversor
    db["usuarios"][usuario]["saldo"] -= cantidad

    # Motor LMSR: inyectar liquidez al lado correspondiente
    if tipo == "SI":
        mercado["q_si"] += cantidad
    else:
        mercado["q_no"] += cantidad

    # Recalcular botes reales y precio instantáneo
    mercado["bote_si"] = max(0.0, mercado["q_si"] - 50.0)
    mercado["bote_no"] = max(0.0, mercado["q_no"] - 50.0)
    mercado["total_apostado"] += cantidad

    nuevo_precio = calcular_precio_lmsr(mercado["q_si"], mercado["q_no"])
    mercado["precio_si"] = nuevo_precio

    hora_actual = datetime.now().strftime("%H:%M")
    mercado["historial_precios"].append({"t": hora_actual, "p": nuevo_precio})
    
    # Mantener historial en tamaño razonable
    if len(mercado["historial_precios"]) > 30:
        mercado["historial_precios"] = mercado["historial_precios"][-30:]

    # Registrar la apuesta en el libro de órdenes
    mercado["apuestas"].append({
        "usuario": usuario,
        "tipo": tipo,
        "cantidad": cantidad,
        "precio_momento": nuevo_precio,
        "timestamp": time.time(),
        "hora": hora_actual
    })

    # Titular de mercado con IA
    titular = ai_service.generar_titular_wallstreet("apuesta", {
        "ticker": mercado["ticker"],
        "usuario": db["usuarios"][usuario]["nombre"],
        "tipo": tipo,
        "cantidad": cantidad,
        "pregunta": mercado["pregunta"]
    })
    db["noticias"].insert(0, {
        "id": f"not_{uuid.uuid4().hex[:6]}",
        "titular": titular,
        "hora": hora_actual,
        "ticker": mercado["ticker"]
    })

    guardar_db(db)
    return jsonify({
        "mensaje": "Apuesta procesada con éxito",
        "nuevo_precio": nuevo_precio,
        "saldo_restante": db["usuarios"][usuario]["saldo"],
        "mercado": mercado
    })


@app.route("/api/mercados/<mercado_id>/resolver", methods=["POST"])
def api_resolver(mercado_id):
    """
    Resuelve el mercado mediante foto analizada por el Oráculo Visual (o contra-foto VAR).
    Multipart form-data: usuario, imagen (File), es_impugnacion ("true"|"false")
    """
    db = cargar_db()
    mercado = next((m for m in db["mercados"] if m["id"] == mercado_id), None)
    if not mercado:
        return jsonify({"error": "Mercado no encontrado"}), 404

    usuario = request.form.get("usuario", "").strip().lower()
    es_impugnacion = request.form.get("es_impugnacion", "false").lower() == "true"
    
    if "imagen" not in request.files:
        return jsonify({"error": "Se requiere subir un archivo de imagen como evidencia"}), 400

    archivo = request.files["imagen"]
    if archivo.filename == "":
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400

    filename = secure_filename(f"{mercado_id}_{int(time.time())}_{archivo.filename}")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    
    imagen_bytes = archivo.read()
    archivo.seek(0)
    archivo.save(filepath)
    imagen_url = f"/static/uploads/{filename}"

    # Verificación de VAR
    if es_impugnacion:
        if mercado["estado"] != "RESUELTO" or mercado["ganador"] != "NO":
            return jsonify({"error": "Solo se puede recurrir al VAR si el mercado fue resuelto en NO"}), 400
        protagonista_ticker = mercado["ticker"].replace("$", "").lower()
        if usuario != protagonista_ticker:
            return jsonify({"error": "Solo el protagonista del reto puede presentar contra-prueba al VAR"}), 403

    # Llamada al Oráculo Visual
    mime_type = archivo.content_type or "image/jpeg"
    veredicto_ia = ai_service.evaluar_oraculo_visual(
        imagen_bytes=imagen_bytes,
        mime_type=mime_type,
        reto=mercado["pregunta"],
        es_impugnacion=es_impugnacion
    )

    veredicto = veredicto_ia.get("veredicto", "SI")
    hora_actual = datetime.now().strftime("%H:%M")

    # ==========================================
    # CASO IMPUGNACIÓN (VAR)
    # ==========================================
    if es_impugnacion:
        if veredicto == "SI":
            mercado["ganador"] = "SI"
            mercado["impugnado"] = True
            
            # Castigo al tramposo que subió la resolución falsa inicial
            tramposo = mercado.get("resolucion", {}).get("resuelto_por")
            multa_tramposo = 0.0
            if tramposo and tramposo in db["usuarios"]:
                # Embargar el doble de lo que apostó o 100 $BROK si no apostó
                apuesta_tramposo = sum(a["cantidad"] for a in mercado["apuestas"] if a["usuario"] == tramposo and a["tipo"] == "NO")
                multa_tramposo = max(100.0, apuesta_tramposo * 2.0)
                db["usuarios"][tramposo]["saldo"] = max(0.0, db["usuarios"][tramposo]["saldo"] - multa_tramposo)
                mercado["tramposo"] = tramposo

            # Re-liquidar en favor del protagonista y de los inversores del SI
            protagonista = mercado["ticker"].replace("$", "").lower()
            asegurar_usuario(db, protagonista)
            
            # Short squeeze payout
            premio_protagonista = (0.30 * mercado["bote_no"]) + 25.0 + (multa_tramposo * 0.5)
            db["usuarios"][protagonista]["saldo"] += premio_protagonista

            # Reparto a inversores del SI
            total_apostado_si = sum(a["cantidad"] for a in mercado["apuestas"] if a["tipo"] == "SI")
            bote_repartible_si = (0.70 * mercado["bote_no"]) + 25.0 + (multa_tramposo * 0.5)
            if total_apostado_si > 0:
                for a in mercado["apuestas"]:
                    if a["tipo"] == "SI":
                        ganancia = a["cantidad"] + (a["cantidad"] / total_apostado_si) * bote_repartible_si
                        db["usuarios"][a["usuario"]]["saldo"] += ganancia

            # Registrar resolución
            mercado["resolucion"] = {
                "resuelto_por": usuario,
                "imagen_url": imagen_url,
                "veredicto": "SI",
                "explicacion": f"VAR: Impugnación aceptada. {veredicto_ia.get('explicacion', '')} Multa de {multa_tramposo:.0f} $BROK aplicada al acusador falso.",
                "hora": hora_actual
            }

            titular = ai_service.generar_titular_wallstreet("var", {
                "ticker": mercado["ticker"],
                "usuario": usuario,
                "pregunta": mercado["pregunta"]
            })
            db["noticias"].insert(0, {
                "id": f"not_{uuid.uuid4().hex[:6]}",
                "titular": titular,
                "hora": hora_actual,
                "ticker": mercado["ticker"]
            })
            guardar_db(db)
            return jsonify({
                "mensaje": "VAR aceptado. Veredicto revertido a SI y sanción ejecutada.",
                "mercado": mercado,
                "veredicto_ia": veredicto_ia
            })
        else:
            return jsonify({
                "error": "El VAR rechazó la contra-prueba",
                "explicacion": veredicto_ia.get("explicacion", "La evidencia sigue sin demostrar el cumplimiento.")
            }), 400

    # ==========================================
    # RESOLUCIÓN NORMAL DE MERCADO
    # ==========================================
    if mercado["estado"] == "RESUELTO":
        return jsonify({"error": "Este mercado ya ha sido resuelto previamente"}), 400

    mercado["estado"] = "RESUELTO"
    mercado["ganador"] = veredicto
    mercado["resolucion"] = {
        "resuelto_por": usuario,
        "imagen_url": imagen_url,
        "veredicto": veredicto,
        "explicacion": veredicto_ia.get("explicacion", ""),
        "confianza": veredicto_ia.get("confianza", 1.0),
        "hora": hora_actual
    }

    protagonista = mercado["ticker"].replace("$", "").lower()
    asegurar_usuario(db, protagonista)

    bote_si = mercado["bote_si"]
    bote_no = mercado["bote_no"]

    total_si = sum(a["cantidad"] for a in mercado["apuestas"] if a["tipo"] == "SI")
    total_no = sum(a["cantidad"] for a in mercado["apuestas"] if a["tipo"] == "NO")

    if veredicto == "SI":
        # REGLA 4.1: Cumplió el reto -> SHORT SQUEEZE
        # Protagonista cobra +0.30 * bote_no + 25 bono del Banco Central
        premio_protagonista = (0.30 * bote_no) + 25.0
        db["usuarios"][protagonista]["saldo"] += premio_protagonista

        # Inversores de SI recuperan inversión + se reparten 0.70 * bote_no + 25 semilla
        bote_repartible = (0.70 * bote_no) + 25.0
        if total_si > 0:
            for a in mercado["apuestas"]:
                if a["tipo"] == "SI":
                    pago = a["cantidad"] + ((a["cantidad"] / total_si) * bote_repartible)
                    db["usuarios"][a["usuario"]]["saldo"] += pago
    else:
        # REGLA 4.2: Falló el reto -> MULTA AL PROTAGONISTA
        # Pierde -0.20 * bote_si de su saldo
        multa_protagonista = 0.20 * bote_si
        db["usuarios"][protagonista]["saldo"] = max(0.0, db["usuarios"][protagonista]["saldo"] - multa_protagonista)

        # Inversores del NO recuperan inversión + se reparten bote_si + multa cobrada
        bote_repartible = bote_si + multa_protagonista
        if total_no > 0:
            for a in mercado["apuestas"]:
                if a["tipo"] == "NO":
                    pago = a["cantidad"] + ((a["cantidad"] / total_no) * bote_repartible)
                    db["usuarios"][a["usuario"]]["saldo"] += pago

    # Titular de resolución con IA
    titular = ai_service.generar_titular_wallstreet("resolucion", {
        "ticker": mercado["ticker"],
        "usuario": usuario,
        "veredicto": veredicto,
        "pregunta": mercado["pregunta"]
    })
    db["noticias"].insert(0, {
        "id": f"not_{uuid.uuid4().hex[:6]}",
        "titular": titular,
        "hora": hora_actual,
        "ticker": mercado["ticker"]
    })

    guardar_db(db)
    return jsonify({
        "mensaje": f"Mercado resuelto con veredicto: {veredicto}",
        "mercado": mercado,
        "veredicto_ia": veredicto_ia
    })


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """
    Restaura el estado global del mercado a los valores de demostración iniciales.
    """
    db = get_semilla_demo()
    guardar_db(db)
    return jsonify({"mensaje": "Mercado reseteado a la configuración inicial con éxito", "estado": db})


if __name__ == "__main__":
    print("[$BROKERS] Servidor financiero activo en http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
