from __future__ import annotations

import os
import socket
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    import pwd  # Linux only
except Exception:  # pragma: no cover
    pwd = None

from . import db
from .settings import DB_PATH, MOUNTS_BASE, SAMBA_BASE
from .samba import add_samba_user, create_base_structure, ensure_groups, ensure_samba_installed, write_smb_conf
from .system import run_cmd


class SchoolSamba:
    def __init__(self) -> None:
        if pwd is None:
            raise RuntimeError("SCC server requires Linux (pwd/groupadd/useradd are not available on Windows).")

        self.base = Path(SAMBA_BASE)
        self.base.mkdir(exist_ok=True)
        Path(MOUNTS_BASE).mkdir(exist_ok=True)

        db.init_db()
        ensure_groups()

        # Auto-init structure on first run.
        classes_dir = self.base / "classes"
        students_dir = self.base / "students"
        teachers_dir = self.base / "teachers"
        if not (classes_dir.exists() and students_dir.exists() and teachers_dir.exists()):
            create_base_structure()
            try:
                ensure_samba_installed()
                write_smb_conf()
            except Exception as exc:
                print(f"warning: samba auto-init failed: {exc}")

    def print_help(self) -> None:
        host = socket.gethostname()
        lines = [
            "SAFE COMPUTER CLASS v0.5",
            "",
            f"share: \\\\{host}\\school",
            "",
            "commands:",
            "  init                             init structure and samba",
            "  addclass <class>                 create class",
            "  addteacher <name> <uid> <pass>   add teacher (no class yet)",
            "  addteacherclass <name> <class>   link teacher to class",
            "  delteacherclass <name> <class>   unlink teacher from class",
            "  addstudent <name> <class> <uid> <pass>   add student",
            "  delclass <class>                 delete class (if no users)",
            "  deluser <name>                   delete user",
            "  mount <name>                     remount user binds",
            "  umount <name>                    unmount user binds",
            "  list                             list users",
            "  listclasses                      list classes",
            "  status                           show status",
            "  restart                          restart samba with config",
            "  backup                           backup database",
            "  serve [host] [port]              run HTTP server for RFID/PIN",
            "  help                             show this help",
        ]
        print("\n".join(lines))

    def init(self) -> None:
        ensure_samba_installed()
        create_base_structure()
        write_smb_conf()

    def add_class(self, class_name: str) -> None:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO classes (name) VALUES (?)", (class_name,))
            conn.commit()

        class_dir = self.base / "classes" / class_name
        students_dir = self.base / "students" / class_name
        class_dir.mkdir(exist_ok=True)
        students_dir.mkdir(exist_ok=True)

        run_cmd(["chown", "root:teachers", str(class_dir)])
        run_cmd(["chmod", "770", str(class_dir)])
        run_cmd(["setfacl", "-m", "g:students:rx", str(class_dir)], check=False)

        run_cmd(["chown", "root:teachers", str(students_dir)])
        run_cmd(["chmod", "770", str(students_dir)])

    def get_user_info(self, username: str):
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT role, class_name FROM users WHERE username = ?", (username,))
            return c.fetchone()

    def get_teacher_classes(self, teacher: str) -> list[str]:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT class_name FROM teacher_classes WHERE teacher = ?", (teacher,))
            return [r[0] for r in c.fetchall()]

    def get_class_students(self, class_name: str) -> list[str]:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT username FROM users WHERE role = 'student' AND class_name = ?",
                (class_name,),
            )
            return [r[0] for r in c.fetchall()]

    def link_teacher_class(self, teacher: str, class_name: str) -> None:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO teacher_classes (teacher, class_name) VALUES (?, ?)",
                (teacher, class_name),
            )
            conn.commit()

    def unlink_teacher_class(self, teacher: str, class_name: str) -> None:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute(
                "DELETE FROM teacher_classes WHERE teacher = ? AND class_name = ?",
                (teacher, class_name),
            )
            conn.commit()

    def get_user_home(self, username: str, role: str, class_name: str | None) -> Path:
        if role == "teacher":
            return self.base / "teachers" / username
        if role == "student":
            return self.base / "students" / (class_name or "") / username
        return self.base / "admin"

    def add_user(self, username: str, role: str, class_name: str | None, uid: int, password: str) -> bool:
        if pwd is None:
            raise RuntimeError("This command is supported only on Linux (pwd module unavailable).")

        try:
            pw = pwd.getpwnam(username)
            uid = pw.pw_uid
            home = Path(pw.pw_dir)
        except KeyError:
            home = self.get_user_home(username, role, class_name)
            home.mkdir(parents=True, exist_ok=True)
            ok, out = run_cmd(
                [
                    "useradd",
                    "-m",
                    "-d",
                    str(home),
                    "-u",
                    str(uid),
                    "-G",
                    f"{role}s,users",
                    "-s",
                    "/bin/bash",
                    username,
                ]
            )
            if not ok:
                print(f"failed to create system user {username}: {out}")
                return False

        run_cmd(["chpasswd"], input_text=f"{username}:{password}\n")

        with db.connect() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO users (username, role, class_name, uid) VALUES (?, ?, ?, ?)",
                (username, role, class_name, uid),
            )
            conn.commit()

        add_samba_user(username, password)

        self.setup_user_permissions(username, role, class_name)
        self.create_user_mounts(username, role)
        return True

    def setup_user_permissions(self, username: str, role: str, class_name: str | None) -> None:
        home = self.get_user_home(username, role, class_name)
        run_cmd(["chown", "-R", f"{username}:{role}s", str(home)])

        if role == "teacher":
            run_cmd(["chmod", "-R", "770", str(home)])
            run_cmd(
                ["setfacl", "-R", "-m", f"u:{username}:rwx", str(self.base / "for_teachers")]
            )
        elif role == "student":
            run_cmd(["chmod", "-R", "700", str(home)])
            run_cmd(["setfacl", "-R", "-m", "g:teachers:rwx", str(home)], check=False)

        run_cmd(["chmod", "750", str(self.base)])
        run_cmd(["chown", "root:users", str(Path(MOUNTS_BASE))])
        run_cmd(["chmod", "750", str(Path(MOUNTS_BASE))])
        run_cmd(["setfacl", "-R", "-m", "g:admins:rwx", str(Path(MOUNTS_BASE))], check=False)

    def create_user_mounts(self, username: str, role: str) -> None:
        mount_base = Path(MOUNTS_BASE) / username
        mount_base.mkdir(parents=True, exist_ok=True)

        run_cmd(["chown", "-R", f"{username}:{role}s", str(mount_base)])
        run_cmd(["chmod", "770" if role == "teacher" else "700", str(mount_base)])
        run_cmd(["setfacl", "-R", "-m", "g:admins:rwx", str(mount_base)], check=False)

        mounts: list[tuple[Path, Path]] = []
        if role == "teacher":
            classes = self.get_teacher_classes(username)
            mounts.append((mount_base / "teachers", self.base / "teachers" / username))
            mounts.append((mount_base / "for_teachers", self.base / "for_teachers"))
            for cls in classes:
                class_root = mount_base / cls
                mounts.append((class_root, self.base / "classes" / cls))
                for student in self.get_class_students(cls):
                    student_src = self.base / "students" / cls / student
                    student_mount = class_root / student
                    mounts.append((student_mount, student_src))
        elif role == "student":
            info = self.get_user_info(username)
            class_name = info[1] if info else None
            if not class_name:
                print(f"no class for student {username}, cannot create mounts")
                return
            self.add_class(class_name)
            student_home = self.base / "students" / class_name / username
            class_dir = self.base / "classes" / class_name
            mounts = [(mount_base, student_home), (mount_base / class_name, class_dir)]
        else:
            print(f"unknown role {role} for {username}, no mounts created")
            return

        with db.connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM mounts WHERE username = ?", (username,))

            for m_path, source in mounts:
                m_path.mkdir(parents=True, exist_ok=True)
                run_cmd(["mount", "--bind", str(source), str(m_path)])
                c.execute(
                    "INSERT INTO mounts (username, mount_path, source_path) VALUES (?, ?, ?)",
                    (username, str(m_path), str(source)),
                )
            conn.commit()

    def umount_user(self, username: str) -> None:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT mount_path FROM mounts WHERE username = ?", (username,))
            mounts = c.fetchall()
        for (m_path,) in mounts:
            run_cmd(["umount", m_path], check=False)

    def del_user(self, username: str) -> None:
        info = self.get_user_info(username)
        if not info:
            print(f"user {username} not found in db")
            return
        role, _ = info
        self.umount_user(username)
        run_cmd(["smbpasswd", "-x", username], check=False)
        run_cmd(["userdel", "-r", username], check=False)
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE username = ?", (username,))
            c.execute("DELETE FROM mounts WHERE username = ?", (username,))
            if role == "teacher":
                c.execute("DELETE FROM teacher_classes WHERE teacher = ?", (username,))
            conn.commit()

    def del_class(self, class_name: str) -> bool:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT username FROM users WHERE class_name = ?", (class_name,))
            students = c.fetchall()
            c.execute("SELECT teacher FROM teacher_classes WHERE class_name = ?", (class_name,))
            teachers = c.fetchall()
            if students or teachers:
                print(f"class {class_name} has users, remove/unlink them first")
                return False
            c.execute("DELETE FROM classes WHERE name = ?", (class_name,))
            conn.commit()

        class_dir = self.base / "classes" / class_name
        students_dir = self.base / "students" / class_name
        if class_dir.exists() and not any(class_dir.iterdir()):
            class_dir.rmdir()
        if students_dir.exists() and not any(students_dir.iterdir()):
            students_dir.rmdir()
        return True

    def list_users(self) -> None:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT username, role, class_name, uid FROM users")
            users = c.fetchall()
        if not users:
            print("no users")
            return
        print("users:")
        print("name           role       class      uid")
        print("--------------------------------------------")
        for username, role, cls, uid in users:
            print(f"{username:<14} {role:<9} {str(cls):<10} {str(uid):<7}")

    def list_classes(self) -> None:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM classes")
            classes = c.fetchall()
        print("classes:")
        if not classes:
            print("  (none)")
            return
        for (name,) in classes:
            print(f"  {name}")

    def status(self) -> None:
        print("status:")
        self.list_users()
        self.list_classes()
        result = subprocess.run(["systemctl", "is-active", "smbd"], capture_output=True, text=True)
        state = "active" if result.returncode == 0 else "inactive"
        print(f"smbd: {state}")

    def backup(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{SAMBA_BASE}/school_backup_{ts}.db"
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(backup_path)
        src.backup(dst)
        src.close()
        dst.close()
        print(f"db backup created: {backup_path}")

    # --- RFID/PIN tables ---
    def register_card(self, username: str, card_hash: str, pin_hash: str) -> tuple[bool, str]:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            if not c.fetchone():
                return False, "user not found"
            c.execute(
                "INSERT OR REPLACE INTO cards (card_hash, username, pin_hash) VALUES (?, ?, ?)",
                (card_hash, username, pin_hash),
            )
            conn.commit()
        return True, "card registered"

    def verify_card(self, card_hash: str) -> tuple[bool, bool]:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT username FROM cards WHERE card_hash = ?", (card_hash,))
            row = c.fetchone()
        if not row:
            return False, False
        return True, True

    def verify_pin(self, card_hash: str, pin_hash: str) -> bool:
        with db.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT pin_hash FROM cards WHERE card_hash = ?", (card_hash,))
            row = c.fetchone()
        if not row:
            return False
        return row[0] == pin_hash

    def auth_uuid_pin(self, uuid: str, pin_hash: str) -> tuple[bool, dict]:
        uuid = (uuid or "").strip()
        pin_hash = (pin_hash or "").strip()
        if not uuid or not pin_hash:
            return False, {}

        with db.connect() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT username, pin_hash FROM cards WHERE card_hash = ?",
                (uuid,),
            )
            row = c.fetchone()
        if not row:
            return False, {}
        username, stored_pin_hash = row
        if stored_pin_hash != pin_hash:
            return False, {}

        smb_server = (
            os.environ.get("SAFE_CLASS_SMB_SERVER", "").strip()
            or os.environ.get("SAFE_CLASS_SERVER", "").strip()
            or socket.gethostname()
        )
        drive_letter = os.environ.get("SAFE_CLASS_DRIVE", "Z:").strip() or "Z:"
        payload = {"server": smb_server, "username": str(username), "drive_letter": drive_letter}

        return_password = os.environ.get("SAFE_CLASS_AUTH_RETURN_PASSWORD", "").strip()
        if return_password.lower() in ("1", "true", "yes", "on"):
            payload["password"] = os.environ.get("SAFE_CLASS_SMB_PASSWORD", "")

        return True, payload

