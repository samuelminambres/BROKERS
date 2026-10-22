import os
import math
import re
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
    """Estado inicial vacío: un grupo nuevo no tiene activos, usuarios ni historial."""
    return {
        "grupos": [],
        "amigos": [],
        "usuarios": {},
        "mercados": [],
        "noticias": []
    }


def migrar_a_grupos(db):
    """Mueve una base antigua de un solo grupo a 'Mi grupo' sin perder datos."""
    usuarios = list(db.get("usuarios", {}).keys())
    if not usuarios:
        db["grupos"] = []
        return db
    gid = "grp_principal"
    grupo = {
        "id": gid,
        "nombre": "Mi grupo",
        "codigo": "PRINCIPAL",
        "creador": usuarios[0] if usuarios else "sistema",
        "miembros": usuarios,
        "saldos": {uid: db["usuarios"][uid].get("saldo", 1000.0) for uid in usuarios},
        "creado": datetime.now().strftime("%Y-%m-%d")
    }
    db["grupos"] = [grupo]
    for a in db.get("amigos", []):
        a["grupo"] = gid
    for m in db.get("mercados", []):
        m["grupo"] = gid
    for n in db.get("noticias", []):
        n["grupo"] = gid
    for uid in usuarios:
        asegurar_ticker_en_grupo(db, grupo, uid)
    return db


def migrar_saldos_por_grupo(db):
    """Añade carteras de 1.000 $BROK a grupos antiguos que no las tuvieran."""
    changed = False
    for grupo in db.get("grupos", []):
        if "saldos" not in grupo:
            grupo["saldos"] = {}
            changed = True
        for uid in grupo.get("miembros", []):
            if uid not in grupo["saldos"]:
                grupo["saldos"][uid] = 1000.0
                changed = True
    return changed


def cargar_db():
    """Lee el estado persistente desde db.json o lo inicializa con los datos semilla."""
    if not os.path.exists(DB_PATH):
        db = get_semilla_demo()
        guardar_db(db)
        return db
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
        changed = False
        if "grupos" not in db:
            db = migrar_a_grupos(db)
            changed = True
        if migrar_saldos_por_grupo(db):
            changed = True
        if changed:
            guardar_db(db)
        return db
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


def get_grupo(db, grupo_id):
    """Busca un grupo por id."""
    return next((g for g in db.get("grupos", []) if g["id"] == grupo_id), None)


def es_miembro(grupo, usuario):
    """Comprueba si el alias pertenece al grupo."""
    return bool(grupo and usuario and usuario.strip().lower() in grupo.get("miembros", []))


def grupos_de_usuario(db, usuario):
    """Lista los grupos a los que pertenece un alias."""
    uid = (usuario or "").strip().lower()
    return [g for g in db.get("grupos", []) if uid in g.get("miembros", [])]


def nuevo_codigo_grupo(db):
    """Genera un código de invitación corto y único."""
    while True:
        codigo = uuid.uuid4().hex[:6].upper()
        if not any(g.get("codigo") == codigo for g in db.get("grupos", [])):
            return codigo


def asegurar_ticker_en_grupo(db, grupo, usuario, nombre=None):
    """Cada miembro es también un activo cotizado dentro de su grupo."""
    uid = usuario.strip().lower()
    ticker = f"${uid.upper()}"
    existente = next((a for a in db["amigos"] if a.get("grupo") == grupo["id"] and a["ticker"] == ticker), None)
    if existente:
        return existente
    if nombre is None:
        nombre = db.get("usuarios", {}).get(uid, {}).get("nombre", uid)
    amigo = {
        "ticker": ticker,
        "nombre": nombre,
        "descripcion": "Broker registrado en el parqué. Cotización inicial de 50.0¢.",
        "cotizacion": 50.0,
        "grupo": grupo["id"]
    }
    db["amigos"].append(amigo)
    return amigo


def asegurar_saldo_grupo(grupo, usuario, saldo=1000.0):
    """Cada grupo tiene su propia cartera por usuario."""
    grupo.setdefault("saldos", {})
    uid = usuario.strip().lower()
    if uid not in grupo["saldos"]:
        grupo["saldos"][uid] = float(saldo)
    return float(grupo["saldos"][uid])


