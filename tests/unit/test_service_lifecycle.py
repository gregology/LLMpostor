"""
Tests for service lifecycle management and BaseService functionality.

Tests:
- BaseService initialization and lifecycle
- Service dependency injection container
- Optional service gating behind config flags
- Service shutdown and cleanup
- Configuration integration
"""

import pytest
import os
from unittest.mock import Mock, patch
from src.services.base_service import BaseService, ServiceRegistry
# Removed unused service imports: MetricsService, PayloadOptimizer
from container import ServiceContainer, ServiceLifecycle
from config_factory import load_config, reset_config


class MockTestService(BaseService):
    """Mock test service implementation for testing BaseService functionality"""
    
    def __init__(self, config=None):
        self.initialization_called = False
        self.cleanup_called = False
        super().__init__(config)  # Call super after setting up instance vars
    
    def _initialize(self):
        self.initialization_called = True
        self.test_value = self.get_config_value('test_value', 'default')
    
    def _cleanup(self):
        self.cleanup_called = True


class TestBaseService:
    """Test BaseService abstract base class"""
    
    def test_base_service_initialization(self):
        """Test BaseService initialization"""
        service = MockTestService({'test_value': 'custom'})
        
        assert service.is_initialized
        assert not service.is_shutdown
        assert service.initialization_called
        assert service.test_value == 'custom'
    
    def test_config_value_hierarchy(self):
        """Test configuration value hierarchy (service > app > default)"""
        # Load app config
        load_config()
        
        service = MockTestService({'test_value': 'service_config'})
        
        # Service config takes precedence
        assert service.get_config_value('test_value', 'default') == 'service_config'
        
        # App config is used when service config missing
        port_value = service.get_config_value('port', 9999)
        assert port_value == 5000  # From app config
        
        # Default is used when neither has the value
        assert service.get_config_value('nonexistent', 'fallback') == 'fallback'
    
    def test_testing_mode_detection(self):
        """Test testing mode detection"""
        # Set environment variable
        os.environ['TESTING'] = '1'
        
        service = MockTestService()
        assert service.is_testing_mode()
        
        # Clean up
        os.environ.pop('TESTING', None)
    
    def test_logging_methods(self):
        """Test logging methods"""
        service = MockTestService()
        
        with patch.object(service._logger, 'info') as mock_info:
            service.log_info('test message', context='test')
            mock_info.assert_called_once()
        
        with patch.object(service._logger, 'error') as mock_error:
            service.log_error('error message', context='test')
            mock_error.assert_called_once()
        
        with patch.object(service._logger, 'debug') as mock_debug:
            service.log_debug('debug message', context='test')
            mock_debug.assert_called_once()
    
    def test_service_shutdown(self):
        """Test service shutdown and cleanup"""
        service = MockTestService()
        
        assert not service.is_shutdown
        assert not service.cleanup_called
        
        service.shutdown()
        
        assert service.is_shutdown
        assert service.cleanup_called
        
        # Shutdown should be idempotent
        service.shutdown()
        assert service.is_shutdown
    
    def test_error_handling(self):
        """Test service error handling"""
        service = MockTestService()
        
        with patch.object(service, 'log_error') as mock_log_error:
            exception = ValueError('test error')
            service.handle_service_error('test_operation', exception, context='test')
            mock_log_error.assert_called_once()


class TestServiceRegistry:
    """Test ServiceRegistry functionality"""
    
    def test_service_registration(self):
        """Test service registration and retrieval"""
        registry = ServiceRegistry()
        service = MockTestService()
        
        registry.register_service('test_service', service)
        
        assert registry.has_service('test_service')
        assert registry.get_service('test_service') is service
        assert 'test_service' in registry.get_service_names()
    
    def test_service_replacement(self):
        """Test service replacement with warning"""
        registry = ServiceRegistry()
        service1 = MockTestService()
        service2 = MockTestService()
        
        registry.register_service('test_service', service1)
        
        with patch.object(registry._logger, 'warning') as mock_warning:
            registry.register_service('test_service', service2)
            mock_warning.assert_called_once()
        
        assert registry.get_service('test_service') is service2
    
    def test_service_removal(self):
        """Test service removal and shutdown"""
        registry = ServiceRegistry()
        service = MockTestService()
        
        registry.register_service('test_service', service)
        
        removed = registry.remove_service('test_service')
        assert removed
        assert not registry.has_service('test_service')
        assert service.is_shutdown
        
        # Removing non-existent service should return False
        assert not registry.remove_service('nonexistent')
    
    def test_shutdown_all(self):
        """Test shutting down all services"""
        registry = ServiceRegistry()
        service1 = MockTestService()
        service2 = MockTestService()
        
        registry.register_service('service1', service1)
        registry.register_service('service2', service2)
        
        registry.shutdown_all()
        
        assert service1.is_shutdown
        assert service2.is_shutdown
        assert len(registry.get_service_names()) == 0


