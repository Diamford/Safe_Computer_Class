# Safe Computer Class (SCC) - Refactored

## Overview

Safe Computer Class v0.6.0 - это система управления доступом к сетевым дискам в школьном компьютерном классе. Система обеспечивает ролевой контроль доступа для учеников и учителей, используя RFID-карты и PIN-коды для аутентификации.

## Architecture

Проект переработан согласно принципам чистой архитектуры с разделением на слои:

- **Domain**: Бизнес-логика и правила (entities, services, exceptions)
- **Application**: Use cases и оркестрация
- **Infrastructure**: Адаптеры для внешних систем (DB, Samba, Linux users)
- **Presentation**: HTTP API и контроллеры

## Installation

```bash
# Install dependencies
pip install -e .

# Initialize database
scc init --db school.db

# Add users
scc addstudent --username student001 --class 9_A --db school.db
scc addteacher --username teacher001 --db school.db
```

## Running

```bash
# Start server (Linux)
python -m src.main serve --host 0.0.0.0 --port 5000 --db school.db

# or
scc serve --host 0.0.0.0 --port 5000 --db school.db
```

### Запуск демона на клиенте (Windows):
1. Без env-переменных (рекомендуется): создайте `client_config.json` рядом с `daemon.pyw` и `mb_mount.py`, либо используйте готовый `client_config.json` в корне проекта:
   ```json
   {
     "SAFE_CLASS_SERVER": "127.0.0.1:5000",
     "SAFE_CLASS_AUTH_URL": "http://127.0.0.1:5000/api/scc/auth",
     "SAFE_CLASS_REGISTER_URL": "http://127.0.0.1:5000/api/scc/register_card",
     "SAFE_CLASS_CARD_URL": "http://127.0.0.1:5000/api/scc/verify_card",
     "SAFE_CLASS_PIN_URL": "http://127.0.0.1:5000/api/scc/verify_pin",
     "SAFE_CLASS_DRIVE": "Z:"
   }
   ```

2. Опционально, при необходимости, можно задать переменные окружения вместо файла:
   - `SAFE_CLASS_AUTH_URL` и прочие (приоритет env > config)

2. Запустите GUI (`mb_mount.py`) для ручного монтирования или регистрации RFID.
   ```bash
   python mb_mount.py
   ```

3. Запустите фоновый демон `daemon.pyw`, который работает с RFID считывателем:
   ```bash
   python daemon.pyw
   ```

4. Для регистрации карты через GUI:
   - Нажмите "register RFID"
   - Поднесите карту к считывателю
   - Введите PIN

5. Для авторизации и монтирования (в режиме `auth`):
   - В режим по умолчанию `SAFE_CLASS_DAEMON_MODE=auth`
   - Приложение попросит PIN, после проверки автоматически смонтирует диск.

## API Endpoints

- `POST /api/scc/register_card` - Регистрация RFID карты
- `POST /api/scc/verify_card` - Проверка существования карты
- `POST /api/scc/auth` - Аутентификация пользователя
- `GET /health` - Проверка здоровья сервиса

## Security Improvements

- Убраны command injection уязвимости
- Добавлена валидация входных данных
- Секреты вынесены в environment variables
- Добавлены health checks

## Next Steps

1. Добавить TLS/HTTPS
2. Интегрировать JWT токены
3. Добавить rate limiting
4. Создать unit и integration тесты
5. Настроить CI/CD pipeline