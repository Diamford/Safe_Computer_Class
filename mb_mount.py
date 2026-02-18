#!/usr/bin/env python3
# safe_class_qt_mounter_win.py

import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            shell=True,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def mount_school_drive(server, username, password, drive_letter="Z:"):
    unc = f"\\\\{server}\\school"
    # /persistent:no чтобы не сохранять подключение навсегда
    cmd = (
        f'net use {drive_letter} "{unc}" "{password}" /user:"{username}" /persistent:no'
    )
    return run_cmd(cmd)


def umount_school_drive(drive_letter="Z:"):
    cmd = f"net use {drive_letter} /delete /y"
    return run_cmd(cmd)


class SafeClassMounterWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Safe Computer Class mounter (Windows)")
        self.setGeometry(200, 200, 520, 340)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        title = QLabel("Safe Computer Class mounter (Windows)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # server
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("server:"))
        self.server_edit = QLineEdit("192.168.0.10")
        h1.addWidget(self.server_edit)
        layout.addLayout(h1)

        # username
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("username:"))
        self.user_edit = QLineEdit()
        h2.addWidget(self.user_edit)
        layout.addLayout(h2)

        # password
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("password:"))
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        h3.addWidget(self.pass_edit)
        layout.addLayout(h3)

        # drive letter
        h4 = QHBoxLayout()
        h4.addWidget(QLabel("drive:"))
        self.drive_combo = QComboBox()
        self.drive_combo.addItems(
            [f"{chr(c)}:" for c in range(ord("Z"), ord("D") - 1, -1)]
        )
        h4.addWidget(self.drive_combo)
        layout.addLayout(h4)

        # buttons
        h5 = QHBoxLayout()
        self.btn_mount = QPushButton("mount")
        self.btn_umount = QPushButton("umount")
        self.btn_mount.clicked.connect(self.on_mount)
        self.btn_umount.clicked.connect(self.on_umount)
        h5.addWidget(self.btn_mount)
        h5.addWidget(self.btn_umount)
        layout.addLayout(h5)

        # user root info
        self.user_path_label = QLabel("user root: (not mounted)")
        layout.addWidget(self.user_path_label)

        # log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        layout.addWidget(self.log)

    def log_msg(self, text: str):
        self.log.append(text)

    def on_mount(self):
        server = self.server_edit.text().strip()
        username = self.user_edit.text().strip()
        password = self.pass_edit.text()
        drive_letter = self.drive_combo.currentText()

        if not server or not username:
            QMessageBox.warning(self, "error", "server and username are required")
            return

        self.log_msg(
            f"mounting {drive_letter} -> \\\\{server}\\school as {username}..."
        )
        ok, msg = mount_school_drive(server, username, password, drive_letter)
        if not ok:
            self.log_msg("mount error: " + msg)
            QMessageBox.critical(self, "mount error", msg)
            return

        self.log_msg("mounted ok")
        user_root = f"{drive_letter}\\{username}"
        self.user_path_label.setText(f"user root: {user_root}")

    def on_umount(self):
        drive_letter = self.drive_combo.currentText()
        self.log_msg(f"unmounting {drive_letter}...")
        ok, msg = umount_school_drive(drive_letter)
        if not ok:
            self.log_msg("umount error: " + msg)
            QMessageBox.critical(self, "umount error", msg)
        else:
            self.log_msg("unmounted")
            self.user_path_label.setText("user root: (not mounted)")


def main():
    app = QApplication(sys.argv)
    w = SafeClassMounterWin()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
