"""
Configuration Factory Tests
Tests for the centralized configuration management system.
"""

import pytest
import os
from unittest.mock import patch, Mock
from config_factory import (
    ConfigurationFactory, AppConfig, Environment, ConfigError,
    load_config, load_config_from_dict, get_config, reset_config, override_config
)


class TestAppConfig:
    """Test AppConfig dataclass"""
    
    def test_config_initialization_with_defaults(self):
        """Test AppConfig initialization with default values"""
        config = AppConfig()
        
        # Check default values
        assert config.secret_key == 'dev-secret-key-change-in-production'
        assert config.debug == False
        assert config.flask_env == 'development'  # Default to development for safety
        assert config.host == '0.0.0.0'
        assert config.port == 5000
        assert config.max_players_per_room == 8
        assert config.response_time_limit == 180
        assert config.guessing_time_limit == 120
        assert config.results_display_time == 30
        assert config.max_response_length == 100
        assert config.prompts_file == 'prompts.yaml'
        assert config.environment == Environment.DEVELOPMENT
    
    def test_config_initialization_with_custom_values(self):
        """Test AppConfig initialization with custom values"""
        config = AppConfig(
            secret_key='custom-secret',
            debug=True,
            port=3000,
            max_players_per_room=12,
            environment=Environment.DEVELOPMENT
        )
        
        assert config.secret_key == 'custom-secret'
        assert config.debug == True
        assert config.port == 3000
        assert config.max_players_per_room == 12
        assert config.environment == Environment.DEVELOPMENT
    
    def test_config_validation_valid_values(self):
        """Test that valid configuration values pass validation"""
        # This should not raise any exceptions
        config = AppConfig(
            port=8080,
            max_players_per_room=6,
            response_time_limit=120,
            guessing_time_limit=90,
            max_response_length=200,
            secret_key='secure-production-key',
            environment=Environment.PRODUCTION
        )
        
        assert config.port == 8080
        assert config.max_players_per_room == 6
    
    def test_config_validation_invalid_port(self):
        """Test validation fails for invalid port numbers"""
        with pytest.raises(ConfigError, match="Invalid port number"):
            AppConfig(port=0)
        
        with pytest.raises(ConfigError, match="Invalid port number"):
            AppConfig(port=70000)
    
    def test_config_validation_invalid_max_players(self):
        """Test validation fails for invalid max_players_per_room"""
        with pytest.raises(ConfigError, match="Invalid max_players_per_room"):
            AppConfig(max_players_per_room=0)
        
        with pytest.raises(ConfigError, match="Invalid max_players_per_room"):
            AppConfig(max_players_per_room=100)
    
    def test_config_validation_invalid_time_limits(self):
        """Test validation fails for invalid time limits"""
        with pytest.raises(ConfigError, match="Invalid response_time_limit"):
            AppConfig(response_time_limit=5)  # Too short
        
        with pytest.raises(ConfigError, match="Invalid response_time_limit"):
            AppConfig(response_time_limit=2000)  # Too long
        
        with pytest.raises(ConfigError, match="Invalid guessing_time_limit"):
            AppConfig(guessing_time_limit=5)
    
    def test_config_validation_invalid_response_length(self):
        """Test validation fails for invalid max_response_length"""
        with pytest.raises(ConfigError, match="Invalid max_response_length"):
            AppConfig(max_response_length=5)  # Too short
        
        with pytest.raises(ConfigError, match="Invalid max_response_length"):
            AppConfig(max_response_length=2000)  # Too long
    
    def test_config_validation_production_secret_key(self):
        """Test validation fails for default secret key in production"""
        with pytest.raises(ConfigError, match="Production environment requires a secure SECRET_KEY"):
            AppConfig(
                environment=Environment.PRODUCTION,
                secret_key='dev-secret-key-change-in-production'
            )
    
    def test_config_validation_min_players_required(self):
        """Test validation for min_players_required"""
        # Valid values
        config = AppConfig(min_players_required=2)
        assert config.min_players_required == 2
        
        # Invalid: less than 1
        with pytest.raises(ConfigError, match="Invalid min_players_required"):
            AppConfig(min_players_required=0)
        
        # Invalid: more than max_players_per_room
        with pytest.raises(ConfigError, match="Invalid min_players_required"):
            AppConfig(max_players_per_room=4, min_players_required=5)
    
    def test_config_validation_game_flow_intervals(self):
        """Test validation for auto game flow timing settings"""
        # Valid values
        config = AppConfig(game_flow_check_interval=2, countdown_broadcast_interval=15)
        assert config.game_flow_check_interval == 2
        assert config.countdown_broadcast_interval == 15
        
        # Invalid: check interval too small
        with pytest.raises(ConfigError, match="Invalid game_flow_check_interval"):
            AppConfig(game_flow_check_interval=0)
        
        # Invalid: check interval too large
        with pytest.raises(ConfigError, match="Invalid game_flow_check_interval"):
            AppConfig(game_flow_check_interval=120)
        
        # Invalid: broadcast interval too small
        with pytest.raises(ConfigError, match="Invalid countdown_broadcast_interval"):
            AppConfig(countdown_broadcast_interval=0)
    
    def test_config_validation_warning_thresholds(self):
        """Test validation for warning threshold settings"""
        # Valid values
        config = AppConfig(warning_threshold_seconds=45, final_warning_threshold_seconds=15)
        assert config.warning_threshold_seconds == 45
        assert config.final_warning_threshold_seconds == 15
        
        # Invalid: final warning >= warning threshold
        with pytest.raises(ConfigError, match="Invalid final_warning_threshold_seconds"):
            AppConfig(warning_threshold_seconds=30, final_warning_threshold_seconds=30)
        
        # Invalid: final warning > warning threshold
        with pytest.raises(ConfigError, match="Invalid final_warning_threshold_seconds"):
            AppConfig(warning_threshold_seconds=10, final_warning_threshold_seconds=15)
    
    def test_config_validation_rate_limiting(self):
        """Test validation for rate limiting settings"""
        # Valid values
        config = AppConfig(max_events_per_second=20, max_events_per_minute=200)
        assert config.max_events_per_second == 20
        assert config.max_events_per_minute == 200
        
        # Invalid: events per second too low
        with pytest.raises(ConfigError, match="Invalid max_events_per_second"):
            AppConfig(max_events_per_second=0)
        
        # Invalid: events per minute less than events per second
        with pytest.raises(ConfigError, match="Invalid max_events_per_minute"):
            AppConfig(max_events_per_second=60, max_events_per_minute=30)
    
    def test_config_validation_cache_settings(self):
        """Test validation for cache settings"""
        # Valid values
        config = AppConfig(cache_max_memory_bytes=10*1024*1024, cache_default_ttl_seconds=300)
        assert config.cache_max_memory_bytes == 10*1024*1024
        assert config.cache_default_ttl_seconds == 300
        
        # Invalid: memory too small
        with pytest.raises(ConfigError, match="Invalid cache_max_memory_bytes"):
            AppConfig(cache_max_memory_bytes=512*1024)  # 512KB, below 1MB minimum
        
        # Invalid: TTL too small
        with pytest.raises(ConfigError, match="Invalid cache_default_ttl_seconds"):
            AppConfig(cache_default_ttl_seconds=0)
    
    # Removed test for deleted metrics settings
    
    def test_environment_properties(self):
        """Test environment property methods"""
        dev_config = AppConfig(environment=Environment.DEVELOPMENT)
        assert dev_config.is_development == True
        assert dev_config.is_production == False
        assert dev_config.is_testing == False
        
        prod_config = AppConfig(environment=Environment.PRODUCTION, secret_key='secure-key')
        assert prod_config.is_development == False
        assert prod_config.is_production == True
        assert prod_config.is_testing == False
        
        test_config = AppConfig(environment=Environment.TESTING)
        assert test_config.is_development == False
        assert test_config.is_production == False
        assert test_config.is_testing == True


