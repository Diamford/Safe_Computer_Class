from __future__ import annotations

import socket
import subprocess
from pathlib import Path

from .settings import MOUNTS_BASE, SAMBA_BASE
from .system import run_cmd, which


def ensure_groups() -> None:
    # Base role groups + shared group for mounts root.
    run_cmd(["groupadd", "-f", "teachers"])
    run_cmd(["groupadd", "-f", "students"])
    run_cmd(["groupadd", "-f", "admins"])
    run_cmd(["groupadd", "-f", "users"])


def ensure_samba_installed() -> None:
    if which("smbd"):
        return
    run_cmd(["apt", "update"])
    run_cmd(["apt", "install", "-y", "samba"])


def create_base_structure() -> None:
    base = Path(SAMBA_BASE)
    base.mkdir(exist_ok=True)
    Path(MOUNTS_BASE).mkdir(exist_ok=True)

    for d in ["for_teachers", "classes", "teachers", "students"]:
        (base / d).mkdir(exist_ok=True)

    run_cmd(["chmod", "750", str(base)])
    run_cmd(["chown", "root:users", str(base)])

    run_cmd(["chown", "root:teachers", str(base / "teachers")])
    run_cmd(["chmod", "770", str(base / "teachers")])
    run_cmd(["chown", "root:teachers", str(base / "for_teachers")])
    run_cmd(["chmod", "770", str(base / "for_teachers")])

    # Admins full access via ACL.
    run_cmd(["setfacl", "-R", "-m", "g:admins:rwx", str(base)], check=False)


def write_smb_conf() -> None:
    host = socket.gethostname()
    config = f"""[global]
workgroup = SCHOOL
server string = Safe Computer Class on {host}
security = user
map to guest = never
hide unreadable = yes

[school]
path = {MOUNTS_BASE}
valid users = @teachers @students @admins
writable = yes
browseable = yes
create mask = 0664
directory mask = 0775
"""
    Path("/etc/samba").mkdir(parents=True, exist_ok=True)
    Path("/etc/samba/smb.conf").write_text(config, encoding="utf-8")
    run_cmd(["pkill", "smbd", "&&", "smbd", "-D"])
    run_cmd(["/usr/sbin/smbd", "-F", "-S", "--no-process-group"])


def add_samba_user(username: str, password: str) -> None:
    # Safe: no shell, password via stdin (twice).
    smb_input = f"{password}\n{password}\n"
    ok, out = run_cmd(["smbpasswd", "-a", "-s", username], input_text=smb_input, check=False)
    if not ok:
        raise RuntimeError(f"smbpasswd failed for {username}: {out}")
    run_cmd(["smbpasswd", "-e", username], check=False)

