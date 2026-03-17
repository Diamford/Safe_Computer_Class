#!/usr/bin/env bash
set -euo pipefail

# Installs Safe Computer Class HTTP API as a systemd service (Linux).
# Expected usage (as root):
#   ./scripts/install_scc_http_service.sh /path/to/Safe_Computer_Class
#
# If you want a simpler "install/update/reinstall" flow, use:
#   ./scripts/scc_server.sh
#
# It will:
# - copy project files to /opt/safe_computer_class
# - install systemd unit scc-http.service
# - (optionally) create /etc/default/scc if missing
# - enable + restart the service

SRC_DIR="${1:-}"
if [[ -z "${SRC_DIR}" ]]; then
  echo "usage: $0 /path/to/Safe_Computer_Class" >&2
  exit 2
fi
if [[ ! -f "${SRC_DIR}/scc.py" ]]; then
  echo "error: ${SRC_DIR}/scc.py not found" >&2
  exit 2
fi
if [[ ! -f "${SRC_DIR}/systemd/scc-http.service" ]]; then
  echo "error: ${SRC_DIR}/systemd/scc-http.service not found" >&2
  exit 2
fi

INSTALL_DIR="/opt/safe_computer_class"
UNIT_DST="/etc/systemd/system/scc-http.service"
ENV_FILE="/etc/default/scc"

echo "[1/5] Installing files to ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
cp -f "${SRC_DIR}/scc.py" "${INSTALL_DIR}/scc.py"
cp -f "${SRC_DIR}/mb_mount.py" "${INSTALL_DIR}/mb_mount.py" 2>/dev/null || true
cp -f "${SRC_DIR}/daemon.pyw" "${INSTALL_DIR}/daemon.pyw" 2>/dev/null || true
mkdir -p "${INSTALL_DIR}/systemd"
cp -f "${SRC_DIR}/systemd/scc-http.service" "${INSTALL_DIR}/systemd/scc-http.service"
chmod 755 "${INSTALL_DIR}/scc.py"

echo "[2/5] Installing systemd unit to ${UNIT_DST}"
cp -f "${SRC_DIR}/systemd/scc-http.service" "${UNIT_DST}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[3/5] Creating default ${ENV_FILE}"
  cat > "${ENV_FILE}" <<'EOF'
# Safe Computer Class HTTP service configuration
#
# Listen host/port for scc.py serve
SCC_HOST=0.0.0.0
SCC_PORT=80
#
# Optional values returned to daemon.pyw via /api/scc/auth
# SAFE_CLASS_SMB_SERVER=192.168.0.10
# SAFE_CLASS_DRIVE=Z:
EOF
  chmod 644 "${ENV_FILE}"
else
  echo "[3/5] Keeping existing ${ENV_FILE}"
fi

echo "[4/5] Reloading systemd"
systemctl daemon-reload

echo "[5/5] Enabling and restarting service"
systemctl enable --now scc-http.service
systemctl restart scc-http.service
systemctl --no-pager --full status scc-http.service || true

echo "done"
