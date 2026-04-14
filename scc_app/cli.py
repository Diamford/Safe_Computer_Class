from __future__ import annotations

import argparse

from .http_api import run_http_server
from .service import SchoolSamba


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe Computer Class v0.5", add_help=False)
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
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None or args.command == "help":
        # Help should work even on Windows.
        print(
            "\n".join(
                [
                    "SAFE COMPUTER CLASS v0.5",
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
            )
        )
        return

    school = SchoolSamba()

    if args.command == "init":
        school.init()
        print("system initialized")
        return

    if args.command == "addteacher" and len(args.args) == 3:
        name, uid, pw = args.args
        school.add_user(name, "teacher", None, int(uid), pw)
        return

    if args.command == "addteacherclass" and len(args.args) == 2:
        teacher, cls = args.args
        school.link_teacher_class(teacher, cls)
        school.create_user_mounts(teacher, "teacher")
        return

    if args.command == "delteacherclass" and len(args.args) == 2:
        teacher, cls = args.args
        school.unlink_teacher_class(teacher, cls)
        school.create_user_mounts(teacher, "teacher")
        return

    if args.command == "addstudent" and len(args.args) == 4:
        name, cls, uid, pw = args.args
        school.add_user(name, "student", cls, int(uid), pw)
        return

    if args.command == "addclass" and len(args.args) == 1:
        school.add_class(args.args[0])
        return

    if args.command == "delclass" and len(args.args) == 1:
        school.del_class(args.args[0])
        return

    if args.command == "deluser" and len(args.args) == 1:
        school.del_user(args.args[0])
        return

    if args.command == "umount" and len(args.args) == 1:
        school.umount_user(args.args[0])
        return

    if args.command == "mount" and len(args.args) == 1:
        info = school.get_user_info(args.args[0])
        if not info:
            print("user not found in db")
            return
        role, _ = info
        school.create_user_mounts(args.args[0], role)
        print(f"user {args.args[0]} remounted")
        return

    if args.command == "list":
        school.list_users()
        return

    if args.command == "listclasses":
        school.list_classes()
        return

    if args.command == "status":
        school.status()
        return

    if args.command == "restart":
        from .samba import write_smb_conf

        write_smb_conf()
        return

    if args.command == "backup":
        school.backup()
        return

    if args.command == "serve":
        host = "0.0.0.0"
        port = 80
        if len(args.args) >= 1:
            host = args.args[0]
        if len(args.args) >= 2:
            port = int(args.args[1])
        run_http_server(host, port)
        return

    school.print_help()

