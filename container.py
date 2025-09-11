"""
Service Container - Dependency Injection Container for LLMpostor
Manages service creation, dependencies, and lifecycle.
"""

from typing import Dict, Any, List, Optional, Callable, Type
import inspect
from enum import Enum


class ServiceLifecycle(Enum):
    """Service lifecycle management options"""
    SINGLETON = "singleton"  # One instance per container
    TRANSIENT = "transient"  # New instance every time


class ServiceDefinition:
    """Definition of how a service should be created"""
    
    def __init__(
        self, 
        name: str,
        factory: Callable,
        dependencies: List[str] = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        config: Dict[str, Any] = None
    ):
        self.name = name
        self.factory = factory
        self.dependencies = dependencies or []
        self.lifecycle = lifecycle
        self.config = config or {}


class CircularDependencyError(Exception):
    """Raised when circular dependency is detected"""
    pass


class ServiceNotFoundError(Exception):
    """Raised when requested service is not registered"""
    pass


class ServiceContainer:
    """
    Dependency Injection Container for managing services and their dependencies.
    
    Features:
    - Automatic dependency resolution
    - Circular dependency detection
    - Singleton and transient lifecycle management
    - Configuration injection
    - Service discovery and validation
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceDefinition] = {}
        self._instances: Dict[str, Any] = {}
        self._creating: set = set()  # Track services being created (circular detection)
        self._config: Dict[str, Any] = {}
    
    def register(
        self,
        name: str,
        factory: Callable,
        dependencies: List[str] = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        config: Dict[str, Any] = None
    ) -> 'ServiceContainer':
        """
        Register a service with the container.
        
        Args:
            name: Service name for retrieval
            factory: Class or function to create the service
            dependencies: List of service names this service depends on
            lifecycle: How the service instance should be managed
            config: Additional configuration for the service
            
        Returns:
            Self for method chaining
        """
        if name in self._services:
            raise ValueError(f"Service '{name}' is already registered")
        
        # Validate factory is callable
        if not callable(factory):
            raise ValueError(f"Factory for '{name}' must be callable")
        
        # Auto-detect dependencies from constructor signature if not provided
        if dependencies is None:
            dependencies = self._auto_detect_dependencies(factory)
        
        service_def = ServiceDefinition(
            name=name,
            factory=factory,
            dependencies=dependencies,
            lifecycle=lifecycle,
            config=config
        )
        
        self._services[name] = service_def
        return self
    
    def _auto_detect_dependencies(self, factory: Callable) -> List[str]:
        """
        Auto-detect dependencies from constructor signature.
        This is a basic implementation that looks for parameter names.
        For LLMpostor, we'll disable auto-detection to avoid issues with string types.
        """
        # Disable auto-detection for now to avoid issues with string parameters
        # Dependencies should be explicitly specified during registration
        return []
    
    def configure_services(self) -> 'ServiceContainer':
        """
        Register all LLMpostor services with their dependencies.
        This method contains the service configuration for the application.
        """
        from src.room_manager import RoomManager
        from src.game_manager import GameManager
        from src.content_manager import ContentManager
        from src.error_handler import ErrorHandler
        from src.services.validation_service import ValidationService
        from src.services.error_response_factory import ErrorResponseFactory
        from src.services.session_service import SessionService
        from src.services.broadcast_service import BroadcastService
        from src.services.auto_game_flow_service import AutoGameFlowService
        
        # Configuration Factory (highest priority - no dependencies)
        from config_factory import ConfigurationFactory
        self.register('ConfigurationFactory', ConfigurationFactory)
        
        # Validation and error handling services - no dependencies
        self.register('ValidationService', ValidationService)
        self.register('ErrorResponseFactory', ErrorResponseFactory)
        
        # Core managers - no dependencies (ErrorHandler now wraps the new services)
        self.register('RoomManager', RoomManager)
        self.register('ContentManager', ContentManager)
        self.register('ErrorHandler', ErrorHandler)
        self.register('SessionService', SessionService)
        
        # Game manager - depends on room manager
        self.register('GameManager', GameManager, dependencies=['RoomManager'])
        
        # Broadcast service - depends on socketio, room_manager, game_manager, error_handler
        # Note: socketio will be injected as external dependency
        self.register('BroadcastService', BroadcastService, dependencies=['socketio', 'RoomManager', 'GameManager', 'ErrorHandler'])
        
        # Auto game flow - depends on broadcast_service, game_manager, room_manager
        self.register('AutoGameFlowService', AutoGameFlowService, dependencies=['BroadcastService', 'GameManager', 'RoomManager'])
        
        return self
    
    def set_external_dependency(self, name: str, instance: Any) -> 'ServiceContainer':
        """
        Set an external dependency that's created outside the container.
        Useful for Flask-SocketIO and similar framework objects.
        """
        self._instances[name] = instance
        return self
    
    def set_config(self, config: Dict[str, Any]) -> 'ServiceContainer':
        """Set global configuration for the container"""
        self._config.update(config)
        return self
    
    def get(self, name: str) -> Any:
        """
        Get a service instance, creating it if necessary.
        
        Args:
            name: Service name to retrieve
            
        Returns:
            Service instance
            
        Raises:
            ServiceNotFoundError: If service is not registered
            CircularDependencyError: If circular dependency detected
        """
        # Check for external dependency first
        if name in self._instances:
            return self._instances[name]
        
        if name not in self._services:
            raise ServiceNotFoundError(f"Service '{name}' is not registered")
        
        service_def = self._services[name]
        
        # Check for singleton instance
        if service_def.lifecycle == ServiceLifecycle.SINGLETON and name in self._instances:
            return self._instances[name]
        
        # Create new instance
        return self._create_service(name)
    
    def _create_service(self, name: str) -> Any:
        """
        Create a service instance with dependency injection.
        """
        if name in self._creating:
            cycle = ' -> '.join(list(self._creating) + [name])
            raise CircularDependencyError(f"Circular dependency detected: {cycle}")
        
        if name in self._instances:
            return self._instances[name]
        
        self._creating.add(name)
        
        try:
            service_def = self._services[name]
            
            # Resolve dependencies
            dependencies = []
            for dep_name in service_def.dependencies:
                dep_instance = self.get(dep_name)
                dependencies.append(dep_instance)
            
            # Create service instance
            if inspect.isclass(service_def.factory):
                # Constructor call
                if service_def.dependencies:
                    instance = service_def.factory(*dependencies)
                else:
                    instance = service_def.factory()
            else:
                # Function call
                instance = service_def.factory(*dependencies, **service_def.config)
            
            # Store singleton instances
            if service_def.lifecycle == ServiceLifecycle.SINGLETON:
                self._instances[name] = instance
            
            return instance
            
        finally:
            self._creating.discard(name)
    
    def has_service(self, name: str) -> bool:
        """Check if a service is registered"""
        return name in self._services
    
    def get_service_names(self) -> List[str]:
        """Get list of all registered service names"""
        return list(self._services.keys())
    
    def validate_dependencies(self) -> Dict[str, List[str]]:
        """
        Validate all service dependencies can be resolved.
        
        Returns:
            Dictionary mapping service names to lists of missing dependencies
        """
        issues = {}
        
        for name, service_def in self._services.items():
            missing_deps = []
            for dep in service_def.dependencies:
                if not self.has_service(dep) and dep not in self._instances:
                    missing_deps.append(dep)
            
            if missing_deps:
                issues[name] = missing_deps
        
        return issues
    
    def clear(self) -> 'ServiceContainer':
        """Clear all services and instances (useful for testing)"""
        self._services.clear()
        self._instances.clear()
        self._creating.clear()
        self._config.clear()
        return self
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the dependency graph for visualization/debugging"""
        return {name: service_def.dependencies for name, service_def in self._services.items()}
    
    def __repr__(self) -> str:
        return f"ServiceContainer(services={len(self._services)}, instances={len(self._instances)})"


# Global container instance for the application
_app_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global application service container"""
    global _app_container
    if _app_container is None:
        _app_container = ServiceContainer()
    return _app_container


def configure_container(socketio=None, config=None) -> ServiceContainer:
    """
    Configure the global service container with LLMpostor services.
    
    Args:
        socketio: Flask-SocketIO instance
        config: Application configuration
        
    Returns:
        Configured service container
    """
    container = get_container()
    container.clear()  # Clear any existing configuration
    
    # Set external dependencies
    if socketio is not None:
        container.set_external_dependency('socketio', socketio)
    
    if config is not None:
        container.set_config(config)
    
    # Configure all services
    container.configure_services()
    
    return container