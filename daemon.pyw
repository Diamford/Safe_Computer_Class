import logging
import os
import subprocess
import sys
import threading
import time
import hashlib
import json
from pathlib import Path

from PyQt6 import QtCore, QtWidgets


def _load_client_config() -> dict:
    """Load local client configuration from client_config.json (optional)."""
    config_path = Path(__file__).resolve().parent / "client_config.json"
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


_CLIENT_CONFIG = _load_client_config()


def _client_setting(key: str, default=None):
    """Get setting from env, then local config, then default."""
    value = os.environ.get(key)
    if value and str(value).strip():
        return str(value).strip()
    value = _CLIENT_CONFIG.get(key)
    if value and str(value).strip():
        return str(value).strip()
    return default


def _default_server_url() -> str:
    """Build default URL for server endpoints.

    - local config key SAFE_CLASS_SERVER
    - env var SAFE_CLASS_SERVER
    - default localhost:5000
    """
    server = _client_setting("SAFE_CLASS_SERVER", "127.0.0.1:5000")
    return f"http://{server}"
try:
    import requests  # HTTP‑клиент для общения с сервером
except ImportError:
    requests = None

from mb_mount import read_card_hash_once, register_card_on_server, mount_school_drive


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
    url = _client_setting("SAFE_CLASS_CARD_URL")
    if not url:
        url = f"{_default_server_url()}/api/scc/verify_card"
        LOGGER.info("SAFE_CLASS_CARD_URL не задан, пробуем %s", url)

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
    url = _client_setting("SAFE_CLASS_PIN_URL")
    if not url:
        url = f"{_default_server_url()}/api/scc/verify_pin"
        LOGGER.info("SAFE_CLASS_PIN_URL не задан, пробуем %s", url)

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


