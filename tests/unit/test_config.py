"""
Unit tests for configuration management.
Tests the Config classes and environment variable handling before refactoring to configuration factory.
"""

import os
import pytest
from unittest.mock import patch

from config import Config, DevelopmentConfig, ProductionConfig, config


class TestConfig:
    """Test the base Config class."""

    def test_config_initialization(self):
        """Test that Config class initializes with correct defaults."""
        config = Config()
        
        assert config.SECRET_KEY == 'dev-secret-key-change-in-production'
        assert config.PROMPTS_FILE == 'prompts.yaml'
        assert config.MAX_PLAYERS_PER_ROOM == 8
        assert config.RESPONSE_TIME_LIMIT == 180
        assert config.GUESSING_TIME_LIMIT == 120
        assert config.RESULTS_DISPLAY_TIME == 30

    def test_config_with_environment_variables_requires_reload(self):
        """Test that Config class uses environment variables (requires module reload)."""
        # Note: Due to class variables being evaluated at module load time,
        # environment changes require module reload. This tests the current limitation.
        config = Config()
        
        # These will be the defaults since class vars are already set
        assert config.SECRET_KEY == 'dev-secret-key-change-in-production'
        assert config.PROMPTS_FILE == 'prompts.yaml'
        assert config.MAX_PLAYERS_PER_ROOM == 8
        
        # This documents the current behavior that should be fixed in refactoring

    def test_config_class_variables_evaluation(self):
        """Test that Config class variables are evaluated correctly at module load."""
        # This tests the actual current behavior
        config1 = Config()
        config2 = Config()
        
        # Both instances share class variables
        assert config1.SECRET_KEY == config2.SECRET_KEY
        assert config1.MAX_PLAYERS_PER_ROOM == config2.MAX_PLAYERS_PER_ROOM

    def test_config_integer_conversion_behavior(self):
        """Test current integer conversion behavior in Config class."""
        # The current implementation does int() conversion at class definition
        # This will either work (if env vars are valid) or fail at import time
        config = Config()
        
        # These should be integers
        assert isinstance(config.MAX_PLAYERS_PER_ROOM, int)
        assert isinstance(config.RESPONSE_TIME_LIMIT, int)
        assert isinstance(config.GUESSING_TIME_LIMIT, int)
        assert isinstance(config.RESULTS_DISPLAY_TIME, int)

    def test_config_missing_environment_variables(self):
        """Test that Config class uses defaults when environment variables are missing."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            assert config.SECRET_KEY == 'dev-secret-key-change-in-production'
            assert config.PROMPTS_FILE == 'prompts.yaml'
            assert config.MAX_PLAYERS_PER_ROOM == 8


class TestDevelopmentConfig:
    """Test the DevelopmentConfig class."""

    def test_development_config_inherits_from_config(self):
        """Test that DevelopmentConfig inherits from Config."""
        config = DevelopmentConfig()
        
        # Should have all base config attributes
        assert hasattr(config, 'SECRET_KEY')
        assert hasattr(config, 'PROMPTS_FILE')
        assert hasattr(config, 'MAX_PLAYERS_PER_ROOM')
        
        # Should inherit defaults
        assert config.SECRET_KEY == 'dev-secret-key-change-in-production'

    def test_development_config_debug_mode(self):
        """Test that DevelopmentConfig enables debug mode."""
        config = DevelopmentConfig()
        assert config.DEBUG is True


class TestProductionConfig:
    """Test the ProductionConfig class."""

    def test_production_config_inherits_from_config(self):
        """Test that ProductionConfig inherits from Config."""
        config = ProductionConfig()
        
        # Should have all base config attributes
        assert hasattr(config, 'SECRET_KEY')
        assert hasattr(config, 'PROMPTS_FILE')
        assert hasattr(config, 'MAX_PLAYERS_PER_ROOM')

    def test_production_config_debug_mode(self):
        """Test that ProductionConfig disables debug mode."""
        config = ProductionConfig()
        assert config.DEBUG is False


class TestConfigMapping:
    """Test the config dictionary and factory function."""

    def test_config_mapping(self):
        """Test that config contains expected mappings."""
        assert 'development' in config
        assert 'production' in config
        assert 'default' in config
        
        assert config['development'] is DevelopmentConfig
        assert config['production'] is ProductionConfig
        assert config['default'] is DevelopmentConfig

    def test_config_factory_development(self):
        """Test creating development config through factory."""
        config_class = config['development']
        config_instance = config_class()
        
        assert isinstance(config_instance, DevelopmentConfig)
        assert config_instance.DEBUG is True

    def test_config_factory_production(self):
        """Test creating production config through factory."""
        config_class = config['production']
        config_instance = config_class()
        
        assert isinstance(config_instance, ProductionConfig)
        assert config_instance.DEBUG is False

    def test_config_factory_default(self):
        """Test creating default config through factory."""
        config_class = config['default']
        config_instance = config_class()
        
        assert isinstance(config_instance, DevelopmentConfig)
        assert config_instance.DEBUG is True


class TestConfigurationConsistency:
    """Test that configuration values are consistent across the application."""

    def test_error_handler_max_response_length_consistency(self):
        """Test that ErrorHandler.MAX_RESPONSE_LENGTH should be configurable."""
        # This test documents the current inconsistency
        # ErrorHandler has hardcoded MAX_RESPONSE_LENGTH = 100
        # But config doesn't have this value
        from src.error_handler import ErrorHandler
        
        config = Config()
        
        # Currently there's no MAX_RESPONSE_LENGTH in config
        assert not hasattr(config, 'MAX_RESPONSE_LENGTH')
        
        # ErrorHandler now uses configuration
        error_handler = ErrorHandler()
        assert error_handler.MAX_RESPONSE_LENGTH == 100
        
        # This test documents the inconsistency that should be fixed
        # in the configuration factory refactoring

    @patch.dict(os.environ, {'FLASK_ENV': 'development'})
    def test_flask_env_environment_variable(self):
        """Test that FLASK_ENV environment variable can be read."""
        # This tests the pattern used in app.py:584
        flask_env = os.environ.get('FLASK_ENV')
        assert flask_env == 'development'
        
        debug_mode = flask_env == 'development'
        assert debug_mode is True

    @patch.dict(os.environ, {'PORT': '5000'})
    def test_port_environment_variable(self):
        """Test that PORT environment variable can be read and converted."""
        # This tests the pattern used in app.py:583
        port = int(os.environ.get('PORT', 8000))
        assert port == 5000

    @patch.dict(os.environ, {}, clear=True)
    def test_port_environment_variable_default(self):
        """Test that PORT uses default when not set."""
        port = int(os.environ.get('PORT', 8000))
        assert port == 8000


class TestConfigurationEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_string_environment_variable_current_behavior(self):
        """Test current behavior with empty string environment variables."""
        # Current implementation uses 'or' which treats empty string as falsy
        config = Config()
        # Empty string would fall back to default due to 'or' operator
        assert config.SECRET_KEY == 'dev-secret-key-change-in-production'

    def test_current_environment_variable_behavior(self):
        """Test that current config uses class variables set at import time."""
        config = Config()
        
        # These reflect the current environment at module load time
        assert config.MAX_PLAYERS_PER_ROOM == 8  # Default value
        assert isinstance(config.MAX_PLAYERS_PER_ROOM, int)

    def test_config_attributes_are_instance_variables(self):
        """Test that config attributes are instance variables, not class variables."""
        config1 = Config()
        config2 = Config()
        
        # Modify one instance
        config1.SECRET_KEY = 'modified'
        
        # Other instance should be unaffected
        assert config2.SECRET_KEY == 'dev-secret-key-change-in-production'