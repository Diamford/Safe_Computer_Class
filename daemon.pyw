import sys
import os
import time
import logging
from pathlib import Path
import threading
import queue

from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt6.QtCore import QTimer
import keyboard

# ----------------- ЛОГИ -----------------

def get_log_path():
    if os.name == "nt":  # Windows
        base = Path(os.getenv("LOCALAPPDATA", Path.home()))
        log_dir = base / "safe_computer_class" / "logs"
    else:
        log_dir = Path("/var/log/safe_computer_class")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "key_daemon.log"

log_file = get_log_path()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ----------------- ОЧЕРЕДЬ СОБЫТИЙ -----------------

events = queue.Queue()

# флаг: открыто ли сейчас окно
dialog_open = False

# ----------------- ОКНО PYQT6 -----------------

class PinDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCC – ввод PIN")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout(self)

        self.label = QLabel("Введите PIN:")
        layout.addWidget(self.label)

        self.entry = QLineEdit()
        self.entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.entry.returnPressed.connect(self.on_submit)
        layout.addWidget(self.entry)

        btn = QPushButton("OK")
        btn.clicked.connect(self.on_submit)
        layout.addWidget(btn)

        self.entry.setFocus()

    def closeEvent(self, event):
        """Сбрасываем флаг, когда окно закрывают (любым способом)."""
        global dialog_open
        dialog_open = False
        logger.info("Окно PIN закрыто, dialog_open = False")
        return super().closeEvent(event)

    def on_submit(self):
        pin = self.entry.text()
        logger.info(f"Введён PIN: {pin}")
        # TODO: проверка PIN, Samba и т.д.
        self.close()

open_dialogs: list[PinDialog] = []

def process_events():
    global dialog_open
    try:
        while True:
            ev = events.get_nowait()
            if ev == "show_pin":
                if dialog_open:
                    logger.info("Окно уже открыто, игнорирую событие show_pin")
                    continue
                logger.info("Открываю окно PyQt6 из главного потока")
                dlg = PinDialog()
                dialog_open = True
                open_dialogs.append(dlg)
                dlg.show()
    except queue.Empty:
        pass

# ----------------- HOOK В ОТДЕЛЬНОМ ПОТОКЕ -----------------

def hook_thread():
    logger.info("Hook-поток запущен, ждём '0'")

    def on_key_0(event):
        # Можно дополнительно отфильтровать авто‑повторы по времени, если нужно
        logger.info("Нажата '0' (hook-поток) – посылаю событие GUI")
        events.put("show_pin")

    keyboard.on_press_key("0", on_key_0)
    while True:
        time.sleep(1)

# ----------------- MAIN -----------------

if __name__ == "__main__":
    if os.name != "nt":
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            logger.error("На Linux запустите с sudo для глобального хука.")
            sys.exit(1)

    t = threading.Thread(target=hook_thread, daemon=True)
    t.start()

    app = QApplication(sys.argv)

    timer = QTimer()
    timer.timeout.connect(process_events)
    timer.start(100)

    logger.info(f"Daemon запущен, лог: {log_file}")
    sys.exit(app.exec())
