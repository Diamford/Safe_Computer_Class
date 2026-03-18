# Installation Guide for Safe Computer Class v0.5

**Important**: This guide is for **v0.5+ with Sprint-1 security fixes**, which close shell injection and password visibility issues.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Quick Start with Docker](#quick-start-with-docker)
3. [Linux Server Installation](#linux-server-installation)
4. [Windows Client Installation](#windows-client-installation)
5. [Linux Daemon Installation](#linux-daemon-installation)
6. [Security Verification](#security-verification)
7. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Server (Linux)

| Parameter | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS |
| Python | 3.9 | 3.10+ |
| RAM | 1 GB | 2 GB |
| Disk | 5 GB | 20 GB |
| CPU | 1 core | 2+ cores |
| Privileges | sudo | sudo or root |

### Windows Client

- **OS**: Windows 7 SP1 and later
- **Python**: 3.9 or higher
- **Access**: Administrator (for disk mounting)
- **Network**: Access to SMB port 445 on server

### Linux Daemon

- **OS**: Ubuntu/Debian with Python 3.9+
- **Environment**: GUI (X11 or Wayland)
- **Hardware**: RFID reader on COM/USB port
- **Access**: Regular user (no sudo required)

---

## Quick Start with Docker

### 1. Clone Repository

```bash
git clone https://github.com/Diamford/Safe_Computer_Class.git
cd Safe_Computer_Class
git checkout modernization-v0.5
```

### 2. Run with Docker Compose

```bash
# Install Docker if needed
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Server will be available at http://localhost/api/scc/...
```

### 3. Initialize Database

```bash
# Create first class
docker-compose exec scc_server python3 scc.py addclass 10a

# Create teacher
docker-compose exec scc_server python3 scc.py addteacher ivan 1001 mypassword

# Link teacher to class
docker-compose exec scc_server python3 scc.py addteacherclass ivan 10a
```

---

## Linux Server Installation

### 1. System Dependencies

```bash
# Update packages
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies
sudo apt-get install -y \
    python3.10 python3.10-venv python3-pip \
    samba samba-vfs-modules \
    acl attr \
    git \
    curl wget \
    build-essential

# Verify Python version
python3 --version
# Should be 3.9 or higher
```

### 2. Clone and Setup

```bash
# Clone repository
git clone https://github.com/Diamford/Safe_Computer_Class.git
cd Safe_Computer_Class
git checkout modernization-v0.5

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Initialize Structure

```bash
# Initialize structure and Samba
sudo python3 scc.py init

# Run HTTP server (port 80) in background
sudo nohup python3 scc.py serve 0.0.0.0 80 > /var/log/scc_server.log 2>&1 &

# Or with systemd (recommended)
sudo cp systemd/scc-http.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start scc-http
sudo systemctl enable scc-http
```

### 4. Add Classes and Users

```bash
# Add classes
sudo python3 scc.py addclass 10a
sudo python3 scc.py addclass 10b
sudo python3 scc.py addclass 11a

# Add teacher (UID must be unique, e.g., 1001)
sudo python3 scc.py addteacher ivan 1001 password123

# Link teacher to class
sudo python3 scc.py addteacherclass ivan 10a
sudo python3 scc.py addteacherclass ivan 11a

# Add student (belongs to class)
sudo python3 scc.py addstudent petr 10a 2001 student_pass

# Verify users
sudo python3 scc.py list

# Check status
sudo python3 scc.py status
```

### 5. Verify Samba

```bash
# Check configuration
sudo testparm /etc/samba/smb.conf

# Check smbd status
sudo systemctl status smbd

# Test share access
net use \\server_ip\school /user:ivan password123
# On Linux: smbclient //server_ip/school -U ivan%password123
```

---

## Windows Client Installation

### 1. Install Python and Dependencies

```bash
# Download Python 3.10+ from https://www.python.org/downloads/
# Run installer with "Add Python to PATH" option

# Open PowerShell as Administrator
# Verify Python
python --version

# Install dependencies
pip install PyQt6 requests keyboard pyserial

# Or use requirements file
pip install -r requirements.txt
```

### 2. Clone Code

```bash
git clone https://github.com/Diamford/Safe_Computer_Class.git
cd Safe_Computer_Class
git checkout modernization-v0.5
```

### 3. Set Environment Variables

Create `.env` file in user's home directory or Windows environment variables:

```bash
# Example .env file
SAFE_CLASS_SERVER=192.168.1.100          # Server IP
SAFE_CLASS_DRIVE=Z:                       # Drive letter for mounting
SAFE_RFID_PORT=COM3                       # RFID reader COM port (auto-detect)
SAFE_CLASS_DAEMON_MODE=auth               # Mode: "auth" or "register"
```

### 4. Run mb_mount.py (Testing)

```bash
# Run from PowerShell as Administrator
python mb_mount.py

# You should see GUI with mount/unmount buttons
```

### 5. Install as Windows Service (Optional)

```bash
# Create batch file for launching
# safe_computer_class_launcher.bat
@echo off
cd c:\path\to\Safe_Computer_Class
python daemon.pyw

# Register as auto-start via Task Scheduler
# Or use NSSM to run Python script as service
```

---

## Linux Daemon Installation

### 1. Install on Linux Workstation

```bash
# Install dependencies
sudo apt-get install -y python3 python3-pip pyqt6

# Clone code
git clone https://github.com/Diamford/Safe_Computer_Class.git
cd Safe_Computer_Class
git checkout modernization-v0.5

# Install Python dependencies
pip3 install PyQt6 requests pyserial keyboard

# Connect USB RFID reader
# Check port: ls -la /dev/ttyUSB*
```

### 2. Set Environment Variables

```bash
# Add to ~/.bashrc or ~/.profile
export SAFE_CLASS_SERVER=192.168.1.100
export SAFE_CLASS_USER=ivan
export SAFE_CLASS_PASS=password123
export SAFE_CLASS_DAEMON_MODE=auth
export SAFE_RFID_PORT=/dev/ttyUSB0

# Or create ~/.safe_computer_class/config and source before running
```

### 3. Run Daemon

```bash
python3 daemon.pyw

# For background systemd service (as administrator)
sudo cp systemd/scc-daemon.user.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start scc-daemon
systemctl --user enable scc-daemon
```

---

## Security Verification

### ✅ Sprint-1 Security Fixes

After upgrading to the security-fixed version, verify:

#### 1. No Shell Injection Vulnerabilities

```bash
# Check server for unsafe shell calls
grep -r "shell=True" .  # Should only be in old comments
grep -r "bash -c" .     # Should not be in production code

# Verify source code:
cat scc.py | grep "smbpasswd"
# Should see: input=password_input instead of "bash -c" with password
```

#### 2. Input Validation

```bash
# Try adding user with dangerous characters
sudo python3 scc.py addteacher "test'; rm -rf /" 1010 password
# Should get: invalid username: username contains invalid characters

# Try class with dangerous name
sudo python3 scc.py addclass "class/../../dangerous"
# Should get: invalid class_name: class_name contains invalid characters

# Try invalid UID
sudo python3 scc.py addteacher validuser abc password
# Should get: invalid uid: must be an integer
```

#### 3. Verify PIN Logging (Not Visible)

```bash
# Check daemon logs on Windows
cat ~/AppData/Local/safe_computer_class/logs/key_daemon.log | grep PIN
# Should see: "PIN entered (value not logged)"
# Should NOT see: actual PIN values

# On Linux
cat /var/log/safe_computer_class/key_daemon.log | grep PIN
# Same verification
```

---

## Troubleshooting

### Problem: Samba Won't Start

```bash
# Check configuration
sudo testparm /etc/samba/smb.conf

# Restart
sudo systemctl restart smbd

# View logs
sudo tail -f /var/log/samba/log.smbd
```

### Problem: Error Adding User

```bash
# Check if UID exists in system
id -u testuser  # If returns number, user exists

# Delete and recreate
sudo python3 scc.py deluser testuser
sudo python3 scc.py addstudent testuser 10a 2050 password

# Check logs
dmesg | tail -20
```

### Problem: Windows Client Can't Connect to SMB

```bash
# Test server accessibility
ping 192.168.1.100

# Check SMB availability (from Linux)
smbclient -L //192.168.1.100 -U%

# Check firewall on Linux server
sudo ufw status
sudo ufw allow samba

# Check firewall on Windows client
# Open ports: 139 (NetBIOS), 445 (SMB)
```

### Problem: RFID Reader Not Connecting

```bash
# List ports on Windows
python -m serial.tools.list_ports

# On Linux
ls -la /dev/ttyUSB*
ls -la /dev/ttyACM*

# Fix access permissions
sudo usermod -a -G dialout $USER
newgrp dialout

# Reboot
reboot
```

### Problem: Insufficient Permissions

```bash
# Commands requiring sudo:
# - useradd, userdel, chown, chmod (file management)
# - smbpasswd (Samba users)
# - systemctl (Samba service)

# For non-root execution, configure sudoers:
# Run: sudo visudo
# Add line:
# www-data ALL=(ALL) NOPASSWD: /usr/bin/python3 /path/to/scc.py

# WARNING: This reduces security, use with caution!
```

### Verify Version and Status

```bash
# Check version
grep "v0.5" scc.py

# Is HTTP server running?
curl http://localhost/api/scc/verify_card -X POST -d '{"card_hash":"test"}'

# Verify database access
sudo python3 scc.py list
sudo python3 scc.py status
```

---

## Documentation Files

- `SECURITY_FIXES_SPRINT1.md` - Detailed description of all security fixes
- `README.md` - Project overview
- `INSTALL.md` - Original installation guide
- `RoaadMap_sprint-1.md` - Remaining work plan

---

## Support and Contacts

If you encounter issues:

1. Check log files (`/var/log/scc_server.log`, `~/AppData/Local/safe_computer_class/logs/`)
2. Run security verification above
3. Consult `SECURITY_FIXES_SPRINT1.md` documentation
4. Open an issue on GitHub: https://github.com/Diamford/Safe_Computer_Class/issues

---

## License

Safe Computer Class - Project for educational institutions  
© 2024-2026

