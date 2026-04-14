from __future__ import annotations

import subprocess
from typing import Iterable, Optional

from .settings import USE_SUDO


def run_cmd(cmd: list[str], *, input_text: Optional[str] = None, check: bool = True) -> tuple[bool, str]:
    full_cmd = (["sudo"] + cmd) if USE_SUDO else cmd
    try:
        result = subprocess.run(
            full_cmd,
            input=input_text,
            check=check,
            capture_output=True,
            text=True,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as exc:
        return False, exc.stderr


def which(binary: str) -> bool:
    return subprocess.run(["which", binary], capture_output=True).returncode == 0

