"""
Mount use case - handles setting up user mounts.
"""

from typing import List
from ..domain.entities import User, Mount
from ..domain.services.permission_service import PermissionService


class SetupMountsUseCase:
    """Use case for setting up user mount points."""

    def __init__(self, mount_repository, samba_adapter):
        self.mount_repository = mount_repository
        self.samba_adapter = samba_adapter

    def execute(self, user: User) -> List[Mount]:
        """
        Set up mount points for a user.
        1. Get required mounts based on permissions
        2. Create bind mounts
        3. Configure Samba shares
        """

        mount_paths = PermissionService.get_user_mounts(user)
        mounts = []

        for mount_path in mount_paths:
            # Determine source path based on mount path
            source_path = self._get_source_path(user, mount_path)

            mount = Mount(
                username=user.username,
                mount_path=mount_path,
                source_path=source_path,
                permissions=PermissionService.get_mount_permissions(user, Mount("", mount_path, source_path, ""))
            )

            # Create the bind mount
            self.samba_adapter.create_bind_mount(source_path, mount_path)

            # Save mount record
            self.mount_repository.save(mount)
            mounts.append(mount)

        return mounts

    def _get_source_path(self, user: User, mount_path: str) -> str:
        """Map mount path to actual source path."""
        if mount_path == f"/{user.username}":
            if user.role.name.lower() == "student":
                return f"/srv/samba/students/{user.class_name}/{user.username}"
            else:
                return f"/srv/samba/teachers/{user.username}"
        elif mount_path == f"/{user.class_name}":
            return f"/srv/samba/classes/{user.class_name}"
        elif mount_path == "/teachers":
            return f"/srv/samba/teachers/{user.username}"
        elif mount_path == "/for_teachers":
            return "/srv/samba/for_teachers"
        else:
            raise ValueError(f"Unknown mount path: {mount_path}")