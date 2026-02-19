import logging
import os
import sys
import threading
from pathlib import Path

from PyQt6 import QtCore, QtWidgets

try:
    import keyboard  # глобальные хоткеи / перехват клавиш
except ImportError:
    keyboard = None


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

    @QtCore.pyqtSlot()
    def show_pin_dialog(self) -> None:
        if self._dialog is not None and self._dialog.isVisible():
            # Диалог уже открыт
            return

        LOGGER.info("Открытие окна ввода PIN")
        self._dialog = PinDialog()
        self._dialog.pin_entered.connect(self.handle_pin)
        self._dialog.show()

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
            # Пример безопасного логирования:
            LOGGER.info("PIN получен (длина: %d символов)", len(pin))

            # TODO: замените этот блок на реальную обработку PIN.
            # Например, вызов функции verify_pin(pin) и разбор результата.
            # if verify_pin(pin):
            #     LOGGER.info("PIN успешно проверен")
            # else:
            #     LOGGER.warning("PIN отклонён")
            #pass
        except Exception:
            # Логируем ошибку обработки без раскрытия PIN
            LOGGER.exception("Ошибка при обработке введённого PIN")


class HookThread(threading.Thread):
    """
    Поток, который отслеживает нажатия клавиш и по нажатию '0'
    инициирует показ окна ввода PIN.

    Внутри цикла есть общий try/except, чтобы исключения не
    останавливали обработку (требование P2 из роадмапа).
    """

    def __init__(self, controller: DaemonController) -> None:
        super().__init__(daemon=True)
        self.controller = controller
        self._running = True

    def run(self) -> None:
        if keyboard is None:
            LOGGER.error(
                "Библиотека 'keyboard' не установлена. "
                "Глобальный перехват клавиш недоступен."
            )
            return

        LOGGER.info("Hook‑поток запущен, ожидаем нажатия клавиши '0'")

        while self._running:
            try:
                event = keyboard.read_event()
                if (
                    event.event_type == keyboard.KEY_DOWN
                    and str(event.name) == "0"
                ):
                    LOGGER.info("Обнаружено нажатие клавиши '0'")
                    # Вызываем показ диалога в GUI‑потоке
                    QtCore.QMetaObject.invokeMethod(
                        self.controller,
                        "show_pin_dialog",
                        QtCore.Qt.ConnectionType.QueuedConnection,
                    )
            except Exception:
                # Любые неожиданные исключения логируем, но не даём потоку упасть
                LOGGER.exception("Необработанное исключение в hook‑потоке")

    def stop(self) -> None:
        self._running = False


def main() -> int:
    LOGGER.info("Запуск PIN‑демона")

    app = QtWidgets.QApplication(sys.argv)
    controller = DaemonController(app)

    hook_thread = HookThread(controller)
    hook_thread.start()

    exit_code = 0
    try:
        exit_code = app.exec()
    except Exception:
        LOGGER.exception("Необработанное исключение в основном GUI‑цикле")
        exit_code = 1
    finally:
        hook_thread.stop()
        LOGGER.info("PIN‑демон завершает работу с кодом %s", exit_code)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

