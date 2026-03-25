"""
Permission service - encapsulates RBAC business rules.
Pure domain logic without external dependencies.
"""

from typing import List
from ..entities import User, Role, Mount
from ..exceptions import PermissionDeniedError


class PermissionService:
    """Service for checking user permissions based on roles."""

    @staticmethod
    def can_access_personal_folder(user: User) -> bool:
        """All users can access their personal folder with RW."""
        return True

    @staticmethod
    def can_access_class_folder(user: User, class_name: str) -> bool:
        """Check if user can access a class folder."""
        if user.role == Role.ADMIN:
            return True
        if user.role == Role.TEACHER:
            return True  # Teachers can access any class folder
        if user.role == Role.STUDENT:
            return user.class_name == class_name
        return False

    @staticmethod
    def can_access_student_folder(user: User, target_student_class: str) -> bool:
        """Check if user can access another student's folder."""
        if user.role == Role.ADMIN:
            return True
        if user.role == Role.TEACHER:
            return True  # Teachers can access student folders for grading
        return False  # Students cannot access other students' folders

    @staticmethod
    def can_access_teachers_folder(user: User) -> bool:
        """Check if user can access teachers-only resources."""
        return user.role in [Role.TEACHER, Role.ADMIN]

    @staticmethod
    def get_mount_permissions(user: User, mount: Mount) -> str:
        """Get the appropriate permissions for a user on a mount point."""
        if mount.username == user.username:
            return "RW"  # Personal folder

        # Class folder
        if "/classes/" in mount.source_path:
            class_name = mount.source_path.split("/classes/")[1].split("/")[0]
            if PermissionService.can_access_class_folder(user, class_name):
                return "RW" if user.role == Role.TEACHER else "RO"
            else:
                raise PermissionDeniedError(f"User {user.username} cannot access class {class_name}")

        # Student folder
        if "/students/" in mount.source_path:
            # Extract class from path like /students/9_A/student001
            parts = mount.source_path.split("/students/")[1].split("/")
            if len(parts) >= 2:
                student_class = parts[0]
                if PermissionService.can_access_student_folder(user, student_class):
                    return "RW"
                else:
                    raise PermissionDeniedError(f"User {user.username} cannot access student folder in class {student_class}")

        # Teachers folder
        if "/teachers/" in mount.source_path or "/for_teachers" in mount.source_path:
            if PermissionService.can_access_teachers_folder(user):
                return "RW"
            else:
                raise PermissionDeniedError(f"User {user.username} cannot access teachers resources")

        raise PermissionDeniedError(f"No permissions defined for mount {mount.mount_path}")

    @staticmethod
    def get_user_mounts(user: User) -> List[str]:
        """Get list of mount paths a user should have access to."""
        mounts = []

        # Personal folder
        mounts.append(f"/{user.username}")

        # Class folder
        if user.class_name:
            mounts.append(f"/{user.class_name}")

        # Teachers resources
        if user.role in [Role.TEACHER, Role.ADMIN]:
            mounts.append("/teachers")
            mounts.append("/for_teachers")

        return mounts