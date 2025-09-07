"""
Gunicorn configuration for LLMpostor application.
Optimized for Socket.IO with eventlet workers.
"""

from config_factory import load_config

# Load configuration (renamed to avoid conflicts with gunicorn's internal 'config')
app_config = load_config()

# Server socket
bind = f"{app_config.host}:{app_config.port}"
backlog = 2048

# Worker processes
workers = 1  # Must be 1 for Socket.IO with eventlet
worker_class = "eventlet"
worker_connections = app_config.worker_connections
timeout = app_config.timeout
keepalive = app_config.keepalive

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = app_config.log_level
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "llmpostor"

# Server mechanics
preload_app = False  # Don't preload for Socket.IO
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# SSL (for production)
keyfile = None
certfile = None