def auth_with_uuid_and_pin(card_hash: str, pin: str) -> tuple[bool, dict]:
    """
    Единый запрос авторизации по UUID (хеш карты) и PIN.

    Эндпоинт задаётся переменной окружения SAFE_CLASS_AUTH_URL.
    Формат запроса:
      { "uuid": "<CARD_HASH>", "pin_hash": "<HEX_SHA256(PIN)>" }

    Ожидаемый ответ:
      {
        "ok": true/false,
        "server": "192.168.0.10",
        "username": "student01",
        "password": "secret",
        "drive_letter": "Z:"   # необязательное поле
      }
    """
    url = _client_setting("SAFE_CLASS_AUTH_URL")
    if not url:
        url = f"{_default_server_url()}/api/scc/auth"
        LOGGER.info("SAFE_CLASS_AUTH_URL не задан, используем %s", url)

    if requests is None:
        LOGGER.error(
            "Библиотека 'requests' не установлена — авторизация по UUID+PIN невозможна"
        )
        return False, {}

    pin_hash = _sha256_hex(pin)

    try:
        resp = requests.post(
            url,
            json={"uuid": card_hash, "card_hash": card_hash, "pin_hash": pin_hash, "pin": pin},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        ok = bool(data.get("success", data.get("ok", False)))
        if not ok:
            LOGGER.warning("Сервер отклонил авторизацию по UUID+PIN")
            return False, {}

        server = str(data.get("server", "")).strip()
        username = str(data.get("username", "")).strip()
        drive_letter = str(data.get("drive_letter", "")).strip() or "Z:"

        LOGGER.info(
            "Сервер подтвердил авторизацию: server=%s, username=%s, drive=%s",
            server,
            username,
            drive_letter,
        )

        payload: dict = {
            "server": server,
            "username": username,
            "drive_letter": drive_letter,
            "password": None,
        }

        if "password" in data:
            payload["password"] = data.get("password")
        elif "password" in data.get("data", {}):
            # backward compatibility
            payload["password"] = data["data"].get("password")

        return True, payload
    except Exception:
        LOGGER.exception("Ошибка HTTP‑запроса при авторизации по UUID+PIN")
        return False, {}


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
            # На Windows stderr/stdout часто в OEM-кодировке (cp866),
            # из-за чего русские сообщения превращаются в "кракозябры".
            encoding="cp866" if os.name == "nt" else "utf-8",
            errors="replace",
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
    # Как в mb_mount.py: монтируем сразу личную папку пользователя.
    unc = f"\\\\{server}\\school\\{username}"
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


def umount_school_drive_from_env() -> None:
    """
    Отключает сетевой диск, подключённый к SMB‑шаре "school".

    Буква диска берётся из SAFE_CLASS_DRIVE (по умолчанию "Z:").
    Функция безопасно логирует только факт операции и результат.
    """
    drive_letter = os.environ.get("SAFE_CLASS_DRIVE", "Z:").strip() or "Z:"

    if os.name != "nt":
        # На Linux этот шаг не нужен, просто выходим.
        LOGGER.info(
            "Отключение SMB‑диска пропущено: umount_school_drive_from_env "
            "актуален только для Windows"
        )
        return

    cmd = f"net use {drive_letter} /delete /y"
    LOGGER.info("Отключение SMB‑диска %s командой: %s", drive_letter, cmd)
    ok, msg = _run_cmd(cmd)
    if ok:
        LOGGER.info("SMB‑диск %s успешно отключён: %s", drive_letter, msg.strip())
    else:
        LOGGER.error("Не удалось отключить SMB‑диск %s: %s", drive_letter, msg.strip())


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
        # Режим работы демона:
        #   - "auth" (по умолчанию) — авторизация по UUID+PIN и монтирование диска
        #   - "register" — регистрация карты за пользователем (как в mb_mount.py)
        self._mode: str = (
            os.environ.get("SAFE_CLASS_DAEMON_MODE", "auth").strip() or "auth"
        )
        LOGGER.info("DaemonController mode: %s", self._mode)
        # SMB‑параметры, полученные от сервера при успешной авторизации
        self._smb_server: str | None = None
        self._smb_username: str | None = None
        # None означает "сервер пароль не выдавал". Пустая строка — "пароль пустой".
        self._smb_password: str | None = None
        self._smb_drive: str | None = None

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
                # Если сервер вернул SMB‑параметры и пароль — используем их.
                # Если пароль НЕ выдавался (self._smb_password is None), то
                # монтирование делаем только через переменные окружения (fallback),
                # иначе net use почти всегда даст System error 86.
                if self._smb_server and self._smb_username is not None and self._smb_password is not None:
                    server = self._smb_server
                    username = self._smb_username
                    password = self._smb_password
                    drive_letter = self._smb_drive or "Z:"
                    LOGGER.info(
                        "Монтируем SMB по данным с сервера: %s -> \\\\%s\\school\\%s",
                        drive_letter,
                        server,
                        username,
                    )
                    ok, msg = mount_school_drive(
                        server, username, password, drive_letter=drive_letter
                    )
                    if not ok:
                        LOGGER.error("Ошибка монтирования SMB‑шары: %s", msg.strip())
                    else:
                        self._run_on_success_hook()
                    return

                # Fallback: старый режим через переменные окружения.
                if self._smb_password is None:
                    LOGGER.info(
                        "Сервер не выдал SMB-пароль — используем монтирование по переменным окружения"
                    )
                mount_school_drive_from_env()
                self._run_on_success_hook()
            except Exception:
                LOGGER.exception(
                    "Не удалось выполнить подключение SMB‑шары после успешной авторизации"
                )

    def _run_on_success_hook(self) -> None:
        cmd = os.environ.get("SAFE_CLASS_ON_SUCCESS_CMD", "").strip()
        if not cmd:
            return
        try:
            LOGGER.info("Запуск SAFE_CLASS_ON_SUCCESS_CMD")
            subprocess.Popen(cmd, shell=True)
        except Exception:
            LOGGER.exception("Не удалось выполнить SAFE_CLASS_ON_SUCCESS_CMD")

    @QtCore.pyqtSlot(str)
    def handle_card_hash(self, card_hash: str) -> None:
        """
        Обработка хеша карты, полученного от ESP32‑C3 (SCC_rfid_scanner.ino).

        Поток с RFID‑ридером вызывает этот слот в GUI‑потоке через invokeMethod.
        """
        try:
            LOGGER.info("Получен хеш карты (длина: %d символов)", len(card_hash))
            self._current_card_hash = card_hash

            if self._mode == "register":
                # Режим регистрации карты: сразу запрашиваем PIN для привязки.
                LOGGER.info("Режим регистрации: запрашиваем PIN для новой карты")
                self.show_pin_dialog()
                return

            # Обычный режим авторизации: UUID+PIN.
            LOGGER.info(
                "Режим авторизации: отображаем окно ввода PIN для UUID (хеша карты)"
            )
            self.show_pin_dialog()
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

            if self._mode == "register":
                # Регистрация карты для пользователя через сервер
                server = os.environ.get("SAFE_CLASS_SERVER", "").strip()
                username = os.environ.get("SAFE_CLASS_USER", "").strip()
                if not server or not username:
                    LOGGER.error(
                        "Режим регистрации: не заданы SAFE_CLASS_SERVER/SAFE_CLASS_USER"
                    )
                    return

                ok, msg = register_card_on_server(
                    server, username, self._current_card_hash, pin
                )
                if ok:
                    LOGGER.info(
                        "RFID‑карта успешно зарегистрирована для пользователя %s: %s",
                        username,
                        msg,
                    )
                    QtWidgets.QMessageBox.information(
                        None,
                        "RFID registered",
                        "RFID‑карта успешно зарегистрирована для этого пользователя.",
                    )
                else:
                    LOGGER.error(
                        "Ошибка регистрации RFID‑карты для пользователя %s: %s",
                        username,
                        msg,
                    )
                    QtWidgets.QMessageBox.critical(
                        None,
                        "RFID error",
                        f"Не удалось зарегистрировать RFID‑карту: {msg}",
                    )
                return

            # Обычный режим авторизации: единый запрос UUID+PIN к серверу.
            if (
                not os.environ.get("SAFE_CLASS_AUTH_URL", "").strip()
                and not os.environ.get("SAFE_CLASS_SERVER", "").strip()
            ):
                QtWidgets.QMessageBox.critical(
                    None,
                    "Config error",
                    "Не задана переменная SAFE_CLASS_AUTH_URL.\n"
                    "Также не задан SAFE_CLASS_SERVER (нужен для fallback URL).\n\n"
                    "Задайте SAFE_CLASS_AUTH_URL (предпочтительно) или SAFE_CLASS_SERVER.",
                )
            ok, smb_data = auth_with_uuid_and_pin(self._current_card_hash, pin)
            if ok:
                self._smb_server = smb_data.get("server") or None
                self._smb_username = smb_data.get("username") or None
                # пароль может отсутствовать совсем
                if "password" in smb_data:
                    self._smb_password = smb_data.get("password") or ""
                else:
                    self._smb_password = None
                self._smb_drive = smb_data.get("drive_letter") or None
                LOGGER.info("Авторизация по UUID+PIN успешна, монтируем диск")
                self._on_auth_success()
            else:
                LOGGER.warning("Авторизация по UUID+PIN отклонена сервером")
                QtWidgets.QMessageBox.warning(
                    None,
                    "Auth failed",
                    "Авторизация не прошла.\n\n"
                    "Проверьте, что сервер доступен, и что карта зарегистрирована на сервере.",
                )
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

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        LOGGER.info("RFID‑поток запущен, ожидание карт от ESP32‑C3...")

        while self._running:
            try:
                card_hash = read_card_hash_once(timeout_seconds=60.0)
                if not card_hash:
                    LOGGER.warning(
                        "Не удалось получить CARD_HASH от устройства (таймаут или ошибка)"
                    )
                    time.sleep(2.0)
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
                time.sleep(2.0)


def main() -> int:
    LOGGER.info("Запуск PIN‑демона")

    app = QtWidgets.QApplication(sys.argv)
    # Важно: у нас нет главного окна, только диалог PIN.
    # Если разрешить выход при закрытии последнего окна, Qt завершит app.exec()
    # сразу после ввода PIN, и RFID-поток будет остановлен.
    app.setQuitOnLastWindowClosed(False)
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
        try:
            umount_school_drive_from_env()
        except Exception:
            LOGGER.exception(
                "Ошибка при попытке отключить SMB‑диск при завершении демона"
            )
        LOGGER.info("PIN‑демон завершает работу с кодом %s", exit_code)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