def get_saldo_grupo(grupo, usuario):
    return asegurar_saldo_grupo(grupo, usuario)


def set_saldo_grupo(grupo, usuario, cantidad):
    grupo.setdefault("saldos", {})
    grupo["saldos"][usuario.strip().lower()] = max(0.0, float(cantidad))


def add_saldo_grupo(grupo, usuario, cantidad):
    actual = get_saldo_grupo(grupo, usuario)
    set_saldo_grupo(grupo, usuario, actual + float(cantidad))
    return get_saldo_grupo(grupo, usuario)


def unir_usuario_a_grupo(db, grupo, usuario, nombre=None):
    """Añade el usuario al grupo, su cartera y su ticker dentro de ese grupo."""
    uid = asegurar_usuario(db, usuario, nombre)
    if uid not in grupo["miembros"]:
        grupo["miembros"].append(uid)
    asegurar_saldo_grupo(grupo, uid)
    asegurar_ticker_en_grupo(db, grupo, uid, nombre)
    return uid


def es_protagonista(db, mercado, usuario):
    """El protagonista es el dueño del ticker o quien coincide con el nombre del activo."""
    if not usuario:
        return False
    nombres = {mercado.get("ticker", "").replace("$", "").lower()}
    amigo = next((
        a for a in db["amigos"]
        if a["ticker"] == mercado.get("ticker") and a.get("grupo") == mercado.get("grupo")
    ), None)
    if amigo and amigo.get("nombre"):
        nombres.add(amigo["nombre"].strip().lower())
    return usuario.strip().lower() in nombres


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
    """Devuelve el mercado del grupo activo y los grupos del usuario."""
    db = cargar_db()
    usuario = request.args.get("usuario", "").strip().lower()
    grupo_id = request.args.get("grupo", "").strip()

    grupos_usuario = grupos_de_usuario(db, usuario) if usuario else []
    grupo = get_grupo(db, grupo_id) if grupo_id else None
    if usuario and grupo and not es_miembro(grupo, usuario):
        grupo = None
    if not grupo and usuario and grupos_usuario:
        grupo = grupos_usuario[0]

    amigos = []
    mercados = []
    noticias = []
    ranking = []

    if grupo:
        amigos = [a for a in db.get("amigos", []) if a.get("grupo") == grupo["id"]]
        mercados = [m for m in db.get("mercados", []) if m.get("grupo") == grupo["id"]]
        noticias = [n for n in db.get("noticias", []) if n.get("grupo") == grupo["id"]]

        for uid in grupo.get("miembros", []):
            data = db.get("usuarios", {}).get(uid, {"nombre": uid})
            ranking.append({
                "usuario": uid,
                "nombre": data.get("nombre", uid),
                "saldo": round(get_saldo_grupo(grupo, uid), 2)
            })
        ranking.sort(key=lambda x: x["saldo"], reverse=True)

        # La cotización del activo refleja su último mercado dentro del grupo
        cotizaciones_amigos = {a["ticker"]: a.get("cotizacion", 50.0) for a in amigos}
        mercados_abiertos = {m["ticker"] for m in mercados if m["estado"] == "ABIERTO"}
        for m in mercados:
            ticker = m["ticker"]
            if m["estado"] == "ABIERTO":
                cotizaciones_amigos[ticker] = m["precio_si"]
            elif ticker not in mercados_abiertos and m["estado"] == "RESUELTO":
                cotizaciones_amigos[ticker] = 100.0 if m.get("ganador") == "SI" else 0.0
        for a in amigos:
            if a["ticker"] in cotizaciones_amigos:
                a["cotizacion"] = cotizaciones_amigos[a["ticker"]]

    return jsonify({
        "grupos": grupos_usuario,
        "grupo_actual": grupo,
        "amigos": amigos,
        "mercados": mercados,
        "noticias": noticias,
        "ranking": ranking
    })


