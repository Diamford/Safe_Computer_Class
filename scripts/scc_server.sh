#!/usr/bin/env bash
set -euo pipefail

# One-stop server installer/updater for Safe Computer Class HTTP API.
#
# Run on the Linux server as root (or via sudo).
#
# Examples:
#   sudo bash ./scripts/scc_server.sh install --src /root/Safe_Computer_Class
#   sudo bash ./scripts/scc_server.sh install --git https://github.com/<you>/<repo>.git --branch features
#   sudo bash ./scripts/scc_server.sh update
#   sudo bash ./scripts/scc_server.sh reinstall --git https://github.com/<you>/<repo>.git
#   sudo bash ./scripts/scc_server.sh status
#   sudo bash ./scripts/scc_server.sh logs
#
# What it does:
# - Installs code into /opt/safe_computer_class
# - Installs/updates systemd unit scc-http.service
# - Creates /etc/default/scc on first install
# - Enables + restarts the service

APP_DIR="/opt/safe_computer_class"
UNIT_DST="/etc/systemd/system/scc-http.service"
ENV_FILE="/etc/default/scc"
SERVICE="scc-http.service"

usage() {
  cat >&2 <<'EOF'
usage:
  scc_server.sh <install|update|reinstall|status|logs> [--git <url> [--branch <name>]] [--src <dir>]

notes:
  - install:   initial install (requires --git or --src)
  - update:    git pull in /opt/safe_computer_class and restart service
  - reinstall: wipe /opt/safe_computer_class and install again (requires --git or --src)
  - status:    systemctl status scc-http.service
  - logs:      journalctl -u scc-http.service
EOF
}

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "error: run as root (sudo)" >&2
    exit 1
  fi
}

ensure_systemd() {
  command -v systemctl >/dev/null 2>&1 || { echo "error: systemctl not found" >&2; exit 1; }
}

install_env_file_if_missing() {
  if [[ -f "${ENV_FILE}" ]]; then
    return
  fi
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
# Return SMB password to clients (DISABLED by default; use carefully)
# SAFE_CLASS_AUTH_RETURN_PASSWORD=1
# SAFE_CLASS_SMB_PASSWORD=secret
EOF
  chmod 644 "${ENV_FILE}"
}

install_unit_from_app_dir() {
  if [[ ! -f "${APP_DIR}/systemd/scc-http.service" ]]; then
    echo "error: ${APP_DIR}/systemd/scc-http.service not found" >&2
    exit 2
  fi
  cp -f "${APP_DIR}/systemd/scc-http.service" "${UNIT_DST}"
  systemctl daemon-reload
  systemctl enable --now "${SERVICE}"
  systemctl restart "${SERVICE}"
}

copy_from_src_dir() {
  local src_dir="$1"
  if [[ ! -f "${src_dir}/scc.py" ]]; then
    echo "error: ${src_dir}/scc.py not found" >&2
    exit 2
  fi
  if [[ ! -f "${src_dir}/systemd/scc-http.service" ]]; then
    echo "error: ${src_dir}/systemd/scc-http.service not found" >&2
    exit 2
  fi

  mkdir -p "${APP_DIR}"
  cp -f "${src_dir}/scc.py" "${APP_DIR}/scc.py"
  cp -f "${src_dir}/mb_mount.py" "${APP_DIR}/mb_mount.py" 2>/dev/null || true
  cp -f "${src_dir}/daemon.pyw" "${APP_DIR}/daemon.pyw" 2>/dev/null || true
  mkdir -p "${APP_DIR}/systemd" "${APP_DIR}/scripts"
  cp -f "${src_dir}/systemd/scc-http.service" "${APP_DIR}/systemd/scc-http.service"
  chmod 755 "${APP_DIR}/scc.py"
}

clone_or_update_git() {
  local git_url="$1"
  local branch="${2:-}"

  command -v git >/dev/null 2>&1 || { echo "error: git not found" >&2; exit 1; }

  if [[ -d "${APP_DIR}/.git" ]]; then
    cd "${APP_DIR}"
    git fetch --all --prune
    if [[ -n "${branch}" ]]; then
      git checkout "${branch}"
    fi
    git pull --ff-only
  else
    rm -rf "${APP_DIR}"
    if [[ -n "${branch}" ]]; then
      git clone --branch "${branch}" --depth 1 "${git_url}" "${APP_DIR}"
    else
      git clone --depth 1 "${git_url}" "${APP_DIR}"
    fi
  fi

  if [[ ! -f "${APP_DIR}/scc.py" ]]; then
    echo "error: ${APP_DIR}/scc.py not found after git operation" >&2
    exit 2
  fi
  chmod 755 "${APP_DIR}/scc.py"
}

cmd="${1:-}"
shift || true

git_url=""
branch=""
src_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --git) git_url="${2:-}"; shift 2 ;;
    --branch) branch="${2:-}"; shift 2 ;;
    --src) src_dir="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

need_root
ensure_systemd

case "${cmd}" in
  install)
    if [[ -z "${git_url}" && -z "${src_dir}" ]]; then
      echo "error: install requires --git or --src" >&2
      usage
      exit 2
    fi
    if [[ -n "${git_url}" ]]; then
      clone_or_update_git "${git_url}" "${branch}"
    else
      copy_from_src_dir "${src_dir}"
    fi
    install_env_file_if_missing
    install_unit_from_app_dir
    systemctl --no-pager --full status "${SERVICE}" || true
    ;;

  update)
    if [[ ! -d "${APP_DIR}/.git" ]]; then
      echo "error: ${APP_DIR} is not a git checkout. Use: reinstall --git <url>  (or install --src ...)" >&2
      exit 2
    fi
    clone_or_update_git "$(git -C "${APP_DIR}" remote get-url origin)" "${branch}"
    install_unit_from_app_dir
    systemctl --no-pager --full status "${SERVICE}" || true
    ;;

  reinstall)
    if [[ -z "${git_url}" && -z "${src_dir}" ]]; then
      echo "error: reinstall requires --git or --src" >&2
      usage
      exit 2
    fi
    rm -rf "${APP_DIR}"
    if [[ -n "${git_url}" ]]; then
      clone_or_update_git "${git_url}" "${branch}"
    else
      copy_from_src_dir "${src_dir}"
    fi
    install_env_file_if_missing
    install_unit_from_app_dir
    systemctl --no-pager --full status "${SERVICE}" || true
    ;;

  status)
    systemctl --no-pager --full status "${SERVICE}"
    ;;

  logs)
    journalctl -u "${SERVICE}" --no-pager -n 200
    ;;

  *)
    usage
    exit 2
    ;;
esac

