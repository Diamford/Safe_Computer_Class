#!/usr/bin/env python3

# SAFE COMPUTER CLASS v0.5



import sys
import json
import subprocess
import pwd
import sqlite3
from pathlib import Path
import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import socket



SAMBA_BASE = "/srv/samba"

DB_PATH = f"{SAMBA_BASE}/school.db"

MOUNTS_BASE = "/srv/samba_mounts"





class SchoolSamba:

    def __init__(self):

        self.base = Path(SAMBA_BASE)

        self.base.mkdir(exist_ok=True)

        Path(MOUNTS_BASE).mkdir(exist_ok=True)

        self.init_db()

        self.ensure_groups()

        # Автоинициализация структуры и Samba при первом запуске.
        # Это избавляет от необходимости вручную вызывать "init" перед "serve".
        classes_dir = self.base / "classes"
        students_dir = self.base / "students"
        teachers_dir = self.base / "teachers"
        if not (classes_dir.exists() and students_dir.exists() and teachers_dir.exists()):
            self.create_base_structure()
            try:
                self.ensure_samba()
                self.update_smb_config()
            except Exception as e:
                # Если установка/перезапуск Samba не удались, не ломаем основной сценарий,
                # но выводим сообщение в консоль.
                print(f"warning: samba auto-init failed: {e}")



    def print_help(self):

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

            "  addstudent <name> <class> <uid> <pass>",

            "                                   add student",

            "  delclass <class>                 delete class (if no users)",

            "  deluser <name>                   delete user",

            "  mount <name>                     remount user binds",

            "  umount <name>                    unmount user binds",

            "  list                             list users",

            "  listclasses                      list classes",

            "  status                           show status",

            "  restart                          restart samba with config",

            "  backup                           backup database",

            "  serve [host] [port]             run HTTP server for RFID/PIN",

            "  help                             show this help",

        ]

        print("\n".join(lines))



    def init_db(self):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   id INTEGER PRIMARY KEY,
                   username TEXT UNIQUE,
                   role TEXT,
                   class_name TEXT,
                   uid INTEGER
               )"""
        )

        c.execute(
            """CREATE TABLE IF NOT EXISTS classes (
                   name TEXT UNIQUE
               )"""
        )

        c.execute(
            """CREATE TABLE IF NOT EXISTS mounts (
                   username TEXT,
                   mount_path TEXT,
                   source_path TEXT,
                   PRIMARY KEY(username, mount_path)
               )"""
        )

        c.execute(
            """CREATE TABLE IF NOT EXISTS teacher_classes (
                   teacher TEXT,
                   class_name TEXT,
                   UNIQUE(teacher, class_name)
               )"""
        )

        # Привязка RFID‑карт к пользователям (для mb_mount.py и daemon.pyw).
        # card_hash и pin_hash уже приходят хешированными на клиенте.
        c.execute(
            """CREATE TABLE IF NOT EXISTS cards (
                   card_hash TEXT PRIMARY KEY,
                   username  TEXT NOT NULL,
                   pin_hash  TEXT NOT NULL,
                   FOREIGN KEY(username) REFERENCES users(username)
               )"""
        )

        conn.commit()

        conn.close()



    def ensure_groups(self):

        # Базовые группы ролей.
        self.run_cmd(["groupadd", "-f", "teachers"])

        self.run_cmd(["groupadd", "-f", "students"])

        self.run_cmd(["groupadd", "-f", "admins"])

        # Общая группа "users", которую мы используем как группу
        # для корня монтирований (/srv/samba_mounts). Без неё chown
        # root:users /srv/samba_mounts в setup_user_permissions
        # падает, и в итоге каталог остаётся root:root, из‑за чего
        # Samba отдаёт ACCESS_DENIED при входе в \\server\school.
        self.run_cmd(["groupadd", "-f", "users"])



    def ensure_samba(self):

        if subprocess.run(["which", "smbd"], capture_output=True).returncode != 0:

            print("installing samba...")

            self.run_cmd(["apt", "update"])

            self.run_cmd(["apt", "install", "-y", "samba"])



    def run_cmd(self, cmd, input=None, check=True):

        full_cmd = ["sudo"] + cmd

        try:

            result = subprocess.run(

                full_cmd,

                input=input,

                check=check,

                capture_output=True,

                text=True,

            )

            return True, result.stdout

        except subprocess.CalledProcessError as e:

            return False, e.stderr



    def create_base_structure(self):

        for d in ["for_teachers", "classes", "teachers", "students"]:

            (self.base / d).mkdir(exist_ok=True)

        # базовый каталог

        self.run_cmd(["chmod", "750", str(self.base)])

        self.run_cmd(["chown", "root:users", str(self.base)])

        # закрываем служебные каталоги для студентов

        self.run_cmd(["chown", "root:teachers", str(self.base / "teachers")])

        self.run_cmd(["chmod", "770", str(self.base / "teachers")])

        self.run_cmd(["chown", "root:teachers", str(self.base / "for_teachers")])

        self.run_cmd(["chmod", "770", str(self.base / "for_teachers")])

        # Администраторам выдаём полный доступ ко всей структуре через ACL.
        self.run_cmd(
            ["setfacl", "-R", "-m", "g:admins:rwx", str(self.base)],
            check=False,
        )

        print("base directory structure created")



    def update_smb_config(self):

        host = socket.gethostname()

        config = f"""[global]
