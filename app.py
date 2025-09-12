"""
LLMpostor - A multiplayer guessing game where players try to identify AI-generated responses.
Main Flask application entry point focusing on app creation, dependency injection, and service wiring.
"""

from flask import Flask, request
from flask_socketio import SocketIO
import os
import logging
import atexit
import sys
import yaml

# Import core dependencies
from src.content_manager import ContentValidationError
from container import configure_container
from config_factory import load_config, ConfigurationFactory
from src.services.rate_limit_service import EventQueueManager, set_event_queue_manager

# Initialize Flask app
app = Flask(__name__)

# Load and apply configuration
app_config = load_config()
config_factory = ConfigurationFactory()
app.config.update(config_factory.get_flask_config())

# Initialize Socket.IO with environment-aware CORS
# In production, restrict to explicitly allowed origins from env var SOCKETIO_CORS_ALLOWED_ORIGINS (comma-separated)
allowed_origins_env = os.environ.get('SOCKETIO_CORS_ALLOWED_ORIGINS', '')
if app_config.is_production:
    _cors_allowed = [o.strip() for o in allowed_origins_env.split(',') if o.strip()]
    # If none provided, default to same-origin only by providing empty list (no cross-origin)
    socketio = SocketIO(app, cors_allowed_origins=_cors_allowed or [], async_mode='eventlet')
else:
    # Development/testing: permissive for local workflows
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure service container with dependencies
container = configure_container(socketio=socketio, config=config_factory.to_dict())

# Initialize services from container
services = {
    'room_manager': container.get('RoomManager'),
    'game_manager': container.get('GameManager'), 
    'content_manager': container.get('ContentManager'),
    'session_service': container.get('SessionService'),
    'broadcast_service': container.get('BroadcastService'),
    'auto_flow_service': container.get('AutoGameFlowService'),
    'validation_service': container.get('ValidationService'),
    'error_response_factory': container.get('ErrorResponseFactory')
}


# Initialize rate limiting
event_queue_manager = EventQueueManager()
set_event_queue_manager(event_queue_manager)


# Load prompts on startup
try:
    services['content_manager'].load_prompts_from_yaml()
    logger.info(f"Loaded {services['content_manager'].get_prompt_count()} prompts from YAML")
except (FileNotFoundError, yaml.YAMLError, ContentValidationError) as e:
    logger.critical(f"FATAL: Prompt file validation failed, which is critical for game play. Server shutting down. Error: {e}")
    sys.exit(1)

# Register REST endpoints
from src.routes.api import create_api_blueprint
api_services = {
    'room_manager': services['room_manager']
}
api_blueprint = create_api_blueprint(api_services)
app.register_blueprint(api_blueprint)

# Register Socket.IO handlers
from src.handlers.socket_handlers import register_socket_handlers
handler_config = {
    'app_config': app_config,
    'allowed_origins_env': allowed_origins_env
}
register_socket_handlers(socketio, services, handler_config)

def cleanup_on_exit():
    """Clean up resources on application exit."""
    logger.info("Shutting down LLMpostor server...")
    services['auto_flow_service'].stop()

atexit.register(cleanup_on_exit)

if __name__ == '__main__':
    # Run the application using configuration
    logger.info(f"Starting LLMpostor server on {app_config.host}:{app_config.port}")
    try:
        socketio.run(app, host=app_config.host, port=app_config.port, debug=app_config.debug)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        cleanup_on_exit()
