from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from .settings import DB_PATH


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
               id INTEGER PRIMARY KEY,
               username TEXT UNIQUE,
               role TEXT,
               class_name TEXT,
               uid INTEGER
           )""")
    c.execute("""CREATE TABLE IF NOT EXISTS classes (name TEXT UNIQUE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS mounts (
               username TEXT,
               mount_path TEXT,
               source_path TEXT,
               PRIMARY KEY(username, mount_path)
           )""")
    c.execute("""CREATE TABLE IF NOT EXISTS teacher_classes (
               teacher TEXT,
               class_name TEXT,
               UNIQUE(teacher, class_name)
           )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cards (
               card_hash TEXT PRIMARY KEY,
               username  TEXT NOT NULL,
               pin_hash  TEXT NOT NULL,
               FOREIGN KEY(username) REFERENCES users(username)
           )""")
    conn.commit()
    conn.close()


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