@app.route("/api/usuarios", methods=["POST"])
def api_crear_usuario():
    """Registra al broker actual sin contraseña y le asigna 1.000 $BROK."""
    db = cargar_db()
    data = request.get_json() or {}

    usuario = data.get("usuario", "").strip().lower().lstrip("@")
    nombre = data.get("nombre", "").strip() or usuario

    if not re.fullmatch(r"[a-z0-9_]{2,12}", usuario):
        return jsonify({"error": "Alias inválido: 2 a 12 caracteres (letras, números o _)"}), 400

    existia = usuario in db["usuarios"]
    uid = asegurar_usuario(db, usuario, nombre)
    guardar_db(db)

    return jsonify({
        "usuario": uid,
        "nombre": db["usuarios"][uid]["nombre"],
        "nuevo": not existia
    }), (200 if existia else 201)


@app.route("/api/grupos", methods=["POST"])
def api_crear_grupo():
    """Crea un grupo y convierte al creador en miembro cotizado."""
    db = cargar_db()
    data = request.get_json() or {}
    usuario = data.get("usuario", "").strip().lower().lstrip("@")
    nombre_grupo = data.get("nombre", "").strip()

    if not re.fullmatch(r"[a-z0-9_]{2,12}", usuario):
        return jsonify({"error": "Alias inválido"}), 400
    if not 2 <= len(nombre_grupo) <= 30:
        return jsonify({"error": "El nombre del grupo debe tener entre 2 y 30 caracteres"}), 400

    uid = asegurar_usuario(db, usuario)
    grupo = {
        "id": f"grp_{uuid.uuid4().hex[:8]}",
        "nombre": nombre_grupo,
        "codigo": nuevo_codigo_grupo(db),
        "creador": uid,
        "miembros": [],
        "saldos": {},
        "creado": datetime.now().strftime("%Y-%m-%d")
    }
    db["grupos"].append(grupo)
    unir_usuario_a_grupo(db, grupo, uid)
    guardar_db(db)

    return jsonify({
        "mensaje": f"Grupo '{nombre_grupo}' creado",
        "grupo": grupo
    }), 201


@app.route("/api/grupos/unirse", methods=["POST"])
def api_unirse_grupo():
    """Añade al usuario a un grupo mediante su código de invitación."""
    db = cargar_db()
    data = request.get_json() or {}
    usuario = data.get("usuario", "").strip().lower().lstrip("@")
    codigo = data.get("codigo", "").strip().upper()

    if not re.fullmatch(r"[a-z0-9_]{2,12}", usuario):
        return jsonify({"error": "Alias inválido"}), 400

    grupo = next((g for g in db.get("grupos", []) if g.get("codigo") == codigo), None)
    if not grupo:
        return jsonify({"error": "Código de grupo no encontrado"}), 404

    ya_miembro = es_miembro(grupo, usuario)
    unir_usuario_a_grupo(db, grupo, usuario)
    guardar_db(db)

    return jsonify({
        "mensaje": f"Te has unido a '{grupo['nombre']}'",
        "grupo": grupo,
        "nuevo": not ya_miembro
    })


@app.route("/api/amigos", methods=["POST"])
def api_crear_amigo():
    """
    Crea un nuevo amigo para cotizar en bolsa.
    Body: { ticker, nombre, descripcion (opcional), grupo }
    """
    db = cargar_db()
    data = request.get_json() or {}
    grupo = get_grupo(db, data.get("grupo", "").strip())

    ticker_raw = data.get("ticker", "").strip().upper()
    nombre = data.get("nombre", "").strip()
    descripcion = data.get("descripcion", "Nuevo activo especulativo de alta volatilidad.").strip()

    if not grupo:
        return jsonify({"error": "El grupo es obligatorio"}), 400
    if not ticker_raw or not nombre:
        return jsonify({"error": "Ticker y nombre son obligatorios"}), 400

    ticker = ticker_raw if ticker_raw.startswith("$") else f"${ticker_raw}"

    # El mismo ticker puede existir en grupos distintos
    if any(a["ticker"] == ticker and a.get("grupo") == grupo["id"] for a in db["amigos"]):
        return jsonify({"error": f"El ticker {ticker} ya cotiza en este grupo"}), 400

    nuevo_amigo = {
        "ticker": ticker,
        "nombre": nombre,
        "descripcion": descripcion,
        "cotizacion": 50.0,
        "grupo": grupo["id"]
    }
    db["amigos"].append(nuevo_amigo)

    # Cada activo tiene su usuario, que también pasa a ser miembro del grupo
    uid = ticker.replace("$", "").lower()
    asegurar_usuario(db, uid, nombre)
    if uid not in grupo["miembros"]:
        grupo["miembros"].append(uid)
    asegurar_saldo_grupo(grupo, uid)

    # Noticia de OPV
    titular = f"SALIDA A BOLSA: {ticker} debuta en el parqué con una cotización base de 50.0¢."
    db["noticias"].insert(0, {
        "id": f"not_{uuid.uuid4().hex[:6]}",
        "titular": titular,
        "hora": datetime.now().strftime("%H:%M"),
        "ticker": ticker,
        "grupo": grupo["id"]
    })

    guardar_db(db)
    return jsonify({"mensaje": "Amigo registrado con éxito", "amigo": nuevo_amigo}), 201


