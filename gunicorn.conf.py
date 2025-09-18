"""
Gunicorn configuration for LLMpostor application.
Optimized for Socket.IO with eventlet workers.
"""

import sys
import logging
import yaml
from src.content_manager import ContentManager, ContentValidationError

def on_starting(server):
    """
    Server hook that runs when the master process is starting.
    We use this to validate the prompts YAML file before workers are forked.
    If validation fails, we exit, preventing the server from starting.
    """
    logger = logging.getLogger(__name__)
    logger.info("Validating prompts.yaml before starting workers...")
    try:
        # We need to create a temporary instance of ContentManager for validation
        content_manager = ContentManager()
        content_manager.load_prompts_from_yaml()
        if content_manager.get_prompt_count() == 0:
            raise ContentValidationError("Prompt file is empty or contains no prompts.")
        logger.info(f"Successfully validated and loaded {content_manager.get_prompt_count()} prompts.")
    except (FileNotFoundError, yaml.YAMLError, ContentValidationError) as e:
        logger.critical(f"FATAL: Prompt file validation failed. Server shutting down. Error: {e}")
        sys.exit(1)

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
max_requests = 2000
max_requests_jitter = 100

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
