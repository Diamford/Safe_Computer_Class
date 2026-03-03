import logging
import os
import subprocess
import sys
import threading
import time
import hashlib
from pathlib import Path

from PyQt6 import QtCore, QtWidgets

try:
    import serial  # связь с ESP32‑C3 по COM‑порту
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

try:
    import requests  # HTTP‑клиент для общения с сервером
except ImportError:
    requests = None


LOG_DIR_WINDOWS = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "safe_computer_class",
    "logs",
)
LOG_DIR_LINUX = "/var/log/safe_computer_class"
LOG_FILENAME = "key_daemon.log"


def get_log_path() -> str:
    """
    Возвращает путь к файлу логов демона.

    - На Windows: %LOCALAPPDATA%/safe_computer_class/logs/key_daemon.log
    - На Linux:  /var/log/safe_computer_class/key_daemon.log
    """
    if os.name == "nt":
        base_dir = Path(LOG_DIR_WINDOWS)
    else:
        base_dir = Path(LOG_DIR_LINUX)

    try:
        base_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Если не получилось создать каталог логов, откатываемся в домашний каталог
        fallback = Path.home() / "safe_computer_class" / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        base_dir = fallback

    return str(base_dir / LOG_FILENAME)


def setup_logger() -> logging.Logger:
    """
    Настраивает логгер для PIN‑демона.

    ВАЖНО: здесь НЕЛЬЗЯ логировать реальные значения PIN.
    """
    logger = logging.getLogger("safe_computer_class.daemon")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        log_path = get_log_path()
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


LOGGER = setup_logger()


