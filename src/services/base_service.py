"""
Base Service - Common patterns and utilities for service classes

Provides:
- Consistent logging setup
- Configuration access
- Common error handling patterns
- Service lifecycle management
- Standard initialization patterns
"""

import logging
import os
from typing import Dict, Any, Optional
from config_factory import get_config, AppConfig
from abc import ABC, abstractmethod


class BaseService(ABC):
    """
    Base class for all services providing common functionality.
    
    Features:
    - Automatic logger setup with service-specific namespace
    - Configuration access
    - Consistent initialization patterns
    - Error handling utilities
    - Service lifecycle hooks
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize base service.
        
        Args:
            config: Optional service-specific configuration
        """
        # Set up logging with service-specific namespace
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Configuration access
        try:
            self._app_config: Optional[AppConfig] = get_config()
        except Exception:
            # Config not loaded yet - use fallback
            self._app_config = None
        self._service_config = config or {}
        
        # Service state
        self._initialized = False
        self._shutdown = False
        
        # Initialize the service
        self._initialize()
        self._initialized = True
        
        self._logger.debug(f"{self.__class__.__name__} initialized")
    
    @abstractmethod
    def _initialize(self) -> None:
        """
        Initialize service-specific components.
        Subclasses must implement this method.
        """
        pass
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with fallback hierarchy.
        
        Priority:
        1. Service-specific config
        2. Application config
        3. Default value
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        # Check service-specific config first
        if key in self._service_config:
            return self._service_config[key]
        
        # Check app config
        if self._app_config and hasattr(self._app_config, key):
            return getattr(self._app_config, key)
        
        return default
    
    def log_error(self, message: str, exception: Optional[Exception] = None, **context) -> None:
        """
        Log error with consistent format and context.
        
        Args:
            message: Error message
            exception: Optional exception to log
            **context: Additional context for logging
        """
        log_context = {
            'service': self.__class__.__name__,
            **context
        }
        
        if exception:
            self._logger.error(f"{message}: {exception}", extra=log_context, exc_info=True)
        else:
            self._logger.error(message, extra=log_context)
    
    def log_info(self, message: str, **context) -> None:
        """
        Log info message with context.
        
        Args:
            message: Info message
            **context: Additional context for logging
        """
        log_context = {
            'service': self.__class__.__name__,
            **context
        }
        self._logger.info(message, extra=log_context)
    
    def log_debug(self, message: str, **context) -> None:
        """
        Log debug message with context.
        
        Args:
            message: Debug message
            **context: Additional context for logging
        """
        log_context = {
            'service': self.__class__.__name__,
            **context
        }
        self._logger.debug(message, extra=log_context)
    
    def handle_service_error(self, operation: str, exception: Exception, **context) -> None:
        """
        Handle service errors with consistent logging and error tracking.
        
        Args:
            operation: Name of operation that failed
            exception: Exception that occurred
            **context: Additional context for error tracking
        """
        self.log_error(
            f"Service error in {operation}",
            exception=exception,
            operation=operation,
            **context
        )
    
    def is_testing_mode(self) -> bool:
        """
        Check if service is running in testing mode.
        
        Returns:
            True if in testing mode
        """
        # Check environment variable first
        if os.environ.get('TESTING') == '1':
            return True
        
        app_config_testing = False
        if self._app_config and hasattr(self._app_config, 'is_testing'):
            app_config_testing = self._app_config.is_testing
        return bool(self.get_config_value('testing', False) or app_config_testing)
    
    def shutdown(self) -> None:
        """
        Shutdown service and cleanup resources.
        Subclasses can override this method to add cleanup logic.
        """
        if self._shutdown:
            return
        
        self._logger.info(f"Shutting down {self.__class__.__name__}")
        
        try:
            self._cleanup()
        except Exception as e:
            self.log_error("Error during service cleanup", exception=e)
        finally:
            self._shutdown = True
            self._logger.debug(f"{self.__class__.__name__} shutdown complete")
    
    def _cleanup(self) -> None:
        """
        Service-specific cleanup logic.
        Subclasses can override this method to add cleanup.
        Default implementation does nothing.
        """
        pass
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized"""
        return self._initialized
    
    @property
    def is_shutdown(self) -> bool:
        """Check if service is shutdown"""
        return self._shutdown
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(initialized={self._initialized}, shutdown={self._shutdown})"


class ServiceRegistry:
    """
    Registry for managing service instances without global singletons.
    Used by the dependency injection container.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)
    
    def register_service(self, name: str, instance: Any) -> None:
        """
        Register a service instance.
        
        Args:
            name: Service name
            instance: Service instance
        """
        if name in self._services:
            self._logger.warning(f"Replacing existing service: {name}")
        
        self._services[name] = instance
        self._logger.debug(f"Registered service: {name}")
    
    def get_service(self, name: str) -> Optional[Any]:
        """
        Get a service instance by name.
        
        Args:
            name: Service name
            
        Returns:
            Service instance or None if not found
        """
        return self._services.get(name)
    
    def has_service(self, name: str) -> bool:
        """
        Check if service is registered.
        
        Args:
            name: Service name
            
        Returns:
            True if service is registered
        """
        return name in self._services
    
    def remove_service(self, name: str) -> bool:
        """
        Remove a service from registry.
        
        Args:
            name: Service name
            
        Returns:
            True if service was removed, False if not found
        """
        if name in self._services:
            instance = self._services.pop(name)
            
            # Call shutdown if service has the method
            if hasattr(instance, 'shutdown'):
                try:
                    instance.shutdown()
                except Exception as e:
                    self._logger.error(f"Error shutting down service {name}: {e}")
            
            self._logger.debug(f"Removed service: {name}")
            return True
        
        return False
    
    def shutdown_all(self) -> None:
        """Shutdown all registered services"""
        self._logger.info("Shutting down all registered services")
        
        for name, instance in list(self._services.items()):
            try:
                if hasattr(instance, 'shutdown'):
                    instance.shutdown()
            except Exception as e:
                self._logger.error(f"Error shutting down service {name}: {e}")
        
        self._services.clear()
        self._logger.info("All services shutdown complete")
    
    def get_service_names(self) -> list:
        """Get list of registered service names"""
        return list(self._services.keys())
    
    def __repr__(self) -> str:
        return f"ServiceRegistry(services={len(self._services)})"