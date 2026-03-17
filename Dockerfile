FROM ubuntu:22.04

# Set environment
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    samba \
    samba-common-bin \
    acl \
    git \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /opt/safe_computer_class

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt gunicorn

# Copy application files
COPY scc.py .
COPY scc_wsgi.py .
COPY gunicorn_config.py .
COPY mb_mount.py .
COPY daemon.pyw .
COPY systemd/ ./systemd/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p /srv/samba /srv/samba_mounts /var/log/safe_computer_class && \
    chmod 755 /opt/safe_computer_class

# Create Samba configuration directory
RUN mkdir -p /etc/samba

# Expose HTTP port
EXPOSE 80 445

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/api/scc/verify_card -X POST -H "Content-Type: application/json" -d '{"card_hash":"test"}' || exit 1

# Default command - run with gunicorn
CMD ["gunicorn", "--config", "/opt/safe_computer_class/gunicorn_config.py", "scc_wsgi:app"]
