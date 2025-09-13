"""
Container package for dependency injection.
"""

from .service_container import ServiceContainer, get_container, register_services, ServiceNotRegisteredError

__all__ = [
    'ServiceContainer',
    'get_container',
    'register_services',
    'ServiceNotRegisteredError'
]