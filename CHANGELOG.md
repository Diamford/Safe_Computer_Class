# Changelog

All notable changes to Safe Computer Class will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2024-03-17

### Added

#### Core Features
- **WSGI Application Support**: Added `scc_wsgi.py` for production WSGI servers (gunicorn, uWSGI)
- **Docker Support**: Complete Docker and Docker Compose setup for easy deployment
- **Nginx Reverse Proxy**: Production-grade HTTP/HTTPS proxy configuration
- **Gunicorn WSGI Server**: Scalable Python application server with configurable workers
- **Health Checks**: Docker health endpoints and monitoring
- **SSL/HTTPS Support**: Built-in SSL certificate generation and management

#### Deployment
- **Automated Installation Script** (`install.sh`): One-command deployment for Docker and native Linux
- **Multiple Installation Methods**: Docker Compose, Docker, or native systemd
- **Environment Configuration**: Template-based `.env` file configuration
- **Systemd Services**: Both system and user-level service units for SCC components
- **Production Ready**: Full deployment stack with nginx, gunicorn, and systemd

#### CI/CD
- **GitHub Actions Workflows**: Automated linting and testing
- **Docker Image Publishing**: Automated build and push to Docker Hub
- **Multi-Python Version Testing**: Testing on Python 3.9, 3.10, 3.11

#### Documentation
- **Comprehensive README**: Complete project documentation with architecture diagrams
- **Installation Guide**: Step-by-step installation for all methods
- **API Reference**: Detailed API endpoint documentation
- **Contributing Guide**: Guidelines for contributors
- **Changelog**: Version history tracking

#### Code Quality
- **Fixed daemon.pyw Bug**: Fixed control flow issue in authentication error handling (missing return statement)
- **Enhanced Error Handling**: Better error messages and logging
- **Type Hints Support**: Prepared for future type annotation improvements
- **Code Comments**: Detailed Russian/English comments in code

#### Configuration
- **Environment Variables**: Comprehensive environment variable support
- **Flexible Configuration**: Per-environment configuration files (.env.dev, .env.prod, etc.)
- **Template System**: .env.template for easy configuration setup

### Changed

#### Deployment
- **Improved Docker Image**: Smaller, more efficient image with all dependencies
- **Updated Dockerfile**: Now uses gunicorn for production workloads
- **Enhanced docker-compose.yml**: Multi-service setup with optional nginx profile

#### Server
- **HTTP Server**: Can now run with gunicorn for better performance
- **Samba Integration**: Improved auto-initialization on first run
- **Logging**: Better structured logging for debugging

### Fixed

- **daemon.pyw**: Fixed missing return after error dialog in authorization check
- **Error handling**: Improved consistency in error responses
- **Configuration**: Fixed environment variable handling

### Security

- **SSL/TLS**: Full HTTPS support with configurable certificates
- **Headers**: Security headers (HSTS, X-Frame-Options, etc.) in nginx config
- **User Isolation**: Enhanced file permission security
- **Logging**: No plaintext passwords or sensitive data in logs

### Known Issues

- SQLite database limits concurrent access (use PostgreSQL for high-load scenarios)
- RFID reader port detection can vary by OS and driver
- Samba configuration is Linux-specific (no Windows SMB server mode)

## [0.4.0] - 2024-02-01

### Added

- Windows RFID mounter GUI (mb_mount.py)
- PIN authentication daemon (daemon.pyw)
- REST API endpoints for RFID/PIN verification
- Samba file sharing integration
- SQLite database for users and cards
- Role-based access control (teachers, students, admins)
- Bind mount system for user-specific directories

### Changed

- Improved Samba configuration
- Enhanced serial communication for RFID readers
- Better error handling in HTTP API

## [0.3.0] - 2024-01-15

### Added

- Basic HTTP server implementation
- Card registration endpoints
- PIN verification system

## [0.2.0] - 2024-01-01

### Added

- Initial Samba setup
- User management commands
- Class management system

## [0.1.0] - 2023-12-01

### Added

- Project initialization
- Basic file structure
- Initial documentation

---

## Upgrade Instructions

### From 0.4.x to 0.5.0

#### Docker Compose Users

```bash
# Backup your database
docker-compose exec scc-http python3 scc.py backup

# Pull latest changes
git pull

# Rebuild image
docker-compose build --no-cache

# Restart services
docker-compose up -d
```

#### Native Installation Users

```bash
# Backup database
cd /opt/safe_computer_class
./venv/bin/python3 scc.py backup

# Update code
sudo git pull

# Update dependencies
./venv/bin/pip install --upgrade -r requirements.txt

# Restart service
sudo systemctl restart scc-http.service
```

---

## Future Roadmap

See `RoaadMap_sprint-1.md` for planned features and improvements.

### Planned for v0.6.0

- [ ] PostgreSQL support for high-load deployments
- [ ] LDAP/Active Directory integration
- [ ] Web dashboard for administration
- [ ] Mobile app support
- [ ] Multi-language UI
- [ ] Advanced logging and analytics
- [ ] Rate limiting and DDoS protection
- [ ] Kubernetes deployment guide

### Under Discussion

- Support for other authentication methods (Biometric, NFC)
- Client applications for macOS
- Integration with Google Workspace
- Advanced ACL management UI
- Performance monitoring dashboard

---

## Support

For issues or questions about specific versions:
- Open an issue on GitHub
- Check existing documentation
- Review tests for usage examples
