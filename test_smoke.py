import json
import pytest
from app import app, cargar_db, get_semilla_demo, guardar_db, calcular_precio_lmsr
import ai_service

def test_lmsr_math():
    # q_si = 50, q_no = 50 -> 50.0%
    p = calcular_precio_lmsr(50.0, 50.0)
    assert p == 50.0

    # q_si = 100, q_no = 50 -> > 50%
    p_up = calcular_precio_lmsr(100.0, 50.0)
    assert p_up > 50.0

def test_ai_service_fallback():
    # Absurd challenge
    res_absurdo = ai_service.validar_reto_cnmv("samu", "$SAMU", "Ir a la Antártida hoy mismo en patinete")
    assert res_absurdo["valido"] is False
    assert res_absurdo["penalizacion"] == 10.0

    # Reasonable challenge
    res_ok = ai_service.validar_reto_cnmv("samu", "$SAMU", "Llegar puntual a la clase de finanzas")
    assert res_ok["valido"] is True
    assert "Ser capaz de" in res_ok["pregunta_final"]

    # Wallstreet headline
    titular = ai_service.generar_titular_wallstreet("apuesta", {"ticker": "$SAMU", "usuario": "mito", "cantidad": 50})
    assert isinstance(titular, str) and len(titular) > 5

def test_registro_usuario_crea_ticker():
    client = app.test_client()
    client.post("/api/reset")

    res = client.post("/api/usuarios", json={"usuario": "pepe", "nombre": "Pepe"})
    assert res.status_code == 201
    assert res.get_json()["ticker"] == "$PEPE"

    estado = client.get("/api/estado").get_json()
    assert any(a["ticker"] == "$PEPE" for a in estado["amigos"])
    assert any(u["usuario"] == "pepe" for u in estado["ranking"])

    # Repetir el registro no duplica el ticker
    assert client.post("/api/usuarios", json={"usuario": "pepe", "nombre": "Pepe"}).status_code == 200
    estado = client.get("/api/estado").get_json()
    assert sum(a["ticker"] == "$PEPE" for a in estado["amigos"]) == 1


def test_api_routes():
    client = app.test_client()
    
    # 1. Reset
    res_reset = client.post("/api/reset")
    assert res_reset.status_code == 200

    # 2. Get estado
    res_estado = client.get("/api/estado")
    assert res_estado.status_code == 200
    data = res_estado.get_json()
    assert "amigos" in data
    assert "mercados" in data
    assert "ranking" in data
    assert "noticias" in data

    # 3. Add amigo
    res_amigo = client.post("/api/amigos", json={"ticker": "$NUEVO", "nombre": "Nuevo Amigo"})
    assert res_amigo.status_code == 201

    # 4. Create mercado with valid challenge
    res_mercado = client.post("/api/mercados", json={
        "creador": "mito",
        "ticker": "$NUEVO",
        "pregunta": "Ser capaz de estudiar 2 horas seguidas"
    })
    assert res_mercado.status_code == 201
    mkt_id = res_mercado.get_json()["mercado"]["id"]

    # 5. No bets until the protagonist accepts
    res_pending = client.post(f"/api/mercados/{mkt_id}/apostar", json={
        "usuario": "samu",
        "tipo": "SI",
        "cantidad": 25.0
    })
    assert res_pending.status_code == 400
    assert "aceptado" in res_pending.get_json()["error"]

    # 6. Only the protagonist can accept
    res_wrong_accept = client.post(f"/api/mercados/{mkt_id}/aceptar", json={"usuario": "samu"})
    assert res_wrong_accept.status_code == 403

    res_accept = client.post(f"/api/mercados/{mkt_id}/aceptar", json={"usuario": "nuevo"})
    assert res_accept.status_code == 200
    assert res_accept.get_json()["mercado"]["aceptado"] is True

    # 7. Place bet after acceptance
    res_bet = client.post(f"/api/mercados/{mkt_id}/apostar", json={
        "usuario": "samu",
        "tipo": "SI",
        "cantidad": 25.0
    })
    assert res_bet.status_code == 200
    assert res_bet.get_json()["nuevo_precio"] > 50.0

    # 8. Protagonist cannot bet either side on their own market
    for tipo in ("SI", "NO"):
        res_fraud = client.post(f"/api/mercados/{mkt_id}/apostar", json={
            "usuario": "nuevo",
            "tipo": tipo,
            "cantidad": 10.0
        })
        assert res_fraud.status_code == 400
        assert "Fraude detectado" in res_fraud.get_json()["error"]

    # 9. Check serving static index.html
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert b"$BROKERS" in res_home.data
    assert b"Bloomberg" in res_home.data

    # 10. Resolver mercado
    import io
    fake_img = (io.BytesIO(b"fake image data"), "test.jpg")
    res_solve = client.post(
        f"/api/mercados/{mkt_id}/resolver",
        data={"usuario": "samu", "imagen": fake_img, "es_impugnacion": "false"},
        content_type="multipart/form-data"
    )
    assert res_solve.status_code == 200
    assert res_solve.get_json()["mercado"]["estado"] == "RESUELTO"
