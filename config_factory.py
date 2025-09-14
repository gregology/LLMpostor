"""
Configuration Factory - Centralized configuration management for LLMpostor
Provides type-safe configuration with validation and environment-specific settings.
"""

import os
import logging
from typing import Any, Dict, Optional, Type
from enum import Enum
from dataclasses import dataclass, field


class Environment(Enum):
    """Environment types for configuration"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class ConfigError(Exception):
    """Configuration-related errors"""
    pass


@dataclass
class AppConfig:
    """Application configuration with type safety and validation"""
    
    # Core Flask settings
    secret_key: str = field(default_factory=lambda: 'dev-secret-key-change-in-production')
    debug: bool = False
    flask_env: str = 'development'  # Default to development for safety
    
    # Server settings
    host: str = '0.0.0.0'
    port: int = 5000
    
    # Game settings
    max_players_per_room: int = 8
    response_time_limit: int = 180  # seconds
    guessing_time_limit: int = 120  # seconds
    results_display_time: int = 30  # seconds
    max_response_length: int = 100  # characters
    min_players_required: int = 2  # minimum players to start/continue game
    
    # Auto Game Flow settings
    game_flow_check_interval: int = 1  # seconds between checks
    countdown_broadcast_interval: int = 10  # seconds between countdown updates
    room_status_broadcast_interval: int = 60  # seconds between room status broadcasts
    warning_threshold_seconds: int = 30  # seconds for first warning
    final_warning_threshold_seconds: int = 10  # seconds for final warning
    room_cleanup_inactive_minutes: int = 60  # minutes before cleaning up inactive rooms
    
    # Rate Limiting settings
    max_events_per_client_queue: int = 50  # max events in client queue
    max_events_rate_tracking: int = 100  # max events for rate tracking
    max_global_events_tracking: int = 1000  # max global events to track
    max_events_per_second: int = 10  # max events per client per second
    max_events_per_minute: int = 100  # max events per client per minute
    rate_limit_window_seconds: int = 60  # time window for rate calculations
    request_dedup_window_seconds: float = 1.0  # request deduplication window in seconds
    
    # Broadcast settings
    compression_threshold_bytes: int = 512  # compress payloads larger than this
    
    # File paths
    prompts_file: str = 'prompts.yaml'
    
    # Gunicorn settings (for production deployment)
    worker_connections: int = 1000
    timeout: int = 30
    keepalive: int = 2
    log_level: str = 'info'
    
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate()
    
    def _validate(self):
        """Validate configuration values"""
        if self.port < 1 or self.port > 65535:
            raise ConfigError(f"Invalid port number: {self.port}")
        
        if self.max_players_per_room < 1 or self.max_players_per_room > 50:
            raise ConfigError(f"Invalid max_players_per_room: {self.max_players_per_room}")
        
        if self.response_time_limit < 10 or self.response_time_limit > 1800:  # 10s to 30min
            raise ConfigError(f"Invalid response_time_limit: {self.response_time_limit}")
        
        if self.guessing_time_limit < 10 or self.guessing_time_limit > 1800:
            raise ConfigError(f"Invalid guessing_time_limit: {self.guessing_time_limit}")
        
        if self.max_response_length < 10 or self.max_response_length > 1000:
            raise ConfigError(f"Invalid max_response_length: {self.max_response_length}")
        
        if self.min_players_required < 1 or self.min_players_required > self.max_players_per_room:
            raise ConfigError(f"Invalid min_players_required: {self.min_players_required}")
        
        # Auto Game Flow validations
        if self.game_flow_check_interval < 1 or self.game_flow_check_interval > 60:
            raise ConfigError(f"Invalid game_flow_check_interval: {self.game_flow_check_interval}")
        
        if self.countdown_broadcast_interval < 1 or self.countdown_broadcast_interval > 300:
            raise ConfigError(f"Invalid countdown_broadcast_interval: {self.countdown_broadcast_interval}")
        
        if self.warning_threshold_seconds < 1 or self.warning_threshold_seconds > 300:
            raise ConfigError(f"Invalid warning_threshold_seconds: {self.warning_threshold_seconds}")
        
        if self.final_warning_threshold_seconds < 1 or self.final_warning_threshold_seconds >= self.warning_threshold_seconds:
            raise ConfigError(f"Invalid final_warning_threshold_seconds: {self.final_warning_threshold_seconds}")
        
        # Rate Limiting validations
        if self.max_events_per_client_queue < 1 or self.max_events_per_client_queue > 1000:
            raise ConfigError(f"Invalid max_events_per_client_queue: {self.max_events_per_client_queue}")
        
        if self.max_events_per_second < 1 or self.max_events_per_second > 1000:
            raise ConfigError(f"Invalid max_events_per_second: {self.max_events_per_second}")
        
        if self.max_events_per_minute < self.max_events_per_second or self.max_events_per_minute > 10000:
            raise ConfigError(f"Invalid max_events_per_minute: {self.max_events_per_minute}")
         
        if self.environment == Environment.PRODUCTION and self.secret_key == 'dev-secret-key-change-in-production':
            raise ConfigError("Production environment requires a secure SECRET_KEY")
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode"""
        return self.environment == Environment.TESTING


