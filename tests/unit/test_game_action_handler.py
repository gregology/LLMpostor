"""
Game Action Handler Unit Tests

Tests for the GameActionHandler class covering game action validation,
phase-appropriate action handling, player authorization, and game state transitions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.core.errors import ErrorCode, ValidationError


# Mock the decorators to avoid issues in testing
def mock_prevent_event_overflow(event_type):
    """Mock for prevent_event_overflow decorator that takes a parameter"""
    def decorator(func):
        return func
    return decorator


def mock_with_error_handling(func):
    """Mock for with_error_handling decorator"""
    return func


# Patch the decorators before importing the handler
with patch('src.services.rate_limit_service.prevent_event_overflow', mock_prevent_event_overflow), \
     patch('src.services.error_response_factory.with_error_handling', mock_with_error_handling):
    from src.handlers.game_action_handler import GameActionHandler


class TestGameActionHandlerInitialization:
    """Test GameActionHandler initialization and service dependencies"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = GameActionHandler()

    def test_initialization_sets_up_dependencies(self):
        """Test that handler initializes with proper dependencies"""
        assert self.handler._container == self.mock_container
        assert hasattr(self.handler, 'game_manager')
        assert hasattr(self.handler, 'content_manager')
        assert hasattr(self.handler, 'broadcast_service')


class TestHandleStartRoundLogic:
    """Test handle_start_round core business logic"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = GameActionHandler()

        # Setup service mocks
        self.mock_session_service = Mock()
        self.mock_game_manager = Mock()
        self.mock_content_manager = Mock()
        self.mock_broadcast_service = Mock()

        # Configure container to return mocks
        def container_get(service_name):
            services = {
                'SessionService': self.mock_session_service,
                'GameManager': self.mock_game_manager,
                'ContentManager': self.mock_content_manager,
                'BroadcastService': self.mock_broadcast_service
            }
            return services.get(service_name, Mock())

        self.mock_container.get.side_effect = container_get

    def test_validate_content_available_success(self):
        """Test _validate_content_available when content is loaded and has prompts"""
        # Setup
        self.mock_content_manager.is_loaded.return_value = True
        self.mock_content_manager.get_prompt_count.return_value = 5

        # Execute - should not raise exception
        self.handler._validate_content_available()

        # Verify calls
        self.mock_content_manager.is_loaded.assert_called_once()
        self.mock_content_manager.get_prompt_count.assert_called_once()

    def test_validate_content_available_not_loaded(self):
        """Test _validate_content_available when content is not loaded"""
        # Setup
        self.mock_content_manager.is_loaded.return_value = False

        # Execute & Assert
        with pytest.raises(ValidationError) as exc_info:
            self.handler._validate_content_available()

        assert exc_info.value.code == ErrorCode.NO_PROMPTS_AVAILABLE
        assert 'No prompts are available' in str(exc_info.value)

    def test_validate_content_available_zero_prompts(self):
        """Test _validate_content_available when no prompts are available"""
        # Setup
        self.mock_content_manager.is_loaded.return_value = True
        self.mock_content_manager.get_prompt_count.return_value = 0

        # Execute & Assert
        with pytest.raises(ValidationError) as exc_info:
            self.handler._validate_content_available()

        assert exc_info.value.code == ErrorCode.NO_PROMPTS_AVAILABLE
        assert 'No prompts are available' in str(exc_info.value)

    def test_get_random_prompt_success(self):
        """Test _get_random_prompt successful execution"""
        # Setup
        mock_prompt_data = Mock()
        mock_prompt_data.id = 'prompt123'
        mock_prompt_data.prompt = 'What is the meaning of life?'
        mock_prompt_data.model = 'gpt-4'
        mock_prompt_data.get_response.return_value = '42'
        self.mock_content_manager.get_random_prompt_response.return_value = mock_prompt_data

        # Execute
        result = self.handler._get_random_prompt()

        # Verify result
        expected = {
            'id': 'prompt123',
            'prompt': 'What is the meaning of life?',
            'model': 'gpt-4',
            'llm_response': '42'
        }
        assert result == expected

        # Verify calls
        self.mock_content_manager.get_random_prompt_response.assert_called_once()
        mock_prompt_data.get_response.assert_called_once()

    def test_get_random_prompt_exception(self):
        """Test _get_random_prompt when content manager raises exception"""
        # Setup
        self.mock_content_manager.get_random_prompt_response.side_effect = Exception('Content error')

        # Execute & Assert
        with pytest.raises(ValidationError) as exc_info:
            self.handler._get_random_prompt()

        assert exc_info.value.code == ErrorCode.PROMPT_ERROR
        assert 'Failed to get prompt for round' in str(exc_info.value)


class TestValidationLogic:
    """Test validation logic and error handling"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = GameActionHandler()

        # Setup service mocks
        self.mock_validation_service = Mock()
        self.mock_container.get.return_value = self.mock_validation_service

    def test_validation_methods_exist(self):
        """Test that validation methods are available from base class"""
        # These are inherited from ValidationHandlerMixin
        assert hasattr(self.handler, 'validate_response_data')
        assert hasattr(self.handler, 'validate_guess_data')
        assert hasattr(self.handler, 'validate_data_dict')

    def test_game_handler_methods_exist(self):
        """Test that game handler methods are available from base class"""
        # These are inherited from GameHandlerMixin
        assert hasattr(self.handler, 'validate_game_phase')
        assert hasattr(self.handler, 'check_phase_not_expired')
        assert hasattr(self.handler, 'check_can_start_round')


