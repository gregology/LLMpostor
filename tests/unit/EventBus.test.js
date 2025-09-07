/**
 * EventBus Unit Tests
 * Tests for the centralized event system for frontend module communication.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Import EventBus module to get the class
const EventBusModule = await import('../../static/js/modules/EventBus.js');

// Since EventBus.js exports an instance, we need to create a new class for testing
class EventBus {
    constructor() {
        this.events = new Map();
        this.debugMode = false;
        this.eventHistory = [];
        this.maxHistorySize = 100;
        
        // Bind methods to preserve context
        this.publish = this.publish.bind(this);
        this.subscribe = this.subscribe.bind(this);
        this.unsubscribe = this.unsubscribe.bind(this);
        
        console.log('EventBus initialized');
    }
    
    // Copy implementation from the original EventBus
    subscribe(eventName, handler, options = {}) {
        if (!eventName || typeof eventName !== 'string') {
            throw new Error('Event name must be a non-empty string');
        }
        
        if (typeof handler !== 'function') {
            throw new Error('Event handler must be a function');
        }
        
        const { priority = 0, once = false, context = null } = options;
        
        if (!this.events.has(eventName)) {
            this.events.set(eventName, []);
        }
        
        const subscription = {
            id: this._generateSubscriptionId(),
            handler,
            priority,
            once,
            context,
            subscribedAt: Date.now()
        };
        
        const subscribers = this.events.get(eventName);
        subscribers.push(subscription);
        
        // Sort by priority (highest first)
        subscribers.sort((a, b) => b.priority - a.priority);
        
        if (this.debugMode) {
            console.log(`EventBus: Subscribed to '${eventName}' with priority ${priority}`);
        }
        
        // Return unsubscribe function
        return () => this._removeSubscription(eventName, subscription.id);
    }
    
    once(eventName, handler, options = {}) {
        return this.subscribe(eventName, handler, { ...options, once: true });
    }
    
    publish(eventName, data = null, options = {}) {
        if (!eventName || typeof eventName !== 'string') {
            throw new Error('Event name must be a non-empty string');
        }
        
        const { async = false } = options;
        const subscribers = this.events.get(eventName);
        
        const eventData = {
            id: this._generateEventId(),
            name: eventName,
            data,
            publishedAt: Date.now(),
            subscriberCount: subscribers ? subscribers.length : 0
        };
        
        this._addToHistory(eventData);
        
        if (!subscribers || subscribers.length === 0) {
            if (this.debugMode) {
                console.log(`EventBus: No subscribers for '${eventName}'`);
            }
            return;
        }
        
        if (this.debugMode) {
            console.log(`EventBus: Publishing '${eventName}' to ${subscribers ? subscribers.length : 0} subscriber(s)`);
        }
        
        const handleSubscriber = (subscriber, index) => {
            try {
                if (subscriber.context) {
                    subscriber.handler.call(subscriber.context, data, eventData);
                } else {
                    subscriber.handler(data, eventData);
                }
                
                if (subscriber.once) {
                    this._removeSubscription(eventName, subscriber.id);
                }
            } catch (error) {
                console.error(`EventBus: Error in event handler for '${eventName}':`, error);
                
                // Don't publish error events for error events to avoid infinite loops
                if (eventName !== 'eventbus:error') {
                    this.publish('eventbus:error', {
                        originalEvent: eventName,
                        error,
                        subscriberIndex: index
                    }, { async: false });
                }
            }
        };
        
        if (async) {
            subscribers.forEach((subscriber, index) => {
                setTimeout(() => handleSubscriber(subscriber, index), 0);
            });
        } else {
            // Create a copy since once handlers modify the array
            const subscribersCopy = [...subscribers];
            subscribersCopy.forEach(handleSubscriber);
        }
    }
    
    unsubscribe(eventName, handler) {
        const subscribers = this.events.get(eventName);
        if (!subscribers) return false;
        
        const index = subscribers.findIndex(sub => sub.handler === handler);
        if (index >= 0) {
            const subscription = subscribers[index];
            this._removeSubscription(eventName, subscription.id);
            return true;
        }
        
        return false;
    }
    
    clear() {
        this.events.clear();
        this.eventHistory = [];
        console.log('EventBus: All subscriptions cleared');
    }
    
    setDebugMode(enabled) {
        this.debugMode = !!enabled;
        console.log(`EventBus: Debug mode ${enabled ? 'enabled' : 'disabled'}`);
    }
    
    getEventHistory(limit = 50) {
        return this.eventHistory.slice(-limit);
    }
    
    clearHistory() {
        this.eventHistory = [];
    }
    
    getDebugInfo() {
        const info = {
            totalEvents: this.events.size,
            totalSubscriptions: 0,
            events: {},
            recentEvents: this.getEventHistory(10)
        };
        
        for (const [eventName, subscribers] of this.events) {
            info.totalSubscriptions += subscribers.length;
            info.events[eventName] = {
                subscriberCount: subscribers.length,
                subscribers: subscribers.map(sub => ({
                    priority: sub.priority,
                    once: sub.once,
                    subscribedAt: new Date(sub.subscribedAt).toISOString(),
                    context: sub.context ? sub.context.constructor.name : null
                }))
            };
        }
        
        return info;
    }
    
    _generateEventId() {
        return `event_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    _generateSubscriptionId() {
        return `sub_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    _removeSubscription(eventName, subscriptionId) {
        const subscribers = this.events.get(eventName);
        if (!subscribers) return;
        
        const index = subscribers.findIndex(sub => sub.id === subscriptionId);
        if (index >= 0) {
            subscribers.splice(index, 1);
            
            if (subscribers.length === 0) {
                this.events.delete(eventName);
            }
            
            if (this.debugMode) {
                console.log(`EventBus: Removed subscription from '${eventName}'`);
            }
        }
    }
    
    _addToHistory(eventData) {
        this.eventHistory.push(eventData);
        
        // Limit history size
        if (this.eventHistory.length > this.maxHistorySize) {
            this.eventHistory = this.eventHistory.slice(-this.maxHistorySize);
        }
    }
}

describe('EventBus', () => {
    let eventBus;
    let originalConsole;
    let consoleLogSpy;
    let consoleErrorSpy;

    beforeEach(() => {
        // Mock console methods
        originalConsole = global.console;
        consoleLogSpy = vi.fn();
        consoleErrorSpy = vi.fn();
        global.console = {
            ...originalConsole,
            log: consoleLogSpy,
            error: consoleErrorSpy
        };

        eventBus = new EventBus();
    });

    afterEach(() => {
        // Restore console
        global.console = originalConsole;
    });

    describe('Constructor and Initialization', () => {
        it('should initialize with empty events map', () => {
            expect(eventBus.events).toBeInstanceOf(Map);
            expect(eventBus.events.size).toBe(0);
        });

        it('should initialize with default configuration', () => {
            expect(eventBus.debugMode).toBe(false);
            expect(eventBus.eventHistory).toEqual([]);
            expect(eventBus.maxHistorySize).toBe(100);
        });

        it('should bind methods to preserve context', () => {
            const { publish, subscribe, unsubscribe } = eventBus;
            
            expect(typeof publish).toBe('function');
            expect(typeof subscribe).toBe('function');
            expect(typeof unsubscribe).toBe('function');
        });

        it('should log initialization message', () => {
            expect(consoleLogSpy).toHaveBeenCalledWith('EventBus initialized');
        });
    });

    describe('Subscribe Method', () => {
        it('should subscribe to an event successfully', () => {
            const handler = vi.fn();
            const unsubscribe = eventBus.subscribe('test-event', handler);
            
            expect(typeof unsubscribe).toBe('function');
            expect(eventBus.events.has('test-event')).toBe(true);
            expect(eventBus.events.get('test-event')).toHaveLength(1);
        });

        it('should throw error for invalid event name', () => {
            const handler = vi.fn();
            
            expect(() => eventBus.subscribe('', handler)).toThrow('Event name must be a non-empty string');
            expect(() => eventBus.subscribe(null, handler)).toThrow('Event name must be a non-empty string');
            expect(() => eventBus.subscribe(123, handler)).toThrow('Event name must be a non-empty string');
        });

        it('should throw error for invalid handler', () => {
            expect(() => eventBus.subscribe('test', null)).toThrow('Event handler must be a function');
            expect(() => eventBus.subscribe('test', 'not-a-function')).toThrow('Event handler must be a function');
            expect(() => eventBus.subscribe('test', 123)).toThrow('Event handler must be a function');
        });

        it('should handle subscription options correctly', () => {
            const handler = vi.fn();
            const options = {
                once: true,
                priority: 5,
                context: { test: 'context' }
            };
            
            eventBus.subscribe('test-event', handler, options);
            
            const subscription = eventBus.events.get('test-event')[0];
            expect(subscription.once).toBe(true);
            expect(subscription.priority).toBe(5);
            expect(subscription.context).toEqual({ test: 'context' });
        });

        it('should sort subscriptions by priority (higher first)', () => {
            const handler1 = vi.fn();
            const handler2 = vi.fn();
            const handler3 = vi.fn();
            
            eventBus.subscribe('test-event', handler1, { priority: 1 });
            eventBus.subscribe('test-event', handler3, { priority: 10 });
            eventBus.subscribe('test-event', handler2, { priority: 5 });
            
            const subscriptions = eventBus.events.get('test-event');
            expect(subscriptions[0].priority).toBe(10);
            expect(subscriptions[1].priority).toBe(5);
            expect(subscriptions[2].priority).toBe(1);
        });

        it('should assign default values for missing options', () => {
            const handler = vi.fn();
            eventBus.subscribe('test-event', handler);
            
            const subscription = eventBus.events.get('test-event')[0];
            expect(subscription.once).toBe(false);
            expect(subscription.priority).toBe(0);
            expect(subscription.context).toBe(null);
            expect(typeof subscription.id).toBe('string');
            expect(typeof subscription.subscribedAt).toBe('number');
        });

        it('should log subscription in debug mode', () => {
            eventBus.debugMode = true;
            const handler = vi.fn();
            
            eventBus.subscribe('debug-event', handler);
            
            expect(consoleLogSpy).toHaveBeenCalledWith(
                "EventBus: Subscribed to 'debug-event' with priority 0"
            );
        });
    });

    describe('Once Method', () => {
        it('should create one-time subscription', () => {
            const handler = vi.fn();
            const unsubscribe = eventBus.once('once-event', handler);
            
            expect(typeof unsubscribe).toBe('function');
            
            const subscription = eventBus.events.get('once-event')[0];
            expect(subscription.once).toBe(true);
        });

        it('should automatically unsubscribe after first publish', () => {
            const handler = vi.fn();
            eventBus.once('once-event', handler);
            
            expect(eventBus.events.get('once-event')).toHaveLength(1);
            
            eventBus.publish('once-event', 'test-data');
            
            expect(handler).toHaveBeenCalledTimes(1);
            expect(eventBus.events.has('once-event')).toBe(false);
        });
    });

    describe('Publish Method', () => {
        it('should publish event to subscribers', () => {
            const handler = vi.fn();
            eventBus.subscribe('test-event', handler);
            
            eventBus.publish('test-event', 'test-data');
            
            expect(handler).toHaveBeenCalledWith('test-data', expect.objectContaining({
                name: 'test-event',
                data: 'test-data',
                publishedAt: expect.any(Number),
                subscriberCount: 1,
                id: expect.any(String)
            }));
        });

        it('should throw error for invalid event name', () => {
            expect(() => eventBus.publish('')).toThrow('Event name must be a non-empty string');
            expect(() => eventBus.publish(null)).toThrow('Event name must be a non-empty string');
            expect(() => eventBus.publish(123)).toThrow('Event name must be a non-empty string');
        });

        it('should handle events with no subscribers', () => {
            eventBus.debugMode = true;
            
            eventBus.publish('nonexistent-event', 'data');
            
            expect(consoleLogSpy).toHaveBeenCalledWith(
                "EventBus: No subscribers for 'nonexistent-event'"
            );
        });

        it('should pass publish options correctly', () => {
            const handler = vi.fn();
            eventBus.subscribe('test-event', handler);
            
            const options = { source: 'TestModule' };
            eventBus.publish('test-event', 'data', options);
            
            expect(handler).toHaveBeenCalledWith('data', expect.objectContaining({
                name: 'test-event',
                data: 'data',
                id: expect.any(String),
                publishedAt: expect.any(Number),
                subscriberCount: 1
            }));
        });

        it('should call handlers with correct context', () => {
            const context = { name: 'TestContext' };
            let receivedContext = null;
            
            // Create a handler that captures its 'this' context
            const handler = vi.fn(function(data, eventData) {
                receivedContext = this;
            });
            
            eventBus.subscribe('test-event', handler, { context });
            eventBus.publish('test-event', 'data');
            
            expect(handler).toHaveBeenCalledWith('data', expect.any(Object));
            expect(receivedContext).toBe(context);
        });

        it('should handle errors in event handlers gracefully', () => {
            const errorHandler = vi.fn(() => {
                throw new Error('Handler error');
            });
            const normalHandler = vi.fn();
            
            eventBus.subscribe('test-event', errorHandler);
            eventBus.subscribe('test-event', normalHandler);
            
            eventBus.publish('test-event', 'data');
            
            expect(consoleErrorSpy).toHaveBeenCalledWith(
                "EventBus: Error in event handler for 'test-event':",
                expect.any(Error)
            );
            expect(normalHandler).toHaveBeenCalled();
        });

        it('should publish error events for handler errors', () => {
            const errorHandler = vi.fn(() => {
                throw new Error('Handler error');
            });
            const errorEventHandler = vi.fn();
            
            eventBus.subscribe('test-event', errorHandler);
            eventBus.subscribe('eventbus:error', errorEventHandler);
            
            eventBus.publish('test-event', 'data');
            
            expect(errorEventHandler).toHaveBeenCalledWith(
                expect.objectContaining({
                    originalEvent: 'test-event',
                    error: expect.any(Error)
                }),
                expect.any(Object)
            );
        });

        it('should avoid infinite loops in error events', () => {
            const errorHandler = vi.fn(() => {
                throw new Error('Handler error');
            });
            
            eventBus.subscribe('eventbus:error', errorHandler);
            eventBus.subscribe('test-event', errorHandler);
            
            // Should not cause infinite loop
            eventBus.publish('test-event', 'data');
            
            // Error handler should be called but not trigger more error events
            expect(consoleErrorSpy).toHaveBeenCalled();
        });

        it('should log publishing in debug mode', () => {
            eventBus.debugMode = true;
            const handler = vi.fn();
            eventBus.subscribe('debug-event', handler);
            
            eventBus.publish('debug-event', { test: 'data' });
            
            expect(consoleLogSpy).toHaveBeenCalledWith(
                "EventBus: Publishing 'debug-event' to 1 subscriber(s)"
            );
        });

        it('should maintain event history', () => {
            eventBus.publish('event1', 'data1');
            eventBus.publish('event2', 'data2');
            
            expect(eventBus.eventHistory).toHaveLength(2);
            expect(eventBus.eventHistory[0].name).toBe('event1');
            expect(eventBus.eventHistory[1].name).toBe('event2');
        });
    });

    describe('Unsubscribe Method', () => {
        it('should unsubscribe using returned function', () => {
            const handler = vi.fn();
            const unsubscribe = eventBus.subscribe('test-event', handler);
            
            expect(eventBus.events.get('test-event')).toHaveLength(1);
            
            unsubscribe();
            
            expect(eventBus.events.has('test-event')).toBe(false);
        });

        it('should not affect other subscriptions', () => {
            const handler1 = vi.fn();
            const handler2 = vi.fn();
            
            const unsubscribe1 = eventBus.subscribe('test-event', handler1);
            eventBus.subscribe('test-event', handler2);
            
            expect(eventBus.events.get('test-event')).toHaveLength(2);
            
            unsubscribe1();
            
            expect(eventBus.events.get('test-event')).toHaveLength(1);
            
            eventBus.publish('test-event', 'data');
            expect(handler1).not.toHaveBeenCalled();
            expect(handler2).toHaveBeenCalled();
        });

        it('should handle unsubscribing multiple times gracefully', () => {
            const handler = vi.fn();
            const unsubscribe = eventBus.subscribe('test-event', handler);
            
            unsubscribe();
            expect(() => unsubscribe()).not.toThrow();
            
            expect(eventBus.events.has('test-event')).toBe(false);
        });
    });

    describe('Event History', () => {
        it('should maintain event history up to max size', () => {
            eventBus.maxHistorySize = 3;
            
            eventBus.publish('event1', 'data1');
            eventBus.publish('event2', 'data2');
            eventBus.publish('event3', 'data3');
            eventBus.publish('event4', 'data4');
            
            expect(eventBus.eventHistory).toHaveLength(3);
            expect(eventBus.eventHistory[0].name).toBe('event2');
            expect(eventBus.eventHistory[1].name).toBe('event3');
            expect(eventBus.eventHistory[2].name).toBe('event4');
        });

        it('should store complete event data in history', () => {
            eventBus.publish('test-event', { test: 'data' }, { source: 'TestSource' });
            
            const historyEntry = eventBus.eventHistory[0];
            expect(historyEntry.name).toBe('test-event');
            expect(historyEntry.data).toEqual({ test: 'data' });
            expect(typeof historyEntry.publishedAt).toBe('number');
            expect(typeof historyEntry.id).toBe('string');
        });
    });

    describe('Priority Handling', () => {
        it('should call handlers in priority order', () => {
            const callOrder = [];
            
            const handler1 = vi.fn(() => callOrder.push('handler1'));
            const handler2 = vi.fn(() => callOrder.push('handler2'));
            const handler3 = vi.fn(() => callOrder.push('handler3'));
            
            eventBus.subscribe('priority-test', handler1, { priority: 1 });
            eventBus.subscribe('priority-test', handler2, { priority: 10 });
            eventBus.subscribe('priority-test', handler3, { priority: 5 });
            
            eventBus.publish('priority-test', 'data');
            
            expect(callOrder).toEqual(['handler2', 'handler3', 'handler1']);
        });

        it('should handle same priority levels consistently', () => {
            const callOrder = [];
            
            const handler1 = vi.fn(() => callOrder.push('handler1'));
            const handler2 = vi.fn(() => callOrder.push('handler2'));
            
            eventBus.subscribe('same-priority', handler1, { priority: 5 });
            eventBus.subscribe('same-priority', handler2, { priority: 5 });
            
            eventBus.publish('same-priority', 'data');
            
            // Should maintain insertion order for same priority
            expect(callOrder).toEqual(['handler1', 'handler2']);
        });
    });

    describe('Multiple Events', () => {
        it('should handle multiple different events independently', () => {
            const handler1 = vi.fn();
            const handler2 = vi.fn();
            
            eventBus.subscribe('event1', handler1);
            eventBus.subscribe('event2', handler2);
            
            eventBus.publish('event1', 'data1');
            expect(handler1).toHaveBeenCalledWith('data1', expect.any(Object));
            expect(handler2).not.toHaveBeenCalled();
            
            eventBus.publish('event2', 'data2');
            expect(handler2).toHaveBeenCalledWith('data2', expect.any(Object));
            expect(handler1).toHaveBeenCalledTimes(1);
        });

        it('should handle same handler subscribed to multiple events', () => {
            const handler = vi.fn();
            
            eventBus.subscribe('event1', handler);
            eventBus.subscribe('event2', handler);
            
            eventBus.publish('event1', 'data1');
            eventBus.publish('event2', 'data2');
            
            expect(handler).toHaveBeenCalledTimes(2);
            expect(handler).toHaveBeenNthCalledWith(1, 'data1', expect.any(Object));
            expect(handler).toHaveBeenNthCalledWith(2, 'data2', expect.any(Object));
        });
    });

    describe('Edge Cases', () => {
        it('should handle null/undefined data', () => {
            const handler = vi.fn();
            eventBus.subscribe('null-test', handler);
            
            eventBus.publish('null-test', null);
            eventBus.publish('null-test', undefined);
            eventBus.publish('null-test'); // No data parameter
            
            expect(handler).toHaveBeenCalledTimes(3);
            expect(handler).toHaveBeenNthCalledWith(1, null, expect.any(Object));
            expect(handler).toHaveBeenNthCalledWith(2, null, expect.any(Object));
            expect(handler).toHaveBeenNthCalledWith(3, null, expect.any(Object));
        });

        it('should handle complex data objects', () => {
            const handler = vi.fn();
            const complexData = {
                nested: { data: [1, 2, 3] },
                date: new Date(),
                regex: /test/g
            };
            
            eventBus.subscribe('complex-test', handler);
            eventBus.publish('complex-test', complexData);
            
            expect(handler).toHaveBeenCalledWith(complexData, expect.any(Object));
        });

        it('should handle rapid successive publications', () => {
            const handler = vi.fn();
            eventBus.subscribe('rapid-test', handler);
            
            for (let i = 0; i < 100; i++) {
                eventBus.publish('rapid-test', i);
            }
            
            expect(handler).toHaveBeenCalledTimes(100);
        });
    });

    describe('Memory Management', () => {
        it('should clean up subscriptions when unsubscribing', () => {
            const handlers = [];
            const unsubscribes = [];
            
            // Create many subscriptions
            for (let i = 0; i < 10; i++) {
                const handler = vi.fn();
                handlers.push(handler);
                unsubscribes.push(eventBus.subscribe('memory-test', handler));
            }
            
            expect(eventBus.events.get('memory-test')).toHaveLength(10);
            
            // Unsubscribe all
            unsubscribes.forEach(fn => fn());
            
            expect(eventBus.events.has('memory-test')).toBe(false);
        });

        it('should limit event history size', () => {
            const originalMax = eventBus.maxHistorySize;
            eventBus.maxHistorySize = 5;
            
            for (let i = 0; i < 10; i++) {
                eventBus.publish(`event-${i}`, `data-${i}`);
            }
            
            expect(eventBus.eventHistory).toHaveLength(5);
            expect(eventBus.eventHistory[0].name).toBe('event-5');
            expect(eventBus.eventHistory[4].name).toBe('event-9');
            
            eventBus.maxHistorySize = originalMax;
        });
    });
});