class TestConfigurationFactory:
    """Test ConfigurationFactory class"""
    
    def setup_method(self):
        """Setup for each test method"""
        # Reset the factory for clean tests
        self.factory = ConfigurationFactory()
        self.factory.reset()
    
    def test_singleton_pattern(self):
        """Test that ConfigurationFactory implements singleton pattern"""
        factory1 = ConfigurationFactory()
        factory2 = ConfigurationFactory()
        assert factory1 is factory2
    
    def test_load_from_environment_development(self):
        """Test loading configuration from environment variables for development"""
        env_vars = {
            'FLASK_ENV': 'development',
            'SECRET_KEY': 'dev-secret-123',
            'PORT': '3000',
            'MAX_PLAYERS_PER_ROOM': '10',
            'DEBUG': 'true'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = self.factory.load_from_environment()
        
        assert config.environment == Environment.DEVELOPMENT
        assert config.debug == True
        assert config.flask_env == 'development'
        assert config.secret_key == 'dev-secret-123'
        assert config.port == 3000
        assert config.max_players_per_room == 10
    
    def test_load_from_environment_production(self):
        """Test loading configuration from environment variables for production"""
        env_vars = {
            'FLASK_ENV': 'production',
            'SECRET_KEY': 'super-secure-production-key',
            'PORT': '8080',
            'DEBUG': 'false',
            'MAX_RESPONSE_LENGTH': '150'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = self.factory.load_from_environment()
        
        assert config.environment == Environment.PRODUCTION
        assert config.debug == False
        assert config.flask_env == 'production'
        assert config.secret_key == 'super-secure-production-key'
        assert config.port == 8080
        assert config.max_response_length == 150
    
    def test_load_from_environment_new_config_fields(self):
        """Test loading new configuration fields from environment"""
        env_vars = {
            'FLASK_ENV': 'development',
            'MIN_PLAYERS_REQUIRED': '3',
            'GAME_FLOW_CHECK_INTERVAL': '2',
            'COUNTDOWN_BROADCAST_INTERVAL': '15',
            'WARNING_THRESHOLD_SECONDS': '45',
            'FINAL_WARNING_THRESHOLD_SECONDS': '15',
            'MAX_EVENTS_PER_SECOND': '20',
            'MAX_EVENTS_PER_MINUTE': '200',
            'COMPRESSION_THRESHOLD_BYTES': '1024',
            'CACHE_MAX_MEMORY_BYTES': str(10*1024*1024),  # 10MB
            'CACHE_DEFAULT_TTL_SECONDS': '300'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = self.factory.load_from_environment()
        
        assert config.min_players_required == 3
        assert config.game_flow_check_interval == 2
        assert config.countdown_broadcast_interval == 15
        assert config.warning_threshold_seconds == 45
        assert config.final_warning_threshold_seconds == 15
        assert config.max_events_per_second == 20
        assert config.max_events_per_minute == 200
        assert config.compression_threshold_bytes == 1024
        assert config.cache_max_memory_bytes == 10*1024*1024
        assert config.cache_default_ttl_seconds == 300
    
    def test_load_from_environment_with_prefix(self):
        """Test loading configuration with environment variable prefix"""
        env_vars = {
            'MYAPP_SECRET_KEY': 'prefixed-secret',
            'MYAPP_PORT': '9000',
            'MYAPP_DEBUG': 'true'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = self.factory.load_from_environment('MYAPP_')
        
        assert config.secret_key == 'prefixed-secret'
        assert config.port == 9000
        assert config.debug == True
    
    def test_load_from_environment_type_conversion(self):
        """Test type conversion of environment variables"""
        env_vars = {
            'PORT': 'not_a_number',  # Invalid integer
            'DEBUG': 'yes',  # Boolean conversion
            'MAX_PLAYERS_PER_ROOM': '12',
            'FLASK_ENV': 'development'  # Avoid production secret key validation
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = self.factory.load_from_environment()
        
        # Should fall back to default for invalid port
        assert config.port == 5000  # Default value
        assert config.debug == True  # 'yes' should convert to True
        assert config.max_players_per_room == 12  # Valid integer conversion
    
    def test_load_from_dict(self):
        """Test loading configuration from dictionary"""
        config_dict = {
            'secret_key': 'dict-secret',
            'port': 4000,
            'debug': True,
            'environment': 'development',
            'max_players_per_room': 6
        }
        
        config = self.factory.load_from_dict(config_dict)
        
        assert config.secret_key == 'dict-secret'
        assert config.port == 4000
        assert config.debug == True
        assert config.environment == Environment.DEVELOPMENT
        assert config.max_players_per_room == 6
    
    def test_override_setting(self):
        """Test overriding specific settings"""
        # First load a base configuration
        self.factory.load_from_dict({'secret_key': 'base-secret', 'port': 5000})
        
        # Override specific setting
        self.factory.override_setting('port', 9000)
        
        config = self.factory.get_config()
        assert config.secret_key == 'base-secret'  # Unchanged
        assert config.port == 9000  # Overridden
    
    def test_override_setting_with_validation(self):
        """Test that overriding settings still triggers validation"""
        self.factory.load_from_dict({'secret_key': 'base-secret'})
        
        with pytest.raises(ConfigError, match="Invalid port number"):
            self.factory.override_setting('port', 0)  # Invalid port
    
    def test_get_config_before_loading(self):
        """Test that getting config before loading raises error"""
        with pytest.raises(ConfigError, match="Configuration not loaded"):
            self.factory.get_config()
    
    def test_to_dict(self):
        """Test converting configuration to dictionary"""
        config_dict = {
            'secret_key': 'test-secret',
            'port': 3000,
            'environment': Environment.DEVELOPMENT
        }
        
        self.factory.load_from_dict(config_dict)
        result_dict = self.factory.to_dict()
        
        assert result_dict['secret_key'] == 'test-secret'
        assert result_dict['port'] == 3000
        assert result_dict['environment'] == 'development'  # Enum converted to string
    
    def test_get_flask_config(self):
        """Test getting Flask-compatible configuration"""
        self.factory.load_from_dict({
            'secret_key': 'flask-secret',
            'debug': True,
            'flask_env': 'development',
            'max_response_length': 150
        })
        
        flask_config = self.factory.get_flask_config()
        
        expected_keys = [
            'SECRET_KEY', 'DEBUG', 'ENV', 'MAX_PLAYERS_PER_ROOM',
            'RESPONSE_TIME_LIMIT', 'GUESSING_TIME_LIMIT', 'RESULTS_DISPLAY_TIME',
            'MAX_RESPONSE_LENGTH', 'PROMPTS_FILE'
        ]
        
        for key in expected_keys:
            assert key in flask_config
        
        assert flask_config['SECRET_KEY'] == 'flask-secret'
        assert flask_config['DEBUG'] == True
        assert flask_config['ENV'] == 'development'
        assert flask_config['MAX_RESPONSE_LENGTH'] == 150


class TestGlobalFunctions:
    """Test global configuration functions"""
    
    def setup_method(self):
        """Reset configuration before each test"""
        reset_config()
    
    def test_load_config_function(self):
        """Test global load_config function"""
        env_vars = {'SECRET_KEY': 'global-secret', 'PORT': '7000'}
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()
        
        assert config.secret_key == 'global-secret'
        assert config.port == 7000
    
    def test_load_config_from_dict_function(self):
        """Test global load_config_from_dict function"""
        config_dict = {'secret_key': 'dict-global-secret', 'port': 6000}
        
        config = load_config_from_dict(config_dict)
        
        assert config.secret_key == 'dict-global-secret'
        assert config.port == 6000
    
    def test_get_config_function(self):
        """Test global get_config function"""
        # First load configuration
        load_config_from_dict({'secret_key': 'get-test-secret'})
        
        config = get_config()
        assert config.secret_key == 'get-test-secret'
    
    def test_override_config_function(self):
        """Test global override_config function"""
        load_config_from_dict({'secret_key': 'original', 'port': 5000})
        
        override_config('port', 8000)
        
        config = get_config()
        assert config.secret_key == 'original'
        assert config.port == 8000
    
    def test_reset_config_function(self):
        """Test global reset_config function"""
        load_config_from_dict({'secret_key': 'to-be-reset'})
        
        # Verify config is loaded
        config = get_config()
        assert config.secret_key == 'to-be-reset'
        
        # Reset configuration
        reset_config()
        
        # Should raise error after reset
        with pytest.raises(ConfigError, match="Configuration not loaded"):
            get_config()


class TestBackwardCompatibility:
    """Test backward compatibility with old config.py"""
    
    def setup_method(self):
        """Setup configuration for compatibility tests"""
        reset_config()
        load_config_from_dict({
            'secret_key': 'compat-secret',
            'prompts_file': 'test-prompts.yaml',
            'max_players_per_room': 10,
            'response_time_limit': 200,
            'guessing_time_limit': 100,
            'results_display_time': 45
        })
    


if __name__ == '__main__':
    pytest.main([__file__])