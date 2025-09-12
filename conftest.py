"""
Global pytest configuration and fixtures.
Provides service fixtures for proper dependency injection in tests.
"""

import pytest
import os
from unittest.mock import Mock
from flask_socketio import SocketIO
from flask import Flask

# Ensure testing environment
os.environ['TESTING'] = '1'


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing."""
    from app import app as flask_app
    return flask_app


@pytest.fixture(scope="session") 
def socketio():
    """Create SocketIO instance for testing."""
    from app import socketio as socketio_instance
    return socketio_instance


@pytest.fixture(scope="function")
def container():
    """Create service container with proper configuration."""
    from container import configure_container
    from config_factory import ConfigurationFactory
    
    # Create test socketio instance
    test_app = Flask(__name__)
    test_socketio = SocketIO(test_app, async_mode='eventlet')
    
    config_factory = ConfigurationFactory()
    config = config_factory.to_dict()
    
    return configure_container(socketio=test_socketio, config=config)


@pytest.fixture(scope="function")
def room_manager(container):
    """Provide RoomManager service through dependency injection."""
    return container.get('RoomManager')


@pytest.fixture(scope="function")
def game_manager(container):
    """Provide GameManager service through dependency injection."""
    return container.get('GameManager')


@pytest.fixture(scope="function")
def content_manager(container):
    """Provide ContentManager service through dependency injection."""
    return container.get('ContentManager')


@pytest.fixture(scope="function")
def session_service(container):
    """Provide SessionService through dependency injection."""
    return container.get('SessionService')


@pytest.fixture(scope="function")
def broadcast_service(container):
    """Provide BroadcastService through dependency injection."""
    return container.get('BroadcastService')


@pytest.fixture(scope="function")
def auto_flow_service(container):
    """Provide AutoGameFlowService through dependency injection."""
    return container.get('AutoGameFlowService')


@pytest.fixture(scope="function")
def validation_service(container):
    """Provide ValidationService through dependency injection."""
    return container.get('ValidationService')


@pytest.fixture(scope="function")
def error_response_factory(container):
    """Provide ErrorResponseFactory through dependency injection."""
    return container.get('ErrorResponseFactory')