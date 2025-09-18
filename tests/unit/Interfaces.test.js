/**
 * Interface Contract Tests
 *
 * Tests to validate that interface contracts are maintained and that
 * concrete implementations properly follow the defined interfaces.
 * These tests ensure type safety and consistent behavior across modules.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setupMinimalDOM, createMockElement } from '../helpers/domMocks.js';

// Import interface classes
import { IModule, IEventModule, IServiceModule } from '../../static/js/interfaces/IModule.js';
import {
    ISocketModule,
    IUIModule,
    IGameStateModule,
    ITimerModule
} from '../../static/js/interfaces/IGameModule.js';

// Import concrete implementations
const ErrorDisplayManager = (await import('../../static/js/modules/ErrorDisplayManager.js')).default;
const EventManager = (await import('../../static/js/modules/EventManager.js')).default;

describe('Interface Contract Tests', () => {
    let mockEventBus;
    let mockServiceContainer;

    beforeEach(() => {
        setupMinimalDOM();

        // Mock EventBus
        mockEventBus = {
            subscribe: vi.fn(() => vi.fn()), // Returns unsubscribe function
            publish: vi.fn(),
            clear: vi.fn(),
            getEventNames: vi.fn(() => [])
        };

        // Mock ServiceContainer
        mockServiceContainer = {
            get: vi.fn(),
            has: vi.fn(() => false),
            register: vi.fn(),
            getAll: vi.fn(() => ({}))
        };
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('IModule Base Interface', () => {
        let module;

        beforeEach(() => {
            module = new IModule('TestModule');
        });

        it('should have required base properties', () => {
            expect(module.name).toBe('TestModule');
            expect(module.initialized).toBe(false);
            expect(module.destroyed).toBe(false);
            expect(module._initTime).toBe(null);
            expect(module._destroyTime).toBe(null);
        });

        it('should implement initialization lifecycle', () => {
            expect(module.initialized).toBe(false);

            module.initialize();

            expect(module.initialized).toBe(true);
            expect(module._initTime).toBeTypeOf('number');
            expect(module.destroyed).toBe(false);
        });

        it('should be idempotent for multiple initializations', () => {
            const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

            module.initialize();
            const firstInitTime = module._initTime;

            module.initialize(); // Second call

            expect(consoleSpy).toHaveBeenCalledWith('Module TestModule already initialized');
            expect(module._initTime).toBe(firstInitTime); // Should not change

            consoleSpy.mockRestore();
        });

        it('should implement destruction lifecycle', () => {
            module.initialize();
            expect(module.destroyed).toBe(false);

            module.destroy();

            expect(module.destroyed).toBe(true);
            expect(module._destroyTime).toBeTypeOf('number');
        });

        it('should be idempotent for multiple destructions', () => {
            const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

            module.initialize();
            module.destroy();
            const firstDestroyTime = module._destroyTime;

            module.destroy(); // Second call

            expect(consoleSpy).toHaveBeenCalledWith('Module TestModule already destroyed');
            expect(module._destroyTime).toBe(firstDestroyTime); // Should not change

            consoleSpy.mockRestore();
        });

        it('should implement health check', () => {
            expect(module.healthCheck()).toBe(false); // Not initialized

            module.initialize();
            expect(module.healthCheck()).toBe(true); // Initialized and not destroyed

            module.destroy();
            expect(module.healthCheck()).toBe(false); // Destroyed
        });

        it('should provide status information', () => {
            module.initialize();
            const status = module.getStatus();

            expect(status).toHaveProperty('name', 'TestModule');
            expect(status).toHaveProperty('initialized', true);
            expect(status).toHaveProperty('destroyed', false);
            expect(status).toHaveProperty('healthy', true);
            expect(status).toHaveProperty('initTime');
            expect(status).toHaveProperty('destroyTime');
            expect(status).toHaveProperty('uptime');
            expect(status.uptime).toBeTypeOf('number');
        });

        it('should implement reset functionality', () => {
            module.initialize();
            module.destroy();

            expect(module.initialized).toBe(true);
            expect(module.destroyed).toBe(true);

            module.reset();

            expect(module.initialized).toBe(true);
            expect(module.destroyed).toBe(false);
            expect(module.healthCheck()).toBe(true);
        });
    });

    describe('IEventModule Interface', () => {
        let eventModule;

        beforeEach(() => {
            eventModule = new IEventModule('TestEventModule', mockEventBus);
        });

        it('should extend IModule with event capabilities', () => {
            expect(eventModule).toBeInstanceOf(IModule);
            expect(eventModule.eventBus).toBe(mockEventBus);
            expect(eventModule._subscriptions).toEqual([]);
        });

        it('should implement event subscription tracking', () => {
            const handler = vi.fn();
            const unsubscribeFn = vi.fn();
            mockEventBus.subscribe.mockReturnValue(unsubscribeFn);

            const returnedUnsub = eventModule.subscribe('test:event', handler, { priority: 1 });

            expect(mockEventBus.subscribe).toHaveBeenCalledWith('test:event', handler, {
                priority: 1,
                context: eventModule
            });
            expect(returnedUnsub).toBe(unsubscribeFn);
            expect(eventModule._subscriptions).toHaveLength(1);
            expect(eventModule._subscriptions[0]).toEqual({
                eventName: 'test:event',
                unsubscribe: unsubscribeFn
            });
        });

        it('should require EventBus for subscription', () => {
            const moduleWithoutBus = new IEventModule('Test', null);

            expect(() => {
                moduleWithoutBus.subscribe('test', vi.fn());
            }).toThrow('Module Test does not have access to EventBus');
        });

        it('should implement event publishing', () => {
            eventModule.publish('test:event', { data: 'test' }, { urgent: true });

            expect(mockEventBus.publish).toHaveBeenCalledWith('test:event', { data: 'test' }, {
                urgent: true,
                source: 'TestEventModule'
            });
        });

        it('should require EventBus for publishing', () => {
            const moduleWithoutBus = new IEventModule('Test', null);

            expect(() => {
                moduleWithoutBus.publish('test', {});
            }).toThrow('Module Test does not have access to EventBus');
        });

        it('should clean up subscriptions on destroy', () => {
            const unsubscribe1 = vi.fn();
            const unsubscribe2 = vi.fn();
            mockEventBus.subscribe.mockReturnValueOnce(unsubscribe1).mockReturnValueOnce(unsubscribe2);

            eventModule.subscribe('event1', vi.fn());
            eventModule.subscribe('event2', vi.fn());

            expect(eventModule._subscriptions).toHaveLength(2);

            eventModule.destroy();

            expect(unsubscribe1).toHaveBeenCalledTimes(1);
            expect(unsubscribe2).toHaveBeenCalledTimes(1);
            expect(eventModule._subscriptions).toEqual([]);
        });

        it('should handle subscription cleanup errors gracefully', () => {
            const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
            const faultyUnsubscribe = vi.fn(() => { throw new Error('Cleanup error'); });
            mockEventBus.subscribe.mockReturnValue(faultyUnsubscribe);

            eventModule.subscribe('event', vi.fn());
            eventModule.destroy();

            expect(faultyUnsubscribe).toHaveBeenCalled();
            expect(consoleSpy).toHaveBeenCalledWith(
                'Error unsubscribing from event in module TestEventModule:',
                expect.any(Error)
            );

            consoleSpy.mockRestore();
        });
    });

    describe('IServiceModule Interface', () => {
        let serviceModule;

        beforeEach(() => {
            serviceModule = new IServiceModule('TestServiceModule', mockEventBus, mockServiceContainer);
        });

        it('should extend IEventModule with service capabilities', () => {
            expect(serviceModule).toBeInstanceOf(IEventModule);
            expect(serviceModule.serviceContainer).toBe(mockServiceContainer);
            expect(serviceModule._dependencies).toEqual([]);
        });

        it('should implement service dependency retrieval', () => {
            const mockService = { name: 'TestService' };
            mockServiceContainer.get.mockReturnValue(mockService);

            const service = serviceModule.getService('TestService');

            expect(mockServiceContainer.get).toHaveBeenCalledWith('TestService');
            expect(service).toBe(mockService);
            expect(serviceModule._dependencies).toContain('TestService');
        });

        it('should require ServiceContainer for service access', () => {
            const moduleWithoutContainer = new IServiceModule('Test', mockEventBus, null);

            expect(() => {
                moduleWithoutContainer.getService('TestService');
            }).toThrow('Module Test does not have access to ServiceContainer');
        });

        it('should check service availability', () => {
            mockServiceContainer.has.mockReturnValue(true);

            expect(serviceModule.hasService('TestService')).toBe(true);
            expect(mockServiceContainer.has).toHaveBeenCalledWith('TestService');

            const moduleWithoutContainer = new IServiceModule('Test', mockEventBus, null);
            expect(moduleWithoutContainer.hasService('TestService')).toBeFalsy();
        });

        it('should track and report dependencies', () => {
            const mockService1 = { name: 'Service1' };
            const mockService2 = { name: 'Service2' };
            mockServiceContainer.get
                .mockReturnValueOnce(mockService1)
                .mockReturnValueOnce(mockService2);

            serviceModule.getService('Service1');
            serviceModule.getService('Service2');

            const dependencies = serviceModule.getDependencies();
            expect(dependencies).toEqual(['Service1', 'Service2']);
        });

        it('should implement enhanced health check with dependency health', () => {
            const healthyService = { healthCheck: vi.fn(() => true) };
            const unhealthyService = { healthCheck: vi.fn(() => false) };

            serviceModule.initialize();

            // Test with healthy dependency
            serviceModule._dependencies = ['HealthyService'];
            mockServiceContainer.get.mockReturnValue(healthyService);
            expect(serviceModule.healthCheck()).toBe(true);

            // Test with unhealthy dependency
            serviceModule._dependencies = ['UnhealthyService'];
            mockServiceContainer.get.mockReturnValue(unhealthyService);
            expect(serviceModule.healthCheck()).toBe(false);

            // Test with service without health check
            const serviceWithoutHealth = { name: 'NoHealth' };
            serviceModule._dependencies = ['NoHealthService'];
            mockServiceContainer.get.mockReturnValue(serviceWithoutHealth);
            expect(serviceModule.healthCheck()).toBe(true); // Should pass
        });

        it('should provide enhanced status with dependency information', () => {
            const healthyService = { healthCheck: vi.fn(() => true) };
            serviceModule.initialize();
            serviceModule._dependencies = ['TestDep'];
            mockServiceContainer.get.mockReturnValue(healthyService);

            const status = serviceModule.getStatus();

            expect(status).toHaveProperty('dependencies', ['TestDep']);
            expect(status).toHaveProperty('dependenciesHealthy', true);
            expect(status.name).toBe('TestServiceModule');
            expect(status.healthy).toBe(true);
        });
    });

    describe('ISocketModule Interface', () => {
        let socketModule;

        beforeEach(() => {
            socketModule = new ISocketModule('TestSocketModule', mockEventBus, mockServiceContainer);
        });

        it('should extend IServiceModule with socket capabilities', () => {
            expect(socketModule).toBeInstanceOf(IServiceModule);
            expect(socketModule._socketHandlers).toBeInstanceOf(Map);
        });

        it('should register socket event handlers', () => {
            const handler = vi.fn();

            socketModule.onSocket('test:event', handler);

            expect(socketModule._socketHandlers.get('test:event')).toBe(handler);
        });

        it('should warn on duplicate handler registration', () => {
            const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
            const handler1 = vi.fn();
            const handler2 = vi.fn();

            socketModule.onSocket('test:event', handler1);
            socketModule.onSocket('test:event', handler2);

            expect(consoleSpy).toHaveBeenCalledWith(
                "Socket handler for 'test:event' already registered in module TestSocketModule"
            );
            expect(socketModule._socketHandlers.get('test:event')).toBe(handler2); // Should be replaced

            consoleSpy.mockRestore();
        });

        it('should require concrete implementation of emitSocket', () => {
            expect(() => {
                socketModule.emitSocket('test', {});
            }).toThrow('emitSocket must be implemented by concrete module');
        });

        it('should provide socket handlers access', () => {
            const handler = vi.fn();
            socketModule.onSocket('test:event', handler);

            const handlers = socketModule.getSocketHandlers();

            expect(handlers).toBeInstanceOf(Map);
            expect(handlers.get('test:event')).toBe(handler);
            expect(handlers).not.toBe(socketModule._socketHandlers); // Should be a copy
        });

        it('should clean up socket handlers on destroy', () => {
            socketModule.onSocket('event1', vi.fn());
            socketModule.onSocket('event2', vi.fn());

            expect(socketModule._socketHandlers.size).toBe(2);

            socketModule.destroy();

            expect(socketModule._socketHandlers.size).toBe(0);
        });
    });

    describe('IUIModule Interface', () => {
        let uiModule;

        beforeEach(() => {
            uiModule = new IUIModule('TestUIModule', mockEventBus, mockServiceContainer);
        });

        it('should extend IServiceModule with UI capabilities', () => {
            expect(uiModule).toBeInstanceOf(IServiceModule);
            expect(uiModule._elements).toBeInstanceOf(Map);
            expect(uiModule._eventListeners).toEqual([]);
        });

        it('should cache DOM elements', () => {
            const testElement = createMockElement('div', { id: 'test-element' });
            const querySelectorSpy = vi.spyOn(document, 'querySelector').mockReturnValue(testElement);

            const element = uiModule.getElement('test', '#test-element');

            expect(querySelectorSpy).toHaveBeenCalledWith('#test-element');
            expect(element).toBe(testElement);
            expect(uiModule._elements.get('test')).toBe(testElement);

            // Second call should use cache
            const element2 = uiModule.getElement('test', '#test-element');
            expect(element2).toBe(testElement);
            expect(querySelectorSpy).toHaveBeenCalledTimes(1); // Only called once

            querySelectorSpy.mockRestore();
        });

        it('should handle missing DOM elements gracefully', () => {
            const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
            const querySelectorSpy = vi.spyOn(document, 'querySelector').mockReturnValue(null);

            const element = uiModule.getElement('missing', '#missing-element');

            expect(element).toBe(null);
            expect(consoleSpy).toHaveBeenCalledWith(
                "Element not found for selector '#missing-element' in module TestUIModule"
            );

            querySelectorSpy.mockRestore();
            consoleSpy.mockRestore();
        });

        it('should add and track event listeners', () => {
            const element = createMockElement('button');
            const handler = vi.fn();

            uiModule.addEventListener(element, 'click', handler, { once: true });

            expect(element.addEventListener).toHaveBeenCalledWith('click', handler, { once: true });
            expect(uiModule._eventListeners).toHaveLength(1);
            expect(uiModule._eventListeners[0]).toEqual({
                element,
                event: 'click',
                handler,
                options: { once: true }
            });
        });

        it('should handle null elements for event listeners', () => {
            const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

            uiModule.addEventListener(null, 'click', vi.fn());

            expect(consoleSpy).toHaveBeenCalledWith(
                'Cannot add event listener: element is null in module TestUIModule'
            );

            consoleSpy.mockRestore();
        });

        it('should provide default updateUI implementation', () => {
            const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

            uiModule.updateUI({ state: 'test' });

            expect(consoleSpy).toHaveBeenCalledWith('updateUI not implemented in module TestUIModule');

            consoleSpy.mockRestore();
        });

        it('should implement loading state methods', () => {
            const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

            uiModule.showLoading();
            expect(consoleSpy).toHaveBeenCalledWith('TestUIModule: Showing loading state');

            uiModule.hideLoading();
            expect(consoleSpy).toHaveBeenCalledWith('TestUIModule: Hiding loading state');

            consoleSpy.mockRestore();
        });

        it('should clean up event listeners and elements on destroy', () => {
            const element1 = createMockElement('button');
            const element2 = createMockElement('input');
            const handler1 = vi.fn();
            const handler2 = vi.fn();

            uiModule.addEventListener(element1, 'click', handler1);
            uiModule.addEventListener(element2, 'input', handler2);
            uiModule._elements.set('cached', element1);

            expect(uiModule._eventListeners).toHaveLength(2);
            expect(uiModule._elements.size).toBe(1);

            uiModule.destroy();

            expect(element1.removeEventListener).toHaveBeenCalledWith('click', handler1, {});
            expect(element2.removeEventListener).toHaveBeenCalledWith('input', handler2, {});
            expect(uiModule._eventListeners).toEqual([]);
            expect(uiModule._elements.size).toBe(0);
        });

        it('should handle event listener cleanup errors', () => {
            const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
            const element = createMockElement('button');
            const handler = vi.fn();

            element.removeEventListener.mockImplementation(() => {
                throw new Error('Cleanup error');
            });

            uiModule.addEventListener(element, 'click', handler);
            uiModule.destroy();

            expect(consoleSpy).toHaveBeenCalledWith(
                'Error removing event listener in module TestUIModule:',
                expect.any(Error)
            );

            consoleSpy.mockRestore();
        });
    });

    describe('IGameStateModule Interface', () => {
        let gameStateModule;

        beforeEach(() => {
            gameStateModule = new IGameStateModule('TestGameState', mockEventBus, mockServiceContainer);
        });

        it('should extend IServiceModule with state management', () => {
            expect(gameStateModule).toBeInstanceOf(IServiceModule);
            expect(gameStateModule._state).toEqual({});
            expect(gameStateModule._stateHistory).toEqual([]);
            expect(gameStateModule._maxHistorySize).toBe(50);
        });

        it('should manage state with immutability', () => {
            const initialState = { count: 0, name: 'test' };
            gameStateModule._state = initialState;

            const state = gameStateModule.getState();

            expect(state).toEqual(initialState);
            expect(state).not.toBe(initialState); // Should be a copy
        });

        it('should update state and publish events', () => {
            gameStateModule.initialize();
            gameStateModule._state = { count: 0 };

            gameStateModule.updateState({ count: 1, name: 'updated' });

            expect(gameStateModule._state).toEqual({ count: 1, name: 'updated' });
            expect(mockEventBus.publish).toHaveBeenCalledWith(
                'testgamestate:state:changed',
                {
                    previousState: { count: 0 },
                    newState: { count: 1, name: 'updated' },
                    changes: { count: 1, name: 'updated' }
                },
                {
                    source: 'TestGameState'
                }
            );
        });

        it('should support silent state updates', () => {
            gameStateModule.initialize();

            gameStateModule.updateState({ silent: true }, { silent: true });

            expect(mockEventBus.publish).not.toHaveBeenCalled();
        });

        it('should maintain state history', () => {
            gameStateModule._state = { count: 0 };

            gameStateModule.updateState({ count: 1 });
            gameStateModule.updateState({ count: 2 });

            const history = gameStateModule.getStateHistory();

            expect(history).toHaveLength(2);
            expect(history[0].previousState).toEqual({ count: 0 });
            expect(history[0].newState).toEqual({ count: 1 });
            expect(history[1].previousState).toEqual({ count: 1 });
            expect(history[1].newState).toEqual({ count: 2 });
            expect(history[0]).toHaveProperty('timestamp');
        });

        it('should limit state history size', () => {
            gameStateModule._maxHistorySize = 3;

            for (let i = 0; i < 5; i++) {
                gameStateModule.updateState({ count: i });
            }

            const history = gameStateModule.getStateHistory();
            expect(history).toHaveLength(3);
            expect(history[0].newState.count).toBe(2); // Should keep last 3
            expect(history[2].newState.count).toBe(4);
        });

        it('should reset state and clear history', () => {
            gameStateModule.initialize();
            gameStateModule.updateState({ count: 1 });

            gameStateModule.resetState({ initial: true });

            expect(gameStateModule._state).toEqual({ initial: true });
            expect(gameStateModule._stateHistory).toEqual([]);
            expect(mockEventBus.publish).toHaveBeenCalledWith(
                'testgamestate:state:reset',
                { newState: { initial: true } },
                {
                    source: 'TestGameState'
                }
            );
        });

        it('should provide default state validation', () => {
            expect(gameStateModule.validateState({ any: 'state' })).toBe(true);
        });

        it('should clean up state on destroy', () => {
            gameStateModule.updateState({ count: 1 });

            gameStateModule.destroy();

            expect(gameStateModule._state).toEqual({});
            expect(gameStateModule._stateHistory).toEqual([]);
        });
    });

    describe('ITimerModule Interface', () => {
        let timerModule;

        beforeEach(() => {
            vi.useFakeTimers();
            timerModule = new ITimerModule('TestTimer', mockEventBus, mockServiceContainer);
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it('should extend IServiceModule with timer capabilities', () => {
            expect(timerModule).toBeInstanceOf(IServiceModule);
            expect(timerModule._timers).toBeInstanceOf(Map);
        });

        it('should start and track timers', () => {
            const callback = vi.fn();

            timerModule.startTimer('test-timer', 1000, callback);

            expect(timerModule.isTimerRunning('test-timer')).toBe(true);
            expect(mockEventBus.publish).toHaveBeenCalledWith('timer:started', {
                name: 'test-timer',
                duration: 1000,
                source: 'TestTimer'
            }, {
                source: 'TestTimer'
            });

            // Timer hasn't expired yet
            expect(callback).not.toHaveBeenCalled();

            // Fast forward time
            vi.advanceTimersByTime(1000);

            expect(callback).toHaveBeenCalledTimes(1);
            expect(timerModule.isTimerRunning('test-timer')).toBe(false);
            expect(mockEventBus.publish).toHaveBeenCalledWith('timer:expired', {
                name: 'test-timer',
                duration: 1000,
                source: 'TestTimer'
            }, {
                source: 'TestTimer'
            });
        });

        it('should clear existing timers when starting new ones with same name', () => {
            const callback1 = vi.fn();
            const callback2 = vi.fn();

            timerModule.startTimer('test', 1000, callback1);
            timerModule.startTimer('test', 2000, callback2);

            vi.advanceTimersByTime(1000);
            expect(callback1).not.toHaveBeenCalled(); // First timer was cleared

            vi.advanceTimersByTime(1000);
            expect(callback2).toHaveBeenCalledTimes(1); // Second timer fired
        });

        it('should manually clear timers', () => {
            const callback = vi.fn();

            timerModule.startTimer('test', 1000, callback);
            expect(timerModule.isTimerRunning('test')).toBe(true);

            timerModule.clearTimer('test');

            expect(timerModule.isTimerRunning('test')).toBe(false);
            expect(mockEventBus.publish).toHaveBeenCalledWith('timer:stopped', {
                name: 'test',
                source: 'TestTimer'
            }, {
                source: 'TestTimer'
            });

            vi.advanceTimersByTime(1000);
            expect(callback).not.toHaveBeenCalled(); // Should not fire
        });

        it('should get remaining time for active timers', () => {
            timerModule.startTimer('test', 1000);

            expect(timerModule.getRemainingTime('test')).toBe(1000);

            vi.advanceTimersByTime(300);
            expect(timerModule.getRemainingTime('test')).toBe(700);

            vi.advanceTimersByTime(700);
            expect(timerModule.getRemainingTime('test')).toBe(0);
        });

        it('should return 0 for non-existent timers', () => {
            expect(timerModule.getRemainingTime('non-existent')).toBe(0);
        });

        it('should track active timers', () => {
            timerModule.startTimer('timer1', 1000);
            timerModule.startTimer('timer2', 2000);

            const activeTimers = timerModule.getActiveTimers();
            expect(activeTimers).toEqual(['timer1', 'timer2']);

            timerModule.clearTimer('timer1');
            expect(timerModule.getActiveTimers()).toEqual(['timer2']);
        });

        it('should clear all timers on destroy', () => {
            timerModule.startTimer('timer1', 1000);
            timerModule.startTimer('timer2', 2000);

            expect(timerModule.getActiveTimers()).toHaveLength(2);

            timerModule.destroy();

            expect(timerModule.getActiveTimers()).toHaveLength(0);
            expect(mockEventBus.publish).toHaveBeenCalledWith('timer:stopped', {
                name: 'timer1',
                source: 'TestTimer'
            }, {
                source: 'TestTimer'
            });
            expect(mockEventBus.publish).toHaveBeenCalledWith('timer:stopped', {
                name: 'timer2',
                source: 'TestTimer'
            }, {
                source: 'TestTimer'
            });
        });
    });

    describe('Concrete Implementation Tests', () => {
        beforeEach(() => {
            // Setup more complete mocks for real implementations
            mockServiceContainer.has.mockImplementation(serviceName => {
                return serviceName === 'ToastManager' || serviceName === 'GameStateManager';
            });

            mockServiceContainer.get.mockImplementation(serviceName => {
                if (serviceName === 'ToastManager') {
                    return {
                        error: vi.fn(),
                        info: vi.fn(),
                        success: vi.fn()
                    };
                }
                return null;
            });
        });

        describe('ErrorDisplayManager Implementation', () => {
            let errorManager;

            beforeEach(() => {
                errorManager = new ErrorDisplayManager(mockEventBus, mockServiceContainer);
            });

            it('should properly extend IUIModule', () => {
                expect(errorManager).toBeInstanceOf(IUIModule);
                expect(errorManager.name).toBe('ErrorDisplayManager');
                expect(errorManager.eventBus).toBe(mockEventBus);
                expect(errorManager.serviceContainer).toBe(mockServiceContainer);
            });

            it('should maintain interface contract properties', () => {
                expect(errorManager).toHaveProperty('initialized', false);
                expect(errorManager).toHaveProperty('destroyed', false);
                expect(errorManager).toHaveProperty('_elements');
                expect(errorManager).toHaveProperty('_eventListeners');
                expect(errorManager).toHaveProperty('activeModals');
                expect(errorManager).toHaveProperty('errorHistory');
            });

            it('should implement required interface methods', () => {
                expect(typeof errorManager.initialize).toBe('function');
                expect(typeof errorManager.destroy).toBe('function');
                expect(typeof errorManager.healthCheck).toBe('function');
                expect(typeof errorManager.getStatus).toBe('function');
                expect(typeof errorManager.updateUI).toBe('function');
                expect(typeof errorManager.getElement).toBe('function');
                expect(typeof errorManager.addEventListener).toBe('function');
            });

            it('should follow initialization lifecycle', () => {
                expect(errorManager.initialized).toBe(false);

                errorManager.initialize();

                expect(errorManager.initialized).toBe(true);
                expect(errorManager.healthCheck()).toBe(true);
            });
        });

        describe('EventManager Implementation', () => {
            let eventManager;

            beforeEach(() => {
                // EventManager requires more setup
                global.window = {
                    roomId: 'test-room'
                };
                eventManager = new EventManager(mockEventBus, mockServiceContainer);
            });

            it('should properly extend IServiceModule', () => {
                expect(eventManager).toBeInstanceOf(IServiceModule);
                expect(eventManager.name).toBe('EventManager');
                expect(eventManager.eventBus).toBe(mockEventBus);
                expect(eventManager.serviceContainer).toBe(mockServiceContainer);
            });

            it('should maintain interface contract properties', () => {
                expect(eventManager).toHaveProperty('initialized', false);
                expect(eventManager).toHaveProperty('destroyed', false);
                expect(eventManager).toHaveProperty('_subscriptions');
                expect(eventManager).toHaveProperty('_dependencies');
            });

            it('should implement required interface methods', () => {
                expect(typeof eventManager.initialize).toBe('function');
                expect(typeof eventManager.destroy).toBe('function');
                expect(typeof eventManager.healthCheck).toBe('function');
                expect(typeof eventManager.getStatus).toBe('function');
                expect(typeof eventManager.getService).toBe('function');
                expect(typeof eventManager.hasService).toBe('function');
            });
        });

        describe('Additional Module Interface Compliance', () => {
            beforeEach(() => {
                // Enhanced ServiceContainer mock for additional modules
                mockServiceContainer.has.mockImplementation(serviceName => {
                    const availableServices = ['ToastManager', 'GameStateManager', 'SocketManager', 'UIManager'];
                    return availableServices.includes(serviceName);
                });

                mockServiceContainer.get.mockImplementation(serviceName => {
                    const mockServices = {
                        'ToastManager': { error: vi.fn(), info: vi.fn(), success: vi.fn(), healthCheck: vi.fn(() => true) },
                        'GameStateManager': { getState: vi.fn(() => ({})), updateState: vi.fn(), healthCheck: vi.fn(() => true) },
                        'SocketManager': { emit: vi.fn(), on: vi.fn(), initialize: vi.fn(), healthCheck: vi.fn(() => true) },
                        'UIManager': { updateUI: vi.fn(), healthCheck: vi.fn(() => true) }
                    };
                    return mockServices[serviceName] || null;
                });
            });

            it('should validate that modules follow naming conventions', () => {
                const moduleNames = ['ErrorDisplayManager', 'EventManager'];

                moduleNames.forEach(name => {
                    expect(name).toMatch(/^[A-Z][a-zA-Z]*Manager$/);
                });
            });

            it('should ensure modules properly implement dependency injection', () => {
                const errorManager = new ErrorDisplayManager(mockEventBus, mockServiceContainer);

                // Should accept dependencies in constructor
                expect(errorManager.eventBus).toBe(mockEventBus);
                expect(errorManager.serviceContainer).toBe(mockServiceContainer);

                // Should be able to get services
                if (errorManager.hasService('ToastManager')) {
                    const toastManager = errorManager.getService('ToastManager');
                    expect(toastManager).toBeDefined();
                    expect(errorManager._dependencies).toContain('ToastManager');
                }
            });

            it('should validate module resource cleanup on destroy', () => {
                const errorManager = new ErrorDisplayManager(mockEventBus, mockServiceContainer);

                errorManager.initialize();

                // Add some tracked resources
                if (errorManager._elements && errorManager._eventListeners) {
                    expect(errorManager._elements).toBeInstanceOf(Map);
                    expect(Array.isArray(errorManager._eventListeners)).toBe(true);
                }

                const initialSubscriptions = errorManager._subscriptions.length;

                errorManager.destroy();

                // Verify cleanup
                expect(errorManager.destroyed).toBe(true);
                expect(errorManager._subscriptions.length).toBe(0);

                if (errorManager._elements) {
                    expect(errorManager._elements.size).toBe(0);
                }
                if (errorManager._eventListeners) {
                    expect(errorManager._eventListeners.length).toBe(0);
                }
            });

            it('should ensure modules handle initialization errors gracefully', () => {
                const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

                // Create module with faulty dependencies
                const faultyContainer = {
                    get: vi.fn(() => { throw new Error('Service unavailable'); }),
                    has: vi.fn(() => true)
                };

                const errorManager = new ErrorDisplayManager(mockEventBus, faultyContainer);

                // Should not crash during initialization
                expect(() => {
                    errorManager.initialize();
                }).not.toThrow();

                consoleSpy.mockRestore();
            });

            it('should validate interface inheritance chains', () => {
                const implementations = [
                    { instance: new ErrorDisplayManager(mockEventBus, mockServiceContainer), expectedBase: IUIModule },
                    { instance: new EventManager(mockEventBus, mockServiceContainer), expectedBase: IServiceModule }
                ];

                implementations.forEach(({ instance, expectedBase }) => {
                    expect(instance).toBeInstanceOf(expectedBase);
                    expect(instance).toBeInstanceOf(IServiceModule);
                    expect(instance).toBeInstanceOf(IEventModule);
                    expect(instance).toBeInstanceOf(IModule);
                });
            });

            it('should ensure consistent status reporting across modules', () => {
                const modules = [
                    new ErrorDisplayManager(mockEventBus, mockServiceContainer),
                    new EventManager(mockEventBus, mockServiceContainer)
                ];

                modules.forEach(module => {
                    module.initialize();
                    const status = module.getStatus();

                    // All modules should report consistent status structure
                    expect(status).toHaveProperty('name');
                    expect(status).toHaveProperty('initialized', true);
                    expect(status).toHaveProperty('destroyed', false);
                    expect(status).toHaveProperty('healthy');
                    expect(status).toHaveProperty('dependencies');
                    expect(status).toHaveProperty('dependenciesHealthy');
                    expect(typeof status.uptime).toBe('number');
                });
            });

            it('should validate event bus integration patterns', () => {
                const eventManager = new EventManager(mockEventBus, mockServiceContainer);

                // Should be able to subscribe to events
                const handler = vi.fn();
                const unsubscribe = eventManager.subscribe('test:event', handler);

                expect(mockEventBus.subscribe).toHaveBeenCalledWith(
                    'test:event',
                    handler,
                    expect.objectContaining({ context: eventManager })
                );

                // Should be able to publish events
                eventManager.publish('test:event', { data: 'test' });

                expect(mockEventBus.publish).toHaveBeenCalledWith(
                    'test:event',
                    { data: 'test' },
                    expect.objectContaining({ source: 'EventManager' })
                );

                // Should track subscriptions
                expect(eventManager._subscriptions.length).toBeGreaterThan(0);
            });

            it('should validate module state consistency after operations', () => {
                const errorManager = new ErrorDisplayManager(mockEventBus, mockServiceContainer);

                // Initial state
                expect(errorManager.healthCheck()).toBe(false);
                expect(errorManager.initialized).toBe(false);

                // After initialization
                errorManager.initialize();
                expect(errorManager.healthCheck()).toBe(true);
                expect(errorManager.initialized).toBe(true);
                expect(errorManager.destroyed).toBe(false);

                // After destruction
                errorManager.destroy();
                expect(errorManager.healthCheck()).toBe(false);
                expect(errorManager.destroyed).toBe(true);

                // After reset
                errorManager.reset();
                expect(errorManager.healthCheck()).toBe(true);
                expect(errorManager.initialized).toBe(true);
                expect(errorManager.destroyed).toBe(false);
            });
        });
    });

    describe('Interface Contract Violations', () => {
        it('should detect missing required methods', () => {
            // Create a class that incorrectly extends ISocketModule
            class IncompleteSocketModule extends ISocketModule {
                constructor() {
                    super('Incomplete', mockEventBus, mockServiceContainer);
                }
                // Missing emitSocket implementation
            }

            const incompleteModule = new IncompleteSocketModule();

            expect(() => {
                incompleteModule.emitSocket('test', {});
            }).toThrow('emitSocket must be implemented by concrete module');
        });

        it('should handle interface extension hierarchy correctly', () => {
            const module = new ITimerModule('Test', mockEventBus, mockServiceContainer);

            // Should have all parent interface capabilities
            expect(module).toBeInstanceOf(IServiceModule);
            expect(module).toBeInstanceOf(IEventModule);
            expect(module).toBeInstanceOf(IModule);

            // Should have its own specific capabilities
            expect(typeof module.startTimer).toBe('function');
            expect(typeof module.clearTimer).toBe('function');
            expect(typeof module.getRemainingTime).toBe('function');
        });
    });
});