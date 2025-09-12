"""
Service access module for tests.
Provides direct access to application services for test files.
"""

# Import the app module to get the services
from app import app, socketio, services

# Expose services for test access
room_manager = services['room_manager'] 
game_manager = services['game_manager']
content_manager = services['content_manager']
session_service = services['session_service']
broadcast_service = services['broadcast_service']
auto_flow_service = services['auto_flow_service']
validation_service = services['validation_service']
error_response_factory = services['error_response_factory']