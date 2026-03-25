"""
Linux user adapter - handles system user operations.
"""

import subprocess
import pwd
from typing import Optional


class LinuxUserAdapter:
    """Adapter for Linux user management operations."""

    def create_user(self, username: str, uid: Optional[int] = None) -> None:
        """Create a system user."""
        cmd = ["useradd", "-M", "-s", "/sbin/nologin"]
        if uid:
            cmd.extend(["-u", str(uid)])
        cmd.append(username)

        subprocess.run(cmd, check=True)

    def delete_user(self, username: str) -> None:
        """Delete a system user."""
        subprocess.run(["userdel", username], check=True)

    def user_exists(self, username: str) -> bool:
        """Check if user exists."""
        try:
            pwd.getpwnam(username)
            return True
        except KeyError:
            return False

    def add_to_group(self, username: str, group: str) -> None:
        """Add user to a group."""
        subprocess.run(["usermod", "-a", "-G", group, username], check=True)

    def set_password(self, username: str, password: str) -> None:
        """Set user password."""
        process = subprocess.Popen(["passwd", username],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate(input=f"{password}\n{password}\n".encode())
        if process.returncode != 0:
            raise RuntimeError(f"Failed to set password for {username}")

    def get_next_uid(self, min_uid: int = 1000) -> int:
        """Get next available UID."""
        # Simplified - in real implementation, check /etc/passwd
        return min_uid