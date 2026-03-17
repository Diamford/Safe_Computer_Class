# Safe Computer Class (SCC) v0.5

🔒 **School Network Security & File Sharing System**

A comprehensive solution for managing secure file sharing in educational institutions using RFID cards, PIN codes, and Samba network shares.

- **Language**: Russian (with English API documentation)
- **Platform**: Linux (Ubuntu/Debian)
- **Architecture**: Client-Server with Docker support
- **Authentication**: RFID + PIN
- **File Sharing**: Samba (SMB/CIFS)

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
  - [Docker Compose (Easiest)](#docker-compose-recommended)
  - [Native Linux](#native-linux)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Management Commands](#management-commands)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Features

### Core Functionality

- **RFID Card Registration**: Students/teachers register RFID cards with PIN codes
- **PIN Authentication**: Secure PIN entry for access control
- **Automated File Sharing**: Dynamic Samba shares based on user roles
- **Role-Based Access**: Teachers, students, administrators with different permissions
- **Class Management**: Create/manage classes and assign users
- **Bind Mounts**: User-specific directory structures in Samba shares
- **Database-Driven**: SQLite for user and card data
- **Web API**: REST endpoints for client integration

### Security Features

- SHA-256 hashing for RFID cards and PINs
- No plaintext passwords in logs or network
- HTTPS support with nginx reverse proxy
- Systemd service hardening
- ACL-based file permissions
- User isolation

### Modern Deployment

- **Docker & Docker Compose**: One-command deployment
- **Systemd Integration**: Service management
- **Nginx Reverse Proxy**: Production-grade HTTP handling
- **Gunicorn WSGI**: Scalable Python app server
- **GitHub Actions**: Automated testing and CI/CD
- **Health Checks**: Automated service monitoring

## Architecture

### Components

```
┌─────────────────────────────────────────┐
│   Client Systems (Windows/Linux)        │
├─────────────────────────────────────────┤
│  mb_mount.py      │     daemon.pyw      │
│  (File Mount)     │   (RFID Reader)     │
└────────┬──────────┴────────┬────────────┘
         │                   │
         │  HTTP APIs (80/443)
         ▼                   ▼
┌────────────────────────────────────────────┐
│   SCC HTTP Server (Docker/Systemd)         │
├────────────────────────────────────────────┤
│  gunicorn (scc_wsgi.py)                   │
│  ├─ /api/scc/register_card                │
│  ├─ /api/scc/verify_card                  │
│  ├─ /api/scc/verify_pin                   │
│  └─ /api/scc/auth                         │
│                                           │
│  Database (SQLite): school.db            │
├────────────────────────────────────────────┤
│   Samba Server (smbd) - File Sharing      │
│  \\server\school                          │
│  └─ /srv/samba_mounts (bind mounts)      │
└────────────────────────────────────────────┘
```

### File Structure

```
Safe_Computer_Class/
├── scc.py                    # Main HTTP API server
├── scc_wsgi.py              # WSGI wrapper for gunicorn
├── mb_mount.py              # Windows file mount client
├── daemon.pyw               # RFID reader daemon
├── gunicorn_config.py       # Gunicorn configuration
├── requirements.txt         # Python dependencies
├── setup.py                 # Package setup
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker Compose orchestration
├── install.sh               # Automated installation script
├── .env.template            # Environment configuration template
├── config/
│   ├── nginx.conf          # Nginx reverse proxy
│   └── ssl/                # SSL certificates
├── systemd/
│   ├── scc-http.service    # Server systemd unit
│   └── scc-daemon.service  # Client daemon unit
├── scripts/
│   ├── scc_server.sh       # Server installation script
│   ├── install_scc_http_service.sh
│   └── uninstall_scc_http_service.sh
├── templates/
│   └── hello.html          # Web UI
└── .github/
    └── workflows/
        ├── tests.yml       # CI/CD tests
        └── docker-publish.yml  # Docker image publishing
```

## Quick Start

### Option 1: Docker Compose (Easiest - Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/Safe_Computer_Class.git
cd Safe_Computer_Class

# Copy environment template
cp .env.template .env

# Edit configuration
nano .env

# Start services
docker-compose up -d

# Initialize database (first run)
docker-compose exec scc-http python3 scc.py init

# Check status
docker-compose ps
docker-compose logs -f
```

### Option 2: Using Installation Script

```bash
sudo bash install.sh --type docker-compose

# For production with nginx:
sudo bash install.sh --type docker-compose --production
```

### Option 3: Native Installation

```bash
sudo bash install.sh --type native

# Check status
systemctl status scc-http.service
journalctl -u scc-http.service -f
```

## Installation

### Docker Compose (Recommended)

#### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Linux server (Ubuntu 20.04+ or similar)

#### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Safe_Computer_Class.git
   cd Safe_Computer_Class
   ```

2. **Configure environment**
   ```bash
   cp .env.template .env
   # Edit with your server IP and settings
   nano .env
   ```

3. **Create required directories**
   ```bash
   mkdir -p logs data/backups config/ssl
   ```

4. **Generate SSL certificates** (optional)
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout config/ssl/key.pem \
       -out config/ssl/cert.pem -days 365 -nodes
   ```

5. **Start services**
   ```bash
   docker-compose up -d
   ```

6. **Initialize database**
   ```bash
   docker-compose exec scc-http python3 scc.py init
   ```

7. **Verify**
   ```bash
   curl http://localhost/api/scc/verify_card
   docker-compose logs -f scc-http
   ```

### Native Linux Installation

#### Prerequisites

- Ubuntu 20.04 or Debian 11+
- Python 3.9+
- Samba 4.0+
- Systemd

#### Steps

1. **Run installation script**
   ```bash
   sudo bash install.sh --type native
   ```

2. **Configure settings**
   ```bash
   sudo nano /opt/safe_computer_class/.env
   ```

3. **Check service status**
   ```bash
   sudo systemctl status scc-http.service
   sudo journalctl -u scc-http.service -f
   ```

## Configuration

### Environment Variables

Create or edit `.env` file with these settings:

```bash
# Server Configuration
SAFE_CLASS_SMB_SERVER=192.168.1.10    # External Samba server IP
SAFE_CLASS_DRIVE=Z:                    # Windows drive letter
SAFE_CLASS_SERVER=192.168.1.10         # Fallback server address

# HTTP Service
SCC_HOST=0.0.0.0                       # Listen address
SCC_PORT=80                            # Listen port

# Authentication
SAFE_CLASS_AUTH_URL=http://...         # Custom auth endpoint
SAFE_CLASS_CARD_URL=http://...         # Custom card check endpoint
SAFE_CLASS_PIN_URL=http://...          # Custom PIN check endpoint

# Optional: Return passwords to clients (⚠️ Use with caution!)
# SAFE_CLASS_AUTH_RETURN_PASSWORD=0
# SAFE_CLASS_SMB_PASSWORD=secret

# RFID Configuration (client side)
SAFE_RFID_PORT=COM3                    # Serial port for RFID reader
SAFE_RFID_SKIP_PORTS=COM1,COM2         # Skip these ports

# Daemon Mode
SAFE_CLASS_DAEMON_MODE=auth            # auth or register
```

### Samba Configuration

The system automatically configures Samba, but you can customize:

- **Base directory**: `/srv/samba`
- **Share name**: `school`
- **Mount points**: `/srv/samba_mounts`

## API Reference

### Endpoints

#### 1. Register RFID Card

**POST** `/api/scc/register_card`

Register an RFID card for a user with optional PIN protection.

**Request:**
```json
{
  "username": "student01",
  "card_hash": "ABC123DEF456...",  // SHA256(UID||SALT)
  "pin_hash": "1234567890ABCDEF..."  // SHA256(PIN)
}
```

**Response (Success):**
```json
{
  "ok": true,
  "message": "card registered"
}
```

**Response (Error):**
```json
{
  "ok": false,
  "message": "user not found"
}
```

---

#### 2. Verify RFID Card

**POST** `/api/scc/verify_card`

Check if an RFID card is registered and if PIN is required.

**Request:**
```json
{
  "card_hash": "ABC123DEF456..."
}
```

**Response:**
```json
{
  "exists": true,
  "require_pin": true
}
```

---

#### 3. Verify PIN

**POST** `/api/scc/verify_pin`

Verify the PIN for a registered card.

**Request:**
```json
{
  "card_hash": "ABC123DEF456...",
  "pin_hash": "1234567890ABCDEF..."
}
```

**Response:**
```json
{
  "ok": true
}
```

---

#### 4. Unified Authentication

**POST** `/api/scc/auth`

Single endpoint for card + PIN authentication. Returns Samba access credentials.

**Request:**
```json
{
  "uuid": "ABC123DEF456...",        // card_hash
  "pin_hash": "1234567890ABCDEF..."  // SHA256(PIN)
}
```

**Response (Success):**
```json
{
  "ok": true,
  "server": "192.168.1.10",
  "username": "student01",
  "drive_letter": "Z:",
  "password": "samba_password"  // Optional, if configured
}
```

**Response (Failure):**
```json
{
  "ok": false
}
```

## Management Commands

### Server Management

```bash
# Initialize system
docker-compose exec scc-http python3 scc.py init

# Show status
docker-compose exec scc-http python3 scc.py status

# Backup database
docker-compose exec scc-http python3 scc.py backup

# Restart Samba
docker-compose exec scc-http python3 scc.py restart

# View help
docker-compose exec scc-http python3 scc.py help
```

### User Management

```bash
# Add a student
python3 scc.py addstudent student01 class_a 1001 password123

# Add a teacher
python3 scc.py addteacher teacher01 2001 password123

# Link teacher to class
python3 scc.py addteacherclass teacher01 class_a

# List users
python3 scc.py list

# Delete user
python3 scc.py deluser student01
```

### Class Management

```bash
# Create a new class
python3 scc.py addclass class_a

# List classes
python3 scc.py listclasses

# Delete class
python3 scc.py delclass class_a
```

### Mount Management

```bash
# Create mounts for user
python3 scc.py mount student01

# Remove mounts for user
python3 scc.py umount student01
```

## Deployment

### Production Deployment with Docker Compose + Nginx

```bash
# Start with production profile (includes nginx)
docker-compose --profile with-nginx up -d

# Access via secure proxy
# https://your-server:8443/api/scc/
```

### High-Availability Setup

1. **Multiple SCC instances** behind load balancer
2. **Shared database** (MySQL/PostgreSQL instead of SQLite)
3. **Persistent volumes** for Samba data
4. **External Samba server** (NAS/storage)

### Environment-Specific Files

Create separate `.env` files:
- `.env.dev` - Development
- `.env.staging` - Staging
- `.env.prod` - Production

Start with: `docker-compose --env-file .env.prod up -d`

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs -f scc-http

# Verify ports are available
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :445

# Restart services
docker-compose restart
```

### Database Issues

```bash
# Backup current database
docker-compose exec scc-http python3 scc.py backup

# Reset database (⚠️ Warning: Deletes all data!)
docker-compose exec scc-http rm /srv/samba/school.db
docker-compose exec scc-http python3 scc.py init
```

### RFID Reader Not Found

```bash
# Check connected serial ports
ls -la /dev/ttyUSB* /dev/ttyACM*

# Set specific port in .env
SAFE_RFID_PORT=/dev/ttyACM0

# Skip problematic ports
SAFE_RFID_SKIP_PORTS=/dev/ttyUSB0,/dev/ttyUSB1
```

### Samba Connection Refused

```bash
# Check Samba status
docker-compose exec scc-http sudo systemctl status smbd

# Restart Samba
docker-compose exec scc-http python3 scc.py restart

# Verify configuration
docker-compose exec scc-http cat /etc/samba/smb.conf
```

### Permission Denied Errors

```bash
# Fix directory permissions
docker-compose exec scc-http sudo chown -R root:users /srv/samba
docker-compose exec scc-http sudo chmod -R 750 /srv/samba
```

## Development

### Local Testing

```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8

# Run linting
black .
flake8 .

# Run tests
pytest tests/

# Build Docker image locally
docker build -t scc-http:dev .

# Start with docker-compose
docker-compose up -d
```

### Running with Gunicorn

```bash
# Development
gunicorn --reload --bind 0.0.0.0:8000 scc_wsgi:app

# Production
gunicorn --workers 4 --bind 0.0.0.0:80 scc_wsgi:app
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

See `RoaadMap_sprint-1.md` for planned features.

## License

See LICENSE file (typically MIT)

## Support

- **Documentation**: See `.md` files in repository
- **Issues**: GitHub Issues
- **Community**: Discussion forums
- **Commercial Support**: Contact team

## Version History

- **v0.5** - Current version with Docker & WSGI support
- **v0.4** - Previous stable release
- **See CHANGELOG.md** for full history

## Authors

SCC Team & Contributors

---

**⚠️ Security Notice**: Always use HTTPS in production. Configure SSL certificates before deploying.
