#!/usr/bin/env python3
# safe_class_qt_mounter_win.py

import hashlib
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
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


LOGGER = logging.getLogger("safe_computer_class.rfid")


def _rfid_log(level: int, msg: str, *args) -> None:
    """
    Логирование для RFID-части.

    В daemon.pyw есть файловый логгер, но mb_mount.py может запускаться и отдельно.
    Поэтому, если логгеры не настроены, печатаем в stdout как fallback.
    """
    try:
        if logging.getLogger().handlers or LOGGER.handlers:
            LOGGER.log(level, msg, *args)
        else:
            text = msg % args if args else msg
            print(f"[RFID] {text}")
    except Exception:
        # Никогда не валим основную логику из-за логирования
        pass


def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="cp866" if os.name == "nt" else "utf-8",
            errors="replace",
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


def _open_rfid_port(preferred_port: str | None = None) -> "serial.Serial | None":
    """
    Открывает COM‑порт с ESP32‑C3 (SCC_rfid_scanner.ino).

    1) Пробует порт из SAFE_RFID_PORT.
    2) Если не задано — выполняет автопоиск по всем доступным портам.
    """
    if serial is None or list_ports is None:
        return None

    def _try_open_and_handshake(port_name: str) -> "serial.Serial | None":
        _rfid_log(logging.INFO, "trying port %s", port_name)
        ser: "serial.Serial | None" = None
        try:
            # На некоторых виртуальных/BT COM-портах open()/write() могут подвисать.
            # timeout=1 ограничивает readline(), write_timeout ограничивает write().
            ser = serial.Serial(port_name, 115200, timeout=1, write_timeout=1)

            # Для Arduino открытие порта может вызывать reset,
            # поэтому даём плате немного времени "выговориться".
            boot_deadline = time.time() + 1.0
            while time.time() < boot_deadline:
                line = ser.readline().decode("utf-8", "ignore").strip()
                if not line:
                    continue
                _rfid_log(logging.DEBUG, "boot line on %r: %r", port_name, line)

            # Теперь пробуем нормальное рукопожатие (укороченный таймаут).
            ser.reset_input_buffer()
            # Некоторые версии прошивки ожидают CRLF, поэтому шлём \r\n.
            ser.write(b"HELLO_SCC\r\n")
            deadline = time.time() + 5.0
            saw_wait_state = False
            while time.time() < deadline:
                line = ser.readline().decode("utf-8", "ignore").strip()
                if not line:
                    continue
                _rfid_log(logging.DEBUG, "handshake response on %r: %r", port_name, line)
                if line == "SCC_RFID_V1_OK":
                    _rfid_log(logging.INFO, "handshake OK on %s", port_name)
                    return ser
                if "WAIT_HANDSHAKE" in line or "SCC RFID device booted" in line:
                    # Это явные строки от прошивки нашего устройства.
                    # Если формального ответа SCC_RFID_V1_OK нет, но мы
                    # получили эти строки, считаем порт корректным и
                    # продолжаем дальше читать CARD_HASH уже вне рукопожатия.
                    saw_wait_state = True
                if line.startswith("ERR:"):
                    _rfid_log(logging.WARNING, "handshake error on %s: %r", port_name, line)
                    break

            if saw_wait_state:
                _rfid_log(
                    logging.INFO,
                    "fallback: using port %s after WAIT_HANDSHAKE/boot messages without SCC_RFID_V1_OK",
                    port_name,
                )
                return ser

            ser.close()
        except Exception as exc:
            _rfid_log(logging.WARNING, "port %s failed: %r", port_name, exc)
            try:
                if ser is not None:
                    ser.close()
            except Exception:
                pass
        return None

    if preferred_port:
        _rfid_log(logging.INFO, "preferred port is set to %r", preferred_port)
        ser = _try_open_and_handshake(preferred_port)
        if ser is not None:
            return ser
        # если рукопожатие не удалось — тихо падаем на автопоиск

    env_port = os.environ.get("SAFE_RFID_PORT", "").strip()
    if env_port:
        _rfid_log(logging.INFO, "SAFE_RFID_PORT is set to %r", env_port)
        ser = _try_open_and_handshake(env_port)
        if ser is not None:
            return ser
        # если рукопожатие не удалось — тихо падаем на автопоиск

    # Список доступных портов с приоритетом более "подходящих".
    skip_raw = os.environ.get("SAFE_RFID_SKIP_PORTS", "").strip()
    skip_ports = {p.strip().upper() for p in skip_raw.split(",") if p.strip()}

    ports_info = list(list_ports.comports())
    ports = []
    for p in ports_info:
        dev = (p.device or "").strip()
        if not dev:
            continue
        if dev.upper() in skip_ports:
            _rfid_log(logging.INFO, "skipping port from SAFE_RFID_SKIP_PORTS: %s", dev)
            continue
        ports.append(dev)

    # Приоритетный список можем расширять по мере необходимости.
    priority = ["COM12", "COM11", "COM10"]

    def _sort_key(dev: str) -> tuple[int, int]:
        if dev in priority:
            return (0, priority.index(dev))
        return (1, 0)

    for dev in sorted(ports, key=_sort_key):
        ser = _try_open_and_handshake(dev)
        if ser is not None:
            return ser

    _rfid_log(logging.WARNING, "no suitable RFID port found")
    return None


