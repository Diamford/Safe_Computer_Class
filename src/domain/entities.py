"""
Domain entities for Safe Computer Class system.
Pure business logic objects without external dependencies.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class Role(Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


@dataclass
class User:
    """Domain entity representing a system user."""
    username: str
    role: Role
    class_name: Optional[str] = None
    uid: Optional[int] = None
    id: Optional[int] = None

    def __post_init__(self):
        if self.role == Role.STUDENT and not self.class_name:
            raise ValueError("Students must have a class_name")


@dataclass
class Card:
    """Domain entity representing an RFID card."""
    card_hash: str
    username: str
    pin_hash: Optional[str] = None

    def has_pin(self) -> bool:
        return self.pin_hash is not None


@dataclass
class Class:
    """Domain entity representing a school class."""
    name: str
    teacher_username: Optional[str] = None


@dataclass
class Mount:
    """Domain entity representing a mount point."""
    username: str
    mount_path: str
    source_path: str
    permissions: str  # "RW" or "RO"


@dataclass
class AuthResult:
    """Result of authentication process."""
    user: User
    server: str
    drive_letter: str
    password: Optional[str] = None
    success: bool = True
    message: Optional[str] = None