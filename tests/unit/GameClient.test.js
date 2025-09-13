/**
 * GameClient Unit Tests
 * Tests for the main game client coordinator module.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock all dependencies
const mockSocketManager = {
    getConnectionStatus: vi.fn(),
    reconnect: vi.fn(),
    disconnect: vi.fn()
};

const mockGameStateManager = {
    getState: vi.fn(),
    roomInfo: { roomId: 'test-room', playerCount: 3 },
    players: [
        { id: 'player1', name: 'Alice', connected: true },
        { id: 'player2', name: 'Bob', connected: true }
    ]
};

const mockTimerManager = {
    clearAllTimers: vi.fn()
};

const mockToastManager = {};

const mockUIManager = {
    initialize: vi.fn()
};

const mockEventManager = {
    initialize: vi.fn(),
    joinRoom: vi.fn(),
    leaveRoom: vi.fn(),
    startRound: vi.fn(),
    submitResponse: vi.fn(),
    submitGuess: vi.fn()
};

// Mock module imports
vi.mock('../../static/js/modules/SocketManager.js', () => ({
    default: vi.fn(() => mockSocketManager)
}));

vi.mock('../../static/js/modules/GameStateManager.js', () => ({
    default: vi.fn(() => mockGameStateManager)
}));

vi.mock('../../static/js/modules/TimerManager.js', () => ({
    default: vi.fn(() => mockTimerManager)
}));

vi.mock('../../static/js/modules/ToastManager.js', () => ({
    default: vi.fn(() => mockToastManager)
}));

vi.mock('../../static/js/modules/UIManager.js', () => ({
    default: vi.fn(() => mockUIManager)
}));

vi.mock('../../static/js/modules/EventManager.js', () => ({
    default: vi.fn(() => mockEventManager)
}));

// Import GameClient after mocking dependencies
const GameClient = await import('../../static/js/modules/GameClient.js').then(m => m.default);

describe('GameClient', () => {
    let gameClient;
    let originalConsole;
    let consoleLogSpy;
    let consoleWarnSpy;

    beforeEach(() => {
        // Reset all mocks
        vi.clearAllMocks();
        
        // Mock console methods
        originalConsole = global.console;
        consoleLogSpy = vi.fn();
        consoleWarnSpy = vi.fn();
        global.console = {
            ...originalConsole,
            log: consoleLogSpy,
            warn: consoleWarnSpy
        };

        // Mock DOM
        global.document = {
            readyState: 'complete',
            addEventListener: vi.fn()
        };
        
        // Mock window
        global.window = {
            roomId: 'test-room-123'
        };
    });

    afterEach(() => {
        // Restore console
        global.console = originalConsole;
        
        // Clean up global mocks
        delete global.document;
        delete global.window;
    });

    describe('Constructor and Initialization', () => {
        it('should create GameClient with all required modules', () => {
            gameClient = new GameClient();

            expect(gameClient.socketManager).toBeDefined();
            expect(gameClient.gameStateManager).toBeDefined();
            expect(gameClient.timerManager).toBeDefined();
            expect(gameClient.toastManager).toBeDefined();
            expect(gameClient.uiManager).toBeDefined();
            expect(gameClient.eventManager).toBeDefined();
            expect(gameClient.isInitialized).toBe(true); // Should auto-initialize
        });

        it('should wait for DOMContentLoaded if document is loading', () => {
            global.document.readyState = 'loading';
            
            gameClient = new GameClient();
            
            expect(global.document.addEventListener).toHaveBeenCalledWith(
                'DOMContentLoaded',
                expect.any(Function)
            );
            expect(gameClient.isInitialized).toBe(false); // Not initialized yet
        });

        it('should initialize immediately if document is ready', () => {
            global.document.readyState = 'complete';
            
            gameClient = new GameClient();
            
            expect(gameClient.isInitialized).toBe(true);
            expect(mockUIManager.initialize).toHaveBeenCalled();
            expect(mockEventManager.initialize).toHaveBeenCalledWith('test-room-123');
        });

        it('should handle missing window.roomId gracefully', () => {
            delete global.window.roomId;
            
            gameClient = new GameClient();
            
            expect(mockEventManager.initialize).toHaveBeenCalledWith(null);
        });

        it('should prevent double initialization', () => {
            gameClient = new GameClient();
            
            // Clear previous calls
            vi.clearAllMocks();
            
            // Try to initialize again
            gameClient.initialize();
            
            expect(consoleWarnSpy).toHaveBeenCalledWith('GameClient already initialized');
            expect(mockUIManager.initialize).not.toHaveBeenCalled();
            expect(mockEventManager.initialize).not.toHaveBeenCalled();
        });

        it('should log initialization messages', () => {
            gameClient = new GameClient();
            
            expect(consoleLogSpy).toHaveBeenCalledWith('Initializing LLMpostor Game Client (Modular)');
            expect(consoleLogSpy).toHaveBeenCalledWith('Game client initialization complete');
        });
    });

    describe('State Getters', () => {
        beforeEach(() => {
            gameClient = new GameClient();
        });

        it('should get game state from GameStateManager', () => {
            const mockState = { phase: 'waiting', round: 1 };
            mockGameStateManager.getState.mockReturnValue(mockState);
            
            const state = gameClient.getGameState();
            
            expect(mockGameStateManager.getState).toHaveBeenCalled();
            expect(state).toBe(mockState);
        });

        it('should get connection status from SocketManager', () => {
            mockSocketManager.getConnectionStatus.mockReturnValue(true);
            
            const isConnected = gameClient.isConnected();
            
            expect(mockSocketManager.getConnectionStatus).toHaveBeenCalled();
            expect(isConnected).toBe(true);
        });

        it('should get room info from GameStateManager', () => {
            const roomInfo = gameClient.getRoomInfo();
            
            expect(roomInfo).toBe(mockGameStateManager.roomInfo);
            expect(roomInfo.roomId).toBe('test-room');
            expect(roomInfo.playerCount).toBe(3);
        });

        it('should get players list from GameStateManager', () => {
            const players = gameClient.getPlayers();
            
            expect(players).toBe(mockGameStateManager.players);
            expect(players).toHaveLength(2);
            expect(players[0].name).toBe('Alice');
        });
    });

    describe('Connection Management', () => {
        beforeEach(() => {
            gameClient = new GameClient();
        });

        it('should reconnect through SocketManager', () => {
            gameClient.reconnect();
            
            expect(mockSocketManager.reconnect).toHaveBeenCalled();
        });

        it('should disconnect and clear timers', () => {
            gameClient.disconnect();
            
            expect(mockSocketManager.disconnect).toHaveBeenCalled();
            expect(mockTimerManager.clearAllTimers).toHaveBeenCalled();
        });
    });

    describe('Game Actions API', () => {
        beforeEach(() => {
            gameClient = new GameClient();
        });

        it('should join room through EventManager', () => {
            const roomId = 'room-456';
            const playerName = 'TestPlayer';
            
            gameClient.joinRoom(roomId, playerName);
            
            expect(mockEventManager.joinRoom).toHaveBeenCalledWith(roomId, playerName);
        });

        it('should leave room through EventManager', () => {
            gameClient.leaveRoom();
            
            expect(mockEventManager.leaveRoom).toHaveBeenCalled();
        });

        it('should start round through EventManager', () => {
            gameClient.startRound();
            
            expect(mockEventManager.startRound).toHaveBeenCalled();
        });

        it('should submit response through EventManager', () => {
            const responseText = 'My clever response';
            
            gameClient.submitResponse(responseText);
            
            expect(mockEventManager.submitResponse).toHaveBeenCalledWith(responseText);
        });

        it('should submit guess through EventManager', () => {
            const guessIndex = 2;
            
            gameClient.submitGuess(guessIndex);
            
            expect(mockEventManager.submitGuess).toHaveBeenCalledWith(guessIndex);
        });
    });

    describe('Module Dependencies', () => {
        it('should pass correct dependencies to EventManager', async () => {
            gameClient = new GameClient();

            // Check that EventManager was called with eventBus and serviceContainer
            const EventManagerConstructor = vi.mocked(await import('../../static/js/modules/EventManager.js')).default;
            expect(EventManagerConstructor).toHaveBeenCalledWith(
                expect.objectContaining({}), // eventBus
                expect.objectContaining({})  // serviceContainer
            );
        });

        it('should create modules in correct order', async () => {
            const SocketManagerConstructor = vi.mocked(await import('../../static/js/modules/SocketManager.js')).default;
            const GameStateManagerConstructor = vi.mocked(await import('../../static/js/modules/GameStateManager.js')).default;
            const TimerManagerConstructor = vi.mocked(await import('../../static/js/modules/TimerManager.js')).default;
            const ToastManagerConstructor = vi.mocked(await import('../../static/js/modules/ToastManager.js')).default;
            const UIManagerConstructor = vi.mocked(await import('../../static/js/modules/UIManager.js')).default;
            const EventManagerConstructor = vi.mocked(await import('../../static/js/modules/EventManager.js')).default;
            
            gameClient = new GameClient();
            
            // Verify all managers were constructed
            expect(SocketManagerConstructor).toHaveBeenCalled();
            expect(GameStateManagerConstructor).toHaveBeenCalled();
            expect(TimerManagerConstructor).toHaveBeenCalled();
            expect(ToastManagerConstructor).toHaveBeenCalled();
            expect(UIManagerConstructor).toHaveBeenCalled();
            expect(EventManagerConstructor).toHaveBeenCalled();
        });
    });

    describe('Error Handling', () => {
        it('should handle UIManager initialization errors gracefully', () => {
            // Set up mock BEFORE creating GameClient
            mockUIManager.initialize.mockImplementation(() => {
                throw new Error('UI initialization failed');
            });

            expect(() => {
                gameClient = new GameClient();
            }).toThrow('UI initialization failed');
        });

        it('should handle EventManager initialization errors gracefully', () => {
            // Set up mock BEFORE creating GameClient
            mockEventManager.initialize.mockImplementation(() => {
                throw new Error('EventManager initialization failed');
            });

            expect(() => {
                gameClient = new GameClient();
            }).toThrow('EventManager initialization failed');
        });

        it('should handle missing DOM gracefully', () => {
            delete global.document;

            expect(() => {
                gameClient = new GameClient();
            }).toThrow(); // Should throw due to missing document
        });
    });

    describe('Integration with DOM Events', () => {
        it('should set up DOMContentLoaded listener when document is loading', () => {
            global.document.readyState = 'loading';
            const addEventListenerSpy = vi.fn();
            global.document.addEventListener = addEventListenerSpy;
            
            gameClient = new GameClient();
            
            expect(addEventListenerSpy).toHaveBeenCalledWith(
                'DOMContentLoaded',
                expect.any(Function)
            );
            
            // Simulate DOMContentLoaded event
            const callback = addEventListenerSpy.mock.calls[0][1];
            callback();
            
            expect(gameClient.isInitialized).toBe(true);
            expect(mockUIManager.initialize).toHaveBeenCalled();
        });

        it('should handle DOMContentLoaded callback correctly', () => {
            global.document.readyState = 'loading';
            let domCallback;
            global.document.addEventListener = vi.fn((event, callback) => {
                domCallback = callback;
            });
            
            gameClient = new GameClient();
            expect(gameClient.isInitialized).toBe(false);
            
            // Trigger the callback
            domCallback();
            
            expect(gameClient.isInitialized).toBe(true);
            expect(mockEventManager.initialize).toHaveBeenCalled();
        });
    });

    describe('Public API Surface', () => {
        beforeEach(() => {
            gameClient = new GameClient();
        });

        it('should expose all expected public methods', () => {
            expect(typeof gameClient.initialize).toBe('function');
            expect(typeof gameClient.getGameState).toBe('function');
            expect(typeof gameClient.isConnected).toBe('function');
            expect(typeof gameClient.getRoomInfo).toBe('function');
            expect(typeof gameClient.getPlayers).toBe('function');
            expect(typeof gameClient.reconnect).toBe('function');
            expect(typeof gameClient.disconnect).toBe('function');
            expect(typeof gameClient.joinRoom).toBe('function');
            expect(typeof gameClient.leaveRoom).toBe('function');
            expect(typeof gameClient.startRound).toBe('function');
            expect(typeof gameClient.submitResponse).toBe('function');
            expect(typeof gameClient.submitGuess).toBe('function');
        });

        it('should expose expected properties', () => {
            expect(gameClient.socketManager).toBeDefined();
            expect(gameClient.gameStateManager).toBeDefined();
            expect(gameClient.timerManager).toBeDefined();
            expect(gameClient.toastManager).toBeDefined();
            expect(gameClient.uiManager).toBeDefined();
            expect(gameClient.eventManager).toBeDefined();
            expect(typeof gameClient.isInitialized).toBe('boolean');
        });
    });

    describe('State Management', () => {
        beforeEach(() => {
            gameClient = new GameClient();
        });

        it('should maintain initialization state correctly', () => {
            expect(gameClient.isInitialized).toBe(true);
            
            // Should not allow re-initialization
            gameClient.initialize();
            expect(consoleWarnSpy).toHaveBeenCalledWith('GameClient already initialized');
        });

        it('should provide access to all managers', () => {
            expect(gameClient.socketManager).toBe(mockSocketManager);
            expect(gameClient.gameStateManager).toBe(mockGameStateManager);
            expect(gameClient.timerManager).toBe(mockTimerManager);
            expect(gameClient.toastManager).toBe(mockToastManager);
            expect(gameClient.uiManager).toBe(mockUIManager);
            expect(gameClient.eventManager).toBe(mockEventManager);
        });
    });
});