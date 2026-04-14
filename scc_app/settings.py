from __future__ import annotations

import os


SAMBA_BASE = os.environ.get("SCC_SAMBA_BASE", "/srv/samba")
MOUNTS_BASE = os.environ.get("SCC_MOUNTS_BASE", "/srv/samba_mounts")
DB_PATH = os.environ.get("SCC_DB_PATH", f"{SAMBA_BASE}/school.db")

# In containers we usually run as root already; avoid forcing sudo.
USE_SUDO = os.environ.get("SCC_USE_SUDO", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

