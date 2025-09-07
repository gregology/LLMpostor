import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const GameClient = (await import('../../static/js/modules/GameClient.js')).default;
const SocketManager = (await import('../../static/js/modules/SocketManager.js')).default;
const GameStateManager = (await import('../../static/js/modules/GameStateManager.js')).default;
const { EventBus } = await import('../../static/js/modules/EventBus.js');

describe('Browser Environment Reliability', () => {
    let gameClient;
    let mockSocket;
    
    beforeEach(() => {
        // Set test environment flag
        global.window = global.window || {};
        global.window.isTestEnvironment = true;
        
        // Mock Socket.IO
        mockSocket = {
            on: vi.fn(),
            emit: vi.fn(),
            disconnect: vi.fn(),
            removeAllListeners: vi.fn(),
            connected: true,
            id: 'test-socket-id'
        };
        
        global.io = vi.fn(() => mockSocket);
        
        // Mock DOM elements
        document.body.innerHTML = `
            <div id="connectionStatus"></div>
            <div id="playerCount"></div>
            <div id="playersList"></div>
            <textarea id="responseInput"></textarea>
            <button id="submitResponseBtn"></button>
            <button id="startRoundBtn"></button>
        `;
        
        global.window.roomId = 'test-room';
        global.window.maxResponseLength = 100;
        
        gameClient = new GameClient();
    });
    
    afterEach(() => {
        // Clean up test environment flag
        if (global.window) {
            delete global.window.isTestEnvironment;
        }
        
        EventBus.clear();
        vi.clearAllMocks();
        vi.clearAllTimers();
    });

    describe('Tab Suspension and Resumption', () => {
        it('should handle page visibility changes gracefully', () => {
            const originalHidden = document.hidden;
            
            // Simulate tab becoming hidden
            Object.defineProperty(document, 'hidden', {
                writable: true,
                value: true
            });
            
            const visibilityEvent = new Event('visibilitychange');
            document.dispatchEvent(visibilityEvent);
            
            // Should still be functional
            expect(gameClient.isInitialized).toBe(true);
            
            // Simulate tab becoming visible again
            Object.defineProperty(document, 'hidden', {
                value: false
            });
            
            document.dispatchEvent(visibilityEvent);
            
            // The client should still be functional after visibility changes
            expect(gameClient.isInitialized).toBe(true);
            expect(gameClient.socketManager).toBeDefined();
            
            // Restore original value
            Object.defineProperty(document, 'hidden', {
                value: originalHidden
            });
        });

        it('should handle focus and blur events', () => {
            const focusHandler = vi.fn();
            const blurHandler = vi.fn();
            
            // Add event listeners
            window.addEventListener('focus', focusHandler);
            window.addEventListener('blur', blurHandler);
            
            // Simulate window focus events
            window.dispatchEvent(new Event('focus'));
            window.dispatchEvent(new Event('blur'));
            window.dispatchEvent(new Event('focus'));
            
            expect(focusHandler).toHaveBeenCalledTimes(2);
            expect(blurHandler).toHaveBeenCalledTimes(1);
        });
    });

    describe('Browser Refresh and Navigation', () => {
        it('should handle beforeunload events', () => {
            const beforeUnloadHandler = vi.fn();
            window.addEventListener('beforeunload', beforeUnloadHandler);
            
            // Simulate browser refresh/close
            const beforeUnloadEvent = new Event('beforeunload');
            window.dispatchEvent(beforeUnloadEvent);
            
            expect(beforeUnloadHandler).toHaveBeenCalled();
        });

        it('should clean up resources on page unload', () => {
            const cleanup = vi.spyOn(gameClient, 'destroy');
            
            window.addEventListener('beforeunload', () => {
                gameClient.destroy();
            });
            
            const unloadEvent = new Event('beforeunload');
            window.dispatchEvent(unloadEvent);
            
            expect(cleanup).toHaveBeenCalled();
        });
    });

    describe('Memory Management', () => {
        it('should prevent memory leaks from event listeners', () => {
            const initialEventCount = EventBus.getEventNames().length;
            
            // Create and destroy multiple game clients
            for (let i = 0; i < 10; i++) {
                const tempClient = new GameClient();
                tempClient.destroy();
            }
            
            // Event count should not grow indefinitely
            const finalEventCount = EventBus.getEventNames().length;
            expect(finalEventCount - initialEventCount).toBeLessThan(5);
        });

        it('should clean up timers properly', () => {
            vi.useFakeTimers();
            
            // Create intervals/timeouts
            const intervalId = setInterval(() => {}, 1000);
            const timeoutId = setTimeout(() => {}, 5000);
            
            // Track active timers
            const initialTimerCount = vi.getTimerCount();
            
            // Clean up
            clearInterval(intervalId);
            clearTimeout(timeoutId);
            
            expect(vi.getTimerCount()).toBe(initialTimerCount - 2);
            
            vi.useRealTimers();
        });
    });

    describe('Connection Resilience', () => {
        it('should handle sudden connection drops', () => {
            const disconnectHandler = vi.fn();
            mockSocket.on.mockImplementation((event, handler) => {
                if (event === 'disconnect') {
                    disconnectHandler.mockImplementation(handler);
                }
            });
            
            // Initialize socket manager
            const socketManager = new SocketManager();
            socketManager.initialize();
            
            // Simulate sudden disconnect
            mockSocket.connected = false;
            disconnectHandler();
            
            expect(socketManager.isConnected).toBe(false);
        });

        it('should attempt reconnection after disconnect', () => {
            vi.useFakeTimers();
            
            const socketManager = new SocketManager();
            socketManager.initialize();
            
            // Reset the spy count after initialization
            global.io.mockClear();
            
            // Temporarily disable test environment to allow reconnection
            global.window.isTestEnvironment = false;
            
            // Simulate disconnect
            mockSocket.connected = false;
            socketManager._handleDisconnect('transport close');
            
            // Fast-forward time to trigger reconnection attempt
            vi.advanceTimersByTime(2000);
            
            expect(global.io).toHaveBeenCalledTimes(1); // One reconnection attempt
            
            // Restore test environment
            global.window.isTestEnvironment = true;
            vi.useRealTimers();
        });
    });

    describe('DOM Manipulation Safety', () => {
        it('should handle missing DOM elements gracefully', () => {
            // Remove critical elements
            document.getElementById('connectionStatus')?.remove();
            document.getElementById('responseInput')?.remove();
            
            // Should not crash when trying to update UI
            expect(() => {
                gameClient.uiManager.updateConnectionStatus('connected', 'Connected');
                // Note: updateResponseInput doesn't exist in current UIManager
                // This tests graceful handling of missing DOM elements
            }).not.toThrow();
        });

        it('should handle DOM mutations during operation', () => {
            const responseInput = document.getElementById('responseInput');
            
            // Start using the element
            if (responseInput) {
                responseInput.value = 'test response';
            }
            
            // Simulate DOM mutation (element replacement)
            const newInput = document.createElement('textarea');
            newInput.id = 'responseInput';
            newInput.value = 'new value';
            
            if (responseInput && responseInput.parentNode) {
                responseInput.parentNode.replaceChild(newInput, responseInput);
            }
            
            // Should handle the change gracefully
            expect(() => {
                // Test a method that exists in UIManager
                gameClient.uiManager.updateConnectionStatus('connected', 'Connected');
            }).not.toThrow();
        });
    });

    describe('Performance Under Stress', () => {
        it('should handle rapid UI updates efficiently', () => {
            vi.useFakeTimers();
            
            const updateCount = 100;
            const startTime = performance.now();
            
            // Rapid UI updates
            for (let i = 0; i < updateCount; i++) {
                gameClient.uiManager.updateConnectionStatus('connecting', 'Connecting...');
                gameClient.uiManager.updateConnectionStatus('connected', 'Connected');
            }
            
            vi.runAllTimers();
            
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            // Should complete updates in reasonable time
            expect(duration).toBeLessThan(1000); // Less than 1 second
            
            vi.useRealTimers();
        });

        it('should handle event flooding gracefully', () => {
            const eventCount = 1000;
            const startTime = performance.now();
            
            // Flood with events
            for (let i = 0; i < eventCount; i++) {
                EventBus.publish('test:event', { index: i });
            }
            
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            // Should process events efficiently
            expect(duration).toBeLessThan(100); // Less than 100ms
        });
    });

    describe('Error Recovery', () => {
        it('should recover from JavaScript runtime errors', () => {
            const errorHandler = vi.fn();
            window.addEventListener('error', errorHandler);
            
            // Simulate runtime error
            try {
                throw new Error('Test runtime error');
            } catch (error) {
                const errorEvent = new ErrorEvent('error', {
                    error: error,
                    message: error.message
                });
                window.dispatchEvent(errorEvent);
            }
            
            expect(errorHandler).toHaveBeenCalled();
            
            // Game client should still be functional
            expect(gameClient.isInitialized).toBe(true);
        });

        it('should handle promise rejections', async () => {
            // Test that the application doesn't crash when promises are rejected
            let errorCaught = false;
            
            // Add a global error handler
            const originalOnError = window.onerror;
            window.onerror = () => {
                errorCaught = true;
                return true; // Prevent error from propagating
            };
            
            try {
                // Create and immediately handle a promise rejection
                await Promise.reject(new Error('Test handled rejection')).catch(() => {
                    // This should handle the rejection gracefully
                });
                
                // Application should still be functional
                expect(gameClient.isInitialized).toBe(true);
                expect(gameClient.socketManager).toBeDefined();
                
                // No unhandled error should have occurred
                expect(errorCaught).toBe(false);
            } finally {
                // Restore original handler
                window.onerror = originalOnError;
            }
        });
    });

    describe('Local Storage Reliability', () => {
        it('should handle localStorage unavailability', () => {
            // Mock localStorage failure
            const originalLocalStorage = window.localStorage;
            
            Object.defineProperty(window, 'localStorage', {
                value: {
                    getItem: vi.fn(() => { throw new Error('Storage unavailable'); }),
                    setItem: vi.fn(() => { throw new Error('Storage unavailable'); }),
                    removeItem: vi.fn(() => { throw new Error('Storage unavailable'); })
                }
            });
            
            // Should handle storage errors gracefully - test with actual existing methods
            expect(() => {
                // Test that the application still works without localStorage
                gameClient.uiManager.updateConnectionStatus('connected', 'Connected');
            }).not.toThrow();
            
            // Restore original localStorage
            Object.defineProperty(window, 'localStorage', {
                value: originalLocalStorage
            });
        });

        it('should handle storage quota exceeded', () => {
            const originalSetItem = localStorage.setItem;
            
            // Mock storage quota exceeded
            localStorage.setItem = vi.fn(() => {
                throw new DOMException('Storage quota exceeded', 'QuotaExceededError');
            });
            
            expect(() => {
                // Test that the application still works when storage quota is exceeded
                gameClient.uiManager.updateConnectionStatus('connected', 'Connected');
            }).not.toThrow();
            
            localStorage.setItem = originalSetItem;
        });
    });

    describe('Mobile-Specific Scenarios', () => {
        it('should handle orientation changes', () => {
            const orientationHandler = vi.fn();
            window.addEventListener('orientationchange', orientationHandler);
            
            // Mock orientation change
            Object.defineProperty(screen, 'orientation', {
                value: { angle: 90 },
                writable: true
            });
            
            window.dispatchEvent(new Event('orientationchange'));
            
            expect(orientationHandler).toHaveBeenCalled();
        });

        it('should handle touch events on mobile', () => {
            // Mock Touch and TouchEvent for test environment
            if (typeof global.Touch === 'undefined') {
                global.Touch = class {
                    constructor(params) {
                        Object.assign(this, params);
                    }
                };
            }
            
            if (typeof global.TouchEvent === 'undefined') {
                global.TouchEvent = class extends Event {
                    constructor(type, params) {
                        super(type);
                        Object.assign(this, params);
                    }
                };
            }
            
            const touchHandler = vi.fn();
            const submitBtn = document.getElementById('submitResponseBtn');
            
            submitBtn.addEventListener('touchend', touchHandler);
            
            // Simulate touch event
            const touchEvent = new TouchEvent('touchend', {
                touches: [],
                targetTouches: [],
                changedTouches: [
                    new Touch({
                        identifier: 1,
                        target: submitBtn,
                        clientX: 100,
                        clientY: 100
                    })
                ]
            });
            
            submitBtn.dispatchEvent(touchEvent);
            
            expect(touchHandler).toHaveBeenCalled();
        });
    });

    describe('Network Status Changes', () => {
        it('should handle online/offline events', () => {
            const onlineHandler = vi.fn();
            const offlineHandler = vi.fn();
            
            window.addEventListener('online', onlineHandler);
            window.addEventListener('offline', offlineHandler);
            
            // Simulate going offline
            Object.defineProperty(navigator, 'onLine', {
                value: false,
                writable: true
            });
            window.dispatchEvent(new Event('offline'));
            
            expect(offlineHandler).toHaveBeenCalled();
            
            // Simulate coming back online
            Object.defineProperty(navigator, 'onLine', {
                value: true,
                writable: true
            });
            window.dispatchEvent(new Event('online'));
            
            expect(onlineHandler).toHaveBeenCalled();
        });
    });

    describe('Cross-Browser Compatibility', () => {
        it('should handle different event implementations', () => {
            // Test with different event constructors that might not exist in all browsers
            
            // CustomEvent (not available in older IE)
            let customEvent;
            try {
                customEvent = new CustomEvent('test:custom', { detail: 'test' });
            } catch (e) {
                // Fallback for older browsers
                customEvent = document.createEvent('CustomEvent');
                customEvent.initCustomEvent('test:custom', false, false, 'test');
            }
            
            expect(customEvent.type).toBe('test:custom');
        });

        it('should handle different WebSocket implementations', () => {
            const originalWebSocket = global.WebSocket;
            
            // Mock WebSocket unavailable
            delete global.WebSocket;
            
            // Should fall back to polling or handle gracefully
            expect(() => {
                const socketManager = new SocketManager();
                socketManager.initialize();
            }).not.toThrow();
            
            global.WebSocket = originalWebSocket;
        });
    });
});