"""
Gunicorn configuration for LLMposter application.
Optimized for Socket.IO with eventlet workers.
"""

import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 8000)}"
backlog = 2048

# Worker processes
workers = int(os.environ.get('WORKERS', 1))  # Must be 1 for Socket.IO with eventlet
worker_class = "eventlet"
worker_connections = int(os.environ.get('WORKER_CONNECTIONS', 1000))
timeout = int(os.environ.get('TIMEOUT', 30))
keepalive = int(os.environ.get('KEEPALIVE', 2))

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get('LOG_LEVEL', 'info')
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