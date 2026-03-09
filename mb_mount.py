#!/usr/bin/env python3
# safe_class_qt_mounter_win.py

import hashlib
import os
import subprocess
import sys
import time
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
    QInputDialog,
)

try:
    import requests  # HTTP‑клиент для общения с сервером регистрации карты
except ImportError:
    requests = None

try:
    import serial  # связь с ESP32‑C3 по COM‑порту
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


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
    # Монтируем сразу личную папку пользователя внутри шары,
    # чтобы он не видел каталоги других пользователей.
    unc = f"\\\\{server}\\school\\{username}"
    # /persistent:no чтобы не сохранять подключение навсегда
    cmd = (
        f'net use {drive_letter} "{unc}" "{password}" /user:"{username}" /persistent:no'
    )
    return run_cmd(cmd)


def umount_school_drive(drive_letter="Z:"):
    cmd = f"net use {drive_letter} /delete /y"
    return run_cmd(cmd)


def _sha256_hex(text: str) -> str:
    """
    Возвращает HEX‑представление SHA‑256 от переданной строки (верхний регистр).
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest.upper()


def _open_rfid_port() -> "serial.Serial | None":
    """
    Открывает COM‑порт с ESP32‑C3 (SCC_rfid_scanner.ino).

    1) Пробует порт из SAFE_RFID_PORT.
    2) Если не задано — выполняет автопоиск по всем доступным портам.
    """
    if serial is None or list_ports is None:
        return None

    env_port = os.environ.get("SAFE_RFID_PORT", "").strip()
    if env_port:
        try:
            return serial.Serial(env_port, 115200, timeout=2)
        except Exception:
            # тихо падаем на автопоиск
            pass

    for port in list_ports.comports():
        dev = port.device
        try:
            ser = serial.Serial(dev, 115200, timeout=2)
            ser.reset_input_buffer()
            ser.write(b"HELLO_SCC\n")
            line = ser.readline().decode("utf-8", "ignore").strip()
            if line == "SCC_RFID_V1_OK":
                return ser
            ser.close()
        except Exception:
            try:
                ser.close()
            except Exception:
                pass

    return None


def read_card_hash_once(timeout_seconds: float = 60.0) -> str | None:
    """
    Ожидает один хеш карты от контроллера SCC_rfid_scanner.ino.

    Протокол:
      ПК -> ESP:  "HELLO_SCC\\n"
      ESP -> ПК:  "SCC_RFID_V1_OK\\n"
      ESP -> ПК:  "CARD_HASH:<HEX>\\n"
    """
    if serial is None:
        return None

    ser = _open_rfid_port()
    if ser is None:
        return None

    try:
        # после успешного рукопожатия ждём строку CARD_HASH:
        prefix = "CARD_HASH:"
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            line = ser.readline().decode("utf-8", "ignore").strip()
            if not line:
                continue
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
            if line.startswith("ERR:"):
                break
    finally:
        try:
            ser.close()
        except Exception:
            pass

    return None


def register_card_on_server(server: str, username: str, card_hash: str, pin: str) -> tuple[bool, str]:
    """
    Регистрирует карту для пользователя на сервере.

    Данные передаются в виде:
      - card_hash: HEX‑SHA256(UID||SALT) (как прислал контроллер)
      - pin_hash:  HEX‑SHA256(PIN)
      - username:  имя залогиненного пользователя (Windows/домена)

    URL эндпоинта берётся из SAFE_CLASS_REGISTER_URL, а если переменная
    не задана — используется HTTP‑адрес по IP сервера:
      http://<server>/api/scc/register_card
    """
    if requests is None:
        return False, "Python‑библиотека 'requests' не установлена"

    url = os.environ.get("SAFE_CLASS_REGISTER_URL", "").strip()
    if not url:
        url = f"http://{server}/api/scc/register_card"

    pin_hash = _sha256_hex(pin)

    try:
        resp = requests.post(
            url,
            json={
                "username": username,
                "card_hash": card_hash,
                "pin_hash": pin_hash,
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        ok = bool(data.get("ok", True))
        msg = str(data.get("message", "registered"))
        return ok, msg
    except Exception as exc:
        return False, f"HTTP error: {exc}"


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
        self.btn_register_rfid = QPushButton("register RFID")
        self.btn_mount.clicked.connect(self.on_mount)
        self.btn_umount.clicked.connect(self.on_umount)
        self.btn_register_rfid.clicked.connect(self.on_register_rfid)
        h5.addWidget(self.btn_mount)
        h5.addWidget(self.btn_umount)
        h5.addWidget(self.btn_register_rfid)
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

    def on_register_rfid(self):
        """
        Привязка RFID‑карты к текущему пользователю через сервер.

        1) Проверяем, что указан сервер и имя пользователя.
        2) Запрашиваем PIN у пользователя (без логирования значения).
        3) Считываем хеш карты с контроллера SCC_rfid_scanner.ino.
        4) Отправляем card_hash + pin_hash + username на сервер.
        """
        server = self.server_edit.text().strip()
        username = self.user_edit.text().strip()

        if not server or not username:
            QMessageBox.warning(
                self,
                "error",
                "server and username are required for RFID registration",
            )
            return

        if requests is None:
            QMessageBox.critical(
                self,
                "error",
                "Python package 'requests' is not installed",
            )
            return

        if serial is None:
            QMessageBox.critical(
                self,
                "error",
                "Python package 'pyserial' is not installed",
            )
            return

        # Запрос PIN у пользователя
        pin, ok = QInputDialog.getText(
            self,
            "RFID PIN",
            "Enter PIN for this card:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not pin:
            return

        self.log_msg("waiting for RFID card (present a card to the reader)...")

        start = time.time()
        card_hash = read_card_hash_once(timeout_seconds=60.0)
        if not card_hash:
            self.log_msg("RFID card not read (timeout or device error)")
            QMessageBox.warning(
                self,
                "RFID error",
                "RFID card was not read. Please ensure the device is connected and try again.",
            )
            return

        elapsed = int(time.time() - start)
        self.log_msg(f"RFID card hash received after {elapsed} s")

        ok, msg = register_card_on_server(server, username, card_hash, pin)
        if ok:
            self.log_msg(f"RFID card registered: {msg}")
            QMessageBox.information(
                self,
                "RFID registered",
                "RFID card has been registered successfully for this user.",
            )
        else:
            self.log_msg(f"RFID registration error: {msg}")
            QMessageBox.critical(
                self,
                "RFID error",
                f"Failed to register RFID card: {msg}",
            )


def main():
    app = QApplication(sys.argv)
    w = SafeClassMounterWin()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
