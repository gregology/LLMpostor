"""
Service Container for Dependency Injection

This module provides a service container that manages service registration,
lifecycle, and dependency resolution for the LLMpostor application.
"""

import logging
from typing import Any, Dict, Optional, Type, Callable

logger = logging.getLogger(__name__)


class ServiceNotRegisteredError(Exception):
    """Raised when attempting to get a service that hasn't been registered."""
    pass


class ServiceContainer:
    """
    A service container for managing dependencies and their lifecycles.

    Supports singleton and transient service lifetimes, and provides
    dependency resolution for handlers and other application components.
    """

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._service_factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._config: Dict[str, Any] = {}

    def register_service(self, name: str, service: Any) -> None:
        """Register a service instance directly."""
        self._services[name] = service
        logger.debug(f"Registered service: {name}")

    def register_singleton(self, name: str, factory: Callable) -> None:
        """Register a service factory that will create a singleton instance."""
        self._service_factories[name] = factory
        logger.debug(f"Registered singleton factory: {name}")

    def register_config(self, name: str, config_value: Any) -> None:
        """Register a configuration value."""
        self._config[name] = config_value
        logger.debug(f"Registered config: {name}")

    def get_service(self, name: str) -> Any:
        """
        Get a service by name.

        Args:
            name: The name of the service to retrieve

        Returns:
            The service instance

        Raises:
            ServiceNotRegisteredError: If the service hasn't been registered
        """
        # Check for direct service registration
        if name in self._services:
            return self._services[name]

        # Check for singleton factory
        if name in self._service_factories:
            if name not in self._singletons:
                logger.debug(f"Creating singleton instance for: {name}")
                self._singletons[name] = self._service_factories[name]()
            return self._singletons[name]

        # Check for config values
        if name in self._config:
            return self._config[name]

        raise ServiceNotRegisteredError(f"Service '{name}' is not registered")

    def get_config(self, name: str) -> Any:
        """Get a configuration value by name."""
        if name in self._config:
            return self._config[name]
        raise ServiceNotRegisteredError(f"Config '{name}' is not registered")

    def has_service(self, name: str) -> bool:
        """Check if a service is registered."""
        return (name in self._services or
                name in self._service_factories or
                name in self._config)

    def get_all_services(self) -> Dict[str, str]:
        """Get a dictionary of all registered service names and their types."""
        services = {}

        # Direct services
        for name, service in self._services.items():
            services[name] = type(service).__name__

        # Singleton factories
        for name in self._service_factories.keys():
            if name in self._singletons:
                services[name] = f"{type(self._singletons[name]).__name__} (singleton)"
            else:
                services[name] = "Not instantiated (singleton factory)"

        # Config values
        for name, value in self._config.items():
            services[name] = f"Config: {type(value).__name__}"

        return services

    def clear(self) -> None:
        """Clear all registered services. Useful for testing."""
        self._services.clear()
        self._service_factories.clear()
        self._singletons.clear()
        self._config.clear()
        logger.debug("Service container cleared")


# Global service container instance
_container = ServiceContainer()


def get_container() -> ServiceContainer:
    """Get the global service container instance."""
    return _container


def register_services(services: Dict[str, Any], config: Dict[str, Any]) -> None:
    """
    Register all services and configuration with the container.

    This is the main entry point for setting up the service container
    with all required services and configuration.

    Args:
        services: Dictionary of service name -> service instance mappings
        config: Dictionary of config name -> config value mappings
    """
    container = get_container()

    # Register all services
    for name, service in services.items():
        container.register_service(name, service)

    # Register all config
    for name, value in config.items():
        container.register_config(name, value)

    logger.info(f"Registered {len(services)} services and {len(config)} config values")