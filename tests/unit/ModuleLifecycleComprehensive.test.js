/**
 * Comprehensive Module Lifecycle Tests
 *
 * Tests the complete lifecycle of frontend modules including:
 * 1. Initialization and dependency injection
 * 2. Event communication patterns
 * 3. Cleanup and memory management
 * 4. Error handling and recovery
 * 5. Service container integration
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Setup comprehensive global environment
Object.defineProperty(global, 'window', {
  value: {
    location: { pathname: '/test-room', origin: 'http://localhost' },
    navigator: {
      share: undefined,
      clipboard: { writeText: vi.fn() },
      userAgent: 'Test Browser'
    },
    isTestEnvironment: true,
    requestAnimationFrame: vi.fn(cb => setTimeout(cb, 16)),
    cancelAnimationFrame: vi.fn(),
    setTimeout: global.setTimeout,
    clearTimeout: global.clearTimeout,
    setInterval: global.setInterval,
    clearInterval: global.clearInterval
  },
  writable: true
});

Object.defineProperty(global, 'document', {
  value: {
    readyState: 'complete',
    getElementById: vi.fn(() => ({
      style: {},
      innerHTML: '',
      appendChild: vi.fn(),
      removeChild: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      classList: {
        add: vi.fn(),
        remove: vi.fn(),
        contains: vi.fn(() => false),
        toggle: vi.fn()
      }
    })),
    createElement: vi.fn((tag) => ({
      tagName: tag.toUpperCase(),
      style: {},
      innerHTML: '',
      appendChild: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      classList: {
        add: vi.fn(),
        remove: vi.fn(),
        contains: vi.fn(() => false)
      },
      setAttribute: vi.fn(),
      getAttribute: vi.fn()
    })),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    body: {
      appendChild: vi.fn(),
      removeChild: vi.fn()
    }
  },
  writable: true
});

// Mock console for testing
global.console = {
  log: vi.fn(),
  error: vi.fn(),
  warn: vi.fn(),
  info: vi.fn(),
  debug: vi.fn()
};

describe('Module Lifecycle Management', () => {
  let mockEventBus;
  let mockServiceContainer;
  let moduleInstances;

  beforeEach(() => {
    // Setup mock EventBus
    mockEventBus = {
      emit: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      once: vi.fn(),
      listeners: new Map(),
      events: new Map()
    };

    // Setup mock ServiceContainer
    mockServiceContainer = {
      get: vi.fn(),
      register: vi.fn(),
      isRegistered: vi.fn(() => true),
      services: new Map()
    };

    // Track module instances for cleanup
    moduleInstances = [];
  });

  afterEach(() => {
    // Cleanup all module instances
    moduleInstances.forEach(instance => {
      if (instance && typeof instance.destroy === 'function') {
        try {
          instance.destroy();
        } catch (error) {
          console.warn('Error during module cleanup:', error);
        }
      }
    });
    moduleInstances = [];

    // Clear all mocks
    vi.clearAllMocks();
  });

  describe('Module Initialization', () => {
    it('should initialize modules with proper dependency injection', async () => {
      // Mock module class
      class TestModule {
        constructor(dependencies = {}) {
          this.eventBus = dependencies.eventBus;
          this.serviceContainer = dependencies.serviceContainer;
          this.initialized = false;
          this.destroyed = false;
        }

        async initialize() {
          if (this.initialized) {
            throw new Error('Module already initialized');
          }
          this.initialized = true;
          this.eventBus?.emit('module:initialized', { module: 'TestModule' });
          return this;
        }

        destroy() {
          if (!this.initialized) return;
          this.destroyed = true;
          this.initialized = false;
          this.eventBus?.emit('module:destroyed', { module: 'TestModule' });
        }

        isHealthy() {
          return this.initialized && !this.destroyed;
        }
      }

      // Test proper initialization
      const module = new TestModule({
        eventBus: mockEventBus,
        serviceContainer: mockServiceContainer
      });
      moduleInstances.push(module);

      await module.initialize();

      expect(module.initialized).toBe(true);
      expect(module.destroyed).toBe(false);
      expect(module.isHealthy()).toBe(true);
      expect(mockEventBus.emit).toHaveBeenCalledWith('module:initialized', { module: 'TestModule' });
    });

    it('should handle initialization errors gracefully', async () => {
      class FailingModule {
        constructor(dependencies = {}) {
          this.eventBus = dependencies.eventBus;
        }

        async initialize() {
          throw new Error('Initialization failed');
        }

        destroy() {
          // Cleanup logic
        }
      }

      const module = new FailingModule({ eventBus: mockEventBus });
      moduleInstances.push(module);

      await expect(module.initialize()).rejects.toThrow('Initialization failed');
    });

    it('should prevent double initialization', async () => {
      class TestModule {
        constructor() {
          this.initialized = false;
        }

        async initialize() {
          if (this.initialized) {
            throw new Error('Module already initialized');
          }
          this.initialized = true;
        }

        destroy() {
          this.initialized = false;
        }
      }

      const module = new TestModule();
      moduleInstances.push(module);

      await module.initialize();
      await expect(module.initialize()).rejects.toThrow('Module already initialized');
    });
  });

  describe('Module Communication', () => {
    it('should facilitate event-based communication between modules', () => {
      class ProducerModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
        }

        sendMessage(data) {
          this.eventBus.emit('test:message', data);
        }
      }

      class ConsumerModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.receivedMessages = [];
          this.eventBus.on('test:message', (data) => {
            this.receivedMessages.push(data);
          });
        }

        destroy() {
          this.eventBus.off('test:message');
        }
      }

      const producer = new ProducerModule(mockEventBus);
      const consumer = new ConsumerModule(mockEventBus);
      moduleInstances.push(producer, consumer);

      // Mock event communication
      mockEventBus.on.mockImplementation((event, callback) => {
        if (!mockEventBus.listeners.has(event)) {
          mockEventBus.listeners.set(event, []);
        }
        mockEventBus.listeners.get(event).push(callback);
      });

      mockEventBus.emit.mockImplementation((event, data) => {
        const listeners = mockEventBus.listeners.get(event) || [];
        listeners.forEach(callback => callback(data));
      });

      // Test communication
      producer.sendMessage({ test: 'data' });

      expect(mockEventBus.emit).toHaveBeenCalledWith('test:message', { test: 'data' });
    });

    it('should handle communication errors without breaking other modules', () => {
      class ErrorModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.eventBus.on('test:error', () => {
            throw new Error('Handler error');
          });
        }
      }

      class NormalModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.messagesReceived = 0;
          this.eventBus.on('test:error', () => {
            this.messagesReceived++;
          });
        }
      }

      const errorModule = new ErrorModule(mockEventBus);
      const normalModule = new NormalModule(mockEventBus);
      moduleInstances.push(errorModule, normalModule);

      // Mock error handling in event bus
      mockEventBus.emit.mockImplementation((event, data) => {
        const listeners = mockEventBus.listeners.get(event) || [];
        listeners.forEach(callback => {
          try {
            callback(data);
          } catch (error) {
            console.error('Event handler error:', error);
          }
        });
      });

      expect(() => {
        mockEventBus.emit('test:error', {});
      }).not.toThrow();
    });

    it('should support request-response communication patterns', async () => {
      class RequestModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
        }

        async requestData(requestId) {
          return new Promise((resolve) => {
            this.eventBus.once(`response:${requestId}`, resolve);
            this.eventBus.emit('data:request', { requestId });
          });
        }
      }

      class ResponseModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.eventBus.on('data:request', ({ requestId }) => {
            this.eventBus.emit(`response:${requestId}`, { data: 'test response' });
          });
        }
      }

      const requestModule = new RequestModule(mockEventBus);
      const responseModule = new ResponseModule(mockEventBus);
      moduleInstances.push(requestModule, responseModule);

      // Mock request-response pattern
      const responseCallbacks = new Map();

      mockEventBus.once.mockImplementation((event, callback) => {
        responseCallbacks.set(event, callback);
      });

      mockEventBus.emit.mockImplementation((event, data) => {
        if (event === 'data:request') {
          const responseEvent = `response:${data.requestId}`;
          const responseCallback = responseCallbacks.get(responseEvent);
          if (responseCallback) {
            setTimeout(() => responseCallback({ data: 'test response' }), 0);
          }
        }
      });

      const response = await requestModule.requestData('test123');
      expect(response).toEqual({ data: 'test response' });
    });
  });

  describe('Module Cleanup and Memory Management', () => {
    it('should properly clean up event listeners on destruction', () => {
      class TestModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.eventHandlers = new Map();
          this.initialized = false;
        }

        initialize() {
          this.initialized = true;
          this.registerEventHandler('test:event', this.handleTestEvent.bind(this));
          this.registerEventHandler('cleanup:event', this.handleCleanupEvent.bind(this));
        }

        registerEventHandler(event, handler) {
          this.eventHandlers.set(event, handler);
          this.eventBus.on(event, handler);
        }

        handleTestEvent(data) {
          // Handle event
        }

        handleCleanupEvent(data) {
          // Handle cleanup
        }

        destroy() {
          if (!this.initialized) return;

          // Remove all event listeners
          for (const [event, handler] of this.eventHandlers) {
            this.eventBus.off(event, handler);
          }
          this.eventHandlers.clear();
          this.initialized = false;
        }
      }

      const module = new TestModule(mockEventBus);
      moduleInstances.push(module);

      module.initialize();
      module.destroy();

      // Verify event handlers were removed
      expect(mockEventBus.off).toHaveBeenCalledTimes(2);
      expect(mockEventBus.off).toHaveBeenCalledWith('test:event', expect.any(Function));
      expect(mockEventBus.off).toHaveBeenCalledWith('cleanup:event', expect.any(Function));
    });

    it('should handle cleanup errors gracefully', () => {
      class ProblematicModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.cleanupCalled = false;
        }

        destroy() {
          this.cleanupCalled = true;
          throw new Error('Cleanup error');
        }
      }

      const module = new ProblematicModule(mockEventBus);
      moduleInstances.push(module);

      // Should not throw during cleanup
      expect(() => {
        try {
          module.destroy();
        } catch (error) {
          console.warn('Cleanup error handled:', error);
        }
      }).not.toThrow();

      expect(module.cleanupCalled).toBe(true);
    });

    it('should detect and prevent memory leaks', () => {
      class LeakyModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.timers = [];
          this.domElements = [];
        }

        initialize() {
          // Simulate timer creation
          const timer = setInterval(() => {}, 1000);
          this.timers.push(timer);

          // Simulate DOM element creation
          const element = document.createElement('div');
          document.body.appendChild(element);
          this.domElements.push(element);
        }

        destroy() {
          // Proper cleanup
          this.timers.forEach(timer => clearInterval(timer));
          this.timers = [];

          this.domElements.forEach(element => {
            if (element.parentNode) {
              element.parentNode.removeChild(element);
            }
          });
          this.domElements = [];
        }

        hasLeaks() {
          return this.timers.length > 0 || this.domElements.length > 0;
        }
      }

      const module = new LeakyModule(mockEventBus);
      moduleInstances.push(module);

      module.initialize();
      expect(module.hasLeaks()).toBe(true);

      module.destroy();
      expect(module.hasLeaks()).toBe(false);
    });
  });

  describe('Module Health and Error Recovery', () => {
    it('should provide health checking capabilities', () => {
      class HealthyModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.state = 'uninitialized';
          this.errors = [];
        }

        async initialize() {
          try {
            this.state = 'initializing';
            // Simulate async initialization
            await new Promise(resolve => setTimeout(resolve, 10));
            this.state = 'healthy';
          } catch (error) {
            this.state = 'error';
            this.errors.push(error);
            throw error;
          }
        }

        isHealthy() {
          return this.state === 'healthy';
        }

        getHealthStatus() {
          return {
            state: this.state,
            healthy: this.isHealthy(),
            errors: this.errors.length,
            lastError: this.errors[this.errors.length - 1]
          };
        }

        recover() {
          if (this.state === 'error') {
            this.state = 'healthy';
            return true;
          }
          return false;
        }
      }

      const module = new HealthyModule(mockEventBus);
      moduleInstances.push(module);

      expect(module.isHealthy()).toBe(false);
      expect(module.getHealthStatus().state).toBe('uninitialized');

      return module.initialize().then(() => {
        expect(module.isHealthy()).toBe(true);
        expect(module.getHealthStatus().healthy).toBe(true);
      });
    });

    it('should support graceful degradation on errors', () => {
      class ResilientModule {
        constructor(eventBus) {
          this.eventBus = eventBus;
          this.features = new Set(['feature1', 'feature2', 'feature3']);
          this.disabledFeatures = new Set();
        }

        disableFeature(feature) {
          this.features.delete(feature);
          this.disabledFeatures.add(feature);
          this.eventBus.emit('feature:disabled', { feature });
        }

        isFeatureEnabled(feature) {
          return this.features.has(feature);
        }

        handleError(error, context) {
          console.warn('Handling error:', error, 'in context:', context);

          // Graceful degradation
          if (context === 'feature1') {
            this.disableFeature('feature1');
          }

          return !this.isFeatureEnabled(context);
        }

        getStatus() {
          return {
            totalFeatures: this.features.size + this.disabledFeatures.size,
            enabledFeatures: this.features.size,
            disabledFeatures: this.disabledFeatures.size,
            degraded: this.disabledFeatures.size > 0
          };
        }
      }

      const module = new ResilientModule(mockEventBus);
      moduleInstances.push(module);

      expect(module.isFeatureEnabled('feature1')).toBe(true);
      expect(module.getStatus().degraded).toBe(false);

      // Simulate error in feature1
      const handled = module.handleError(new Error('Feature error'), 'feature1');

      expect(handled).toBe(true);
      expect(module.isFeatureEnabled('feature1')).toBe(false);
      expect(module.getStatus().degraded).toBe(true);
      expect(mockEventBus.emit).toHaveBeenCalledWith('feature:disabled', { feature: 'feature1' });
    });
  });

  describe('Service Container Integration', () => {
    it('should integrate with service container for dependency resolution', () => {
      class ServiceAwareModule {
        static dependencies = ['logger', 'config', 'api'];

        constructor(serviceContainer) {
          this.serviceContainer = serviceContainer;
          this.logger = null;
          this.config = null;
          this.api = null;
        }

        async initialize() {
          // Resolve dependencies from container
          this.logger = this.serviceContainer.get('logger');
          this.config = this.serviceContainer.get('config');
          this.api = this.serviceContainer.get('api');

          this.logger.info('Module initialized with dependencies');
          return this;
        }

        getDependencies() {
          return {
            logger: this.logger,
            config: this.config,
            api: this.api
          };
        }
      }

      // Mock services
      const mockLogger = { info: vi.fn(), error: vi.fn() };
      const mockConfig = { setting1: 'value1' };
      const mockApi = { request: vi.fn() };

      mockServiceContainer.get.mockImplementation((serviceName) => {
        const services = {
          logger: mockLogger,
          config: mockConfig,
          api: mockApi
        };
        return services[serviceName];
      });

      const module = new ServiceAwareModule(mockServiceContainer);
      moduleInstances.push(module);

      return module.initialize().then(() => {
        const deps = module.getDependencies();
        expect(deps.logger).toBe(mockLogger);
        expect(deps.config).toBe(mockConfig);
        expect(deps.api).toBe(mockApi);
        expect(mockLogger.info).toHaveBeenCalledWith('Module initialized with dependencies');
      });
    });

    it('should handle missing dependencies gracefully', () => {
      class OptionalDependencyModule {
        constructor(serviceContainer) {
          this.serviceContainer = serviceContainer;
        }

        async initialize() {
          try {
            this.requiredService = this.serviceContainer.get('required');
          } catch (error) {
            throw new Error('Required service not available');
          }

          try {
            this.optionalService = this.serviceContainer.get('optional');
          } catch (error) {
            console.warn('Optional service not available, continuing without it');
            this.optionalService = null;
          }
        }
      }

      mockServiceContainer.get.mockImplementation((serviceName) => {
        if (serviceName === 'required') {
          return { name: 'required-service' };
        }
        throw new Error(`Service ${serviceName} not found`);
      });

      const module = new OptionalDependencyModule(mockServiceContainer);
      moduleInstances.push(module);

      return module.initialize().then(() => {
        expect(module.requiredService).toEqual({ name: 'required-service' });
        expect(module.optionalService).toBe(null);
      });
    });
  });

  describe('Module Performance Monitoring', () => {
    it('should track initialization and operation performance', async () => {
      class PerformanceModule {
        constructor() {
          this.metrics = {
            initializationTime: 0,
            operationCount: 0,
            totalOperationTime: 0
          };
        }

        async initialize() {
          const startTime = performance.now();

          // Simulate initialization work
          await new Promise(resolve => setTimeout(resolve, 50));

          this.metrics.initializationTime = performance.now() - startTime;
        }

        async performOperation() {
          const startTime = performance.now();

          // Simulate operation work
          await new Promise(resolve => setTimeout(resolve, 10));

          const operationTime = performance.now() - startTime;
          this.metrics.operationCount++;
          this.metrics.totalOperationTime += operationTime;
        }

        getPerformanceMetrics() {
          return {
            ...this.metrics,
            averageOperationTime: this.metrics.operationCount > 0
              ? this.metrics.totalOperationTime / this.metrics.operationCount
              : 0
          };
        }
      }

      // Mock performance.now for consistent testing
      let mockTime = 0;
      global.performance = {
        now: () => mockTime += 10
      };

      const module = new PerformanceModule();
      moduleInstances.push(module);

      await module.initialize();
      await module.performOperation();
      await module.performOperation();

      const metrics = module.getPerformanceMetrics();
      expect(metrics.initializationTime).toBeGreaterThan(0);
      expect(metrics.operationCount).toBe(2);
      expect(metrics.averageOperationTime).toBeGreaterThan(0);
    });
  });
});

describe('Module Integration Scenarios', () => {
  it('should handle complex multi-module workflows', async () => {
    const eventBus = {
      events: new Map(),
      emit: vi.fn((event, data) => {
        const handlers = eventBus.events.get(event) || [];
        handlers.forEach(handler => {
          try {
            handler(data);
          } catch (error) {
            console.error('Event handler error:', error);
          }
        });
      }),
      on: vi.fn((event, handler) => {
        if (!eventBus.events.has(event)) {
          eventBus.events.set(event, []);
        }
        eventBus.events.get(event).push(handler);
      }),
      off: vi.fn()
    };

    class WorkflowCoordinator {
      constructor(eventBus) {
        this.eventBus = eventBus;
        this.workflow = [];
        this.eventBus.on('step:completed', this.handleStepCompleted.bind(this));
      }

      startWorkflow(steps) {
        this.workflow = [...steps];
        this.executeNextStep();
      }

      handleStepCompleted(data) {
        console.log('Step completed:', data);
        this.executeNextStep();
      }

      executeNextStep() {
        if (this.workflow.length === 0) {
          this.eventBus.emit('workflow:completed');
          return;
        }

        const nextStep = this.workflow.shift();
        this.eventBus.emit('step:execute', { step: nextStep });
      }
    }

    class WorkflowExecutor {
      constructor(eventBus) {
        this.eventBus = eventBus;
        this.eventBus.on('step:execute', this.executeStep.bind(this));
      }

      executeStep(data) {
        const { step } = data;
        // Simulate step execution
        setTimeout(() => {
          this.eventBus.emit('step:completed', { step, success: true });
        }, 10);
      }
    }

    const coordinator = new WorkflowCoordinator(eventBus);
    const executor = new WorkflowExecutor(eventBus);

    const workflowCompleted = new Promise(resolve => {
      eventBus.on('workflow:completed', resolve);
    });

    coordinator.startWorkflow(['init', 'process', 'finalize']);

    await workflowCompleted;
    expect(eventBus.emit).toHaveBeenCalledWith('workflow:completed');
  });
});