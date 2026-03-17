#!/usr/bin/env bash
set -euo pipefail

# Uninstalls Safe Computer Class HTTP API systemd service (Linux).
# Expected usage (as root):
#   ./scripts/uninstall_scc_http_service.sh

UNIT_DST="/etc/systemd/system/scc-http.service"
INSTALL_DIR="/opt/safe_computer_class"

systemctl disable --now scc-http.service 2>/dev/null || true

rm -f "${UNIT_DST}"
systemctl daemon-reload

echo "removed unit: ${UNIT_DST}"
echo "project files left in: ${INSTALL_DIR} (remove manually if desired)"
