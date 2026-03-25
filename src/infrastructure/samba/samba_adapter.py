"""
Samba adapter - handles Samba configuration and operations.
"""

import subprocess
import os
from typing import List


class SambaAdapter:
    """Adapter for Samba operations using subprocess calls."""

    def __init__(self, samba_config_path: str = "/etc/samba/smb.conf"):
        self.samba_config_path = samba_config_path

    def create_samba_user(self, username: str, password: str) -> None:
        """Create a Samba user with password."""
        # Add system user first (if not exists)
        try:
            subprocess.run(["useradd", "-M", "-s", "/sbin/nologin", username],
                         check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass  # User might already exist

        # Set Samba password
        process = subprocess.Popen(["smbpasswd", "-a", username],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate(input=f"{password}\n{password}\n".encode())
        if process.returncode != 0:
            raise RuntimeError(f"Failed to create Samba user {username}")

    def reload_samba_config(self) -> None:
        """Reload Samba configuration."""
        subprocess.run(["smbcontrol", "all", "reload-config"], check=True)

    def create_bind_mount(self, source_path: str, mount_path: str) -> None:
        """Create a bind mount."""
        os.makedirs(mount_path, exist_ok=True)
        subprocess.run(["mount", "--bind", source_path, mount_path], check=True)

    def remove_bind_mount(self, mount_path: str) -> None:
        """Remove a bind mount."""
        subprocess.run(["umount", mount_path], check=True)

    def set_share_permissions(self, share_name: str, permissions: str) -> None:
        """Set permissions on a Samba share."""
        # This would modify smb.conf - simplified for now
        pass

    def get_samba_users(self) -> List[str]:
        """Get list of Samba users."""
        result = subprocess.run(["pdbedit", "-L"], capture_output=True, text=True, check=True)
        return [line.split(":")[0] for line in result.stdout.strip().split("\n") if line]