"""
API Routes Unit Tests

Tests for the API routes in src/routes/api.py including route handling,
template serving, error responses, and request validation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from src.routes.api import create_api_blueprint


class TestApiRoutesBlueprintCreation:
    """Test API blueprint creation and configuration"""

    def test_create_api_blueprint_basic(self):
        """Test that API blueprint is created with proper configuration"""
        # Mock services
        mock_room_manager = Mock()
        services = {'room_manager': mock_room_manager}

        # Create blueprint
        blueprint = create_api_blueprint(services)

        # Verify blueprint properties
        assert blueprint.name == 'api'
        assert blueprint is not None

    def test_create_api_blueprint_sets_global_room_manager(self):
        """Test that blueprint creation sets the global room manager reference"""
        # Mock services
        mock_room_manager = Mock()
        services = {'room_manager': mock_room_manager}

        # Import the module to access globals
        from src.routes import api

        # Create blueprint
        create_api_blueprint(services)

        # Verify global room_manager is set
        assert api.room_manager is mock_room_manager

    def test_create_api_blueprint_registers_routes(self):
        """Test that all expected routes are registered on the blueprint"""
        # Mock services
        mock_room_manager = Mock()
        services = {'room_manager': mock_room_manager}

        # Create blueprint and register with Flask app to inspect routes
        blueprint = create_api_blueprint(services)
        app = Flask(__name__)
        app.register_blueprint(blueprint)

        # Get registered routes from the app's url_map
        route_rules = [rule.rule for rule in app.url_map.iter_rules()]

        # Verify expected routes are registered
        expected_routes = ['/', '/api/find-available-room', '/<room_id>']
        for expected_route in expected_routes:
            assert any(expected_route == rule for rule in route_rules)


class TestIndexRoute:
    """Test the index route (/"""

    def setup_method(self):
        """Setup test fixtures"""
        self.app = Flask(__name__)
        self.mock_room_manager = Mock()
        services = {'room_manager': self.mock_room_manager}
        self.blueprint = create_api_blueprint(services)
        self.app.register_blueprint(self.blueprint)

    @patch('src.routes.api.render_template')
    def test_index_route_success(self, mock_render_template):
        """Test index route returns rendered template"""
        mock_render_template.return_value = "<html>Game Interface</html>"

        with self.app.test_client() as client:
            response = client.get('/')

            # Verify template is rendered correctly
            mock_render_template.assert_called_once_with('index.html')
            assert response.status_code == 200
            assert response.data.decode() == "<html>Game Interface</html>"

    @patch('src.routes.api.render_template')
    def test_index_route_template_error_returns_500(self, mock_render_template):
        """Test that template rendering errors return 500 status"""
        mock_render_template.side_effect = Exception("Template error")

        with self.app.test_client() as client:
            response = client.get('/')
            # Flask catches template errors and returns 500
            assert response.status_code == 500


class TestFindAvailableRoomRoute:
    """Test the find available room route (/api/find-available-room)"""

    def setup_method(self):
        """Setup test fixtures"""
        self.app = Flask(__name__)
        self.mock_room_manager = Mock()
        services = {'room_manager': self.mock_room_manager}
        self.blueprint = create_api_blueprint(services)
        self.app.register_blueprint(self.blueprint)

    def test_find_available_room_success(self):
        """Test finding an available room successfully"""
        # Setup mock room manager
        self.mock_room_manager.get_all_rooms.return_value = ['room1', 'room2']
        self.mock_room_manager.get_room_state.side_effect = [
            # First room - not waiting phase
            {
                'game_state': {'phase': 'playing'},
                'players': {'player1': {}, 'player2': {}}
            },
            # Second room - waiting phase with space
            {
                'game_state': {'phase': 'waiting'},
                'players': {'player1': {}, 'player2': {}}
            }
        ]

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Verify response
            assert response.status_code == 200
            data = response.get_json()
            assert data == {'room_id': 'room2'}

            # Verify room manager calls
            self.mock_room_manager.get_all_rooms.assert_called_once()
            assert self.mock_room_manager.get_room_state.call_count == 2

    def test_find_available_room_requires_minimum_players(self):
        """Test that rooms must have at least 1 player to be considered available"""
        # Setup room with no players
        self.mock_room_manager.get_all_rooms.return_value = ['empty_room']
        self.mock_room_manager.get_room_state.return_value = {
            'game_state': {'phase': 'waiting'},
            'players': {}  # No players
        }

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Should not find available room
            assert response.status_code == 200
            data = response.get_json()
            assert data == {'room_id': None}

    def test_find_available_room_excludes_full_rooms(self):
        """Test that full rooms (8+ players) are not considered available"""
        # Setup full room
        self.mock_room_manager.get_all_rooms.return_value = ['full_room']
        players = {f'player{i}': {} for i in range(8)}  # 8 players (full)
        self.mock_room_manager.get_room_state.return_value = {
            'game_state': {'phase': 'waiting'},
            'players': players
        }

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Should not find available room
            assert response.status_code == 200
            data = response.get_json()
            assert data == {'room_id': None}

    def test_find_available_room_only_waiting_phase(self):
        """Test that only rooms in waiting phase are considered"""
        # Setup room in playing phase
        self.mock_room_manager.get_all_rooms.return_value = ['playing_room']
        self.mock_room_manager.get_room_state.return_value = {
            'game_state': {'phase': 'playing'},
            'players': {'player1': {}, 'player2': {}}
        }

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Should not find available room
            assert response.status_code == 200
            data = response.get_json()
            assert data == {'room_id': None}

    def test_find_available_room_no_rooms_exist(self):
        """Test behavior when no rooms exist"""
        self.mock_room_manager.get_all_rooms.return_value = []

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Should return None
            assert response.status_code == 200
            data = response.get_json()
            assert data == {'room_id': None}

    def test_find_available_room_handles_none_room_state(self):
        """Test handling of rooms that return None for room state"""
        self.mock_room_manager.get_all_rooms.return_value = ['invalid_room']
        self.mock_room_manager.get_room_state.return_value = None

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Should return None
            assert response.status_code == 200
            data = response.get_json()
            assert data == {'room_id': None}

    def test_find_available_room_handles_malformed_room_state(self):
        """Test handling of rooms with malformed state data"""
        self.mock_room_manager.get_all_rooms.return_value = ['malformed_room']
        self.mock_room_manager.get_room_state.return_value = {
            # Missing game_state or players
            'some_other_data': 'value'
        }

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Should return None
            assert response.status_code == 200
            data = response.get_json()
            assert data == {'room_id': None}

    @patch('src.routes.api.logger')
    def test_find_available_room_handles_room_manager_error(self, mock_logger):
        """Test error handling when room manager raises exception"""
        self.mock_room_manager.get_all_rooms.side_effect = Exception("Room manager error")

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Should return None and log error
            assert response.status_code == 200
            data = response.get_json()
            assert data == {'room_id': None}

            # Verify error was logged
            mock_logger.error.assert_called_once()
            assert "Error finding available room" in mock_logger.error.call_args[0][0]

    @patch('src.routes.api.logger')
    def test_find_available_room_logs_success(self, mock_logger):
        """Test that successful room finding is logged"""
        # Setup available room
        self.mock_room_manager.get_all_rooms.return_value = ['room1']
        self.mock_room_manager.get_room_state.return_value = {
            'game_state': {'phase': 'waiting'},
            'players': {'player1': {}, 'player2': {}}
        }

        with self.app.test_client() as client:
            response = client.get('/api/find-available-room')

            # Should log the found room
            assert response.status_code == 200
            mock_logger.info.assert_called_once()
            assert "Found available room: room1 with 2 players" in mock_logger.info.call_args[0][0]


class TestRoomRoute:
    """Test the room-specific route (/<room_id>)"""

    def setup_method(self):
        """Setup test fixtures"""
        self.app = Flask(__name__)
        self.mock_room_manager = Mock()
        services = {'room_manager': self.mock_room_manager}
        self.blueprint = create_api_blueprint(services)
        self.app.register_blueprint(self.blueprint)

    @patch('src.routes.api.render_template')
    @patch('src.services.validation_service.ValidationService')
    def test_room_route_success(self, mock_validation_service, mock_render_template):
        """Test room route returns rendered template with room ID"""
        # Setup mocks
        mock_service_instance = Mock()
        mock_service_instance.get_max_response_length.return_value = 150
        mock_validation_service.return_value = mock_service_instance
        mock_render_template.return_value = "<html>Game Room</html>"

        with self.app.test_client() as client:
            response = client.get('/test-room-123')

            # Verify template rendering
            mock_render_template.assert_called_once_with(
                'game.html',
                room_id='test-room-123',
                max_response_length=150
            )
            assert response.status_code == 200
            assert response.data.decode() == "<html>Game Room</html>"

    @patch('src.routes.api.render_template')
    @patch('src.services.validation_service.ValidationService')
    def test_room_route_gets_max_response_length(self, mock_validation_service, mock_render_template):
        """Test that room route properly retrieves max response length from validation service"""
        # Setup mocks
        mock_service_instance = Mock()
        mock_service_instance.get_max_response_length.return_value = 200
        mock_validation_service.return_value = mock_service_instance
        mock_render_template.return_value = "<html>Game Room</html>"

        with self.app.test_client() as client:
            response = client.get('/room-456')

            # Verify validation service was called
            mock_validation_service.assert_called_once()
            mock_service_instance.get_max_response_length.assert_called_once()

            # Verify correct max_response_length passed to template
            mock_render_template.assert_called_once_with(
                'game.html',
                room_id='room-456',
                max_response_length=200
            )

    @patch('src.routes.api.render_template')
    @patch('src.services.validation_service.ValidationService')
    def test_room_route_handles_validation_service_error(self, mock_validation_service, mock_render_template):
        """Test room route handles validation service initialization errors"""
        # Setup validation service to raise error
        mock_validation_service.side_effect = Exception("Validation service error")
        mock_render_template.return_value = "<html>Game Room</html>"

        with self.app.test_client() as client:
            # Should return 500 due to validation service error
            response = client.get('/error-room')
            assert response.status_code == 500

    @patch('src.routes.api.render_template')
    @patch('src.services.validation_service.ValidationService')
    def test_room_route_handles_get_max_response_length_error(self, mock_validation_service, mock_render_template):
        """Test room route handles max response length retrieval errors"""
        # Setup validation service instance to raise error on method call
        mock_service_instance = Mock()
        mock_service_instance.get_max_response_length.side_effect = Exception("Max length error")
        mock_validation_service.return_value = mock_service_instance
        mock_render_template.return_value = "<html>Game Room</html>"

        with self.app.test_client() as client:
            # Should return 500 due to max length error
            response = client.get('/length-error-room')
            assert response.status_code == 500

    @patch('src.routes.api.render_template')
    @patch('src.services.validation_service.ValidationService')
    def test_room_route_template_error_returns_500(self, mock_validation_service, mock_render_template):
        """Test that template rendering errors return 500 status"""
        # Setup mocks
        mock_service_instance = Mock()
        mock_service_instance.get_max_response_length.return_value = 100
        mock_validation_service.return_value = mock_service_instance
        mock_render_template.side_effect = Exception("Template error")

        with self.app.test_client() as client:
            response = client.get('/template-error-room')
            # Flask catches template errors and returns 500
            assert response.status_code == 500

    @patch('src.routes.api.render_template')
    @patch('src.services.validation_service.ValidationService')
    def test_room_route_with_special_characters(self, mock_validation_service, mock_render_template):
        """Test room route handles room IDs with special characters"""
        # Setup mocks
        mock_service_instance = Mock()
        mock_service_instance.get_max_response_length.return_value = 100
        mock_validation_service.return_value = mock_service_instance
        mock_render_template.return_value = "<html>Special Room</html>"

        # Test with various special characters that might appear in URLs
        test_room_ids = [
            'room-with-hyphens',
            'room_with_underscores',
            'room123with456numbers',
            'UPPERCASE-room',
            'mixed-Case_Room123'
        ]

        with self.app.test_client() as client:
            for room_id in test_room_ids:
                response = client.get(f'/{room_id}')

                # Should handle all these room IDs successfully
                assert response.status_code == 200

                # Verify room_id was passed correctly to template
                call_args = mock_render_template.call_args
                assert call_args[1]['room_id'] == room_id


class TestApiRoutesIntegration:
    """Integration tests for API routes within Flask application"""

    def setup_method(self):
        """Setup Flask app with API blueprint for integration testing"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True

        self.mock_room_manager = Mock()
        services = {'room_manager': self.mock_room_manager}
        self.blueprint = create_api_blueprint(services)
        self.app.register_blueprint(self.blueprint)

    def test_all_routes_accessible_via_app(self):
        """Test that all routes are accessible through the Flask app"""
        with self.app.test_client() as client:
            # Test index route exists
            with patch('src.routes.api.render_template') as mock_render:
                mock_render.return_value = "index"
                response = client.get('/')
                assert response.status_code == 200

            # Test find available room route exists
            self.mock_room_manager.get_all_rooms.return_value = []
            response = client.get('/api/find-available-room')
            assert response.status_code == 200

            # Test room route exists
            with patch('src.routes.api.render_template') as mock_render:
                with patch('src.services.validation_service.ValidationService'):
                    mock_render.return_value = "room"
                    response = client.get('/test-room')
                    assert response.status_code == 200

    def test_blueprint_url_prefix_handling(self):
        """Test that routes work correctly with potential URL prefixes"""
        # Create app with blueprint registered with prefix
        app_with_prefix = Flask(__name__)
        app_with_prefix.config['TESTING'] = True

        services = {'room_manager': self.mock_room_manager}
        blueprint = create_api_blueprint(services)
        app_with_prefix.register_blueprint(blueprint, url_prefix='/game')

        with app_with_prefix.test_client() as client:
            # Test routes with prefix
            with patch('src.routes.api.render_template') as mock_render:
                mock_render.return_value = "index"
                response = client.get('/game/')
                assert response.status_code == 200

            self.mock_room_manager.get_all_rooms.return_value = []
            response = client.get('/game/api/find-available-room')
            assert response.status_code == 200

            with patch('src.routes.api.render_template') as mock_render:
                with patch('src.services.validation_service.ValidationService'):
                    mock_render.return_value = "room"
                    response = client.get('/game/test-room')
                    assert response.status_code == 200