workgroup = SCHOOL
server string = Safe Computer Class on {host}
security = user
map to guest = never
hide unreadable = yes

[school]
path = {MOUNTS_BASE}
valid users = @teachers @students @admins
writable = yes
browseable = yes
create mask = 0664
directory mask = 0775
"""

        with open("/etc/samba/smb.conf", "w") as f:

            f.write(config)

        self.run_cmd(["systemctl", "restart", "smbd"])

        self.run_cmd(["systemctl", "enable", "smbd"])

        print("samba config updated and smbd restarted")



    def add_class(self, class_name: str):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute("INSERT OR IGNORE INTO classes (name) VALUES (?)", (class_name,))

        conn.commit()

        conn.close()



        class_dir = self.base / "classes" / class_name

        students_dir = self.base / "students" / class_name

        class_dir.mkdir(exist_ok=True)

        students_dir.mkdir(exist_ok=True)

        # Папка класса:
        #  - учителя: чтение/запись;
        #  - ученики: чтение;
        #  - админ: полный доступ (через ACL admins выше).
        self.run_cmd(["chown", "root:teachers", str(class_dir)])
        self.run_cmd(["chmod", "770", str(class_dir)])
        # Даём право чтения для группы students через ACL.
        self.run_cmd(
            ["setfacl", "-m", "g:students:rx", str(class_dir)],
            check=False,
        )

        # Каталог с личными папками учеников данного класса.
        self.run_cmd(["chown", "root:teachers", str(students_dir)])
        self.run_cmd(["chmod", "770", str(students_dir)])

        print(f"class {class_name} created")



    def get_user_info(self, username: str):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute(

            "SELECT role, class_name FROM users WHERE username = ?", (username,)

        )

        result = c.fetchone()

        conn.close()

        return result



    def get_teacher_classes(self, teacher: str):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute(

            "SELECT class_name FROM teacher_classes WHERE teacher = ?", (teacher,)

        )

        rows = c.fetchall()

        conn.close()

        return [r[0] for r in rows]



    def link_teacher_class(self, teacher: str, class_name: str):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute(

            "INSERT OR IGNORE INTO teacher_classes (teacher, class_name) VALUES (?, ?)",

            (teacher, class_name),

        )

        conn.commit()

        conn.close()

        print(f"teacher {teacher} linked to class {class_name}")



    def unlink_teacher_class(self, teacher: str, class_name: str):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute(

            "DELETE FROM teacher_classes WHERE teacher = ? AND class_name = ?",

            (teacher, class_name),

        )

        conn.commit()

        conn.close()

        print(f"teacher {teacher} unlinked from class {class_name}")



    def add_user(self, username: str, role: str, class_name: str | None, uid: int, password: str):

        # Unix-пользователь

        try:

            pw = pwd.getpwnam(username)

            print(f"user {username} already exists, using system account")

            uid = pw.pw_uid

            home = Path(pw.pw_dir)

        except KeyError:

            home = self.get_user_home(username, role, class_name)

            home.mkdir(parents=True, exist_ok=True)

            ok, out = self.run_cmd(

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

            print(f"system user {username} created with uid {uid}")



        # пароль Unix

        self.run_cmd(["chpasswd"], input=f"{username}:{password}\n")



        # запись в SQLite

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute(

            "INSERT OR REPLACE INTO users (username, role, class_name, uid) VALUES (?, ?, ?, ?)",

            (username, role, class_name, uid),

        )

        conn.commit()

        conn.close()



        # Samba‑пользователь

        self.add_samba_user(username, password)



        # права и монтирования

        self.setup_user_permissions(username, role, class_name)

        self.create_user_mounts(username, role)

        print(f"user {username} ({role}, uid {uid}) fully configured")

        return True



    def get_user_home(self, username: str, role: str, class_name: str | None) -> Path:

        if role == "teacher":

            return self.base / "teachers" / username

        elif role == "student":

            return self.base / "students" / (class_name or "") / username

        else:

            return self.base / "admin"



    def add_samba_user(self, username: str, password: str):

        cmd = [

            "bash",

            "-c",

            f'printf "%s\\n%s\\n" "{password}" "{password}" | smbpasswd -a -s "{username}"'

        ]

        ok, out = self.run_cmd(cmd, check=False)

        if not ok:

            print(f"smbpasswd failed for {username}: {out}")

            return

        self.run_cmd(["smbpasswd", "-e", username], check=False)

        print(f"samba password set for {username}")



    def setup_user_permissions(self, username: str, role: str, class_name: str | None):

        home = self.get_user_home(username, role, class_name)

        # Базовый владелец — сам пользователь, роль отражается в основной группе,
        # дополнительный доступ раздаём через ACL.
        self.run_cmd(["chown", "-R", f"{username}:{role}s", str(home)])



        if role == "teacher":

            self.run_cmd(["chmod", "-R", "770", str(home)])

            # ACL для доступа учителя к for_teachers

            self.run_cmd(

                [

                    "setfacl",

                    "-R",

                    "-m",

                    f"u:{username}:rwx",

                    str(self.base / "for_teachers"),

                ]

            )

        elif role == "student":

            # Ученик: чтение/запись своей папки, учителя могут помогать в его каталоге.

            self.run_cmd(["chmod", "-R", "700", str(home)])
            self.run_cmd(
                [
                    "setfacl",
                    "-R",
                    "-m",
                    "g:teachers:rwx",
                    str(home),
                ],
                check=False,
            )



        # закрываем корни, чтобы hide unreadable работал красиво

        self.run_cmd(["chmod", "750", str(self.base)])

        # корень монтирования должен быть доступен группе users,
        # иначе учителя/ученики не смогут войти в свой каталог внутри share
        self.run_cmd(["chown", "root:users", str(Path(MOUNTS_BASE))])
        self.run_cmd(["chmod", "750", str(Path(MOUNTS_BASE))])

        # Для админов даём полный доступ к монтам.
        self.run_cmd(
            ["setfacl", "-R", "-m", "g:admins:rwx", str(Path(MOUNTS_BASE))],
            check=False,
        )



    def create_user_mounts(self, username: str, role: str):

        mount_base = Path(MOUNTS_BASE) / username

        mount_base.mkdir(parents=True, exist_ok=True)

        # Закрываем корневую папку монтирований конкретного пользователя,
        # чтобы другие пользователи не видели его каталог внутри шары.
        # Админам при этом оставляем полный доступ через ACL.
        self.run_cmd(["chown", "-R", f"{username}:{role}s", str(mount_base)])
        if role == "teacher":
            self.run_cmd(["chmod", "770", str(mount_base)])
        else:
            self.run_cmd(["chmod", "700", str(mount_base)])
        self.run_cmd(
            ["setfacl", "-R", "-m", "g:admins:rwx", str(mount_base)],
            check=False,
        )

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute("DELETE FROM mounts WHERE username = ?", (username,))



        mounts = []



        if role == "teacher":

            classes = self.get_teacher_classes(username)

            mounts.append((mount_base / "teachers", self.base / "teachers" / username))

            mounts.append((mount_base / "for_teachers", self.base / "for_teachers"))

            for cls in classes:

                mounts.append((mount_base / f"class_{cls}", self.base / "classes" / cls))

                mounts.append((mount_base / f"students_{cls}", self.base / "students" / cls))



        elif role == "student":

            info = self.get_user_info(username)

            class_name = info[1] if info else None

            if not class_name:

                print(f"no class for student {username}, cannot create mounts")

                conn.close()

                return

            # Если класс не был заранее создан через addclass, создаём/инициализируем
            # его структуру здесь. Повторный вызов безопасен (INSERT OR IGNORE + mkdir).
            self.add_class(class_name)

            mounts = [

                (mount_base / "home", self.base / "students" / class_name / username),

                (mount_base / "class", self.base / "classes" / class_name),

            ]



        else:

            print(f"unknown role {role} for {username}, no mounts created")

            conn.close()

            return



        for m_path, source in mounts:

            m_path.mkdir(parents=True, exist_ok=True)

            self.run_cmd(["mount", "--bind", str(source), str(m_path)])

            c.execute(

                "INSERT INTO mounts (username, mount_path, source_path) VALUES (?, ?, ?)",

                (username, str(m_path), str(source)),

            )



        conn.commit()

        conn.close()

        print(f"bind mounts for {username} created in {mount_base}")



    def umount_user(self, username: str):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute("SELECT mount_path FROM mounts WHERE username = ?", (username,))

        mounts = c.fetchall()

        conn.close()



        for (m_path,) in mounts:

            self.run_cmd(["umount", m_path], check=False)



        print(f"mounts for {username} unmounted")



    def del_user(self, username: str):

        info = self.get_user_info(username)

        if not info:

            print(f"user {username} not found in db")

            return

        role, _ = info



        self.umount_user(username)

        self.run_cmd(["smbpasswd", "-x", username], check=False)

        self.run_cmd(["userdel", "-r", username], check=False)



        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute("DELETE FROM users WHERE username = ?", (username,))

        c.execute("DELETE FROM mounts WHERE username = ?", (username,))

        if role == "teacher":

            c.execute("DELETE FROM teacher_classes WHERE teacher = ?", (username,))

        conn.commit()

        conn.close()



        print(f"user {username} removed")



    def del_class(self, class_name: str):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute("SELECT username FROM users WHERE class_name = ?", (class_name,))

        students = c.fetchall()

        c.execute(

            "SELECT teacher FROM teacher_classes WHERE class_name = ?", (class_name,)

        )

        teachers = c.fetchall()



        if students or teachers:

            print(f"class {class_name} has users:")

            for (u,) in students:

                print(f"  student: {u}")

            for (t,) in teachers:

                print(f"  teacher: {t}")

            print("remove or unlink them first")

            conn.close()

            return False



        c.execute("DELETE FROM classes WHERE name = ?", (class_name,))

        conn.commit()

        conn.close()



        class_dir = self.base / "classes" / class_name

        students_dir = self.base / "students" / class_name



        if class_dir.exists() and not any(class_dir.iterdir()):

            class_dir.rmdir()

        if students_dir.exists() and not any(students_dir.iterdir()):

            students_dir.rmdir()



        print(f"class {class_name} removed")

        return True



    def list_users(self):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute("SELECT username, role, class_name, uid FROM users")

        users = c.fetchall()

        conn.close()



        if not users:

            print("no users")

            return



        print("users:")

        print("name           role       class      uid")

        print("--------------------------------------------")

        for username, role, cls, uid in users:

            print(f"{username:<14} {role:<9} {str(cls):<10} {str(uid):<7}")



    def list_classes(self):

        conn = sqlite3.connect(DB_PATH)

        c = conn.cursor()

        c.execute("SELECT name FROM classes")

        classes = c.fetchall()

        conn.close()



        print("classes:")

        if not classes:

            print("  (none)")

            return

        for (name,) in classes:

            print(f"  {name}")



    def status(self):

        print("status:")

        self.list_users()

        self.list_classes()

        result = subprocess.run(

            ["systemctl", "is-active", "smbd"], capture_output=True, text=True

        )

        state = "active" if result.returncode == 0 else "inactive"

        print(f"smbd: {state}")



    def backup(self):

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_path = f"{SAMBA_BASE}/school_backup_{ts}.db"

        src = sqlite3.connect(DB_PATH)

        dst = sqlite3.connect(backup_path)

        src.backup(dst)

        src.close()

        dst.close()

        print(f"db backup created: {backup_path}")



    # --- Работа с RFID‑картами и PIN через SQLite, для mb_mount.py и daemon.pyw ---

    def register_card(self, username: str, card_hash: str, pin_hash: str) -> tuple[bool, str]:
        """
        Регистрирует (или перезаписывает) RFID‑карту для пользователя.

        Используется HTTP‑эндпоинтом /api/scc/register_card.
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            conn.close()
            return False, "user not found"

        c.execute(
            "INSERT OR REPLACE INTO cards (card_hash, username, pin_hash) VALUES (?, ?, ?)",
            (card_hash, username, pin_hash),
        )
        conn.commit()
        conn.close()
        return True, "card registered"

    def verify_card(self, card_hash: str) -> tuple[bool, bool]:
        """
        Проверка существования карты.

        Возвращает (exists, require_pin). Пока всегда требуем PIN, но
        интерфейс оставляем расширяемым.
        Используется HTTP‑эндпоинтом /api/scc/verify_card.
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT username FROM cards WHERE card_hash = ?", (card_hash,))
        row = c.fetchone()
        conn.close()
        if not row:
            return False, False
        # На первом этапе всегда требуем PIN.
        return True, True

    def verify_pin(self, card_hash: str, pin_hash: str) -> bool:
        """
        Проверка PIN по хешу карты.

        Клиент уже передаёт SHA‑256(PIN) (см. daemon.pyw), здесь мы
        сравниваем только хеши один к одному.
        Используется HTTP‑эндпоинтом /api/scc/verify_pin.
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT pin_hash FROM cards WHERE card_hash = ?",
            (card_hash,),
        )
        row = c.fetchone()
        conn.close()
        if not row:
            return False
        stored_hash = row[0]
        return stored_hash == pin_hash


class SCCRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP‑сервер без внешних зависимостей, который даёт REST‑эндпоинты
    для клиентов mb_mount.py и daemon.pyw:

      - POST /api/scc/register_card  {username, card_hash, pin_hash}
      - POST /api/scc/verify_card    {card_hash}
      - POST /api/scc/verify_pin     {card_hash, pin_hash}
    """

    # Экземпляр SchoolSamba прокидываем через атрибут класса.
    school: "SchoolSamba | None" = None

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not SCCRequestHandler.school:
            self._send_json(500, {"ok": False, "message": "server not initialized"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw_body.decode("utf-8") or "{}")
        except Exception:
            self._send_json(400, {"ok": False, "message": "invalid JSON"})
            return

        if self.path == "/api/scc/register_card":
            username = str(data.get("username", "")).strip()
            card_hash = str(data.get("card_hash", "")).strip()
            pin_hash = str(data.get("pin_hash", "")).strip()
            if not username or not card_hash or not pin_hash:
                self._send_json(400, {"ok": False, "message": "missing fields"})
                return
            ok, msg = SCCRequestHandler.school.register_card(
                username, card_hash, pin_hash
            )
            self._send_json(200 if ok else 400, {"ok": ok, "message": msg})

        elif self.path == "/api/scc/verify_card":
            card_hash = str(data.get("card_hash", "")).strip()
            if not card_hash:
                self._send_json(400, {"exists": False, "require_pin": False})
                return
            exists, require_pin = SCCRequestHandler.school.verify_card(card_hash)
            self._send_json(200, {"exists": exists, "require_pin": require_pin})

        elif self.path == "/api/scc/verify_pin":
            card_hash = str(data.get("card_hash", "")).strip()
            pin_hash = str(data.get("pin_hash", "")).strip()
            if not card_hash or not pin_hash:
                self._send_json(400, {"ok": False})
                return
            ok = SCCRequestHandler.school.verify_pin(card_hash, pin_hash)
            self._send_json(200, {"ok": ok})

        else:
            self._send_json(404, {"ok": False, "message": "not found"})


def run_http_server(host: str, port: int):
    """
    Запуск HTTP‑сервера для работы с mb_mount.py и daemon.pyw.

    Пример:
        sudo python3 scc.py serve 0.0.0.0 8000
    """
    school = SchoolSamba()
    SCCRequestHandler.school = school
    httpd = HTTPServer((host, port), SCCRequestHandler)
    print(f"HTTP server running on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("HTTP server stopped")
    finally:
        httpd.server_close()


def main():

    parser = argparse.ArgumentParser(

        description="Safe Computer Class v0.5", add_help=False

    )

    parser.add_argument(

        "command",

        nargs="?",

        choices=[

            "init",

            "addteacher",

            "addteacherclass",

            "delteacherclass",

            "addstudent",

            "addclass",

            "delclass",

            "deluser",

            "umount",

            "mount",

            "list",

            "listclasses",

            "status",

            "restart",

            "backup",

            "serve",

            "help",

        ],

    )

    parser.add_argument("args", nargs="*", help="command args")

    args = parser.parse_args()



    if args.command is None or args.command == "help":

        school = SchoolSamba()

        school.print_help()

        return



    school = SchoolSamba()



    if args.command == "init":

        school.ensure_samba()

        school.create_base_structure()

        school.update_smb_config()

        print("system initialized")



    elif args.command == "addteacher" and len(args.args) == 3:

        name, uid, pw = args.args

        school.add_user(name, "teacher", None, int(uid), pw)



    elif args.command == "addteacherclass" and len(args.args) == 2:

        teacher, cls = args.args

        school.link_teacher_class(teacher, cls)

        school.create_user_mounts(teacher, "teacher")



    elif args.command == "delteacherclass" and len(args.args) == 2:

        teacher, cls = args.args

        school.unlink_teacher_class(teacher, cls)

        school.create_user_mounts(teacher, "teacher")



    elif args.command == "addstudent" and len(args.args) == 4:

        name, cls, uid, pw = args.args

        school.add_user(name, "student", cls, int(uid), pw)



    elif args.command == "addclass" and len(args.args) == 1:

        school.add_class(args.args[0])



    elif args.command == "delclass" and len(args.args) == 1:

        school.del_class(args.args[0])



    elif args.command == "deluser" and len(args.args) == 1:

        school.del_user(args.args[0])



    elif args.command == "umount" and len(args.args) == 1:

        school.umount_user(args.args[0])



    elif args.command == "mount" and len(args.args) == 1:

        info = school.get_user_info(args.args[0])

        if not info:

            print("user not found in db")

        else:

            role, _ = info

            school.create_user_mounts(args.args[0], role)

            print(f"user {args.args[0]} remounted")



    elif args.command == "list":

        school.list_users()



    elif args.command == "listclasses":

        school.list_classes()



    elif args.command == "status":

        school.status()



    elif args.command == "restart":

        school.update_smb_config()



    elif args.command == "backup":

        school.backup()

    elif args.command == "serve":

        # Простой HTTP‑сервер для работы с mb_mount.py и daemon.pyw.

        host = "0.0.0.0"

        port = 8000

        if len(args.args) >= 1:

            host = args.args[0]

        if len(args.args) >= 2:

            port = int(args.args[1])

        run_http_server(host, port)



    else:

        school.print_help()





if __name__ == "__main__":

    main()

