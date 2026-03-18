# Руководство по установке Safe Computer Class v0.5

**Важно**: Это руководство актуально для версии **v0.5+ с security fixes Sprint-1**, где закрыты уязвимости shell injection и проблемы видимости паролей.

## Содержание

1. [Системные требования](#системные-требования)
2. [Быстрый старт (Docker)](#быстрый-старт-docker)
3. [Установка на Linux сервер](#установка-на-linux-сервер)
4. [Установка Windows клиента](#установка-windows-клиента)
5. [Установка Linux демона](#установка-linux-демона)
6. [Проверка безопасности](#проверка-безопасности)
7. [Диагностика и помощь](#диагностика-и-помощь)

---

## Системные требования

### Для сервера (Linux)

| Параметр | Минимум | Рекомендуется |
|----------|---------|--------------|
| ОС | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS |
| Python | 3.9 | 3.10+ |
| RAM | 1 GB | 2 GB |
| Диск | 5 GB | 20 GB |
| CPU | 1 ядро | 2+ ядра |
| Права | sudo | sudo или root |

### Для Windows клиента

- **ОС**: Windows 7 SP1 и выше
- **Python**: 3.9 или выше
- **Доступ**: Администратор (для монтирования дисков)
- **Сеть**: Доступ к SMB порту 445 сервера

### Для Linux демона

- **ОС**: Ubuntu/Debian с Python 3.9+
- **Окружение**: GUI (X11 или Wayland)
- **Оборудование**: RFID читатель на COM/USB порту
- **Доступ**: Обычный пользователь (без sudo)

---

## Быстрый старт (Docker)

### 1. Клонирование репозитория

```bash
git clone https://github.com/Diamford/Safe_Computer_Class.git
cd Safe_Computer_Class
git checkout modernization-v0.5
```

### 2. Запуск с Docker Compose

```bash
# Установить Docker (если не установлен)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Запустить сервис
docker-compose up -d

# Проверить статус
docker-compose logs -f

# Сервис будет доступен на http://localhost/api/scc/...
```

### 3. Инициализация базы данных

```bash
# Создать первого учителя
docker-compose exec scc_server python3 scc.py addclass 10a
docker-compose exec scc_server python3 scc.py addteacher ivan 1001 mypassword
docker-compose exec scc_server python3 scc.py addteacherclass ivan 10a
```

---

## Установка на Linux сервер

### 1. Системные зависимости

```bash
# Обновить пакеты
sudo apt-get update
sudo apt-get upgrade -y

# Установить зависимости
sudo apt-get install -y \
    python3.10 python3.10-venv python3-pip \
    samba samba-vfs-modules \
    acl attr \
    git \
    curl wget \
    build-essential

# Проверить Python версию
python3 --version
# Должно быть 3.9 или выше
```

### 2. Клонирование и настройка

```bash
# Клонировать репозиторий
git clone https://github.com/Diamford/Safe_Computer_Class.git
cd Safe_Computer_Class
git checkout modernization-v0.5

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

### 3. Инициализация структуры

```bash
# Инициализировать структуру и Samba
sudo python3 scc.py init

# Запустить HTTP сервер (порт 80)
# На background:
sudo nohup python3 scc.py serve 0.0.0.0 80 > /var/log/scc_server.log 2>&1 &

# Или с systemd (рекомендуется):
sudo cp systemd/scc-http.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start scc-http
sudo systemctl enable scc-http
```

### 4. Добавление первых классов и учителей

```bash
# Добавить классы
sudo python3 scc.py addclass 10a
sudo python3 scc.py addclass 10b
sudo python3 scc.py addclass 11a

# Добавить учителя (UID должен быть уникален, например 1001)
sudo python3 scc.py addteacher ivan 1001 password123

# Связать учителя с классом
sudo python3 scc.py addteacherclass ivan 10a
sudo python3 scc.py addteacherclass ivan 11a

# Добавить ученика (относится к классу)
sudo python3 scc.py addstudent petr 10a 2001 student_pass

# Проверить список пользователей
sudo python3 scc.py list

# Проверить базу данных
sudo python3 scc.py status
```

### 5. Проверка Samba

```bash
# Проверить конфигурацию
sudo smbclient -L localhost -U%

# Проверить статус smbd
sudo systemctl status smbd

# Проверить доступность шары
net use \\server_ip\school /user:ivan password123
# На Linux: smbclient //server_ip/school -U ivan%password123
```

---

## Установка Windows клиента

### 1. Установка Python и зависимостей

```bash
# Скачать Python 3.10+ с https://www.python.org/downloads/
# Запустить установщик с флагом "Add Python to PATH"

# Открыть PowerShell от администратора
# Проверить Python
python --version

# Установить зависимости
pip install PyQt6 requests keyboard pyserial

# Или через requirements
pip install -r requirements.txt
```

### 2. Клонирование кода

```bash
git clone https://github.com/Diamford/Safe_Computer_Class.git
cd Safe_Computer_Class
git checkout modernization-v0.5
```

### 3. Настройка переменных окружения

Создать файл `.env` в домашней папке пользователя или в переменных окружения Windows:

```bash
# Пример .env файла
SAFE_CLASS_SERVER=192.168.1.100          # IP сервера
SAFE_CLASS_DRIVE=Z:                       # Буква диска для монтирования
SAFE_RFID_PORT=COM3                       # COM порт RFID читателя (или авто)
SAFE_CLASS_DAEMON_MODE=auth               # Режим: "auth" или "register"
```

### 4. Запуск mb_mount.py (тестирование)

```bash
# В PowerShell от администратора
python mb_mount.py

# Если всё работает - видите GUI с кнопками для монтирования/размонтирования
```

### 5. Установка как сервис Windows (опционально)

```bash
# Создать bat файл для запуска
# safe_computer_class_launcher.bat
@echo off
cd c:\path\to\Safe_Computer_Class
python daemon.pyw

# Установить как автозапуск через Task Scheduler
# или использовать программу типа NSSM для запуска python скрипта как сервиса
```

---

## Установка Linux демона

### 1. Установка на рабочую станцию Linux

```bash
# Установить зависимости
sudo apt-get install -y python3 python3-pip pyqt6

# Клонировать код
git clone https://github.com/Diamford/Safe_Computer_Class.git
cd Safe_Computer_Class
git checkout modernization-v0.5

# Установить Python зависимости
pip3 install PyQt6 requests pyserial keyboard

# Подключить USB RFID читатель
# Проверить порт: ls -la /dev/ttyUSB*
```

### 2. Настройка переменных окружения

```bash
# Создать ~/.bashrc или ~/.profile запись
export SAFE_CLASS_SERVER=192.168.1.100
export SAFE_CLASS_USER=ivan
export SAFE_CLASS_PASS=password123
export SAFE_CLASS_DAEMON_MODE=auth
export SAFE_RFID_PORT=/dev/ttyUSB0

# Или создать файл ~/.safe_computer_class/config
# и источить его перед запуском
```

### 3. Запуск демона

```bash
python3 daemon.pyw

# Если нужен фоновый запуск через systemd (для администратора):
sudo cp systemd/scc-daemon.user.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start scc-daemon
systemctl --user enable scc-daemon
```

---

## Проверка безопасности

### ✅ Sprint-1 Security Fixes

После обновления до версии с security fixes, проверьте:

#### 1. Отсутствие shell injection уязвимостей

```bash
# На сервере проверить, что команды используют безопасные вызовы
grep -r "shell=True" .  # Должны быть только в старых комментариях
grep -r "bash -c" .     # Не должны быть в production коде

# Проверить исходный код:
cat scc.py | grep "smbpasswd"
# Должна видеть: input=password_input вместо "bash -c" с паролем
```

#### 2. Валидация входных данных

```bash
# Попробуйте добавить пользователя с опасными символами
sudo python3 scc.py addteacher "test'; rm -rf /" 1010 password
# Должен получить: invalid username: username contains invalid characters

# Добавьте класс с опасным именем
sudo python3 scc.py addclass "class/../../dangerous"
# Должен получить: invalid class_name: class_name contains invalid characters

# Добавьте с неверным UID
sudo python3 scc.py addteacher validuser abc password
# Должен получить: invalid uid: must be an integer
```

#### 3. Проверка логов (PIN не видны)

```bash
# Проверить логи демона на Windows
cat ~/AppData/Local/safe_computer_class/logs/key_daemon.log | grep PIN
# Должны видеть: "PIN введён (значение не логируется)"
# НЕ должны видеть: реальные значения PIN

# На Linux
cat /var/log/safe_computer_class/key_daemon.log | grep PIN
# Аналогично
```

---

## Диагностика и помощь

### Проблема: Samba не стартует

```bash
# Проверить конфигурацию
sudo testparm /etc/samba/smb.conf

# Перезапустить
sudo systemctl restart smbd

# Посмотреть логи
sudo tail -f /var/log/samba/log.smbd
```

### Проблема: Ошибка при добавлении пользователя

```bash
# Проверить наличие UID в системе
id -u testuser  # Если выведет число - пользователь существует

# Удалить пользователя и пересоздать
sudo python3 scc.py deluser testuser
sudo python3 scc.py addstudent testuser 10a 2050 password

# Проверить логи
dmesg | tail -20
```

### Проблема: Windows клиент не подключается к SMB

```bash
# Проверить доступность сервера
ping 192.168.1.100

# Проверить SMB доступность (с Linux)
smbclient -L //192.168.1.100 -U%

# Проверить firewall на Linux сервере
sudo ufw status
sudo ufw allow samba

# Проверить firewall на Windows клиенте
# Открыть ports: 139 (NetBIOS), 445 (SMB)
```

### Проблема: RFID читатель не подключается

```bash
# Проверить порты на Windows
python -m serial.tools.list_ports

# На Linux
ls -la /dev/ttyUSB*
ls -la /dev/ttyACM*

# Проверить права доступа
sudo usermod -a -G dialout $USER
newgrp dialout

# Перезагрузить
reboot
```

### Проблема: Недостаточно прав для операции

```bash
# Команды scc.py требуют sudo для:
# - useradd, userdel, chown, chmod (управление файлами)
# - smbpasswd (Samba пользователи)
# - systemctl (перезапуск samba)

# Если нужен non-root запуск, настроить sudoers:
# Отредактировать: sudo visudo
# Добавить строку:
# www-data ALL=(ALL) NOPASSWD: /usr/bin/python3 /path/to/scc.py

# ВНИМАНИЕ: Это уменьшает безопасность, используйте осторожно!
```

### Проверить версию и статус

```bash
# Проверить версию
cat scc.py | grep "v0.5"

# HTTP сервер работает?
curl http://localhost/api/scc/verify_card -X POST -d '{"card_hash":"test"}'

# Проверить доступ к БД
sudo python3 scc.py list
sudo python3 scc.py status
```

---

## Файлы документации

- `SECURITY_FIXES_SPRINT1.md` - Детальное описание всех security fixes
- `README.md` - Общее описание проекта
- `INSTALL.md` - Оригинальное руководство установки
- `RoaadMap_sprint-1.md` - План оставшихся работ

---

## Поддержка и контакты

При возникновении проблем:

1. Проверьте файл логов (`/var/log/scc_server.log`, `~/AppData/Local/safe_computer_class/logs/`)
2. Запустите проверку безопасности выше
3. Обратитесь к документации в `SECURITY_FIXES_SPRINT1.md`
4. Откройте issue на GitHub: https://github.com/Diamford/Safe_Computer_Class/issues

---

## Лицензия

Safe Computer Class - Project for educational institutions  
© 2024-2026

