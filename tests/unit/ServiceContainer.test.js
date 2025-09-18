/**
 * ServiceContainer Tests
 *
 * Tests for dependency injection container functionality including:
 * - Service registration and retrieval
 * - Dependency injection and resolution
 * - Singleton lifecycle management
 * - Circular dependency detection
 * - Service health checking
 * - Configuration management
 * - Error handling and cleanup
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ServiceContainer } from '../../static/js/utils/ServiceContainer.js';
import { setupGlobalEnvironment } from '../helpers/domMocks.js';

describe('ServiceContainer', () => {
  let container;
  let mockConsole;

  beforeEach(() => {
    setupGlobalEnvironment();

    // Mock console methods
    mockConsole = {
      log: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn()
    };
    vi.stubGlobal('console', mockConsole);

    container = new ServiceContainer();
  });

  afterEach(() => {
    if (container) {
      container.clear();
    }
    vi.restoreAllMocks();
  });

  describe('Constructor and Initialization', () => {
    it('should initialize with empty collections', () => {
      expect(container.services).toBeInstanceOf(Map);
      expect(container.singletons).toBeInstanceOf(Map);
      expect(container.config).toBeInstanceOf(Map);
      expect(container.initializing).toBeInstanceOf(Set);
      expect(container.debugMode).toBe(false);
    });

    it('should log initialization message', () => {
      new ServiceContainer();
      expect(mockConsole.log).toHaveBeenCalledWith('ServiceContainer initialized');
    });
  });

  describe('Service Registration', () => {
    it('should register a basic service', () => {
      const factory = () => ({ name: 'test' });

      container.register('testService', factory);

      expect(container.has('testService')).toBe(true);
      expect(container.getServiceNames()).toContain('testService');
    });

    it('should register service with options', () => {
      const factory = () => ({ name: 'test' });
      const options = {
        singleton: false,
        dependencies: ['dep1', 'dep2']
      };

      const result = container.register('testService', factory, options);

      expect(result).toBe(container); // Should return container for chaining
      expect(container.has('testService')).toBe(true);
    });

    it('should default to singleton mode', () => {
      const factory = () => ({ name: 'test' });

      container.register('testService', factory);

      const serviceConfig = container.services.get('testService');
      expect(serviceConfig.singleton).toBe(true);
    });

    it('should respect singleton: false option', () => {
      const factory = () => ({ name: 'test' });

      container.register('testService', factory, { singleton: false });

      const serviceConfig = container.services.get('testService');
      expect(serviceConfig.singleton).toBe(false);
    });

    it('should throw error for invalid service name', () => {
      const factory = () => ({ name: 'test' });

      expect(() => container.register('', factory)).toThrow('Service name must be a non-empty string');
      expect(() => container.register(null, factory)).toThrow('Service name must be a non-empty string');
      expect(() => container.register(123, factory)).toThrow('Service name must be a non-empty string');
    });

    it('should throw error for invalid factory', () => {
      expect(() => container.register('test', null)).toThrow('Service factory must be a function');
      expect(() => container.register('test', 'not-a-function')).toThrow('Service factory must be a function');
      expect(() => container.register('test', 123)).toThrow('Service factory must be a function');
    });

    it('should log registration in debug mode', () => {
      container.setDebugMode(true);
      const factory = () => ({ name: 'test' });

      container.register('testService', factory);

      expect(mockConsole.log).toHaveBeenCalledWith("ServiceContainer: Registered 'testService' service");
    });
  });

  describe('Service Retrieval', () => {
    it('should retrieve registered service', () => {
      const expectedInstance = { name: 'test', value: 42 };
      const factory = () => expectedInstance;

      container.register('testService', factory);
      const instance = container.get('testService');

      expect(instance).toBe(expectedInstance);
    });

    it('should throw error for unregistered service', () => {
      expect(() => container.get('nonexistent')).toThrow("Service 'nonexistent' is not registered");
    });

    it('should return same instance for singleton services', () => {
      const factory = () => ({ id: Math.random() });

      container.register('singletonService', factory);

      const instance1 = container.get('singletonService');
      const instance2 = container.get('singletonService');

      expect(instance1).toBe(instance2);
    });

    it('should return different instances for non-singleton services', () => {
      const factory = () => ({ id: Math.random() });

      container.register('nonSingletonService', factory, { singleton: false });

      const instance1 = container.get('nonSingletonService');
      const instance2 = container.get('nonSingletonService');

      expect(instance1).not.toBe(instance2);
    });

    it('should log instance creation in debug mode', () => {
      container.setDebugMode(true);
      const factory = () => ({ name: 'test' });

      container.register('testService', factory);
      container.get('testService');

      expect(mockConsole.log).toHaveBeenCalledWith("ServiceContainer: Created instance of 'testService'");
    });
  });

  describe('Dependency Injection', () => {
    it('should inject dependencies in correct order', () => {
      const depFactory = () => ({ name: 'dependency' });
      const mainFactory = (dep) => ({ dependency: dep, name: 'main' });

      container.register('dependency', depFactory);
      container.register('mainService', mainFactory, { dependencies: ['dependency'] });

      const instance = container.get('mainService');

      expect(instance.dependency).toEqual({ name: 'dependency' });
      expect(instance.name).toBe('main');
    });

    it('should inject multiple dependencies', () => {
      const dep1Factory = () => ({ name: 'dep1' });
      const dep2Factory = () => ({ name: 'dep2' });
      const mainFactory = (dep1, dep2) => ({ dep1, dep2, name: 'main' });

      container.register('dep1', dep1Factory);
      container.register('dep2', dep2Factory);
      container.register('mainService', mainFactory, { dependencies: ['dep1', 'dep2'] });

      const instance = container.get('mainService');

      expect(instance.dep1).toEqual({ name: 'dep1' });
      expect(instance.dep2).toEqual({ name: 'dep2' });
    });

    it('should pass container as last parameter', () => {
      const factory = (containerParam) => ({ container: containerParam });

      container.register('serviceWithContainer', factory);

      const instance = container.get('serviceWithContainer');

      expect(instance.container).toBe(container);
    });

    it('should throw error for missing dependency', () => {
      const mainFactory = (dep) => ({ dependency: dep });

      container.register('mainService', mainFactory, { dependencies: ['missingDep'] });

      expect(() => container.get('mainService')).toThrow("Dependency 'missingDep' for service 'mainService' is not registered");
    });

    it('should handle complex dependency chains', () => {
      const level1Factory = () => ({ level: 1 });
      const level2Factory = (dep1) => ({ level: 2, dep: dep1 });
      const level3Factory = (dep2) => ({ level: 3, dep: dep2 });

      container.register('level1', level1Factory);
      container.register('level2', level2Factory, { dependencies: ['level1'] });
      container.register('level3', level3Factory, { dependencies: ['level2'] });

      const instance = container.get('level3');

      expect(instance.level).toBe(3);
      expect(instance.dep.level).toBe(2);
      expect(instance.dep.dep.level).toBe(1);
    });
  });

  describe('Circular Dependency Detection', () => {
    it('should detect direct circular dependency', () => {
      const factory1 = (dep) => ({ name: 'service1', dep });
      const factory2 = (dep) => ({ name: 'service2', dep });

      container.register('service1', factory1, { dependencies: ['service2'] });
      container.register('service2', factory2, { dependencies: ['service1'] });

      expect(() => container.get('service1')).toThrow("Circular dependency detected for service 'service1'");
    });

    it('should detect indirect circular dependency', () => {
      const factory1 = (dep) => ({ name: 'service1', dep });
      const factory2 = (dep) => ({ name: 'service2', dep });
      const factory3 = (dep) => ({ name: 'service3', dep });

      container.register('service1', factory1, { dependencies: ['service2'] });
      container.register('service2', factory2, { dependencies: ['service3'] });
      container.register('service3', factory3, { dependencies: ['service1'] });

      expect(() => container.get('service1')).toThrow("Circular dependency detected for service 'service1'");
    });

    it('should clean up initializing set after error', () => {
      const factory1 = (dep) => ({ name: 'service1', dep });
      const factory2 = (dep) => ({ name: 'service2', dep });

      container.register('service1', factory1, { dependencies: ['service2'] });
      container.register('service2', factory2, { dependencies: ['service1'] });

      try {
        container.get('service1');
      } catch (error) {
        // Expected error
      }

      expect(container.initializing.size).toBe(0);
    });
  });

  describe('Service Management', () => {
    it('should check if service exists', () => {
      const factory = () => ({ name: 'test' });

      expect(container.has('testService')).toBe(false);

      container.register('testService', factory);

      expect(container.has('testService')).toBe(true);
    });

    it('should return all service names', () => {
      const factory = () => ({ name: 'test' });

      container.register('service1', factory);
      container.register('service2', factory);
      container.register('service3', factory);

      const names = container.getServiceNames();

      expect(names).toHaveLength(3);
      expect(names).toContain('service1');
      expect(names).toContain('service2');
      expect(names).toContain('service3');
    });

    it('should remove service and call destroy method', () => {
      const destroyMock = vi.fn();
      const factory = () => ({ name: 'test', destroy: destroyMock });

      container.register('testService', factory);
      container.get('testService'); // Create instance

      container.remove('testService');

      expect(destroyMock).toHaveBeenCalled();
      expect(container.has('testService')).toBe(false);
    });

    it('should handle destroy method errors gracefully', () => {
      const destroyMock = vi.fn(() => { throw new Error('Destroy failed'); });
      const factory = () => ({ name: 'test', destroy: destroyMock });

      container.register('testService', factory);
      container.get('testService'); // Create instance

      expect(() => container.remove('testService')).not.toThrow();
      expect(mockConsole.error).toHaveBeenCalledWith("Error destroying service 'testService':", expect.any(Error));
    });

    it('should log removal in debug mode', () => {
      container.setDebugMode(true);
      const factory = () => ({ name: 'test' });

      container.register('testService', factory);
      container.remove('testService');

      expect(mockConsole.log).toHaveBeenCalledWith("ServiceContainer: Removed 'testService' service");
    });

    it('should clear all services', () => {
      const factory = () => ({ name: 'test' });

      container.register('service1', factory);
      container.register('service2', factory);
      container.setConfig('key', 'value');

      container.clear();

      expect(container.getServiceNames()).toHaveLength(0);
      expect(container.getConfig('key')).toBeUndefined();
      expect(mockConsole.log).toHaveBeenCalledWith('ServiceContainer: All services cleared');
    });
  });

  describe('Configuration Management', () => {
    it('should set and get configuration values', () => {
      const result = container.setConfig('testKey', 'testValue');

      expect(result).toBe(container); // Should return container for chaining
      expect(container.getConfig('testKey')).toBe('testValue');
    });

    it('should return default value for missing config', () => {
      expect(container.getConfig('missingKey', 'defaultValue')).toBe('defaultValue');
    });

    it('should return undefined for missing config without default', () => {
      expect(container.getConfig('missingKey')).toBeUndefined();
    });

    it('should handle null and undefined values', () => {
      container.setConfig('nullKey', null);
      container.setConfig('undefinedKey', undefined);

      // Both null and undefined are treated as nullish by ??, so they return the default value (undefined)
      expect(container.getConfig('nullKey')).toBeUndefined();
      expect(container.getConfig('undefinedKey')).toBeUndefined();

      // To verify the values were actually stored, we can provide explicit defaults
      expect(container.getConfig('nullKey', 'explicit-default')).toBe('explicit-default');
      expect(container.getConfig('undefinedKey', 'explicit-default')).toBe('explicit-default');
    });

    it('should use nullish coalescing for default values', () => {
      container.setConfig('nullKey', null);
      container.setConfig('zeroKey', 0);
      container.setConfig('falseKey', false);
      container.setConfig('emptyStringKey', '');

      expect(container.getConfig('nullKey', 'default')).toBe('default');
      expect(container.getConfig('zeroKey', 'default')).toBe(0);
      expect(container.getConfig('falseKey', 'default')).toBe(false);
      expect(container.getConfig('emptyStringKey', 'default')).toBe('');
    });
  });

  describe('Health Checking', () => {
    it('should return unknown health for unregistered service', () => {
      expect(container.checkHealth('nonexistent')).toBe('unknown');
    });

    it('should return unknown health for uninitialized service', () => {
      const factory = () => ({ name: 'test' });

      container.register('testService', factory);

      expect(container.checkHealth('testService')).toBe('unknown');
    });

    it('should return healthy for basic service without health check', () => {
      const factory = () => ({ name: 'test' });

      container.register('testService', factory);
      container.get('testService'); // Initialize

      expect(container.checkHealth('testService')).toBe('healthy');
    });

    it('should call custom health check method', () => {
      const healthCheckMock = vi.fn(() => true);
      const factory = () => ({ name: 'test', healthCheck: healthCheckMock });

      container.register('testService', factory);
      container.get('testService'); // Initialize

      const health = container.checkHealth('testService');

      expect(healthCheckMock).toHaveBeenCalled();
      expect(health).toBe('healthy');
    });

    it('should handle health check returning false', () => {
      const healthCheckMock = vi.fn(() => false);
      const factory = () => ({ name: 'test', healthCheck: healthCheckMock });

      container.register('testService', factory);
      container.get('testService'); // Initialize

      expect(container.checkHealth('testService')).toBe('unhealthy');
    });

    it('should handle health check throwing error', () => {
      const healthCheckMock = vi.fn(() => { throw new Error('Health check failed'); });
      const factory = () => ({ name: 'test', healthCheck: healthCheckMock });

      container.register('testService', factory);
      container.get('testService'); // Initialize

      expect(container.checkHealth('testService')).toBe('unhealthy');
      expect(mockConsole.error).toHaveBeenCalledWith("Health check failed for service 'testService':", expect.any(Error));
    });

    it('should get health status for all services', () => {
      const factory1 = () => ({ name: 'test1' });
      const factory2 = () => ({ name: 'test2', healthCheck: () => false });

      container.register('service1', factory1, { dependencies: ['dep1'] });
      container.register('service2', factory2);
      container.get('service2'); // Initialize only service2

      const status = container.getHealthStatus();

      expect(status).toHaveProperty('service1');
      expect(status).toHaveProperty('service2');
      expect(status.service1.health).toBe('unknown');
      expect(status.service1.initialized).toBe(false);
      expect(status.service1.singleton).toBe(true);
      expect(status.service1.dependencies).toEqual(['dep1']);
      expect(status.service2.health).toBe('unhealthy');
      expect(status.service2.initialized).toBe(true);
    });
  });

  describe('Debug Mode', () => {
    it('should enable debug mode', () => {
      container.setDebugMode(true);

      expect(container.debugMode).toBe(true);
      expect(mockConsole.log).toHaveBeenCalledWith('ServiceContainer: Debug mode enabled');
    });

    it('should disable debug mode', () => {
      container.setDebugMode(false);

      expect(container.debugMode).toBe(false);
      expect(mockConsole.log).toHaveBeenCalledWith('ServiceContainer: Debug mode disabled');
    });

    it('should handle truthy/falsy values', () => {
      container.setDebugMode('true');
      expect(container.debugMode).toBe(true);

      container.setDebugMode(0);
      expect(container.debugMode).toBe(false);

      container.setDebugMode(1);
      expect(container.debugMode).toBe(true);
    });
  });

  describe('Service Initialization', () => {
    it('should initialize all services', async () => {
      const initMock1 = vi.fn().mockResolvedValue();
      const initMock2 = vi.fn().mockResolvedValue();
      const factory1 = () => ({ name: 'test1', initialize: initMock1 });
      const factory2 = () => ({ name: 'test2', initialize: initMock2 });

      container.register('service1', factory1);
      container.register('service2', factory2);

      await container.initializeAll();

      expect(initMock1).toHaveBeenCalled();
      expect(initMock2).toHaveBeenCalled();
      expect(mockConsole.log).toHaveBeenCalledWith('ServiceContainer: All services initialized');
    });

    it('should handle services without initialize method', async () => {
      const factory = () => ({ name: 'test' });

      container.register('testService', factory);

      await expect(container.initializeAll()).resolves.not.toThrow();
    });

    it('should handle initialization errors', async () => {
      const initMock = vi.fn().mockRejectedValue(new Error('Init failed'));
      const factory = () => ({ name: 'test', initialize: initMock });

      container.register('testService', factory);

      await expect(container.initializeAll()).rejects.toThrow('Init failed');
      expect(mockConsole.error).toHaveBeenCalledWith("Failed to initialize service 'testService':", expect.any(Error));
    });
  });

  describe('Error Handling', () => {
    it('should handle factory errors and update health status', () => {
      const factory = () => { throw new Error('Factory failed'); };

      container.register('testService', factory);

      expect(() => container.get('testService')).toThrow('Factory failed');

      const serviceConfig = container.services.get('testService');
      expect(serviceConfig.health).toBe('unhealthy');
      expect(mockConsole.error).toHaveBeenCalledWith("Failed to create service 'testService':", expect.any(Error));
    });

    it('should clean up initializing state after factory error', () => {
      const factory = () => { throw new Error('Factory failed'); };

      container.register('testService', factory);

      expect(() => container.get('testService')).toThrow();
      expect(container.initializing.has('testService')).toBe(false);
    });

    it('should handle dependency resolution errors', () => {
      const factory = (dep) => ({ dep });

      container.register('testService', factory, { dependencies: ['missingDep'] });

      expect(() => container.get('testService')).toThrow("Dependency 'missingDep' for service 'testService' is not registered");
    });
  });

  describe('Integration Scenarios', () => {
    it('should handle complex service registration and retrieval flow', () => {
      // Register a logger service
      const loggerFactory = () => ({
        log: vi.fn(),
        error: vi.fn()
      });

      // Register a config service
      const configFactory = () => ({
        get: vi.fn((key) => key === 'apiUrl' ? 'https://api.test.com' : null)
      });

      // Register an API service with dependencies
      const apiFactory = (logger, config) => ({
        logger,
        config,
        fetch: vi.fn()
      });

      container.register('logger', loggerFactory);
      container.register('config', configFactory);
      container.register('api', apiFactory, { dependencies: ['logger', 'config'] });

      const api = container.get('api');

      expect(api.logger).toBeDefined();
      expect(api.config).toBeDefined();
      expect(api.logger.log).toBeInstanceOf(Function);
      expect(api.config.get).toBeInstanceOf(Function);
    });

    it('should maintain singleton instances across multiple dependency chains', () => {
      const sharedFactory = () => ({ id: Math.random() });
      const consumer1Factory = (shared) => ({ shared, name: 'consumer1' });
      const consumer2Factory = (shared) => ({ shared, name: 'consumer2' });

      container.register('shared', sharedFactory);
      container.register('consumer1', consumer1Factory, { dependencies: ['shared'] });
      container.register('consumer2', consumer2Factory, { dependencies: ['shared'] });

      const c1 = container.get('consumer1');
      const c2 = container.get('consumer2');

      expect(c1.shared).toBe(c2.shared); // Same instance
    });

    it('should handle service replacement scenario', () => {
      const factory1 = () => ({ version: 1 });
      const factory2 = () => ({ version: 2 });

      container.register('testService', factory1);
      const instance1 = container.get('testService');

      container.remove('testService');
      container.register('testService', factory2);
      const instance2 = container.get('testService');

      expect(instance1.version).toBe(1);
      expect(instance2.version).toBe(2);
    });
  });
});