@app.route("/api/mercados", methods=["POST"])
def api_crear_mercado():
    """
    Crea un nuevo contrato flash.
    Pasa obligatoriamente por el filtro de la CNMV IA.
    Body: { creador, ticker, pregunta, grupo }
    """
    db = cargar_db()
    data = request.get_json() or {}
    grupo = get_grupo(db, data.get("grupo", "").strip())
    
    creador = data.get("creador", "").strip().lower()
    ticker = data.get("ticker", "").strip().upper()
    pregunta = data.get("pregunta", "").strip()

    if not grupo:
        return jsonify({"error": "El grupo es obligatorio"}), 400
    if not creador or not ticker or not pregunta:
        return jsonify({"error": "creador, ticker y pregunta son obligatorios"}), 400
    if not es_miembro(grupo, creador):
        return jsonify({"error": "No perteneces a este grupo"}), 403
    if not any(a["ticker"] == ticker and a.get("grupo") == grupo["id"] for a in db["amigos"]):
        return jsonify({"error": f"El ticker {ticker} no cotiza en este grupo"}), 400

    # 1. Filtro CNMV IA
    analisis = ai_service.validar_reto_cnmv(creador, ticker, pregunta)
    if not analisis.get("valido", False):
        penalizacion = analisis.get("penalizacion", 10.0)
        saldo_actual = get_saldo_grupo(grupo, creador)
        set_saldo_grupo(grupo, creador, saldo_actual - penalizacion)
        
        # Registrar noticia de sanción
        db["noticias"].insert(0, {
            "id": f"not_{uuid.uuid4().hex[:6]}",
            "titular": f"SANCIÓN CNMV: {creador} multado con -{penalizacion:.0f} $BROK por intentar colocar un contrato delirante en {ticker}.",
            "hora": datetime.now().strftime("%H:%M"),
            "ticker": ticker,
            "grupo": grupo["id"]
        })
        guardar_db(db)
        
        return jsonify({
            "error": "Contrato rechazado por la CNMV",
            "motivo": analisis.get("motivo", "Reto físicamente imposible o no verificable."),
            "penalizacion": penalizacion,
            "saldo_actual": get_saldo_grupo(grupo, creador)
        }), 400

    pregunta_final = analisis.get("pregunta_final") or pregunta

    # 2. Creación del Mercado con Liquidez Semilla Hanson
    precio_inicial = calcular_precio_lmsr(50.0, 50.0)  # 50.0¢
    hora_actual = datetime.now().strftime("%H:%M")

    nuevo_mercado = {
        "id": f"mkt_{uuid.uuid4().hex[:8]}",
        "grupo": grupo["id"],
        "ticker": ticker,
        "creador": creador,
        "pregunta": pregunta_final,
        "estado": "ABIERTO",
        "creado_en": datetime.now().isoformat(timespec="seconds"),
        "aceptado": False,
        "aceptado_por": None,
        "aceptado_en": None,
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
        "ticker": ticker,
        "grupo": grupo["id"]
    })

    guardar_db(db)
    return jsonify({
        "mensaje": "Mercado creado y validado por la CNMV",
        "mercado": nuevo_mercado,
        "analisis_cnmv": analisis
    }), 201


