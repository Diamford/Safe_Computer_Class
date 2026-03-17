# Installation Guide

Comprehensive installation guide for Safe Computer Class deployment methods.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Docker Compose Installation](#docker-compose-installation)
3. [Native Linux Installation](#native-linux-installation)
4. [Post-Installation Setup](#post-installation-setup)
5. [Troubleshooting](#troubleshooting)

## System Requirements

### Docker Compose (Recommended)

- **Docker Engine**: 20.10 or later
- **Docker Compose**: 2.0 or later
- **RAM**: Minimum 1GB (2GB recommended)
- **Disk Space**: Minimum 2GB for data/database
- **OS**: Ubuntu 20.04 LTS, Debian 11, or similar
- **CPU**: 1 core minimum (2+ recommended)

### Native Linux

- **OS**: Ubuntu 20.04 LTS, Ubuntu 22.04, Debian 11, or compatible
- **Python**: 3.9 or later
- **RAM**: Minimum 512MB
- **Disk Space**: Minimum 1GB
- **CPU**: 1 core minimum
- **Permissions**: Root/sudo access required

### Client Requirements

- **Windows**:
  - Windows 7 or later
  - Python 3.9+ (for mb_mount.py)
  - PyQt6 library
  
- **Linux**:
  - Python 3.9+
  - PyQt6 library
  - PySerial library for RFID

## Docker Compose Installation

### Quick Start (Recommended for New Users)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/Safe_Computer_Class.git
cd Safe_Computer_Class

# 2. Copy environment configuration
cp .env.template .env

# 3. Edit configuration (set your server IP)
nano .env

# 4. Create directories
mkdir -p logs data/backups config/ssl

# 5. Start the application
docker-compose up -d

# 6. Initialize the database
docker-compose exec scc-http python3 scc.py init

# 7. Verify it's running
docker-compose ps
curl http://localhost/api/scc/verify_card
```

### Development Setup

For development with hot-reloading:

```bash
# Build with development settings
docker-compose -f docker-compose.yml build --no-cache

# Start in foreground for logs
docker-compose up

# In another terminal, run tests
docker-compose exec scc-http pytest tests/
```

### Production Setup with HTTPS

```bash
# 1. Generate SSL certificates
mkdir -p config/ssl
openssl req -x509 -newkey rsa:4096 \
  -keyout config/ssl/key.pem \
  -out config/ssl/cert.pem \
  -days 365 -nodes \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=School/CN=scc.example.com"

# 2. Update .env for production
cat > .env << EOF
SAFE_CLASS_SMB_SERVER=192.168.1.10
SAFE_CLASS_DRIVE=Z:
SCC_HOST=0.0.0.0
SCC_PORT=80
EOF

# 3. Start with nginx profile
docker-compose --profile with-nginx up -d

# 4. Access via
# HTTP:  http://localhost:8080 (redirects to HTTPS)
# HTTPS: https://localhost:8443
```

## Native Linux Installation

### Automated Installation (Recommended)

```bash
# Download and run installation script
cd /tmp
wget https://github.com/yourusername/Safe_Computer_Class/raw/main/install.sh
chmod +x install.sh

# Run installer
sudo bash install.sh --type native

# Follow prompts and configure
```

### Manual Installation

#### Step 1: Update System

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

#### Step 2: Install Dependencies

```bash
sudo apt-get install -y \
  python3.10 python3-pip python3-venv \
  samba samba-common-bin \
  acl getfacl setfacl \
  git curl wget \
  supervisor \
  nginx
```

#### Step 3: Create Application Directory

```bash
sudo mkdir -p /opt/safe_computer_class
cd /tmp
git clone https://github.com/yourusername/Safe_Computer_Class.git
sudo cp -r Safe_Computer_Class/* /opt/safe_computer_class/
cd /opt/safe_computer_class
```

#### Step 4: Set Up Python Virtual Environment

```bash
cd /opt/safe_computer_class

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Deactivate
deactivate
```

#### Step 5: Create Application User

```bash
# Create dedicated user (optional)
sudo useradd -r -s /bin/bash -m -d /opt/safe_computer_class scc

# Set permissions
sudo chown -R scc:scc /opt/safe_computer_class
```

#### Step 6: Install Systemd Service

```bash
# Copy service file
sudo cp systemd/scc-http.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable scc-http.service
sudo systemctl start scc-http.service

# Verify
sudo systemctl status scc-http.service
```

#### Step 7: Configure Nginx

```bash
# Copy nginx config
sudo cp config/nginx.conf /etc/nginx/sites-available/scc
sudo ln -s /etc/nginx/sites-available/scc /etc/nginx/sites-enabled/

# Disable default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

#### Step 8: Initialize Database

```bash
cd /opt/safe_computer_class
./venv/bin/python3 scc.py init
```

## Post-Installation Setup

### Create Your First Class

```bash
# Using Docker Compose
docker-compose exec scc-http python3 scc.py addclass class_9a

# Using native installation
cd /opt/safe_computer_class
./venv/bin/python3 scc.py addclass class_9a
```

### Add a Teacher

```bash
# Using Docker Compose
docker-compose exec scc-http python3 scc.py addteacher ivan 2001 securepass

# Using native installation
./venv/bin/python3 scc.py addteacher ivan 2001 securepass

# Link to class
./venv/bin/python3 scc.py addteacherclass ivan class_9a
```

### Add Students

```bash
# Add student to class
docker-compose exec scc-http python3 scc.py addstudent john class_9a 1001 pass123
docker-compose exec scc-http python3 scc.py addstudent mary class_9a 1002 pass456
```

### Configure RFID Readers

For Windows clients using ESP32-C3 RFID reader:

```bash
# Install driver for CH340 USB-to-Serial chip
# Windows: Download from https://www.wch-ic.com/downloads/CH341SER_ZIP.html

# Test connection
python mb_mount.py  # This will open the GUI

# Can also set in .env or environment:
set SAFE_RFID_PORT=COM3
```

### Set Up Samba Shares

The system automatically configures Samba. Verify:

```bash
# Check Samba status
sudo systemctl status smbd

# View configuration
sudo cat /etc/samba/smb.conf

# Test connection from client
# Windows: \\192.168.1.10\school
# Linux: smb://192.168.1.10/school
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Server Configuration
export SAFE_CLASS_SMB_SERVER=192.168.1.10
export SAFE_CLASS_DRIVE=Z:

# HTTP Service
export SCC_HOST=0.0.0.0
export SCC_PORT=80

# Logging
export SCC_LOG_LEVEL=INFO

# Number of Gunicorn workers
export SCC_WORKERS=4
```

### Service Configuration Files

**For Docker Compose:**
- `.env` - Environment variables
- `docker-compose.yml` - Service definition

**For Native Installation:**
- `/opt/safe_computer_class/.env` - Environment variables
- `/etc/systemd/system/scc-http.service` - Systemd unit
- `/etc/nginx/sites-available/scc` - Nginx proxy

## Troubleshooting

### Docker Issues

```bash
# View logs
docker-compose logs -f scc-http

# Check service status
docker-compose ps

# Restart service
docker-compose restart scc-http

# Full reset (WARNING: deletes data!)
docker-compose down -v
```

### Systemd Service Issues

```bash
# Check service status
sudo systemctl status scc-http.service

# View recent logs
sudo journalctl -u scc-http.service -n 50

# Follow logs
sudo journalctl -u scc-http.service -f

# Restart service
sudo systemctl restart scc-http.service
```

### Database Issues

```bash
# Backup database
docker-compose exec scc-http python3 scc.py backup

# Reset database (WARNING: Deletes all data!)
rm -f /srv/samba/school.db
docker-compose exec scc-http python3 scc.py init
```

### Port Conflicts

```bash
# Check if ports are in use
sudo lsof -i -P -n | grep LISTEN

# Change ports in .env or systemd service:
# Docker: Edit docker-compose.yml
# Systemd: Edit /etc/systemd/system/scc-http.service
```

### Samba Not Working

```bash
# Check Samba service
sudo systemctl status smbd

# Restart Samba
sudo systemctl restart smbd

# Verify configuration
sudo smbclient -U% //localhost/school
```

## Updating

### Docker Compose

```bash
# Pull latest code
git pull

# Rebuild image
docker-compose build --no-cache

# Restart services
docker-compose up -d
```

### Native Installation

```bash
# Backup database
cd /opt/safe_computer_class
./venv/bin/python3 scc.py backup

# Update code
sudo git pull  # If installed from git

# Update dependencies
./venv/bin/pip install --upgrade -r requirements.txt

# Restart service
sudo systemctl restart scc-http.service
```

## Uninstallation

### Docker Compose

```bash
# Stop and remove containers
docker-compose down

# Remove images (optional)
docker rmi scc-http:latest
```

### Native Installation

```bash
# Stop service
sudo systemctl stop scc-http.service
sudo systemctl disable scc-http.service

# Remove service file
sudo rm /etc/systemd/system/scc-http.service
sudo systemctl daemon-reload

# Remove application directory
sudo rm -rf /opt/safe_computer_class

# Remove nginx config
sudo rm -f /etc/nginx/sites-available/scc /etc/nginx/sites-enabled/scc

# Remove user (optional)
sudo userdel -r scc
```

## Getting Help

- **Documentation**: See README.md
- **Issues**: GitHub Issues
- **Logs**: Check application logs
- **Community**: Discussion forums