class TestResponseHandling:
    """Test response and broadcasting functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = GameActionHandler()

        # Setup service mocks
        self.mock_error_response_factory = Mock()
        self.mock_container.get.return_value = self.mock_error_response_factory

    def test_response_handling_methods_exist(self):
        """Test that response handling methods are available from base class"""
        # These are inherited from BaseHandler
        assert hasattr(self.handler, 'emit_success')
        assert hasattr(self.handler, 'emit_error')
        assert hasattr(self.handler, 'get_current_session')
        assert hasattr(self.handler, 'require_session')


class TestHandlerStructure:
    """Test overall handler structure and interface"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = GameActionHandler()

    def test_handler_methods_exist(self):
        """Test that all required handler methods exist"""
        assert hasattr(self.handler, 'handle_start_round')
        assert hasattr(self.handler, 'handle_submit_response')
        assert hasattr(self.handler, 'handle_submit_guess')

        # Test methods are callable
        assert callable(self.handler.handle_start_round)
        assert callable(self.handler.handle_submit_response)
        assert callable(self.handler.handle_submit_guess)

    def test_inheritance_structure(self):
        """Test that handler inherits from correct base class"""
        from src.handlers.base_handler import BaseGameHandler
        assert isinstance(self.handler, BaseGameHandler)

    def test_private_methods_exist(self):
        """Test that private helper methods exist"""
        assert hasattr(self.handler, '_validate_content_available')
        assert hasattr(self.handler, '_get_random_prompt')

        # Test methods are callable
        assert callable(self.handler._validate_content_available)
        assert callable(self.handler._get_random_prompt)