@app.route("/api/mercados/<mercado_id>/aceptar", methods=["POST"])
def api_aceptar_mercado(mercado_id):
    """El protagonista acepta el reto y abre el mercado a las apuestas."""
    db = cargar_db()
    data = request.get_json() or {}
    usuario = data.get("usuario", "").strip().lower()

    mercado = next((m for m in db["mercados"] if m["id"] == mercado_id), None)
    if not mercado:
        return jsonify({"error": "Mercado no encontrado"}), 404
    grupo = get_grupo(db, mercado.get("grupo", ""))
    if not grupo or not es_miembro(grupo, usuario):
        return jsonify({"error": "No perteneces a este grupo"}), 403
    if mercado["estado"] != "ABIERTO":
        return jsonify({"error": "El mercado ya está cerrado o resuelto"}), 400
    if not es_protagonista(db, mercado, usuario):
        return jsonify({"error": "Solo el protagonista del reto puede aceptarlo"}), 403

    if not mercado.get("aceptado"):
        mercado["aceptado"] = True
        mercado["aceptado_por"] = usuario
        mercado["aceptado_en"] = datetime.now().strftime("%H:%M")
        guardar_db(db)

    return jsonify({
        "mensaje": "Reto aceptado. El mercado queda abierto a apuestas.",
        "mercado": mercado
    })


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
    grupo = get_grupo(db, mercado.get("grupo", ""))
    if not grupo or not es_miembro(grupo, usuario):
        return jsonify({"error": "No perteneces a este grupo"}), 403

    if mercado["estado"] != "ABIERTO":
        return jsonify({"error": "El mercado ya está cerrado o resuelto"}), 400
    if not mercado.get("aceptado"):
        return jsonify({"error": "El protagonista aún no ha aceptado el reto."}), 400

    # REGLA 3: El protagonista no puede apostar en su propio mercado
    if es_protagonista(db, mercado, usuario):
        return jsonify({
            "error": "Fraude detectado: el protagonista no puede apostar en su propio reto."
        }), 400

    asegurar_usuario(db, usuario)

    # Comprobación de saldo del grupo
    saldo_usuario = get_saldo_grupo(grupo, usuario)
    if saldo_usuario < cantidad:
        return jsonify({
            "error": f"Saldo insuficiente. Tienes {saldo_usuario:.2f} $BROK disponibles en este grupo."
        }), 400

    # Descontar saldo al inversor
    set_saldo_grupo(grupo, usuario, saldo_usuario - cantidad)

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
        "ticker": mercado["ticker"],
        "grupo": mercado["grupo"]
    })

    guardar_db(db)
    return jsonify({
        "mensaje": "Apuesta procesada con éxito",
        "nuevo_precio": nuevo_precio,
        "saldo_restante": get_saldo_grupo(grupo, usuario),
        "mercado": mercado
    })