def read_card_hash_once(timeout_seconds: float = 60.0, preferred_port: str | None = None) -> str | None:
    """
    Ожидает один хеш карты от контроллера SCC_rfid_scanner.ino.

    Протокол:
      ПК -> ESP:  "HELLO_SCC\\n"
      ESP -> ПК:  "SCC_RFID_V1_OK\\n"
      ESP -> ПК:  "CARD_HASH:<HEX>\\n"
    """
    if serial is None:
        _rfid_log(logging.ERROR, "pyserial is not available")
        return None

    ser = _open_rfid_port(preferred_port=preferred_port)
    if ser is None:
        _rfid_log(logging.ERROR, "failed to open RFID port")
        return None

    try:
        # Дополнительное рукопожатие ПЕРЕД ожиданием карты, чтобы
        # гарантированно перевести прошивку из WAIT_HANDSHAKE в WAIT_CARD.
        try:
            ser.reset_input_buffer()
            ser.write(b"HELLO_SCC\r\n")
            handshake_deadline = time.time() + 2.0
            while time.time() < handshake_deadline:
                line = ser.readline().decode("utf-8", "ignore").strip()
                if not line:
                    continue
                _rfid_log(logging.DEBUG, "second-stage handshake: %r", line)
                if line == "SCC_RFID_V1_OK":
                    _rfid_log(logging.INFO, "second-stage handshake OK")
                    break
        except Exception:
            # Не рвём основное ожидание карты, даже если рукопожатие
            # отработало неидеально — прошивка всё равно примет HELLO_SCC.
            pass

        # после рукопожатия ждём строку CARD_HASH:
        prefix = "CARD_HASH:"
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            line = ser.readline().decode("utf-8", "ignore").strip()
            if not line:
                continue
            _rfid_log(logging.DEBUG, "line from device: %r", line)
            if line.startswith(prefix):
                _rfid_log(logging.INFO, "CARD_HASH line received")
                return line[len(prefix) :].strip()
            if line.startswith("ERR:"):
                _rfid_log(logging.WARNING, "error line from device, breaking: %r", line)
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



class RfidReadWorker(QObject):
    """
    Фоновый работник для чтения хеша RFID‑карты, чтобы не блокировать GUI‑поток.
    """

    finished = pyqtSignal(str, str, float)

    def __init__(self, timeout_seconds: float = 60.0, preferred_port: str | None = None):
        super().__init__()
        self._timeout = timeout_seconds
        self._preferred_port = preferred_port

    def run(self):
        start = time.time()
        card_hash = read_card_hash_once(
            timeout_seconds=self._timeout, preferred_port=self._preferred_port
        )
        elapsed = time.time() - start
        if not card_hash:
            self.finished.emit(
                "",
                "RFID card was not read. Please ensure the device is connected and try again.",
                elapsed,
            )
        else:
            self.finished.emit(card_hash, "", elapsed)


class SafeClassMounterWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Safe Computer Class mounter (Windows)")
        self.setGeometry(200, 200, 520, 340)

        self._rfid_thread: QThread | None = None
        self._rfid_worker: RfidReadWorker | None = None
        self._pending_server: str | None = None
        self._pending_username: str | None = None

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

        # RFID port
        h4b = QHBoxLayout()
        h4b.addWidget(QLabel("RFID port:"))
        self.rfid_port_combo = QComboBox()
        self.rfid_port_combo.setEditable(False)
        self.btn_refresh_ports = QPushButton("refresh")
        self.btn_refresh_ports.clicked.connect(self.refresh_rfid_ports)
        h4b.addWidget(self.rfid_port_combo)
        h4b.addWidget(self.btn_refresh_ports)
        layout.addLayout(h4b)

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

        self.refresh_rfid_ports()

    def refresh_rfid_ports(self):
        # Заполняем список доступных COM‑портов для RFID (Auto + COMx...)
        current = self.rfid_port_combo.currentText().strip()
        self.rfid_port_combo.clear()
        self.rfid_port_combo.addItem("Auto")

        if list_ports is not None:
            try:
                ports = [p.device for p in list_ports.comports()]
                for dev in ports:
                    self.rfid_port_combo.addItem(dev)
            except Exception:
                pass

        # По умолчанию пытаемся выбрать SAFE_RFID_PORT, если он задан,
        # иначе сохраняем прежний выбор, иначе остаёмся в Auto.
        env_port = os.environ.get("SAFE_RFID_PORT", "").strip()
        preferred = env_port or current
        if preferred and preferred != "Auto":
            idx = self.rfid_port_combo.findText(preferred)
            if idx >= 0:
                self.rfid_port_combo.setCurrentIndex(idx)
            else:
                self.rfid_port_combo.setCurrentIndex(0)
        else:
            self.rfid_port_combo.setCurrentIndex(0)

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
        2) В фоне считываем хеш карты с контроллера SCC_rfid_scanner.ino
           (без блокировки GUI‑потока).
        3) После успешного чтения запрашиваем PIN у пользователя (без логирования значения).
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

        self._pending_server = server
        self._pending_username = username

        # Запускаем чтение RFID в отдельном потоке, чтобы не блокировать GUI.
        self.log_msg("waiting for RFID card (present a card to the reader)...")
        self.btn_register_rfid.setEnabled(False)

        chosen_port = self.rfid_port_combo.currentText().strip()
        preferred_port = None if (not chosen_port or chosen_port == "Auto") else chosen_port

        thread = QThread(self)
        worker = RfidReadWorker(timeout_seconds=60.0, preferred_port=preferred_port)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_rfid_read_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._rfid_thread = thread
        self._rfid_worker = worker

        thread.start()

    def _on_rfid_read_finished(self, card_hash: str, error_message: str, elapsed: float):
        self.btn_register_rfid.setEnabled(True)

        elapsed_int = int(elapsed)

        if error_message:
            self.log_msg("RFID card not read (timeout or device error)")
            QMessageBox.warning(
                self,
                "RFID error",
                error_message,
            )
            return

        self.log_msg(f"RFID card hash received after {elapsed_int} s")

        server = self._pending_server or self.server_edit.text().strip()
        username = self._pending_username or self.user_edit.text().strip()

        if not server or not username:
            QMessageBox.warning(
                self,
                "error",
                "server and username are required for RFID registration",
            )
            return

        # Запрос PIN у пользователя (только после успешного считывания карты)
        pin, ok = QInputDialog.getText(
            self,
            "RFID PIN",
            "Enter PIN for this card:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not pin:
            return

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
