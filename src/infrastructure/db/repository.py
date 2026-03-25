"""
Repository interfaces and implementations for data access.
"""

import sqlite3
from typing import Optional, List
from abc import ABC, abstractmethod
from ...domain.entities import User, Card, Mount, Role


class UserRepository(ABC):
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        pass

    @abstractmethod
    def save(self, user: User) -> None:
        pass

    @abstractmethod
    def find_all_students_in_class(self, class_name: str) -> List[User]:
        pass


class CardRepository(ABC):
    @abstractmethod
    def find_by_card_hash(self, card_hash: str) -> Optional[Card]:
        pass

    @abstractmethod
    def save(self, card: Card) -> None:
        pass

    @abstractmethod
    def find_by_username(self, username: str) -> Optional[Card]:
        pass


class MountRepository(ABC):
    @abstractmethod
    def save(self, mount: Mount) -> None:
        pass

    @abstractmethod
    def find_by_username(self, username: str) -> List[Mount]:
        pass


class SQLiteUserRepository(UserRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_by_username(self, username: str) -> Optional[User]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, role, class_name, uid FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                return User(
                    id=row[0],
                    username=row[1],
                    role=Role(row[2]),
                    class_name=row[3],
                    uid=row[4]
                )
        return None

    def save(self, user: User) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if user.id:
                cursor.execute("""
                    UPDATE users SET username=?, role=?, class_name=?, uid=? WHERE id=?
                """, (user.username, user.role.value, user.class_name, user.uid, user.id))
            else:
                cursor.execute("""
                    INSERT INTO users (username, role, class_name, uid) VALUES (?, ?, ?, ?)
                """, (user.username, user.role.value, user.class_name, user.uid))
            conn.commit()

    def find_all_students_in_class(self, class_name: str) -> List[User]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, role, class_name, uid FROM users
                WHERE role = ? AND class_name = ?
            """, (Role.STUDENT.value, class_name))
            return [
                User(id=row[0], username=row[1], role=Role(row[2]), class_name=row[3], uid=row[4])
                for row in cursor.fetchall()
            ]


class SQLiteCardRepository(CardRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_by_card_hash(self, card_hash: str) -> Optional[Card]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT card_hash, username, pin_hash FROM cards WHERE card_hash = ?", (card_hash,))
            row = cursor.fetchone()
            if row:
                return Card(card_hash=row[0], username=row[1], pin_hash=row[2])
        return None

    def save(self, card: Card) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cards (card_hash, username, pin_hash) VALUES (?, ?, ?)
            """, (card.card_hash, card.username, card.pin_hash))
            conn.commit()

    def find_by_username(self, username: str) -> Optional[Card]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT card_hash, username, pin_hash FROM cards WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                return Card(card_hash=row[0], username=row[1], pin_hash=row[2])
        return None


class SQLiteMountRepository(MountRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def save(self, mount: Mount) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mounts (username, mount_path, source_path) VALUES (?, ?, ?)
            """, (mount.username, mount.mount_path, mount.source_path))
            conn.commit()

    def find_by_username(self, username: str) -> List[Mount]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, mount_path, source_path FROM mounts WHERE username = ?", (username,))
            return [
                Mount(username=row[0], mount_path=row[1], source_path=row[2], permissions="")
                for row in cursor.fetchall()
            ]