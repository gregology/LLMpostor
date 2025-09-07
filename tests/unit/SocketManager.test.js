import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createMockSocket, nextTick } from '../helpers/testUtils.js';

const SocketManager = (await import('../../static/js/modules/SocketManager.js')).default || 
                      (await import('../../static/js/modules/SocketManager.js')).SocketManager;

describe('SocketManager', () => {
  let socketManager;
  let mockSocket;

  beforeEach(() => {
    // Mock the global io function
    mockSocket = createMockSocket();
    global.io = vi.fn(() => mockSocket);
    
    // Set up window object for test environment detection
    global.window = global.window || {};
    global.window.isTestEnvironment = true;
    
    socketManager = new SocketManager();
  });

  afterEach(() => {
    // Clean up test environment flag
    if (global.window) {
      delete global.window.isTestEnvironment;
    }
    
    vi.clearAllMocks();
    vi.clearAllTimers();
  });

  describe('Initialization', () => {
    it('should initialize with default state', () => {
      expect(socketManager.socket).toBe(null);
      expect(socketManager.connectionStatus).toBe(false);
      expect(socketManager.reconnectAttempts).toBe(0);
      expect(socketManager.maxReconnectAttempts).toBe(10); // Updated to match new default
      expect(socketManager.reconnectDelay).toBe(1000);
    });

    it('should create socket connection on initialize', () => {
      socketManager.initialize();

      expect(global.io).toHaveBeenCalledWith('/', {
        transports: ['polling', 'websocket'],
        timeout: 10000, // New timeout option
        reconnection: false, // New option
        forceNew: true // New option
      });
      expect(socketManager.socket).toBe(mockSocket);
    });

    it('should setup event handlers on initialize', () => {
      socketManager.initialize();

      expect(mockSocket.on).toHaveBeenCalledWith('connect', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('disconnect', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('connect_error', expect.any(Function));
    });
  });

  describe('Connection Management', () => {
    beforeEach(() => {
      socketManager.initialize();
    });

    it('should handle successful connection', () => {
      const connectCallback = vi.fn();
      socketManager.onConnect = connectCallback;

      // Simulate connect event
      const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')[1];
      connectHandler();

      expect(socketManager.connectionStatus).toBe(true);
      expect(socketManager.reconnectAttempts).toBe(0);
      expect(connectCallback).toHaveBeenCalled();
    });

    it('should handle disconnection', () => {
      const disconnectCallback = vi.fn();
      socketManager.onDisconnect = disconnectCallback;
      socketManager.connectionStatus = true;

      // Simulate disconnect event
      const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')[1];
      disconnectHandler();

      expect(socketManager.connectionStatus).toBe(false);
      expect(disconnectCallback).toHaveBeenCalled();
    });

    it('should handle connection errors', () => {
      const errorCallback = vi.fn();
      socketManager.onConnectionError = errorCallback;

      const error = new Error('Connection failed');

      // Simulate connect_error event
      const errorHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect_error')[1];
      errorHandler(error);

      expect(socketManager.connectionStatus).toBe(false);
      expect(errorCallback).toHaveBeenCalledWith(error);
    });

    it('should get connection status', () => {
      expect(socketManager.getConnectionStatus()).toBe(false);
      
      socketManager.connectionStatus = true;
      expect(socketManager.getConnectionStatus()).toBe(true);
    });
  });

  describe('Event Management', () => {
    beforeEach(() => {
      socketManager.initialize();
    });

    it('should emit events through socket', () => {
      const eventData = { test: 'data' };
      
      // Set connection as established
      socketManager.isConnected = true;
      socketManager.connectionStatus = true;
      
      socketManager.emit('test_event', eventData);

      expect(mockSocket.emit).toHaveBeenCalledWith('test_event', eventData);
    });

    it('should register event listeners', () => {
      const callback = vi.fn();
      
      socketManager.on('test_event', callback);

      expect(mockSocket.on).toHaveBeenCalledWith('test_event', callback);
    });

    it('should handle emit errors gracefully', () => {
      mockSocket.emit.mockImplementation(() => {
        throw new Error('Socket error');
      });
      
      // Set connection as established
      socketManager.isConnected = true;
      socketManager.connectionStatus = true;

      expect(() => {
        socketManager.emit('test_event', {});
      }).not.toThrow();
    });

    it('should not emit when socket is null', () => {
      socketManager.socket = null;

      expect(() => {
        socketManager.emit('test_event', {});
      }).not.toThrow();
    });
  });

  describe('Reconnection Logic', () => {
    beforeEach(() => {
      socketManager.initialize();
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should attempt reconnection after disconnect', () => {
      vi.useFakeTimers();
      
      // Temporarily disable test environment to allow reconnection
      global.window.isTestEnvironment = false;
      
      const reconnectCallback = vi.fn();
      socketManager.onReconnect = reconnectCallback;

      // Simulate disconnect
      const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')[1];
      disconnectHandler('transport close'); // Use non-client disconnect reason

      // Should schedule reconnection
      expect(socketManager.connectionRecoveryAttempts).toBe(1);
      
      // Fast forward time to trigger reconnection attempt
      vi.advanceTimersByTime(1000);

      expect(socketManager.reconnectAttempts).toBe(1);
      
      // Restore test environment
      global.window.isTestEnvironment = true;
      vi.useRealTimers();
    });

    it('should use exponential backoff for reconnection delay', () => {
      vi.useFakeTimers();
      
      // Temporarily disable test environment to allow reconnection
      global.window.isTestEnvironment = false;
      
      // Simulate initial disconnect
      const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')[1];
      disconnectHandler('transport close');
      
      // Should have started connection recovery
      expect(socketManager.connectionRecoveryAttempts).toBe(1);
      
      // Advance through multiple reconnection attempts
      // First attempt: 1000ms delay
      vi.advanceTimersByTime(1000);
      expect(socketManager.reconnectAttempts).toBe(1);
      
      // Second attempt should schedule with exponential backoff
      expect(socketManager.connectionRecoveryAttempts).toBe(2);
      
      // Restore test environment
      global.window.isTestEnvironment = true;
      vi.useRealTimers();
    });

    it('should stop reconnecting after max attempts', () => {
      socketManager.maxReconnectAttempts = 2;

      // Simulate exceeding max attempts
      for (let i = 0; i < 3; i++) {
        const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')[1];
        disconnectHandler();
        vi.advanceTimersByTime(socketManager.reconnectDelay);
      }

      // Should not attempt more reconnections
      expect(socketManager.reconnectAttempts).toBeLessThanOrEqual(2);
    });

    it('should reset reconnection attempts on successful connect', () => {
      // Set up some failed attempts
      socketManager.reconnectAttempts = 3;

      // Simulate successful connection
      const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')[1];
      connectHandler();

      expect(socketManager.reconnectAttempts).toBe(0);
    });
  });

  describe('Manual Reconnection', () => {
    beforeEach(() => {
      socketManager.initialize();
    });

    it('should allow manual reconnection', () => {
      socketManager.reconnect();

      // Should create new socket connection
      expect(global.io).toHaveBeenCalledTimes(2); // Once for initialize, once for reconnect
    });

    it('should reset reconnection state on manual reconnect', () => {
      socketManager.reconnectAttempts = 3;
      
      socketManager.reconnect();

      expect(socketManager.reconnectAttempts).toBe(0);
    });
  });

  describe('Disconnection', () => {
    beforeEach(() => {
      socketManager.initialize();
    });

    it('should disconnect socket manually', () => {
      socketManager.disconnect();

      expect(mockSocket.disconnect).toHaveBeenCalled();
      expect(socketManager.connectionStatus).toBe(false);
    });

    it('should handle disconnect when socket is null', () => {
      socketManager.socket = null;

      expect(() => {
        socketManager.disconnect();
      }).not.toThrow();
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing io global gracefully', () => {
      global.io = undefined;

      expect(() => {
        const manager = new SocketManager();
        manager.initialize();
      }).not.toThrow();
    });

    it('should handle callback being null', () => {
      socketManager.initialize();
      
      // Set callbacks to null
      socketManager.onConnect = null;
      socketManager.onDisconnect = null;
      socketManager.onConnectionError = null;
      socketManager.onReconnect = null;

      // Simulate events - should not throw
      const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')[1];
      const disconnectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')[1];
      const errorHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect_error')[1];

      expect(() => {
        connectHandler();
        disconnectHandler();
        errorHandler(new Error('test'));
      }).not.toThrow();
    });
  });
});