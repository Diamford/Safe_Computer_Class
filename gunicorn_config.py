# Gunicorn configuration for Safe Computer Class
# See: https://docs.gunicorn.org/en/stable/configure.html

import multiprocessing
import os

# Server socket
bind = os.environ.get('SCC_BIND', '0.0.0.0:80')
backlog = 2048

# Worker processes
workers = int(os.environ.get('SCC_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = os.environ.get('SCC_ACCESS_LOG', '-')
errorlog = os.environ.get('SCC_ERROR_LOG', '-')
loglevel = os.environ.get('SCC_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(T)s'

# Process naming
proc_name = 'scc-http'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = os.environ.get('SCC_SSL_KEYFILE')
# certfile = os.environ.get('SCC_SSL_CERTFILE')

# Server hooks
def on_starting(server):
    """Called when the gunicorn server is starting."""
    print("[SCC] Gunicorn server starting...")

def when_ready(server):
    """Called when the gunicorn server is ready to accept connections."""
    print(f"[SCC] Gunicorn ready. Listening on {bind}")

def on_exit(server):
    """Called when the gunicorn server is shutting down."""
    print("[SCC] Gunicorn server shutting down...")
