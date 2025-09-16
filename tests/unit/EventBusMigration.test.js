/**
 * EventBusMigration Tests
 *
 * Tests for the EventBusMigration utilities including:
 * - EventBusModule base class
 * - CallbackToEventAdapter for legacy callback adaptation
 * - GradualMigrationHelper for phased migration
 * - EventValidator for event data validation
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setupGlobalEnvironment, cleanupDOM } from '../helpers/domMocks.js';

// Mock the EventBus module before importing
vi.mock('/Users/greg/src/LLMpostor/static/js/modules/EventBus.js', () => {
  const mockEventBus = {
    publish: vi.fn(),
    subscribe: vi.fn((eventName, handler, options) => {
      // Return a mock unsubscribe function
      return vi.fn();
    }),
    getSubscriberCount: vi.fn(() => 0),
    clear: vi.fn()
  };

  const mockEvents = {
    USER: {
      RESPONSE_SUBMITTED: 'user:response:submitted',
      GUESS_SUBMITTED: 'user:guess:submitted'
    },
    TIMER: {
      UPDATED: 'timer:updated'
    }
  };

  return {
    EventBus: mockEventBus,
    Events: mockEvents
  };
});

// Now import the modules under test
import {
  EventBusModule,
  CallbackToEventAdapter,
  GradualMigrationHelper,
  EventValidator,
  migrationHelper,
  eventValidator
} from '/Users/greg/src/LLMpostor/static/js/modules/EventBusMigration.js';

// Import the mocked EventBus to access in tests
import { EventBus as mockEventBus } from '/Users/greg/src/LLMpostor/static/js/modules/EventBus.js';

describe('EventBusMigration', () => {
  beforeEach(() => {
    setupGlobalEnvironment();
    vi.clearAllMocks();
    // Reset console.log mock
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    cleanupDOM();
    vi.restoreAllMocks();
  });

  describe('EventBusModule', () => {
    let module;

    beforeEach(() => {
      module = new EventBusModule('TestModule');
    });

    afterEach(() => {
      if (module) {
        module.cleanup();
      }
    });

    it('should initialize with module name and EventBus integration', () => {
      expect(module.moduleName).toBe('TestModule');
      expect(module.eventBus).toBe(mockEventBus);
      expect(module.subscriptions).toBeInstanceOf(Set);
      expect(module.subscriptions.size).toBe(0);
      expect(console.log).toHaveBeenCalledWith('TestModule: Initialized with EventBus integration');
    });

    it('should bind common methods to preserve context', () => {
      expect(typeof module.publish).toBe('function');
      expect(typeof module.subscribe).toBe('function');
      expect(typeof module.once).toBe('function');
      expect(typeof module.cleanup).toBe('function');
    });

    describe('publish', () => {
      it('should publish events with module context', () => {
        const eventData = { test: 'data' };
        module.publish('test:event', eventData);

        expect(mockEventBus.publish).toHaveBeenCalledWith(
          'test:event',
          eventData,
          { source: 'TestModule' }
        );
      });

      it('should publish events with null data when not provided', () => {
        module.publish('test:event');

        expect(mockEventBus.publish).toHaveBeenCalledWith(
          'test:event',
          null,
          { source: 'TestModule' }
        );
      });
    });

    describe('subscribe', () => {
      it('should subscribe to events and track subscriptions', () => {
        const handler = vi.fn();
        const mockUnsubscribe = vi.fn();
        mockEventBus.subscribe.mockReturnValue(mockUnsubscribe);

        const unsubscribe = module.subscribe('test:event', handler);

        expect(mockEventBus.subscribe).toHaveBeenCalledWith(
          'test:event',
          handler,
          { context: module }
        );
        expect(module.subscriptions.size).toBe(1);
        expect(module.subscriptions.has(mockUnsubscribe)).toBe(true);
        expect(typeof unsubscribe).toBe('function');
      });

      it('should pass through subscription options with context', () => {
        const handler = vi.fn();
        const options = { priority: 10, once: true };

        module.subscribe('test:event', handler, options);

        expect(mockEventBus.subscribe).toHaveBeenCalledWith(
          'test:event',
          handler,
          { ...options, context: module }
        );
      });

      it('should return wrapped unsubscribe function that removes from tracking', () => {
        const handler = vi.fn();
        const mockUnsubscribe = vi.fn();
        mockEventBus.subscribe.mockReturnValue(mockUnsubscribe);

        const wrappedUnsubscribe = module.subscribe('test:event', handler);

        // Initially tracked
        expect(module.subscriptions.size).toBe(1);

        // Call wrapped unsubscribe
        wrappedUnsubscribe();

        // Should call original and remove from tracking
        expect(mockUnsubscribe).toHaveBeenCalled();
        expect(module.subscriptions.size).toBe(0);
      });
    });

    describe('once', () => {
      it('should subscribe with once option', () => {
        const handler = vi.fn();

        module.once('test:event', handler);

        expect(mockEventBus.subscribe).toHaveBeenCalledWith(
          'test:event',
          handler,
          { once: true, context: module }
        );
      });
    });

    describe('cleanup', () => {
      it('should clean up all subscriptions', () => {
        const unsubscribe1 = vi.fn();
        const unsubscribe2 = vi.fn();

        // Mock multiple subscriptions
        mockEventBus.subscribe
          .mockReturnValueOnce(unsubscribe1)
          .mockReturnValueOnce(unsubscribe2);

        module.subscribe('event1', vi.fn());
        module.subscribe('event2', vi.fn());

        expect(module.subscriptions.size).toBe(2);

        module.cleanup();

        expect(console.log).toHaveBeenCalledWith('TestModule: Cleaning up 2 subscriptions');
        expect(unsubscribe1).toHaveBeenCalled();
        expect(unsubscribe2).toHaveBeenCalled();
        expect(module.subscriptions.size).toBe(0);
      });

      it('should handle cleanup with no subscriptions', () => {
        module.cleanup();

        expect(console.log).toHaveBeenCalledWith('TestModule: Cleaning up 0 subscriptions');
        expect(module.subscriptions.size).toBe(0);
      });
    });

    describe('getSubscriptionCount', () => {
      it('should return current subscription count', () => {
        expect(module.getSubscriptionCount()).toBe(0);

        module.subscribe('event1', vi.fn());
        expect(module.getSubscriptionCount()).toBe(1);

        module.subscribe('event2', vi.fn());
        expect(module.getSubscriptionCount()).toBe(2);
      });
    });
  });

  describe('CallbackToEventAdapter', () => {
    let adapter;

    beforeEach(() => {
      adapter = new CallbackToEventAdapter('TestAdapter');
    });

    it('should initialize with module name and EventBus reference', () => {
      expect(adapter.moduleName).toBe('TestAdapter');
      expect(adapter.eventBus).toBe(mockEventBus);
      expect(adapter.adapters).toBeInstanceOf(Map);
      expect(console.log).toHaveBeenCalledWith('TestAdapter: Callback-to-Event adapter initialized');
    });

    describe('adaptCallback', () => {
      it('should create adapter that calls original callback and publishes event', () => {
        const originalCallback = vi.fn();
        const eventData = { test: 'data' };

        const adaptedCallback = adapter.adaptCallback('test:event', originalCallback);

        adaptedCallback(eventData);

        expect(originalCallback).toHaveBeenCalledWith(eventData);
        expect(mockEventBus.publish).toHaveBeenCalledWith(
          'test:event',
          eventData,
          { source: 'TestAdapter' }
        );
        expect(adapter.adapters.has('test:event')).toBe(true);
      });

      it('should create adapter without original callback', () => {
        const eventData = { test: 'data' };

        const adaptedCallback = adapter.adaptCallback('test:event');

        adaptedCallback(eventData);

        expect(mockEventBus.publish).toHaveBeenCalledWith(
          'test:event',
          eventData,
          { source: 'TestAdapter' }
        );
      });

      it('should handle errors in original callback gracefully', () => {
        const failingCallback = vi.fn(() => {
          throw new Error('Callback error');
        });

        const adaptedCallback = adapter.adaptCallback('test:event', failingCallback);

        expect(() => adaptedCallback({ test: 'data' })).not.toThrow();
        expect(failingCallback).toHaveBeenCalled();
        expect(mockEventBus.publish).toHaveBeenCalled();
        expect(console.error).toHaveBeenCalledWith(
          'TestAdapter: Error in original callback:',
          expect.any(Error)
        );
      });

      it('should store adapter in adapters map', () => {
        const adapter1 = adapter.adaptCallback('event1');
        const adapter2 = adapter.adaptCallback('event2');

        expect(adapter.adapters.size).toBe(2);
        expect(adapter.adapters.get('event1')).toBe(adapter1);
        expect(adapter.adapters.get('event2')).toBe(adapter2);
      });
    });

    describe('adaptSubscription', () => {
      it('should subscribe to event with adapter context', () => {
        const callback = vi.fn();

        adapter.adaptSubscription('test:event', callback);

        expect(mockEventBus.subscribe).toHaveBeenCalledWith(
          'test:event',
          callback,
          { context: adapter }
        );
      });
    });

    describe('getAdapters', () => {
      it('should return copy of adapters map', () => {
        adapter.adaptCallback('event1');
        adapter.adaptCallback('event2');

        const adapters = adapter.getAdapters();

        expect(adapters).toBeInstanceOf(Map);
        expect(adapters.size).toBe(2);
        expect(adapters.has('event1')).toBe(true);
        expect(adapters.has('event2')).toBe(true);

        // Should be a copy, not the original
        adapters.clear();
        expect(adapter.adapters.size).toBe(2);
      });
    });
  });

  describe('GradualMigrationHelper', () => {
    let helper;

    beforeEach(() => {
      helper = new GradualMigrationHelper();
    });

    it('should initialize with dual mode enabled', () => {
      expect(helper.migrationFlags).toBeInstanceOf(Map);
      expect(helper.dualMode).toBe(true);
      expect(console.log).toHaveBeenCalledWith('GradualMigrationHelper: Initialized for seamless migration');
    });

    describe('setMigrationFlag', () => {
      it('should set migration flag for features', () => {
        helper.setMigrationFlag('feature1', true);
        helper.setMigrationFlag('feature2', false);

        expect(helper.migrationFlags.get('feature1')).toBe(true);
        expect(helper.migrationFlags.get('feature2')).toBe(false);
        expect(console.log).toHaveBeenCalledWith('Migration: feature1 -> Events');
        expect(console.log).toHaveBeenCalledWith('Migration: feature2 -> Direct calls');
      });
    });

    describe('shouldUseEvents', () => {
      it('should return migration flag value or false if not set', () => {
        expect(helper.shouldUseEvents('unknown')).toBe(false);

        helper.setMigrationFlag('feature1', true);
        helper.setMigrationFlag('feature2', false);

        expect(helper.shouldUseEvents('feature1')).toBe(true);
        expect(helper.shouldUseEvents('feature2')).toBe(false);
      });
    });

    describe('execute', () => {
      it('should execute both patterns in dual mode when using events', () => {
        const oldPattern = vi.fn();
        const newPattern = vi.fn();
        const data = { test: 'data' };

        helper.setMigrationFlag('feature1', true);
        helper.execute('feature1', oldPattern, newPattern, data);

        expect(newPattern).toHaveBeenCalledWith(data);
        expect(oldPattern).toHaveBeenCalledWith(data);
      });

      it('should execute both patterns in dual mode when using old pattern', () => {
        const oldPattern = vi.fn();
        const newPattern = vi.fn();
        const data = { test: 'data' };

        helper.setMigrationFlag('feature1', false);
        helper.execute('feature1', oldPattern, newPattern, data);

        expect(oldPattern).toHaveBeenCalledWith(data);
        expect(newPattern).toHaveBeenCalledWith(data);
      });

      it('should execute only new pattern when not in dual mode and using events', () => {
        const oldPattern = vi.fn();
        const newPattern = vi.fn();
        const data = { test: 'data' };

        helper.disableDualMode();
        helper.setMigrationFlag('feature1', true);
        helper.execute('feature1', oldPattern, newPattern, data);

        expect(newPattern).toHaveBeenCalledWith(data);
        expect(oldPattern).not.toHaveBeenCalled();
      });

      it('should execute only old pattern when not in dual mode and using old calls', () => {
        const oldPattern = vi.fn();
        const newPattern = vi.fn();
        const data = { test: 'data' };

        helper.disableDualMode();
        helper.setMigrationFlag('feature1', false);
        helper.execute('feature1', oldPattern, newPattern, data);

        expect(oldPattern).toHaveBeenCalledWith(data);
        expect(newPattern).not.toHaveBeenCalled();
      });

      it('should handle missing old pattern gracefully', () => {
        const newPattern = vi.fn();
        const data = { test: 'data' };

        helper.disableDualMode();
        helper.setMigrationFlag('feature1', false);
        helper.execute('feature1', null, newPattern, data);

        expect(newPattern).not.toHaveBeenCalled();
      });

      it('should handle errors in new pattern when using events flag', () => {
        const oldPattern = vi.fn();
        const newPattern = vi.fn(() => {
          throw new Error('New pattern error');
        });

        helper.setMigrationFlag('feature1', true);
        helper.execute('feature1', oldPattern, newPattern);

        expect(console.error).toHaveBeenCalledWith(
          'Migration error in feature1:',
          expect.any(Error)
        );
        // When newPattern throws, oldPattern on line 196 never gets called
        // and fallback only happens when !useEvents
        expect(oldPattern).not.toHaveBeenCalled();
        expect(newPattern).toHaveBeenCalled();
      });

      it('should fallback to old pattern on error when not using events', () => {
        const oldPattern = vi.fn();
        const newPattern = vi.fn(() => {
          throw new Error('New pattern error');
        });

        helper.setMigrationFlag('feature1', false);
        helper.execute('feature1', oldPattern, newPattern);

        expect(console.error).toHaveBeenCalledWith(
          'Migration error in feature1:',
          expect.any(Error)
        );
        expect(oldPattern).toHaveBeenCalledTimes(2); // Once in normal flow, once in fallback
      });
    });

    describe('disableDualMode', () => {
      it('should disable dual mode', () => {
        expect(helper.dualMode).toBe(true);

        helper.disableDualMode();

        expect(helper.dualMode).toBe(false);
        expect(console.log).toHaveBeenCalledWith('Migration: Dual mode disabled - running only selected patterns');
      });
    });

    describe('getStatus', () => {
      it('should return migration status report', () => {
        helper.setMigrationFlag('feature1', true);
        helper.setMigrationFlag('feature2', false);

        const status = helper.getStatus();

        expect(status).toEqual({
          dualMode: true,
          features: {
            feature1: true,
            feature2: false
          },
          totalFeatures: 2
        });
      });

      it('should reflect disabled dual mode in status', () => {
        helper.disableDualMode();

        const status = helper.getStatus();

        expect(status.dualMode).toBe(false);
      });
    });
  });

  describe('EventValidator', () => {
    let validator;

    beforeEach(() => {
      validator = new EventValidator();
    });

    it('should initialize with empty schemas map', () => {
      expect(validator.schemas).toBeInstanceOf(Map);
      expect(validator.schemas.size).toBe(0);
    });

    describe('registerSchema', () => {
      it('should register event schema', () => {
        const schema = { type: 'object', required: true };

        validator.registerSchema('test:event', schema);

        expect(validator.schemas.get('test:event')).toBe(schema);
      });
    });

    describe('validate', () => {
      it('should return true when no schema is registered', () => {
        const result = validator.validate('unknown:event', { test: 'data' });

        expect(result).toBe(true);
      });

      it('should validate required data', () => {
        validator.registerSchema('test:event', { required: true });

        expect(validator.validate('test:event', { test: 'data' })).toBe(true);
        expect(validator.validate('test:event', null)).toBe(false);
        expect(validator.validate('test:event', undefined)).toBe(false);
      });

      it('should validate data type', () => {
        validator.registerSchema('test:event', { type: 'string' });

        expect(validator.validate('test:event', 'test')).toBe(true);
        expect(validator.validate('test:event', 123)).toBe(false);
        expect(validator.validate('test:event', {})).toBe(false);
      });

      it('should validate object properties', () => {
        validator.registerSchema('test:event', {
          type: 'object',
          properties: {
            name: { type: 'string', required: true },
            age: { type: 'number' }
          }
        });

        expect(validator.validate('test:event', { name: 'John', age: 30 })).toBe(true);
        // Note: The current implementation validates ALL properties defined in schema
        // So missing 'age' property means data.age is undefined, which fails type: 'number' check
        expect(validator.validate('test:event', { name: 'John' })).toBe(false); // age is undefined, fails number check
        expect(validator.validate('test:event', { name: null })).toBe(false); // required but null
        expect(validator.validate('test:event', { age: 30 })).toBe(false); // missing required name
      });

      it('should handle validation errors gracefully', () => {
        validator.registerSchema('test:event', { type: 'object' });

        // Override _validateAgainstSchema to throw
        validator._validateAgainstSchema = vi.fn(() => {
          throw new Error('Validation error');
        });

        const result = validator.validate('test:event', {});

        expect(result).toBe(false);
        expect(console.error).toHaveBeenCalledWith(
          'Event validation error for test:event:',
          expect.any(Error)
        );
      });
    });

    describe('_validateAgainstSchema', () => {
      it('should validate null/undefined against required schema', () => {
        expect(validator._validateAgainstSchema(null, { required: true })).toBe(false);
        expect(validator._validateAgainstSchema(undefined, { required: true })).toBe(false);
        expect(validator._validateAgainstSchema('data', { required: true })).toBe(true);
        expect(validator._validateAgainstSchema(null, {})).toBe(true);
      });

      it('should validate type checking', () => {
        expect(validator._validateAgainstSchema('test', { type: 'string' })).toBe(true);
        expect(validator._validateAgainstSchema(123, { type: 'number' })).toBe(true);
        expect(validator._validateAgainstSchema({}, { type: 'object' })).toBe(true);
        expect(validator._validateAgainstSchema('test', { type: 'number' })).toBe(false);
      });

      it('should validate nested object properties', () => {
        const schema = {
          type: 'object',
          properties: {
            user: {
              type: 'object',
              properties: {
                name: { type: 'string', required: true }
              }
            }
          }
        };

        const validData = { user: { name: 'John' } };
        const invalidData = { user: { name: 123 } };

        expect(validator._validateAgainstSchema(validData, schema)).toBe(true);
        expect(validator._validateAgainstSchema(invalidData, schema)).toBe(false);
      });
    });
  });

  describe('Global Instances', () => {
    it('should export global migration helper instance', () => {
      expect(migrationHelper).toBeInstanceOf(GradualMigrationHelper);
    });

    it('should export global event validator instance', () => {
      expect(eventValidator).toBeInstanceOf(EventValidator);
    });

    it('should have common event schemas pre-registered', () => {
      // These schemas are registered in the module
      expect(eventValidator.validate('user:response:submitted', { response: 'test' })).toBe(true);
      expect(eventValidator.validate('user:response:submitted', { response: 123 })).toBe(false);

      expect(eventValidator.validate('user:guess:submitted', { guessIndex: 1 })).toBe(true);
      expect(eventValidator.validate('user:guess:submitted', { guessIndex: 'invalid' })).toBe(false);

      expect(eventValidator.validate('timer:updated', {
        timeRemaining: 30,
        totalTime: 60,
        phase: 'response'
      })).toBe(true);
      expect(eventValidator.validate('timer:updated', {
        timeRemaining: '30',
        totalTime: 60,
        phase: 'response'
      })).toBe(false);
    });
  });
});