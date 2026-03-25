"""
Main entry point for the Safe Computer Class server.
"""

import sys
import argparse
from .config import config
from .presentation.api import create_app


def init_database(db_path: str):
    """Initialize the database with required tables."""
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                role TEXT,
                class_name TEXT,
                uid INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                name TEXT PRIMARY KEY
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mounts (
                username TEXT,
                mount_path TEXT,
                source_path TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teacher_classes (
                teacher TEXT,
                class_name TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                card_hash TEXT PRIMARY KEY,
                username TEXT,
                pin_hash TEXT
            )
        """)

        conn.commit()
    print(f"Database initialized at {db_path}")


def add_student(username: str, class_name: str, db_path: str):
    """Add a student to the system."""
    from .infrastructure.db.repository import SQLiteUserRepository
    from .domain.entities import User, Role

    repo = SQLiteUserRepository(db_path)
    user = User(username=username, role=Role.STUDENT, class_name=class_name)
    repo.save(user)
    print(f"Student {username} added to class {class_name}")


def add_teacher(username: str, db_path: str):
    """Add a teacher to the system."""
    from .infrastructure.db.repository import SQLiteUserRepository
    from .domain.entities import User, Role

    repo = SQLiteUserRepository(db_path)
    user = User(username=username, role=Role.TEACHER)
    repo.save(user)
    print(f"Teacher {username} added")


def serve(host: str, port: int, db_path: str):
    """Start the HTTP server."""
    config.load_from_env()
    config._config.update({
        'DATABASE_PATH': db_path,
        'HOST': host,
        'PORT': port
    })

    app = create_app(config._config)
    print(f"Starting server on {host}:{port}")
    app.run(host=host, port=port, debug=config.debug)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Safe Computer Class Server')
    parser.add_argument('command', choices=['init', 'addstudent', 'addteacher', 'serve'])
    parser.add_argument('--db', default='/srv/samba/school.db', help='Database path')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=80, help='Server port')
    parser.add_argument('--username', help='Username for add commands')
    parser.add_argument('--class', dest='class_name', help='Class name for student')

    args = parser.parse_args()

    if args.command == 'init':
        init_database(args.db)
    elif args.command == 'addstudent':
        if not args.username or not args.class_name:
            print("Error: --username and --class required for addstudent")
            sys.exit(1)
        add_student(args.username, args.class_name, args.db)
    elif args.command == 'addteacher':
        if not args.username:
            print("Error: --username required for addteacher")
            sys.exit(1)
        add_teacher(args.username, args.db)
    elif args.command == 'serve':
        serve(args.host, args.port, args.db)


if __name__ == '__main__':
    main()