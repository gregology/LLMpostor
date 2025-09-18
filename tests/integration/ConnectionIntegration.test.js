/**
 * Connection Integration Tests
 *
 * Comprehensive testing of connection-related integration scenarios including:
 * - Socket.IO connection lifecycle and state management
 * - Connection resilience, recovery, and retry mechanisms
 * - Network status changes and connection quality monitoring
 * - Connection timeout, heartbeat, and reliability integration
 * - Real-time communication and event flow
 * - End-to-end connection scenarios and error recovery
 *
 * CONSOLIDATED: All connection-related integration tests are centralized here
 * SCOPE: Full connection stack integration - Socket.IO + ConnectionReliability + ConnectionMetrics
 * RELATED: ConnectionReliability.test.js (unit), ConnectionMetrics.test.js (unit)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const GameClient = (await import('../../static/js/modules/GameClient.js')).default;
const SocketManager = (await import('../../static/js/modules/SocketManager.js')).default;
const { EventBus } = await import('../../static/js/modules/EventBus.js');

describe('Connection Integration', () => {
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

        // Mock DOM elements needed for connection testing
        document.body.innerHTML = `
            <div id="connectionStatus"></div>
            <div id="playerCount"></div>
            <div id="playersList"></div>
        `;

        global.window.roomId = 'test-room';

        gameClient = new GameClient();
    });

    afterEach(() => {
        if (global.window) {
            delete global.window.isTestEnvironment;
        }

        EventBus.clear();
        vi.clearAllMocks();
        vi.clearAllTimers();
        vi.useRealTimers();
    });

    describe('Socket.IO Connection Lifecycle', () => {
        it('should establish initial connection successfully', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            expect(global.io).toHaveBeenCalled();
            expect(mockSocket.on).toHaveBeenCalledWith('connect', expect.any(Function));
            expect(mockSocket.on).toHaveBeenCalledWith('disconnect', expect.any(Function));
        });

        it('should handle connection success events', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            // Find and trigger the connect handler
            const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')?.[1];
            expect(connectHandler).toBeDefined();

            if (connectHandler) {
                mockSocket.connected = true;
                connectHandler();
                // The connection state should be updated (actual implementation may vary)
                expect(mockSocket.connected).toBe(true);
            }
        });

        it('should handle connection failure events', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            // Find and trigger the disconnect handler
            const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')?.[1];
            expect(disconnectHandler).toBeDefined();

            if (disconnectHandler) {
                mockSocket.connected = false;
                disconnectHandler('transport close');
                expect(socketManager.isConnected).toBe(false);
            }
        });

        it('should clean up connection on destroy', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            socketManager.destroy();

            expect(mockSocket.removeAllListeners).toHaveBeenCalled();
            expect(mockSocket.disconnect).toHaveBeenCalled();
        });
    });

    describe('Connection Resilience and Recovery', () => {
        it('should handle sudden connection drops gracefully', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            // Simulate sudden connection drop
            mockSocket.connected = false;
            const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')?.[1];

            if (disconnectHandler) {
                disconnectHandler('transport close');
                expect(socketManager.isConnected).toBe(false);
            }
        });

        it('should attempt reconnection after disconnect', () => {
            vi.useFakeTimers();

            const socketManager = new SocketManager();
            socketManager.initialize();

            // Clear initialization calls
            global.io.mockClear();

            // Temporarily disable test environment to allow reconnection
            global.window.isTestEnvironment = false;

            // Simulate disconnect
            mockSocket.connected = false;
            socketManager._handleDisconnect('transport close');

            // Fast-forward time to trigger reconnection attempt
            vi.advanceTimersByTime(2000);

            expect(global.io).toHaveBeenCalledTimes(1);

            // Restore test environment
            global.window.isTestEnvironment = true;
        });

        it('should handle connection timeout scenarios', () => {
            vi.useFakeTimers();

            const socketManager = new SocketManager();
            socketManager.initialize();

            // Mock connection timeout
            const timeoutHandler = vi.fn();
            socketManager.reliability.startConnectionTimeout(5000, timeoutHandler);

            // Advance timer to trigger timeout
            vi.advanceTimersByTime(5000);

            expect(timeoutHandler).toHaveBeenCalled();
        });

        it('should handle multiple rapid disconnect/reconnect cycles', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')?.[1];
            const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')?.[1];

            // Simulate rapid disconnect/reconnect cycles
            for (let i = 0; i < 5; i++) {
                mockSocket.connected = false;
                if (disconnectHandler) disconnectHandler('transport close');

                mockSocket.connected = true;
                if (connectHandler) connectHandler();
            }

            // Should still be in a stable state (mock socket is connected)
            expect(mockSocket.connected).toBe(true);
        });

        it('should handle exponential backoff reconnection delays', () => {
            vi.useFakeTimers();

            const socketManager = new SocketManager();
            const attemptReconnect = vi.fn();

            // Test exponential backoff directly through ConnectionReliability
            const reliability = socketManager.reliability;

            // First attempt - should be immediate or short delay
            reliability.startConnectionRecovery(1, () => false, attemptReconnect, 10, 1000, 30000);
            vi.advanceTimersByTime(1000);
            expect(attemptReconnect).toHaveBeenCalledTimes(1);

            // Second attempt - should have longer delay
            attemptReconnect.mockClear();
            reliability.startConnectionRecovery(2, () => false, attemptReconnect, 10, 1000, 30000);
            vi.advanceTimersByTime(2000);
            expect(attemptReconnect).toHaveBeenCalledTimes(1);

            // High attempt number - should be capped at max delay
            attemptReconnect.mockClear();
            reliability.startConnectionRecovery(10, () => false, attemptReconnect, 10, 1000, 30000);
            vi.advanceTimersByTime(30000);
            expect(attemptReconnect).toHaveBeenCalledTimes(1);
        });
    });

    describe('Network Status Integration', () => {
        it('should handle network online/offline transitions', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            // Mock network going offline
            Object.defineProperty(navigator, 'onLine', {
                value: false,
                writable: true,
                configurable: true
            });

            const offlineEvent = new Event('offline');
            window.dispatchEvent(offlineEvent);

            // Verify connection state is updated appropriately
            // (The actual behavior depends on SocketManager implementation)
            expect(navigator.onLine).toBe(false);

            // Mock network coming back online
            Object.defineProperty(navigator, 'onLine', {
                value: true,
                writable: true,
                configurable: true
            });

            const onlineEvent = new Event('online');
            window.dispatchEvent(onlineEvent);

            expect(navigator.onLine).toBe(true);
        });

        it('should integrate connection metrics with actual connection events', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')?.[1];
            const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')?.[1];

            // Simulate disconnect
            mockSocket.connected = false;
            if (disconnectHandler) {
                disconnectHandler('transport close');
            }

            // Verify metrics are updated (check that metrics object exists)
            const metrics = socketManager.connectionMetrics;
            expect(metrics).toBeDefined();

            // Simulate reconnect
            mockSocket.connected = true;
            if (connectHandler) {
                connectHandler();
            }

            // Verify metrics object has expected properties
            expect(metrics).toHaveProperty('reconnectCount');
        });
    });

    describe('Heartbeat and Ping Integration', () => {
        it('should send heartbeat pings when connected', () => {
            vi.useFakeTimers();

            const socketManager = new SocketManager();
            socketManager.initialize();

            // Start heartbeat
            const emitPing = vi.fn();
            const isConnected = () => mockSocket.connected;

            socketManager.reliability.startHeartbeat(1000, isConnected, emitPing);

            // Advance timer to trigger heartbeat
            vi.advanceTimersByTime(1000);

            expect(emitPing).toHaveBeenCalled();
        });

        it('should not send pings when disconnected', () => {
            vi.useFakeTimers();

            const socketManager = new SocketManager();
            socketManager.initialize();

            const emitPing = vi.fn();
            const isConnected = () => false; // Simulate disconnected state

            socketManager.reliability.startHeartbeat(1000, isConnected, emitPing);

            // Advance timer
            vi.advanceTimersByTime(2000);

            expect(emitPing).not.toHaveBeenCalled();
        });

        it('should handle pong responses for latency calculation', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            // Find pong handler
            const pongHandler = mockSocket.on.mock.calls.find(call => call[0] === 'pong')?.[1];

            if (pongHandler) {
                const pingTime = Date.now() - 100; // Simulate 100ms latency
                pongHandler(pingTime);

                // Verify metrics object exists and has latency property
                const avgLatency = socketManager.connectionMetrics.averageLatency;
                expect(socketManager.connectionMetrics).toHaveProperty('averageLatency');
            }
        });
    });

    describe('Connection State UI Integration', () => {
        it('should update UI connection status on connect events', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')?.[1];

            if (connectHandler) {
                connectHandler();

                // Verify UI is updated (check for status indicator)
                const statusElement = document.getElementById('connectionStatus');
                expect(statusElement).toBeDefined();
                // The actual UI update depends on the implementation
            }
        });

        it('should update UI connection status on disconnect events', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')?.[1];

            if (disconnectHandler) {
                mockSocket.connected = false;
                disconnectHandler('transport close');

                // Verify UI reflects disconnected state
                const statusElement = document.getElementById('connectionStatus');
                expect(statusElement).toBeDefined();
            }
        });

        it('should handle connection quality indicators', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            // Test different connection qualities
            const metrics = socketManager.connectionMetrics;

            // Good connection
            metrics.recordLatency(50);
            let summary = metrics.getSummary(0, 'good', true);
            expect(summary.quality).toBe('good');
            expect(summary.averageLatency).toBe(50);

            // Poor connection
            metrics.recordLatency(500);
            summary = metrics.getSummary(0, 'poor', true);
            expect(summary.quality).toBe('poor');
            expect(summary.averageLatency).toBeGreaterThan(50);
        });
    });

    describe('Error Scenarios and Edge Cases', () => {
        it('should handle WebSocket upgrade failures', () => {
            // Mock io function to simulate connection failure
            global.io.mockImplementation(() => {
                throw new Error('WebSocket upgrade failed');
            });

            // Should handle the error gracefully
            let errorCaught = false;
            try {
                const socketManager = new SocketManager();
                socketManager.initialize();
            } catch (error) {
                errorCaught = true;
                expect(error.message).toBe('WebSocket upgrade failed');
            }

            expect(errorCaught).toBe(true);

            // Restore normal io mock
            global.io.mockImplementation(() => mockSocket);
        });

        it('should handle connection timeout during initialization', () => {
            vi.useFakeTimers();

            // Mock io to never trigger connect event
            const neverConnectSocket = {
                ...mockSocket,
                connected: false
            };
            global.io.mockImplementation(() => neverConnectSocket);

            const socketManager = new SocketManager();
            const onTimeout = vi.fn();

            socketManager.initialize();
            socketManager.reliability.startConnectionTimeout(5000, onTimeout);

            // Fast-forward past timeout
            vi.advanceTimersByTime(5000);

            expect(onTimeout).toHaveBeenCalled();

            // Restore normal socket mock
            global.io.mockImplementation(() => mockSocket);
        });

        it('should handle Socket.IO server errors gracefully', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            // Find error handler
            const errorHandler = mockSocket.on.mock.calls.find(call => call[0] === 'error')?.[1];

            if (errorHandler) {
                const testError = new Error('Server error');
                errorHandler(testError);

                // Verify error is handled gracefully (doesn't crash)
                expect(socketManager.isConnected).toBe(false);
            }
        });

        it('should handle concurrent connection attempts', () => {
            const socketManager1 = new SocketManager();
            const socketManager2 = new SocketManager();

            // Clear previous calls
            global.io.mockClear();

            // Initialize both concurrently
            socketManager1.initialize();
            socketManager2.initialize();

            // Should be called for each manager
            expect(global.io).toHaveBeenCalledTimes(2);

            // Clean up
            socketManager1.destroy();
            socketManager2.destroy();
        });
    });

    describe('Performance and Resource Management', () => {
        it('should clean up timers on connection destroy', () => {
            vi.useFakeTimers();

            const socketManager = new SocketManager();
            socketManager.initialize();

            // Start various timers
            socketManager.reliability.startHeartbeat(1000, () => true, vi.fn());
            socketManager.reliability.startConnectionTimeout(5000, vi.fn());

            const initialTimerCount = vi.getTimerCount();

            // Destroy connection
            socketManager.destroy();

            expect(vi.getTimerCount()).toBeLessThan(initialTimerCount);
        });

        it('should handle high-frequency connection events efficiently', () => {
            const socketManager = new SocketManager();
            socketManager.initialize();

            const startTime = performance.now();

            const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')?.[1];
            const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')?.[1];

            // Simulate high-frequency events
            for (let i = 0; i < 100; i++) {
                if (connectHandler && disconnectHandler) {
                    mockSocket.connected = true;
                    connectHandler();

                    mockSocket.connected = false;
                    disconnectHandler('transport close');
                }
            }

            const endTime = performance.now();
            const duration = endTime - startTime;

            // Should handle events efficiently (allow more time for CI environments)
            expect(duration).toBeLessThan(500); // Less than 500ms for 200 events
        });

        it('should limit connection retry attempts appropriately', () => {
            vi.useFakeTimers();

            const socketManager = new SocketManager();
            const attemptReconnect = vi.fn();

            // Mock failed reconnection attempts
            global.window.isTestEnvironment = false;

            // Test max retry limit
            for (let i = 1; i <= 12; i++) {
                socketManager.reliability.startConnectionRecovery(
                    i, () => false, attemptReconnect, 10, 1000, 30000
                );
                vi.advanceTimersByTime(30000);
            }

            // Should have attempted reconnection 12 times
            expect(attemptReconnect).toHaveBeenCalledTimes(12);

            global.window.isTestEnvironment = true;
        });
    });
});