#!/bin/bash
#
# Safe Computer Class - Automated Installation & Deployment Script
# 
# This script automates the deployment of SCC on development and production systems.
# It can install using Docker, Docker Compose, or native systemd services.
#
# Usage:
#   sudo bash install.sh --type docker       # Docker installation
#   sudo bash install.sh --type docker-compose --production  # Production Docker setup
#   sudo bash install.sh --type native        # Native Linux installation
#   sudo bash install.sh --help              # Show help

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_TYPE="${INSTALL_TYPE:-docker-compose}"
IS_PRODUCTION=false
APP_NAME="Safe Computer Class"
APP_DIR="/opt/safe_computer_class"
LOG_DIR="/var/log/safe_computer_class"

##############################################################################
# Helper Functions
##############################################################################

print_header() {
    echo -e "${BLUE}=== ${1} ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

print_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

check_root() {
    if [[ "$EUID" -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        return 1
    fi
    return 0
}

require_command() {
    if ! check_command "$1"; then
        print_error "Required command not found: $1"
        exit 1
    fi
}

##############################################################################
# Installation Functions
##############################################################################

install_docker_dependencies() {
    print_header "Installing Docker Dependencies"
    
    if ! check_command docker; then
        print_info "Installing Docker..."
        apt-get update
        apt-get install -y docker.io
        systemctl enable docker
        systemctl start docker
        print_success "Docker installed"
    else
        print_success "Docker already installed"
    fi
    
    if ! check_command docker-compose; then
        print_info "Installing Docker Compose..."
        apt-get install -y docker-compose
        print_success "Docker Compose installed"
    else
        print_success "Docker Compose already installed"
    fi
}

install_docker_image() {
    print_header "Building Docker Image"
    
    cd "$SCRIPT_DIR"
    docker build -t scc-http:latest .
    print_success "Docker image built"
}

install_docker_compose_setup() {
    print_header "Setting up Docker Compose"
    
    cd "$SCRIPT_DIR"
    
    # Create logs and data directories
    mkdir -p logs data/backups config/ssl
    chmod 755 logs data
    
    # Copy .env if missing
    if [[ ! -f .env ]]; then
        if [[ -f .env.template ]]; then
            cp .env.template .env
            print_success "Created .env from template - please edit with your settings"
        fi
    fi
    
    # Start services
    if [[ "$IS_PRODUCTION" == "true" ]]; then
        print_info "Starting in production mode (with nginx)..."
        docker-compose --profile with-nginx up -d
        print_success "Production services started"
        print_info "Services: SCC HTTP on http://localhost:8443 (nginx reverse proxy)"
    else
        print_info "Starting in development mode..."
        docker-compose up -d
        print_success "Development services started"
        print_info "Services: SCC HTTP on http://localhost:80"
    fi
    
    # Wait for service to be ready
    print_info "Waiting for services to be ready..."
    sleep 5
    
    docker-compose ps
}

install_native_dependencies() {
    print_header "Installing Native Linux Dependencies"
    
    # Update package lists
    apt-get update
    
    # Install required packages
    apt-get install -y \
        python3.10 \
        python3-pip \
        python3-venv \
        samba \
        samba-common-bin \
        acl \
        git \
        curl \
        supervisor \
        systemd
    
    print_success "Native dependencies installed"
}

install_native_python_env() {
    print_header "Setting up Python Environment"
    
    # Create app directory
    mkdir -p "$APP_DIR"
    cd "$SCRIPT_DIR"
    
    # Copy files
    cp scc.py scc_wsgi.py gunicorn_config.py mb_mount.py daemon.pyw "$APP_DIR/"
    mkdir -p "$APP_DIR/systemd" "$APP_DIR/scripts"
    cp -r systemd/ scripts/ "$APP_DIR/"
    
    # Create virtualenv
    python3 -m venv "$APP_DIR/venv"
    source "$APP_DIR/venv/bin/activate"
    
    # Install dependencies
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt gunicorn
    
    chmod 755 "$APP_DIR/scc.py"
    print_success "Python environment ready at $APP_DIR"
}

install_native_systemd_server() {
    print_header "Installing Systemd Service"
    
    # Copy systemd unit file
    cp "$SCRIPT_DIR/systemd/scc-http.service" /etc/systemd/system/
    
    # Update service file with correct paths
    sed -i "s|/opt/safe_computer_class|$APP_DIR|g" /etc/systemd/system/scc-http.service
    
    # Reload systemd
    systemctl daemon-reload
    systemctl enable scc-http.service
    systemctl start scc-http.service
    
    print_success "Systemd service installed and started"
    systemctl --no-pager status scc-http.service
}

install_native_systemd_daemon() {
    print_header "Installing Systemd Daemon Service"
    
    # Copy user-level systemd unit
    mkdir -p /etc/systemd/user
    cp "$SCRIPT_DIR/systemd/scc-daemon.user.service" /etc/systemd/user/
    
    print_success "User daemon service template installed"
    print_info "Each user should run: systemctl --user enable scc-daemon.user.service"
}

install_supervisor_config() {
    print_header "Installing Supervisor Configuration"
    
    # Create supervisor config for gunicorn
    cat > /etc/supervisor/conf.d/scc-http.conf <<EOF
[program:scc-http]
command=$APP_DIR/venv/bin/gunicorn --config $APP_DIR/gunicorn_config.py scc_wsgi:app
directory=$APP_DIR
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/gunicorn.log
environment=PATH="$APP_DIR/venv/bin"
EOF
    
    supervisorctl reread
    supervisorctl update
    
    print_success "Supervisor configuration installed"
}

install_nginx_config() {
    print_header "Installing Nginx Configuration"
    
    if ! check_command nginx; then
        print_info "Installing Nginx..."
        apt-get install -y nginx
        systemctl enable nginx
    fi
    
    # Copy nginx configuration
    cp "$SCRIPT_DIR/config/nginx.conf" /etc/nginx/sites-available/scc
    ln -sf /etc/nginx/sites-available/scc /etc/nginx/sites-enabled/scc
    
    # Disable default site
    rm -f /etc/nginx/sites-enabled/default
    
    # Test and reload nginx
    nginx -t && systemctl reload nginx
    
    print_success "Nginx configuration installed"
}

install_samba_config() {
    print_header "Installing Samba Configuration"
    
    # Ensure samba is installed
    if ! check_command smbd; then
        print_error "Samba not installed. Run install dependencies first."
        exit 1
    fi
    
    # Create Samba directories
    mkdir -p /srv/samba /srv/samba_mounts
    
    # Initialize database if needed
    cd "$APP_DIR"
    "$APP_DIR/venv/bin/python3" scc.py init
    
    print_success "Samba initialized"
}

create_log_directory() {
    print_header "Creating Log Directory"
    
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    print_success "Log directory created at $LOG_DIR"
}

generate_ssl_certificates() {
    print_header "Generating SSL Certificates"
    
    mkdir -p config/ssl
    
    # Generate self-signed certificate if not present
    if [[ ! -f config/ssl/cert.pem || ! -f config/ssl/key.pem ]]; then
        openssl req -x509 -newkey rsa:4096 -keyout config/ssl/key.pem \
            -out config/ssl/cert.pem -days 365 -nodes \
            -subj "/C=RU/ST=Moscow/L=Moscow/O=School/CN=localhost"
        print_success "Self-signed SSL certificate generated"
    else
        print_success "SSL certificates already exist"
    fi
}

print_summary() {
    print_header "Installation Summary"
    
    case "$INSTALL_TYPE" in
        docker|docker-compose)
            print_info "Installation type: Docker"
            print_info "Location: Current directory"
            print_info "Access: http://localhost / http://localhost:8080"
            print_info ""
            print_info "Next steps:"
            print_info "1. Edit .env file with your configuration"
            print_info "2. Run: docker-compose up -d"
            print_info "3. Check status: docker-compose ps"
            print_info "4. View logs: docker-compose logs -f"
            ;;
        native)
            print_info "Installation type: Native/Systemd"
            print_info "Location: $APP_DIR"
            print_info "Access: http://localhost:80 / http://localhost:443"
            print_info ""
            print_info "Next steps:"
            print_info "1. Edit configuration files in $APP_DIR"
            print_info "2. Start service: systemctl start scc-http.service"
            print_info "3. Check status: systemctl status scc-http.service"
            print_info "4. View logs: journalctl -u scc-http.service -f"
            ;;
    esac
    
    print_success "Installation complete!"
}

show_help() {
    cat <<EOF
${BLUE}${APP_NAME} - Automated Installation Script${NC}

Usage:
  sudo bash install.sh [OPTIONS]

Options:
  --type TYPE              Installation type: docker, docker-compose, native (default: docker-compose)
  --production             Install for production (with nginx reverse proxy)
  --skip-ssl              Skip SSL certificate generation
  --help, -h              Show this help message

Examples:
  # Docker Compose (development)
  sudo bash install.sh --type docker-compose

  # Docker Compose (production with nginx)
  sudo bash install.sh --type docker-compose --production

  # Native systemd installation
  sudo bash install.sh --type native

Environment Variables:
  INSTALL_TYPE            Override installation type
  APP_DIR                 Override application directory (default: $APP_DIR)

EOF
}

##############################################################################
# Main
##############################################################################

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)
                INSTALL_TYPE="$2"
                shift 2
                ;;
            --production)
                IS_PRODUCTION=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    print_header "${APP_NAME} Installation"
    print_info "Installation type: $INSTALL_TYPE"
    print_info "Production mode: $IS_PRODUCTION"
    
    # Validate installation type
    case "$INSTALL_TYPE" in
        docker|docker-compose|native)
            ;;
        *)
            print_error "Invalid installation type: $INSTALL_TYPE"
            show_help
            exit 1
            ;;
    esac
    
    case "$INSTALL_TYPE" in
        docker|docker-compose)
            print_header "Docker Installation"
            check_root
            install_docker_dependencies
            install_docker_image
            generate_ssl_certificates
            install_docker_compose_setup
            ;;
        native)
            print_header "Native Installation"
            check_root
            install_native_dependencies
            create_log_directory
            install_native_python_env
            install_native_systemd_server
            install_native_systemd_daemon
            install_nginx_config
            install_samba_config
            ;;
    esac
    
    print_summary
}

# Run main if script is executed (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
