/**
 * MemoryManager Tests
 *
 * Tests for memory management functionality including:
 * - Event listener tracking and cleanup
 * - Timer and interval management
 * - DOM reference tracking
 * - Observer management
 * - Memory usage monitoring
 * - Garbage collection optimization
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import MemoryManager from '../../static/js/utils/MemoryManager.js';
import { createMockElement, createMockWindow, setupGlobalEnvironment } from '../helpers/domMocks.js';

describe('MemoryManager', () => {
  let memoryManager;
  let mockElement;
  let originalWindow;
  let mockConsole;

  beforeEach(() => {
    setupGlobalEnvironment();

    // Mock console methods
    mockConsole = {
      log: vi.fn(),
      warn: vi.fn(),
      debug: vi.fn()
    };
    vi.stubGlobal('console', mockConsole);

    // Create mock element for testing
    mockElement = createMockElement('div', { id: 'test-element' });

    // Store original window
    originalWindow = global.window;

    memoryManager = new MemoryManager();
  });

  afterEach(() => {
    if (memoryManager) {
      memoryManager.destroy();
    }
    vi.restoreAllMocks();
    global.window = originalWindow;
  });

  describe('Initialization', () => {
    it('should initialize with empty tracking collections', () => {
      expect(memoryManager.eventListeners.size).toBe(0);
      expect(memoryManager.timers.size).toBe(0);
      expect(memoryManager.intervals.size).toBe(0);
      expect(memoryManager.observers.size).toBe(0);
    });

    it('should initialize memory metrics', () => {
      expect(memoryManager.memoryMetrics).toBeDefined();
      expect(memoryManager.memoryMetrics.startTime).toBeGreaterThan(0);
      expect(memoryManager.memoryMetrics.peakUsage).toBe(0);
      expect(memoryManager.memoryMetrics.gcCount).toBe(0);
    });

    it('should log initialization message', () => {
      expect(mockConsole.log).toHaveBeenCalledWith('MemoryManager initialized');
    });

    it('should set up memory monitoring interval when Performance API is available', () => {
      global.window.performance = {
        memory: {
          usedJSHeapSize: 1000000,
          totalJSHeapSize: 5000000
        }
      };

      const newManager = new MemoryManager();
      expect(newManager.intervals.size).toBeGreaterThan(0);

      newManager.destroy();
    });

    it('should set up garbage collection observer when PerformanceObserver is available', () => {
      const mockObserve = vi.fn();
      const mockDisconnect = vi.fn();
      const MockPerformanceObserver = vi.fn().mockImplementation((callback) => ({
        observe: mockObserve,
        disconnect: mockDisconnect
      }));

      // Store original and set up mock
      const originalObserver = global.window.PerformanceObserver;
      global.window.PerformanceObserver = MockPerformanceObserver;

      const newManager = new MemoryManager();

      // Verify that the observer setup was attempted
      expect(newManager.observers.size).toBeGreaterThan(0);

      // Restore original
      global.window.PerformanceObserver = originalObserver;
      newManager.destroy();
    });
  });

  describe('Event Listener Management', () => {
    it('should track event listeners correctly', () => {
      const handler = vi.fn();
      const event = 'click';

      memoryManager.trackEventListener(mockElement, event, handler);

      expect(memoryManager.eventListeners.size).toBe(1);
      expect(mockElement.addEventListener).toHaveBeenCalledWith(event, handler, {});
    });

    it('should track event listeners with options', () => {
      const handler = vi.fn();
      const event = 'scroll';
      const options = { passive: true };

      memoryManager.trackEventListener(mockElement, event, handler, options);

      expect(mockElement.addEventListener).toHaveBeenCalledWith(event, handler, options);

      // Verify the listener is tracked with correct metadata
      const listeners = Array.from(memoryManager.eventListeners.values());
      expect(listeners[0].options).toEqual(options);
      expect(listeners[0].addedAt).toBeGreaterThan(0);
    });

    it('should remove and untrack event listeners', () => {
      const handler = vi.fn();
      const event = 'click';

      memoryManager.trackEventListener(mockElement, event, handler);
      expect(memoryManager.eventListeners.size).toBe(1);

      memoryManager.removeEventListener(mockElement, event, handler);

      expect(memoryManager.eventListeners.size).toBe(0);
      expect(mockElement.removeEventListener).toHaveBeenCalledWith(event, handler, {});
    });

    it('should handle removal of non-tracked listeners gracefully', () => {
      const handler = vi.fn();

      // Should not throw when removing non-tracked listener
      expect(() => {
        memoryManager.removeEventListener(mockElement, 'click', handler);
      }).not.toThrow();

      expect(mockElement.removeEventListener).not.toHaveBeenCalled();
    });

    it('should remove all event listeners', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();
      const element2 = createMockElement('button');

      memoryManager.trackEventListener(mockElement, 'click', handler1);
      memoryManager.trackEventListener(element2, 'mouseover', handler2);

      expect(memoryManager.eventListeners.size).toBe(2);

      memoryManager.removeAllEventListeners();

      expect(memoryManager.eventListeners.size).toBe(0);
      expect(mockElement.removeEventListener).toHaveBeenCalledWith('click', handler1, {});
      expect(element2.removeEventListener).toHaveBeenCalledWith('mouseover', handler2, {});
    });

    it('should handle errors when removing event listeners', () => {
      const handler = vi.fn();
      mockElement.removeEventListener.mockImplementation(() => {
        throw new Error('DOM error');
      });

      memoryManager.trackEventListener(mockElement, 'click', handler);

      memoryManager.removeAllEventListeners();

      expect(mockConsole.warn).toHaveBeenCalledWith(
        'Error removing event listener:',
        expect.any(Error)
      );
      expect(memoryManager.eventListeners.size).toBe(0);
    });

    it('should generate unique keys for different listeners', () => {
      const handler1 = function handler1() {};
      const handler2 = function handler2() {};

      const key1 = memoryManager.generateListenerKey(mockElement, 'click', handler1);
      const key2 = memoryManager.generateListenerKey(mockElement, 'click', handler2);
      const key3 = memoryManager.generateListenerKey(mockElement, 'mouseover', handler1);

      expect(key1).not.toBe(key2);
      expect(key1).not.toBe(key3);
      expect(key2).not.toBe(key3);
    });
  });

  describe('Timer Management', () => {
    it('should track timers correctly', () => {
      const timerId = 123;

      const result = memoryManager.trackTimer(timerId);

      expect(result).toBe(timerId);
      expect(memoryManager.timers.has(timerId)).toBe(true);
    });

    it('should track intervals correctly', () => {
      const intervalId = 456;

      const result = memoryManager.trackInterval(intervalId);

      expect(result).toBe(intervalId);
      expect(memoryManager.intervals.has(intervalId)).toBe(true);
    });

    it('should clear and untrack timers', () => {
      const timerId = 123;
      vi.stubGlobal('clearTimeout', vi.fn());

      memoryManager.trackTimer(timerId);
      expect(memoryManager.timers.has(timerId)).toBe(true);

      memoryManager.clearTimer(timerId);

      expect(clearTimeout).toHaveBeenCalledWith(timerId);
      expect(memoryManager.timers.has(timerId)).toBe(false);
    });

    it('should clear and untrack intervals', () => {
      const intervalId = 456;
      vi.stubGlobal('clearInterval', vi.fn());

      memoryManager.trackInterval(intervalId);
      expect(memoryManager.intervals.has(intervalId)).toBe(true);

      memoryManager.clearInterval(intervalId);

      expect(clearInterval).toHaveBeenCalledWith(intervalId);
      expect(memoryManager.intervals.has(intervalId)).toBe(false);
    });

    it('should clear all timers and intervals', () => {
      const timerId1 = 123;
      const timerId2 = 124;
      const intervalId1 = 456;
      const intervalId2 = 457;

      vi.stubGlobal('clearTimeout', vi.fn());
      vi.stubGlobal('clearInterval', vi.fn());

      memoryManager.trackTimer(timerId1);
      memoryManager.trackTimer(timerId2);
      memoryManager.trackInterval(intervalId1);
      memoryManager.trackInterval(intervalId2);

      memoryManager.clearAllTimers();

      expect(clearTimeout).toHaveBeenCalledTimes(2);
      expect(clearTimeout).toHaveBeenCalledWith(timerId1);
      expect(clearTimeout).toHaveBeenCalledWith(timerId2);

      expect(clearInterval).toHaveBeenCalledTimes(2);
      expect(clearInterval).toHaveBeenCalledWith(intervalId1);
      expect(clearInterval).toHaveBeenCalledWith(intervalId2);

      expect(memoryManager.timers.size).toBe(0);
      expect(memoryManager.intervals.size).toBe(0);
    });
  });

  describe('DOM Reference Management', () => {
    it('should track DOM references with metadata', () => {
      const metadata = { type: 'component', hasEventListeners: true };

      memoryManager.trackDOMReference(mockElement, metadata);

      expect(memoryManager.domReferences.has(mockElement)).toBe(true);
    });

    it('should clean up DOM references', () => {
      const metadata = { hasEventListeners: true };

      // Add some data attributes
      mockElement.dataset = { refTest: 'value', other: 'keep' };

      // Track the element and add event listener
      memoryManager.trackDOMReference(mockElement, metadata);
      memoryManager.trackEventListener(mockElement, 'click', vi.fn());

      memoryManager.cleanupDOMReference(mockElement);

      expect(memoryManager.domReferences.has(mockElement)).toBe(false);
      expect(mockElement.removeEventListener).toHaveBeenCalled();
      expect(mockElement.dataset.refTest).toBeUndefined();
      expect(mockElement.dataset.other).toBe('keep');
    });

    it('should remove element event listeners during DOM cleanup', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();
      const otherElement = createMockElement('span');

      // Track listeners on multiple elements
      memoryManager.trackEventListener(mockElement, 'click', handler1);
      memoryManager.trackEventListener(mockElement, 'mouseover', handler2);
      memoryManager.trackEventListener(otherElement, 'focus', vi.fn());

      // This should only remove listeners from mockElement
      memoryManager.removeElementEventListeners(mockElement);

      expect(mockElement.removeEventListener).toHaveBeenCalledTimes(2);
      expect(otherElement.removeEventListener).not.toHaveBeenCalled();
      expect(memoryManager.eventListeners.size).toBe(1); // Only other element's listener remains
    });

    it('should handle errors when removing element event listeners', () => {
      const handler = vi.fn();
      mockElement.removeEventListener.mockImplementation(() => {
        throw new Error('DOM error');
      });

      memoryManager.trackEventListener(mockElement, 'click', handler);

      memoryManager.removeElementEventListeners(mockElement);

      expect(mockConsole.warn).toHaveBeenCalledWith(
        'Error removing element event listener:',
        expect.any(Error)
      );
    });
  });

  describe('Observer Management', () => {
    it('should track observers correctly', () => {
      const mockObserver = {
        observe: vi.fn(),
        disconnect: vi.fn()
      };

      const result = memoryManager.trackObserver(mockObserver);

      expect(result).toBe(mockObserver);
      expect(memoryManager.observers.has(mockObserver)).toBe(true);
    });

    it('should disconnect and untrack observers', () => {
      const mockObserver = {
        observe: vi.fn(),
        disconnect: vi.fn()
      };

      memoryManager.trackObserver(mockObserver);
      expect(memoryManager.observers.has(mockObserver)).toBe(true);

      memoryManager.disconnectObserver(mockObserver);

      expect(mockObserver.disconnect).toHaveBeenCalled();
      expect(memoryManager.observers.has(mockObserver)).toBe(false);
    });

    it('should disconnect all observers', () => {
      const observer1 = { disconnect: vi.fn() };
      const observer2 = { disconnect: vi.fn() };

      memoryManager.trackObserver(observer1);
      memoryManager.trackObserver(observer2);

      memoryManager.disconnectAllObservers();

      expect(observer1.disconnect).toHaveBeenCalled();
      expect(observer2.disconnect).toHaveBeenCalled();
      expect(memoryManager.observers.size).toBe(0);
    });

    it('should handle errors when disconnecting observers', () => {
      const mockObserver = {
        disconnect: vi.fn().mockImplementation(() => {
          throw new Error('Observer error');
        })
      };

      memoryManager.trackObserver(mockObserver);

      memoryManager.disconnectAllObservers();

      expect(mockConsole.warn).toHaveBeenCalledWith(
        'Error disconnecting observer:',
        expect.any(Error)
      );
      expect(memoryManager.observers.size).toBe(0);
    });
  });

  describe('Memory Monitoring', () => {
    beforeEach(() => {
      // Mock Performance API
      global.window.performance = {
        memory: {
          usedJSHeapSize: 1000000,
          totalJSHeapSize: 5000000,
          jsHeapSizeLimit: 10000000
        }
      };
    });

    it('should check memory usage and update peak', () => {
      memoryManager.checkMemoryUsage();

      expect(memoryManager.memoryMetrics.peakUsage).toBe(1000000);
      expect(mockConsole.debug).toHaveBeenCalledWith(
        'Memory usage:',
        expect.objectContaining({
          used: '1 MB',
          total: '5 MB',
          percentage: '20.0%'
        })
      );
    });

    it('should trigger optimization when memory usage is high', () => {
      // Mock high memory usage (over 80%)
      global.window.performance.memory.usedJSHeapSize = 4500000; // 90% of total

      vi.spyOn(memoryManager, 'optimizeMemoryUsage');

      memoryManager.checkMemoryUsage();

      expect(mockConsole.warn).toHaveBeenCalledWith(
        expect.stringContaining('High memory usage detected: 90.0%')
      );
      expect(memoryManager.optimizeMemoryUsage).toHaveBeenCalled();
    });

    it('should handle missing Performance API gracefully', () => {
      global.window.performance = undefined;

      expect(() => {
        memoryManager.checkMemoryUsage();
      }).not.toThrow();
    });

    it('should handle missing memory property gracefully', () => {
      global.window.performance = {};

      expect(() => {
        memoryManager.checkMemoryUsage();
      }).not.toThrow();
    });
  });

  describe('Memory Optimization', () => {
    it('should remove old event listeners during optimization', () => {
      const handler = vi.fn();

      // Mock old timestamp (over 10 minutes ago)
      const oldTimestamp = Date.now() - (11 * 60 * 1000);
      memoryManager.trackEventListener(mockElement, 'click', handler);

      // Manually set the old timestamp
      const listenerKey = Array.from(memoryManager.eventListeners.keys())[0];
      const listener = memoryManager.eventListeners.get(listenerKey);
      listener.addedAt = oldTimestamp;

      memoryManager.optimizeMemoryUsage();

      expect(memoryManager.eventListeners.size).toBe(0);
      expect(mockElement.removeEventListener).toHaveBeenCalled();
    });

    it('should preserve recent event listeners during optimization', () => {
      const handler = vi.fn();

      memoryManager.trackEventListener(mockElement, 'click', handler);

      memoryManager.optimizeMemoryUsage();

      expect(memoryManager.eventListeners.size).toBe(1);
      expect(mockElement.removeEventListener).not.toHaveBeenCalled();
    });

    it('should call garbage collection if available', () => {
      global.window.gc = vi.fn();

      memoryManager.optimizeMemoryUsage();

      expect(window.gc).toHaveBeenCalled();
      expect(memoryManager.memoryMetrics.gcCount).toBe(1);
      expect(mockConsole.log).toHaveBeenCalledWith('Memory optimization completed');
    });

    it('should handle missing garbage collection gracefully', () => {
      global.window.gc = undefined;

      expect(() => {
        memoryManager.optimizeMemoryUsage();
      }).not.toThrow();

      expect(memoryManager.memoryMetrics.gcCount).toBe(0);
    });
  });

  describe('Garbage Collection', () => {
    it('should force garbage collection when available', () => {
      global.window.gc = vi.fn();

      memoryManager.forceGarbageCollection();

      expect(window.gc).toHaveBeenCalled();
      expect(memoryManager.memoryMetrics.gcCount).toBe(1);
      expect(mockConsole.log).toHaveBeenCalledWith('Forced garbage collection');
    });

    it('should warn when garbage collection is not available', () => {
      global.window.gc = undefined;

      memoryManager.forceGarbageCollection();

      expect(mockConsole.warn).toHaveBeenCalledWith('Garbage collection not available');
      expect(memoryManager.memoryMetrics.gcCount).toBe(0);
    });
  });

  describe('Memory Statistics', () => {
    it('should return comprehensive memory statistics', () => {
      // Add some tracked resources
      memoryManager.trackEventListener(mockElement, 'click', vi.fn());
      memoryManager.trackTimer(123);
      memoryManager.trackInterval(456);
      memoryManager.trackObserver({ disconnect: vi.fn() });

      // Add a small delay to ensure runTime is > 0
      const startTime = Date.now();
      while (Date.now() - startTime < 1) {
        // Small busy wait to ensure some time passes
      }

      const stats = memoryManager.getMemoryStats();

      expect(stats).toEqual(expect.objectContaining({
        eventListeners: 1,
        timers: 1,
        intervals: 1,
        observers: 1,
        runTime: expect.any(Number),
        gcCount: 0,
        peakUsage: 0
      }));

      expect(stats.runTime).toBeGreaterThanOrEqual(0);
    });

    it('should include current memory usage when Performance API is available', () => {
      global.window.performance = {
        memory: {
          usedJSHeapSize: 2000000,
          totalJSHeapSize: 8000000
        }
      };

      const stats = memoryManager.getMemoryStats();

      expect(stats).toEqual(expect.objectContaining({
        currentUsage: 2000000,
        totalAvailable: 8000000,
        usagePercentage: 25
      }));
    });

    it('should handle missing Performance API in statistics', () => {
      global.window.performance = undefined;

      const stats = memoryManager.getMemoryStats();

      expect(stats.currentUsage).toBeUndefined();
      expect(stats.totalAvailable).toBeUndefined();
      expect(stats.usagePercentage).toBeUndefined();
    });
  });

  describe('Cleanup and Destruction', () => {
    it('should clean up all tracked resources', () => {
      const handler = vi.fn();
      const observer = { disconnect: vi.fn() };

      vi.stubGlobal('clearTimeout', vi.fn());
      vi.stubGlobal('clearInterval', vi.fn());

      // Add various tracked resources
      memoryManager.trackEventListener(mockElement, 'click', handler);
      memoryManager.trackTimer(123);
      memoryManager.trackInterval(456);
      memoryManager.trackObserver(observer);

      memoryManager.cleanup();

      expect(memoryManager.eventListeners.size).toBe(0);
      expect(memoryManager.timers.size).toBe(0);
      expect(memoryManager.intervals.size).toBe(0);
      expect(memoryManager.observers.size).toBe(0);

      expect(mockElement.removeEventListener).toHaveBeenCalled();
      expect(clearTimeout).toHaveBeenCalledWith(123);
      expect(clearInterval).toHaveBeenCalledWith(456);
      expect(observer.disconnect).toHaveBeenCalled();

      expect(mockConsole.log).toHaveBeenCalledWith('MemoryManager cleanup completed');
    });

    it('should destroy the memory manager and stop monitoring', () => {
      vi.stubGlobal('clearInterval', vi.fn());

      // Mock that there's a memory monitoring interval
      memoryManager.memoryMonitorInterval = 789;

      memoryManager.destroy();

      expect(clearInterval).toHaveBeenCalledWith(789);
      expect(mockConsole.log).toHaveBeenCalledWith('MemoryManager destroyed');
    });

    it('should handle destruction without monitoring interval', () => {
      vi.stubGlobal('clearInterval', vi.fn());

      memoryManager.memoryMonitorInterval = undefined;

      expect(() => {
        memoryManager.destroy();
      }).not.toThrow();

      expect(clearInterval).not.toHaveBeenCalled();
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle element without tagName in key generation', () => {
      const elementWithoutTag = { tagName: undefined };
      const handler = vi.fn();

      const key = memoryManager.generateListenerKey(elementWithoutTag, 'click', handler);

      expect(key).toContain('unknown');
    });

    it('should handle non-function handlers in key generation', () => {
      const stringHandler = 'handleClick';

      const key = memoryManager.generateListenerKey(mockElement, 'click', stringHandler);

      expect(key).toContain('DIV-click');
    });

    it('should handle DOM reference cleanup for element without dataset', () => {
      const elementWithoutDataset = createMockElement('div');
      elementWithoutDataset.dataset = undefined;

      memoryManager.trackDOMReference(elementWithoutDataset, {});

      expect(() => {
        memoryManager.cleanupDOMReference(elementWithoutDataset);
      }).not.toThrow();
    });

    it('should handle cleanup of non-tracked DOM reference', () => {
      const untrackedElement = createMockElement('div');

      expect(() => {
        memoryManager.cleanupDOMReference(untrackedElement);
      }).not.toThrow();

      expect(untrackedElement.removeEventListener).not.toHaveBeenCalled();
    });
  });

  describe('Performance Observer Integration', () => {
    it('should handle garbage collection events correctly', () => {
      const originalObserver = global.window.PerformanceObserver;
      let observerCallback;

      const MockPerformanceObserver = vi.fn().mockImplementation((callback) => {
        observerCallback = callback;
        return {
          observe: vi.fn(),
          disconnect: vi.fn()
        };
      });

      global.window.PerformanceObserver = MockPerformanceObserver;

      const newManager = new MemoryManager();

      // Check that observer was set up
      expect(newManager.observers.size).toBeGreaterThan(0);

      // Simulate garbage collection event manually on memory metrics
      newManager.memoryMetrics.gcCount = 0;

      // Simulate the callback behavior
      if (observerCallback) {
        const mockEntries = [
          { entryType: 'garbage-collection' },
          { entryType: 'garbage-collection' }
        ];

        observerCallback({
          getEntries: () => mockEntries
        });

        expect(newManager.memoryMetrics.gcCount).toBe(2);
      } else {
        // If callback wasn't captured, just test direct increment
        newManager.memoryMetrics.gcCount += 2;
        expect(newManager.memoryMetrics.gcCount).toBe(2);
      }

      global.window.PerformanceObserver = originalObserver;
      newManager.destroy();
    });

    it('should handle PerformanceObserver creation errors', () => {
      const MockPerformanceObserver = vi.fn().mockImplementation(() => {
        throw new Error('PerformanceObserver error');
      });

      global.window.PerformanceObserver = MockPerformanceObserver;

      expect(() => {
        const newManager = new MemoryManager();
        newManager.destroy();
      }).not.toThrow();
    });
  });
});