@app.route("/api/mercados/<mercado_id>/resolver", methods=["POST"])
def api_resolver(mercado_id):
    """
    Resuelve el mercado mediante foto analizada por el Oráculo Visual (o contra-foto VAR).
    Multipart form-data: usuario, imagen (captura de cámara), captura_ts (ms), origen="camara", es_impugnacion.
    """
    db = cargar_db()
    mercado = next((m for m in db["mercados"] if m["id"] == mercado_id), None)
    if not mercado:
        return jsonify({"error": "Mercado no encontrado"}), 404

    usuario = request.form.get("usuario", "").strip().lower()
    es_impugnacion = request.form.get("es_impugnacion", "false").lower() == "true"
    grupo = get_grupo(db, mercado.get("grupo", ""))
    if not grupo or not es_miembro(grupo, usuario):
        return jsonify({"error": "No perteneces a este grupo"}), 403

    if not es_impugnacion and mercado["estado"] == "ABIERTO" and not mercado.get("aceptado"):
        return jsonify({"error": "El reto todavía no ha sido aceptado por el protagonista."}), 400

    if request.form.get("origen", "").strip().lower() != "camara":
        return jsonify({"error": "La evidencia debe ser una foto tomada en directo con la cámara."}), 400
    try:
        captura_ts = float(request.form.get("captura_ts", ""))
    except (TypeError, ValueError):
        return jsonify({"error": "Falta la hora de captura de la foto en directo."}), 400
    if abs(time.time() * 1000 - captura_ts) > 120000:
        return jsonify({"error": "La foto no es actual. Vuelve a capturarla en directo."}), 400

    if "imagen" not in request.files:
        return jsonify({"error": "Se requiere una captura de cámara como evidencia"}), 400

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
        es_impugnacion=es_impugnacion,
        hora_actual=datetime.now().isoformat(timespec="seconds"),
        captura_ts=captura_ts,
        reto_creado=mercado.get("creado_en")
    )

    if veredicto_ia.get("error"):
        return jsonify({"error": veredicto_ia["error"]}), 503

    veredicto = veredicto_ia.get("veredicto", "NO")
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
                set_saldo_grupo(grupo, tramposo, get_saldo_grupo(grupo, tramposo) - multa_tramposo)
                mercado["tramposo"] = tramposo

            # Re-liquidar en favor del protagonista y de los inversores del SI
            protagonista = mercado["ticker"].replace("$", "").lower()
            asegurar_usuario(db, protagonista)
            
            # Short squeeze payout
            premio_protagonista = (0.30 * mercado["bote_no"]) + 25.0 + (multa_tramposo * 0.5)
            add_saldo_grupo(grupo, protagonista, premio_protagonista)

            # Reparto a inversores del SI
            total_apostado_si = sum(a["cantidad"] for a in mercado["apuestas"] if a["tipo"] == "SI")
            bote_repartible_si = (0.70 * mercado["bote_no"]) + 25.0 + (multa_tramposo * 0.5)
            if total_apostado_si > 0:
                for a in mercado["apuestas"]:
                    if a["tipo"] == "SI":
                        ganancia = a["cantidad"] + (a["cantidad"] / total_apostado_si) * bote_repartible_si
                        add_saldo_grupo(grupo, a["usuario"], ganancia)

            # Registrar resolución
            mercado["resolucion"] = {
                "resuelto_por": usuario,
                "imagen_url": imagen_url,
                "veredicto": "SI",
                "explicacion": f"VAR: Impugnación aceptada. {veredicto_ia.get('explicacion', '')} Multa de {multa_tramposo:.0f} $BROK aplicada al acusador falso.",
                "hora": hora_actual,
                "captura_ts": captura_ts
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
                "ticker": mercado["ticker"],
                "grupo": mercado["grupo"]
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
        "hora": hora_actual,
        "captura_ts": captura_ts
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
        add_saldo_grupo(grupo, protagonista, premio_protagonista)

        # Inversores de SI recuperan inversión + se reparten 0.70 * bote_no + 25 semilla
        bote_repartible = (0.70 * bote_no) + 25.0
        if total_si > 0:
            for a in mercado["apuestas"]:
                if a["tipo"] == "SI":
                    pago = a["cantidad"] + ((a["cantidad"] / total_si) * bote_repartible)
                    add_saldo_grupo(grupo, a["usuario"], pago)
    else:
        # REGLA 4.2: Falló el reto -> MULTA AL PROTAGONISTA
        # Pierde -0.20 * bote_si de su saldo
        multa_protagonista = 0.20 * bote_si
        set_saldo_grupo(grupo, protagonista, get_saldo_grupo(grupo, protagonista) - multa_protagonista)

        # Inversores del NO recuperan inversión + se reparten bote_si + multa cobrada
        bote_repartible = bote_si + multa_protagonista
        if total_no > 0:
            for a in mercado["apuestas"]:
                if a["tipo"] == "NO":
                    pago = a["cantidad"] + ((a["cantidad"] / total_no) * bote_repartible)
                    add_saldo_grupo(grupo, a["usuario"], pago)

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
        "ticker": mercado["ticker"],
        "grupo": mercado["grupo"]
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
    Restaura el estado global del mercado a un grupo vacío.
    """
    db = get_semilla_demo()
    guardar_db(db)
    return jsonify({"mensaje": "Mercado reseteado a la configuración inicial con éxito", "estado": db})


if __name__ == "__main__":
    print("[$BROKERS] Servidor financiero activo en http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