def _sha256_hex(text: str) -> str:
    """
    Возвращает HEX‑представление SHA‑256 от переданной строки.

    ВАЖНО: сюда не передавать "сырые" секреты для логирования где‑то ещё.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest.upper()


def verify_card_hash(card_hash: str) -> tuple[bool, bool]:
    """
    Проверка хеша карты на стороне сервера.

    Возвращает пару (exists, require_pin):
      - exists:     True, если карта найдена в базе
      - require_pin: True, если сервер требует ввод PIN для этой карты

    Эндпоинт задаётся переменной окружения SAFE_CLASS_CARD_URL.
    Формат ответа предполагается JSON:
      { "exists": true/false, "require_pin": true/false }
    """
    url = os.environ.get("SAFE_CLASS_CARD_URL", "").strip()

    if not url:
        LOGGER.error(
            "SAFE_CLASS_CARD_URL не задан — проверка карты на сервере невозможна"
        )
        return False, False

    if requests is None:
        LOGGER.error(
            "Библиотека 'requests' не установлена — проверка карты на сервере невозможна"
        )
        return False, False

    try:
        resp = requests.post(
            url,
            json={"card_hash": card_hash},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        exists = bool(data.get("exists"))
        require_pin = bool(data.get("require_pin", True))
        LOGGER.info(
            "Результат проверки карты на сервере: exists=%s, require_pin=%s",
            exists,
            require_pin,
        )
        return exists, require_pin
    except Exception:
        LOGGER.exception("Ошибка HTTP‑запроса при проверке карты на сервере")
        return False, False


def verify_pin_on_server(card_hash: str, pin: str) -> bool:
    """
    Проверка PIN на стороне сервера.

    Перед отправкой PIN хешируется с помощью SHA‑256.

    Эндпоинт задаётся переменной окружения SAFE_CLASS_PIN_URL.
    Формат ответа предполагается JSON:
      { "ok": true/false }
    """
    url = os.environ.get("SAFE_CLASS_PIN_URL", "").strip()

    if not url:
        LOGGER.error(
            "SAFE_CLASS_PIN_URL не задан — проверка PIN на сервере невозможна"
        )
        return False

    if requests is None:
        LOGGER.error(
            "Библиотека 'requests' не установлена — проверка PIN на сервере невозможна"
        )
        return False

    # Хешируем PIN перед отправкой.
    pin_hash = _sha256_hex(pin)

    try:
        resp = requests.post(
            url,
            json={"card_hash": card_hash, "pin_hash": pin_hash},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        ok = bool(data.get("ok"))
        LOGGER.info("Результат проверки PIN на сервере: ok=%s", ok)
        return ok
    except Exception:
        LOGGER.exception("Ошибка HTTP‑запроса при проверке PIN на сервере")
        return False


def _run_cmd(cmd: str) -> tuple[bool, str]:
    """
    Запуск shell‑команды и возврат (ok, stdout/stderr).

    Используется для подключения SMB‑шары так же, как в mb_mount.py.
    """
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            shell=True,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as exc:
        return False, exc.stderr


def mount_school_drive_from_env() -> None:
    """
    Подключает SMB‑шару "school" к сетевому диску, как в mb_mount.py.

    Параметры берутся из переменных окружения:
      - SAFE_CLASS_SERVER  (обязателен), пример: 192.168.0.10
      - SAFE_CLASS_USER    (обязателен)
      - SAFE_CLASS_PASS    (может быть пустым)
      - SAFE_CLASS_DRIVE   (необязателен, по умолчанию "Z:")

    При ошибке только логируем, работу демона не останавливаем.
    """
    server = os.environ.get("SAFE_CLASS_SERVER", "").strip()
    username = os.environ.get("SAFE_CLASS_USER", "").strip()
    password = os.environ.get("SAFE_CLASS_PASS", "")
    drive_letter = os.environ.get("SAFE_CLASS_DRIVE", "Z:").strip() or "Z:"

    if not server or not username:
        LOGGER.info(
            "Параметры SMB не заданы (SAFE_CLASS_SERVER/SAFE_CLASS_USER), "
            "подключение сетевого диска пропущено"
        )
        return

    unc = f"\\\\{server}\\school"
    cmd = (
        f'net use {drive_letter} "{unc}" "{password}" '
        f'/user:"{username}" /persistent:no'
    )

    LOGGER.info(
        "Подключение SMB‑шары %s к диску %s для пользователя %s",
        unc,
        drive_letter,
        username,
    )
    ok, msg = _run_cmd(cmd)
    if ok:
        LOGGER.info("SMB‑шара успешно подключена: %s", msg.strip())
    else:
        LOGGER.error("Ошибка подключения SMB‑шары: %s", msg.strip())


class PinDialog(QtWidgets.QDialog):
    """
    Простое диалоговое окно для ввода PIN.

    Обратите внимание: само значение PIN НИГДЕ не логируется.
    """

    pin_entered = QtCore.pyqtSignal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Введите PIN")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel("Пожалуйста, введите PIN:")
        self.pin_edit = QtWidgets.QLineEdit()
        self.pin_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.pin_edit.setMaxLength(32)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(label)
        layout.addWidget(self.pin_edit)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        pin = self.pin_edit.text()
        # НЕЛЬЗЯ логировать значение PIN!
        # Разрешается только зафиксировать факт ввода.
        LOGGER.info("PIN введён (значение не логируется)")
        self.pin_entered.emit(pin)
        self.accept()


class DaemonController(QtCore.QObject):
    """
    Контроллер, который:
    - показывает диалог ввода PIN по запросу
    - обрабатывает введённый PIN (без логирования значения)
    """

    def __init__(self, app: QtWidgets.QApplication) -> None:
        super().__init__()
        self.app = app
        self._dialog: PinDialog | None = None
        self._current_card_hash: str | None = None

    @QtCore.pyqtSlot()
    def show_pin_dialog(self) -> None:
        if self._dialog is not None and self._dialog.isVisible():
            # Диалог уже открыт
            return

        LOGGER.info("Открытие окна ввода PIN")
        self._dialog = PinDialog()
        self._dialog.pin_entered.connect(self.handle_pin)
        self._dialog.show()

    @QtCore.pyqtSlot()
    def _on_auth_success(self) -> None:
        """
        Вызывается, когда сервер подтвердил доступ (карта + PIN при необходимости).
        Здесь запускается дальнейшая логика — подключение сетевой папки и т.п.
        """
        LOGGER.info("Сервер подтвердил доступ, выполняем подключение папки")

        if os.name == "nt":
            try:
                mount_school_drive_from_env()
            except Exception:
                LOGGER.exception(
                    "Не удалось выполнить подключение SMB‑шары после успешной авторизации"
                )

    @QtCore.pyqtSlot(str)
    def handle_card_hash(self, card_hash: str) -> None:
        """
        Обработка хеша карты, полученного от ESP32‑C3 (SCC_rfid_scanner.ino).

        Поток с RFID‑ридером вызывает этот слот в GUI‑потоке через invokeMethod.
        """
        try:
            LOGGER.info("Получен хеш карты (длина: %d символов)", len(card_hash))

            exists, require_pin = verify_card_hash(card_hash)
            if not exists:
                LOGGER.warning("Карта не найдена на сервере")
                return

            self._current_card_hash = card_hash

            if require_pin:
                LOGGER.info("Сервер требует ввод PIN для данной карты")
                self.show_pin_dialog()
            else:
                LOGGER.info(
                    "Сервер не требует PIN для данной карты, доступ предоставлен"
                )
                self._on_auth_success()
        except Exception:
            LOGGER.exception("Ошибка при обработке хеша карты")

    @QtCore.pyqtSlot(str)
    def handle_pin(self, pin: str) -> None:
        """
        Здесь должна находиться бизнес‑логика обработки PIN.

        ПРИМЕР:
          - проверка PIN на стороне сервера;
          - запуск/разблокировка локального приложения;
          - запись в защищённое хранилище и т.д.

        ВАЖНО: не писать значение PIN в логи и на экран.
        Можно логировать только факт успешной/неуспешной проверки.
        """
        try:
            LOGGER.info("PIN получен (длина: %d символов)", len(pin))

            if not self._current_card_hash:
                LOGGER.warning(
                    "PIN введён, но нет активной карты (card_hash не установлен)"
                )
                return

            ok = verify_pin_on_server(self._current_card_hash, pin)
            if ok:
                LOGGER.info("PIN успешно проверен сервером")
                self._on_auth_success()
            else:
                LOGGER.warning("PIN отклонён сервером")
        except Exception:
            LOGGER.exception("Ошибка при обработке введённого PIN")


class RfidThread(threading.Thread):
    """
    Поток, который работает с ESP32‑C3 + SCC_rfid_scanner.ino по Serial:
      1) Находит подходящий COM‑порт (либо из SAFE_RFID_PORT, либо автопоиск).
      2) Выполняет рукопожатие "HELLO_SCC" / "SCC_RFID_V1_OK".
      3) Ожидает строку "CARD_HASH:<HEX>".
      4) Передаёт полученный хеш в GUI‑поток через DaemonController.handle_card_hash.

    Все исключения логируются и не останавливают поток.
    """

    HANDSHAKE_REQUEST = "HELLO_SCC"
    HANDSHAKE_RESPONSE = "SCC_RFID_V1_OK"
    PREFIX_CARD_HASH = "CARD_HASH:"

    def __init__(self, controller: DaemonController) -> None:
        super().__init__(daemon=True)
        self.controller = controller
        self._running = True
        self._serial: "serial.Serial | None" = None

    def stop(self) -> None:
        self._running = False
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass

    def run(self) -> None:
        if serial is None:
            LOGGER.error(
                "Библиотека 'pyserial' не установлена. "
                "Связь с ESP32‑C3 по Serial недоступна."
            )
            return

        LOGGER.info("RFID‑поток запущен, поиск устройства ESP32‑C3...")

        while self._running:
            try:
                if self._serial is None:
                    self._serial = self._open_device_port()
                    if self._serial is None:
                        time.sleep(5)
                        continue

                if not self._do_handshake():
                    LOGGER.warning("Рукопожатие с устройством не удалось, переподключение")
                    self._close_serial()
                    time.sleep(2)
                    continue

                card_hash = self._wait_for_card_hash()
                if not card_hash:
                    # либо таймаут, либо ошибка — попробуем начать всё заново
                    continue

                LOGGER.info("Хеш карты получен от устройства, передаём в GUI‑поток")
                QtCore.QMetaObject.invokeMethod(
                    self.controller,
                    "handle_card_hash",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, card_hash),
                )

            except Exception:
                LOGGER.exception("Необработанное исключение в RFID‑потоке")
                self._close_serial()
                time.sleep(2)

    def _close_serial(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    def _open_device_port(self) -> "serial.Serial | None":
        """
        Открывает COM‑порт с ESP32‑C3.

        Сначала пытается использовать SAFE_RFID_PORT, затем — автопоиск
        по всем доступным портам, отправляя HELLO_SCC и ожидая
        SCC_RFID_V1_OK в ответ.
        """
        if list_ports is None:
            LOGGER.error(
                "serial.tools.list_ports недоступен — автопоиск COM‑порта невозможен"
            )
            return None

        env_port = os.environ.get("SAFE_RFID_PORT", "").strip()
        if env_port:
            LOGGER.info("Пробуем подключиться к ESP32‑C3 на порту %s", env_port)
            try:
                ser = serial.Serial(env_port, 115200, timeout=2)
                return ser
            except Exception:
                LOGGER.exception(
                    "Не удалось открыть порт из SAFE_RFID_PORT: %s", env_port
                )

        LOGGER.info("Поиск ESP32‑C3 по доступным COM‑портам")
        for port in list_ports.comports():
            dev = port.device
            try:
                ser = serial.Serial(dev, 115200, timeout=2)
                LOGGER.info("Пробная попытка рукопожатия с устройством на %s", dev)
                ser.reset_input_buffer()
                ser.write((self.HANDSHAKE_REQUEST + "\n").encode("utf-8"))
                line = ser.readline().decode("utf-8", "ignore").strip()
                if line == self.HANDSHAKE_RESPONSE:
                    LOGGER.info("Найдено RFID‑устройство на порту %s", dev)
                    return ser
                ser.close()
            except Exception:
                LOGGER.exception("Ошибка при проверке порта %s", dev)

        LOGGER.warning("RFID‑устройство не найдено ни на одном COM‑порту")
        return None

    def _do_handshake(self) -> bool:
        """
        HELLO_SCC / SCC_RFID_V1_OK с устройством.
        """
        if self._serial is None:
            return False

        try:
            self._serial.reset_input_buffer()
            self._serial.write((self.HANDSHAKE_REQUEST + "\n").encode("utf-8"))
            deadline = time.time() + 5.0
            while time.time() < deadline and self._running:
                line = self._serial.readline().decode("utf-8", "ignore").strip()
                if not line:
                    continue
                LOGGER.info("Ответ от устройства при рукопожатии: %s", line)
                if line == self.HANDSHAKE_RESPONSE:
                    LOGGER.info("Рукопожатие с RFID‑устройством успешно")
                    return True
                if line.startswith("ERR:"):
                    LOGGER.warning("Ошибка от устройства при рукопожатии: %s", line)
                    return False
        except Exception:
            LOGGER.exception("Ошибка при рукопожатии с устройством")
            return False

        LOGGER.warning("Таймаут рукопожатия с устройством")
        return False

    def _wait_for_card_hash(self) -> str | None:
        """
        Ожидает строку вида "CARD_HASH:<HEX>" от устройства.
        После получения возвращает только HEX‑часть.
        """
        if self._serial is None:
            return None

        try:
            deadline = time.time() + 60.0  # до минуты ожидания карты
            while time.time() < deadline and self._running:
                line = self._serial.readline().decode("utf-8", "ignore").strip()
                if not line:
                    continue
                LOGGER.info("Строка от RFID‑устройства: %s", line)
                if line.startswith(self.PREFIX_CARD_HASH):
                    return line[len(self.PREFIX_CARD_HASH) :].strip()
                if line.startswith("ERR:"):
                    LOGGER.warning("Ошибка от устройства: %s", line)
                    return None
        except Exception:
            LOGGER.exception("Ошибка при ожидании CARD_HASH от устройства")
            return None

        LOGGER.warning("Таймаут ожидания CARD_HASH от устройства")
        return None


def main() -> int:
    LOGGER.info("Запуск PIN‑демона")

    app = QtWidgets.QApplication(sys.argv)
    controller = DaemonController(app)

    rfid_thread = RfidThread(controller)
    rfid_thread.start()

    exit_code = 0
    try:
        exit_code = app.exec()
    except Exception:
        LOGGER.exception("Необработанное исключение в основном GUI‑цикле")
        exit_code = 1
    finally:
        rfid_thread.stop()
        LOGGER.info("PIN‑демон завершает работу с кодом %s", exit_code)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