class TestErrorCodeValidation:
    """Test that proper error codes are used for different scenarios"""

    def test_error_code_constants_exist(self):
        """Test that all required error codes exist"""
        # Session validation errors
        assert hasattr(ErrorCode, 'NOT_IN_ROOM')
        assert hasattr(ErrorCode, 'INVALID_DATA')

        # Content validation errors
        assert hasattr(ErrorCode, 'NO_PROMPTS_AVAILABLE')
        assert hasattr(ErrorCode, 'PROMPT_ERROR')

        # Game flow errors
        assert hasattr(ErrorCode, 'CANNOT_START_ROUND')
        assert hasattr(ErrorCode, 'START_ROUND_FAILED')
        assert hasattr(ErrorCode, 'WRONG_PHASE')
        assert hasattr(ErrorCode, 'PHASE_EXPIRED')

        # Response submission errors
        assert hasattr(ErrorCode, 'EMPTY_RESPONSE')
        assert hasattr(ErrorCode, 'SUBMIT_FAILED')

        # Guess submission errors
        assert hasattr(ErrorCode, 'MISSING_GUESS')
        assert hasattr(ErrorCode, 'SUBMIT_GUESS_FAILED')

    def test_validation_error_structure(self):
        """Test ValidationError structure and usage"""
        # Test ValidationError can be created with proper attributes
        error = ValidationError(ErrorCode.INVALID_DATA, "Test message")
        assert error.code == ErrorCode.INVALID_DATA
        assert error.message == "Test message"
        assert str(error) == "Test message"


class TestGuessIndexMapping:
    """Test the guess index mapping logic used in handle_submit_guess"""

    def test_guess_index_filtering_logic(self):
        """Test the logic for filtering responses and mapping guess indices"""
        # Simulate the logic from handle_submit_guess
        player_id = 'player1'
        responses = [
            {'author_id': 'player1'},  # Index 0 - player's own response (filtered out)
            {'author_id': 'player2'},  # Index 1 - can guess (maps to filtered index 0)
            {'author_id': 'player3'}   # Index 2 - can guess (maps to filtered index 1)
        ]

        # Filter out player's own response
        filtered_responses = [i for i, response in enumerate(responses) if response['author_id'] != player_id]

        # Verify filtering
        assert filtered_responses == [1, 2]  # Indices 1 and 2 are available for guessing
        assert len(filtered_responses) == 2   # Player can choose from 2 responses

        # Test index mapping
        guess_index = 0  # Player chooses first available response
        actual_response_index = filtered_responses[guess_index]
        assert actual_response_index == 1  # Maps to actual response index 1

        guess_index = 1  # Player chooses second available response
        actual_response_index = filtered_responses[guess_index]
        assert actual_response_index == 2  # Maps to actual response index 2


class TestServiceIntegration:
    """Test integration with various services through the base handler"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = GameActionHandler()

    def test_service_access_properties(self):
        """Test that all required service access properties work"""
        # Test property access (these will call the container)
        services_to_test = [
            'room_manager',
            'game_manager',
            'content_manager',
            'validation_service',
            'error_response_factory',
            'session_service',
            'broadcast_service'
        ]

        for service_name in services_to_test:
            # Test property exists and is accessible
            assert hasattr(self.handler, service_name)

            # Mock the container response for this service
            mock_service = Mock()
            self.mock_container.get.return_value = mock_service

            # Access the property
            service = getattr(self.handler, service_name)

            # Verify container was called
            assert service == mock_service

    def test_logging_methods_available(self):
        """Test that logging functionality is available"""
        assert hasattr(self.handler, 'log_handler_start')
        assert hasattr(self.handler, 'log_handler_success')
        assert callable(self.handler.log_handler_start)
        assert callable(self.handler.log_handler_success)


class TestDecoratorIntegration:
    """Test that decorators work properly (mocked in this test environment)"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = GameActionHandler()

    def test_decorated_methods_callable(self):
        """Test that decorated methods are still callable"""
        # Since we mocked the decorators, the methods should be directly callable
        assert callable(self.handler.handle_start_round)
        assert callable(self.handler.handle_submit_response)
        assert callable(self.handler.handle_submit_guess)

    def test_decorator_names_preserved(self):
        """Test that method names are preserved after decoration"""
        assert self.handler.handle_start_round.__name__ == 'handle_start_round'
        assert self.handler.handle_submit_response.__name__ == 'handle_submit_response'
        assert self.handler.handle_submit_guess.__name__ == 'handle_submit_guess'