# Removed test classes for deleted services: TestCacheServiceLifecycle, TestMetricsServiceLifecycle, TestPayloadOptimizerLifecycle


class TestServiceContainer:
    """Test ServiceContainer functionality"""
    
    def setup_method(self):
        """Set up each test method"""
        reset_config()
        load_config()
    
    def test_service_container_configuration(self):
        """Test service container configuration"""
        container = ServiceContainer()
        container.configure_services()
        
        # Core services should always be registered
        assert container.has_service('ConfigurationFactory')
        assert container.has_service('ValidationService')
        assert container.has_service('ErrorResponseFactory')
        assert container.has_service('RoomManager')
        assert container.has_service('ContentManager')
        assert container.has_service('ErrorResponseFactory')
        assert container.has_service('SessionService')
        
        # Game logic services
        assert container.has_service('GameManager')
        assert container.has_service('BroadcastService')
        assert container.has_service('AutoGameFlowService')
    
    def test_optional_services_gated_by_config(self):
        """Test that optional services are properly gated by configuration"""
        container = ServiceContainer()
        container.configure_services()
        
        # These services have been removed from the codebase entirely
        assert not container.has_service('MetricsService')
        assert not container.has_service('PayloadOptimizer')
        assert not container.has_service('DatabaseOptimizer')
    
    
    def test_dependency_resolution(self):
        """Test service dependency resolution"""
        container = ServiceContainer()
        container.configure_services()
        
        # GameManager depends on RoomManager
        game_manager = container.get('GameManager')
        assert game_manager is not None
        
        # Should be singleton
        game_manager2 = container.get('GameManager')
        assert game_manager is game_manager2
    
    def test_external_dependency_injection(self):
        """Test external dependency injection"""
        container = ServiceContainer()
        mock_socketio = Mock()
        
        container.set_external_dependency('socketio', mock_socketio)
        container.configure_services()
        
        # BroadcastService should get the mock socketio
        broadcast_service = container.get('BroadcastService')
        assert broadcast_service.socketio is mock_socketio
    
    def test_container_validation(self):
        """Test container dependency validation"""
        container = ServiceContainer()
        container.configure_services()
        
        # Should have no missing dependencies
        issues = container.validate_dependencies()
        # BroadcastService requires socketio which is not set, so there should be 1 issue
        assert 'BroadcastService' in issues
        assert 'socketio' in issues['BroadcastService']
    
    def test_container_clear(self):
        """Test container clearing"""
        container = ServiceContainer()
        container.configure_services()
        
        assert len(container.get_service_names()) > 0
        
        container.clear()
        
        assert len(container.get_service_names()) == 0


class TestServiceIntegration:
    """Integration tests for service lifecycle"""
    
    def setup_method(self):
        """Set up each test method"""
        reset_config()
        load_config()
    
    def test_end_to_end_service_lifecycle(self):
        """Test complete service lifecycle from container to shutdown"""
        container = ServiceContainer()
        container.configure_services()
        
        # Get a service
        validation_service = container.get('ValidationService')
        assert validation_service is not None

        # Use the service
        validated_room_id = validation_service.validate_room_id('test123')
        assert validated_room_id == 'test123'

        # Container can be cleared
        container.clear()
        assert len(container._instances) == 0
    
    def test_service_configuration_integration(self):
        """Test service integration with configuration"""
        # Load config with custom values
        custom_config = {
            'cache_max_memory_bytes': 2 * 1024 * 1024,  # 2MB
            'cache_default_ttl_seconds': 1800  # 30 minutes
        }
        
        from config_factory import load_config_from_dict
        load_config_from_dict(custom_config)
        
        # Service initialization works with custom config
        from src.services.validation_service import ValidationService
        service = ValidationService()

        # Should be functional
        assert service is not None
        assert hasattr(service, 'validate_room_id')
    
    def test_service_graceful_degradation(self):
        """Test services handle missing dependencies gracefully"""
        # Test without loading config first
        reset_config()
        
        # Services should still initialize with fallback values
        from src.services.validation_service import ValidationService
        service = ValidationService()
        assert service is not None
        assert hasattr(service, 'validate_room_id')