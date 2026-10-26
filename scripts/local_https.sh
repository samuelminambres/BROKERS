#!/usr/bin/env bash
set -euo pipefail

# Levanta la app por HTTPS en la Wi-Fi local para que el móvil pueda usar la cámara.
# Uso: ./scripts/local_https.sh
# Requiere openssl y el entorno virtual .venv.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
TLS_DIR="${TLS_DIR:-$ROOT/.local-tls}"
HTTPS_PORT="${HTTPS_PORT:-5443}"
LAN_IP="${LAN_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"

if [[ -z "${LAN_IP:-}" ]]; then
  echo "No se pudo detectar la IP local. Define LAN_IP=192.168.x.x" >&2
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "No existe $PYTHON. Crea el entorno con: python3 -m venv .venv" >&2
  exit 1
fi
command -v openssl >/dev/null || { echo "Falta openssl" >&2; exit 1; }

mkdir -p "$TLS_DIR"
if [[ ! -f "$TLS_DIR/server.crt" || ! -f "$TLS_DIR/server.key" ]]; then
  echo "Generando CA y certificado local para $LAN_IP..."
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$TLS_DIR/rootCA.key" -out "$TLS_DIR/rootCA.crt" \
    -days 3650 -subj "/CN=BROKERS Local CA" >/dev/null 2>&1
  openssl req -newkey rsa:2048 -nodes \
    -keyout "$TLS_DIR/server.key" -out "$TLS_DIR/server.csr" \
    -subj "/CN=$LAN_IP" >/dev/null 2>&1
  cat > "$TLS_DIR/server.ext" <<EOF
subjectAltName=DNS:localhost,DNS:brokers.local,DNS:fedora.local,IP:127.0.0.1,IP:$LAN_IP
extendedKeyUsage=serverAuth
keyUsage=digitalSignature,keyEncipherment
EOF
  openssl x509 -req -in "$TLS_DIR/server.csr" \
    -CA "$TLS_DIR/rootCA.crt" -CAkey "$TLS_DIR/rootCA.key" \
    -CAcreateserial -out "$TLS_DIR/server.crt" -days 825 -sha256 \
    -extfile "$TLS_DIR/server.ext" >/dev/null 2>&1
fi

# El CA se sirve por la app HTTP para instalarlo en el móvil.
cp "$TLS_DIR/rootCA.crt" "$ROOT/static/rootCA.crt"

echo
echo "App HTTPS:       https://$LAN_IP:$HTTPS_PORT"
echo "CA para el móvil: http://$LAN_IP:5000/static/rootCA.crt"
echo "Instala el CA en el móvil y abre la URL HTTPS. Ctrl-C para parar."
echo

exec "$PYTHON" -c "from backend.app import app; app.run(host='0.0.0.0', port=$HTTPS_PORT, debug=False, use_reloader=False, ssl_context=('$TLS_DIR/server.crt', '$TLS_DIR/server.key'))"