class ConfigurationFactory:
    """
    Factory for creating and managing application configuration.
    
    Features:
    - Environment variable loading with type conversion
    - Configuration validation
    - Environment-specific defaults
    - Singleton pattern for global config access
    """
    
    _instance: Optional['ConfigurationFactory'] = None
    _config: Optional[AppConfig] = None
    
    def __new__(cls) -> 'ConfigurationFactory':
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration factory"""
        if not hasattr(self, '_initialized'):
            self._logger = logging.getLogger(__name__)
            self._env_overrides: Dict[str, Any] = {}
            self._initialized = True
    
    def load_from_environment(self, env_prefix: str = '') -> AppConfig:
        """
        Load configuration from environment variables.
        
        Args:
            env_prefix: Optional prefix for environment variables (e.g., 'LLMPOSTOR_')
            
        Returns:
            Configured AppConfig instance
        """
        def get_env_var(key: str, default: Any = None, var_type: Type = str) -> Any:
            """Get environment variable with type conversion"""
            env_key = f"{env_prefix}{key}" if env_prefix else key
            value = os.environ.get(env_key)
            
            if value is None:
                return default
            
            # Type conversion
            if var_type == bool:
                return value.lower() in ('true', '1', 'yes', 'on')
            elif var_type == int:
                try:
                    return int(value)
                except ValueError:
                    self._logger.warning(f"Invalid integer value for {env_key}: {value}, using default: {default}")
                    return default
            elif var_type == float:
                try:
                    return float(value)
                except ValueError:
                    self._logger.warning(f"Invalid float value for {env_key}: {value}, using default: {default}")
                    return default
            else:
                return value
        
        # Determine environment
        flask_env = get_env_var('FLASK_ENV', 'development')  # Default to development for safety
        if flask_env == 'development':
            environment = Environment.DEVELOPMENT
            debug = True
        elif flask_env == 'testing':
            environment = Environment.TESTING
            debug = True
        else:
            environment = Environment.PRODUCTION
            debug = False
        
        # Load all configuration values
        config = AppConfig(
            # Core Flask settings
            secret_key=get_env_var('SECRET_KEY', 'dev-secret-key-change-in-production'),
            debug=get_env_var('DEBUG', debug, bool),
            flask_env=flask_env,
            
            # Server settings
            host=get_env_var('HOST', '0.0.0.0'),
            port=get_env_var('PORT', 5000, int),
            
            # Game settings
            max_players_per_room=get_env_var('MAX_PLAYERS_PER_ROOM', 8, int),
            response_time_limit=get_env_var('RESPONSE_TIME_LIMIT', 180, int),
            guessing_time_limit=get_env_var('GUESSING_TIME_LIMIT', 120, int),
            results_display_time=get_env_var('RESULTS_DISPLAY_TIME', 30, int),
            max_response_length=get_env_var('MAX_RESPONSE_LENGTH', 100, int),
            min_players_required=get_env_var('MIN_PLAYERS_REQUIRED', 2, int),
            
            # Auto Game Flow settings
            game_flow_check_interval=get_env_var('GAME_FLOW_CHECK_INTERVAL', 1, int),
            countdown_broadcast_interval=get_env_var('COUNTDOWN_BROADCAST_INTERVAL', 10, int),
            room_status_broadcast_interval=get_env_var('ROOM_STATUS_BROADCAST_INTERVAL', 60, int),
            warning_threshold_seconds=get_env_var('WARNING_THRESHOLD_SECONDS', 30, int),
            final_warning_threshold_seconds=get_env_var('FINAL_WARNING_THRESHOLD_SECONDS', 10, int),
            room_cleanup_inactive_minutes=get_env_var('ROOM_CLEANUP_INACTIVE_MINUTES', 60, int),
            
            # Rate Limiting settings
            max_events_per_client_queue=get_env_var('MAX_EVENTS_PER_CLIENT_QUEUE', 50, int),
            max_events_rate_tracking=get_env_var('MAX_EVENTS_RATE_TRACKING', 100, int),
            max_global_events_tracking=get_env_var('MAX_GLOBAL_EVENTS_TRACKING', 1000, int),
            max_events_per_second=get_env_var('MAX_EVENTS_PER_SECOND', 10, int),
            max_events_per_minute=get_env_var('MAX_EVENTS_PER_MINUTE', 100, int),
            rate_limit_window_seconds=get_env_var('RATE_LIMIT_WINDOW_SECONDS', 60, int),
            request_dedup_window_seconds=get_env_var('REQUEST_DEDUP_WINDOW_SECONDS', 1.0, float),
            
            # Broadcast settings
            compression_threshold_bytes=get_env_var('COMPRESSION_THRESHOLD_BYTES', 512, int),

            # File paths
            prompts_file=get_env_var('PROMPTS_FILE', 'prompts.yaml'),
            
            # Gunicorn settings
            worker_connections=get_env_var('WORKER_CONNECTIONS', 1000, int),
            timeout=get_env_var('TIMEOUT', 30, int),
            keepalive=get_env_var('KEEPALIVE', 2, int),
            log_level=get_env_var('LOG_LEVEL', 'info'),
            
            # Environment
            environment=environment
        )
        
        # Apply any manual overrides
        for key, value in self._env_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        self._config = config
        self._logger.info(f"Configuration loaded for environment: {environment.value}")
        return config
    
    def load_from_dict(self, config_dict: Dict[str, Any]) -> AppConfig:
        """
        Load configuration from dictionary (useful for testing).
        
        Args:
            config_dict: Dictionary of configuration values
            
        Returns:
            Configured AppConfig instance
        """
        # Convert environment string to enum if provided
        if 'environment' in config_dict and isinstance(config_dict['environment'], str):
            config_dict['environment'] = Environment(config_dict['environment'])
        
        self._config = AppConfig(**config_dict)
        return self._config
    
    def override_setting(self, key: str, value: Any) -> 'ConfigurationFactory':
        """
        Override a specific configuration setting.
        
        Args:
            key: Configuration key to override
            value: New value for the setting
            
        Returns:
            Self for method chaining
        """
        self._env_overrides[key] = value
        
        # Update current config if loaded
        if self._config and hasattr(self._config, key):
            setattr(self._config, key, value)
            self._config._validate()  # Re-validate after change
        
        return self
    
    def get_config(self) -> AppConfig:
        """
        Get the current configuration.
        
        Returns:
            Current AppConfig instance
            
        Raises:
            ConfigError: If no configuration has been loaded
        """
        if self._config is None:
            raise ConfigError("Configuration not loaded. Call load_from_environment() or load_from_dict() first.")
        return self._config
    
    def reset(self) -> 'ConfigurationFactory':
        """Reset the factory (useful for testing)"""
        self._config = None
        self._env_overrides.clear()
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert current configuration to dictionary"""
        if self._config is None:
            raise ConfigError("Configuration not loaded")
        
        config_dict = {}
        for field_info in self._config.__dataclass_fields__.values():
            value = getattr(self._config, field_info.name)
            if isinstance(value, Environment):
                config_dict[field_info.name] = value.value
            else:
                config_dict[field_info.name] = value
        
        return config_dict
    
    def get_flask_config(self) -> Dict[str, Any]:
        """
        Get Flask-compatible configuration dictionary.
        
        Returns:
            Dictionary suitable for Flask app.config.update()
        """
        if self._config is None:
            raise ConfigError("Configuration not loaded")
        
        return {
            'SECRET_KEY': self._config.secret_key,
            'DEBUG': self._config.debug,
            'ENV': self._config.flask_env,
            'MAX_PLAYERS_PER_ROOM': self._config.max_players_per_room,
            'RESPONSE_TIME_LIMIT': self._config.response_time_limit,
            'GUESSING_TIME_LIMIT': self._config.guessing_time_limit,
            'RESULTS_DISPLAY_TIME': self._config.results_display_time,
            'MAX_RESPONSE_LENGTH': self._config.max_response_length,
            'MIN_PLAYERS_REQUIRED': self._config.min_players_required,
            'PROMPTS_FILE': self._config.prompts_file,
        }


# Global factory instance
_config_factory = ConfigurationFactory()


def get_config() -> AppConfig:
    """Get the global application configuration"""
    return _config_factory.get_config()


def load_config(env_prefix: str = '') -> AppConfig:
    """Load configuration from environment variables"""
    return _config_factory.load_from_environment(env_prefix)


def load_config_from_dict(config_dict: Dict[str, Any]) -> AppConfig:
    """Load configuration from dictionary"""
    return _config_factory.load_from_dict(config_dict)


def override_config(key: str, value: Any) -> ConfigurationFactory:
    """Override a configuration setting"""
    return _config_factory.override_setting(key, value)


def reset_config() -> ConfigurationFactory:
    """Reset configuration (for testing)"""
    return _config_factory.reset()


