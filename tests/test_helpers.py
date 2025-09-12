"""
Test helpers for service access.
This module provides access to services for tests.
"""

def get_services():
    """Get services from the container for tests."""
    from container import configure_container
    from config_factory import ConfigurationFactory
    from flask import Flask
    from flask_socketio import SocketIO
    
    # Create test app and socketio
    app = Flask(__name__)
    socketio = SocketIO(app, async_mode='eventlet')
    
    config_factory = ConfigurationFactory()
    config = config_factory.to_dict()
    container = configure_container(socketio=socketio, config=config)
    
    # Return services dictionary
    return {
        'room_manager': container.get('RoomManager'),
        'game_manager': container.get('GameManager'),
        'content_manager': container.get('ContentManager'),
        'session_service': container.get('SessionService'),
        'broadcast_service': container.get('BroadcastService'),
        'auto_flow_service': container.get('AutoGameFlowService'),
        'validation_service': container.get('ValidationService'),
        'error_response_factory': container.get('ErrorResponseFactory')
    }

# Create service instances for test access
_services = get_services()
room_manager = _services['room_manager']
game_manager = _services['game_manager'] 
content_manager = _services['content_manager']
session_service = _services['session_service']
broadcast_service = _services['broadcast_service']
auto_flow_service = _services['auto_flow_service']
validation_service = _services['validation_service']
error_response_factory = _services['error_response_factory']