/**
 * GameClient - Main coordinator for the modular LLMpostor game client
 * 
 * Responsible for:
 * - Initializing and coordinating all modules
 * - Providing the main API for the game
 * - Managing module dependencies
 * - Handling initialization flow
 */

import SocketManager from './SocketManager.js';
import GameStateManager from './GameStateManager.js';
import TimerManager from './TimerManager.js';
import ToastManager from './ToastManager.js';
import UIManager from './UIManager.js';
import EventManager from './EventManager.js';
import serviceContainer from '../utils/ServiceContainer.js';
import eventBus from './EventBus.js';
import { getBootstrapValue } from '../utils/Bootstrap.js';

class GameClient {
    constructor() {
        this.serviceContainer = serviceContainer;
        this.eventBus = eventBus;
        this.isInitialized = false;
        this.isRejoining = false;

        // Register all services with the container
        this._registerServices();

        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initialize());
        } else {
            this.initialize();
        }
    }

    /**
     * Register all services with the ServiceContainer
     * @private
     */
    _registerServices() {
        console.log('Registering services with ServiceContainer...');

        // Register core modules as services
        this.serviceContainer
            .register('SocketManager', () => new SocketManager())
            .register('GameStateManager', () => new GameStateManager())
            .register('TimerManager', () => new TimerManager())
            .register('ToastManager', () => new ToastManager())
            .register('UIManager', () => new UIManager())
            .register('EventManager', (socketManager, gameStateManager, uiManager, timerManager, toastManager, container) =>
                new EventManager(this.eventBus, container), {
                dependencies: ['SocketManager', 'GameStateManager', 'UIManager', 'TimerManager', 'ToastManager']
            });

        // Note: ErrorDisplayManager is registered externally in game-modular.js

        console.log('All services registered successfully');
    }

    /**
     * Get a service instance from the container
     * @param {string} serviceName - Name of the service
     * @returns {*} Service instance
     */
    getService(serviceName) {
        return this.serviceContainer.get(serviceName);
    }

    // Backward compatibility getters for tests
    get socketManager() {
        return this.getService('SocketManager');
    }

    get gameStateManager() {
        return this.getService('GameStateManager');
    }

    get timerManager() {
        return this.getService('TimerManager');
    }

    get toastManager() {
        return this.getService('ToastManager');
    }

    get uiManager() {
        return this.getService('UIManager');
    }

    get eventManager() {
        return this.getService('EventManager');
    }
    
    /**
     * Initialize the game client
     */
    initialize() {
        if (this.isInitialized) {
            console.warn('GameClient already initialized');
            return;
        }

        console.log('Initializing LLMpostor Game Client (Modular)');

        try {
            // Initialize UI first as other modules may depend on it
            const uiManager = this.getService('UIManager');
            uiManager.initialize();

            // Set up connection handling
            this._setupConnectionFlow();

            // Initialize event manager with room ID
            const eventManager = this.getService('EventManager');
            let roomId = null;
            try {
                roomId = getBootstrapValue('roomId', null);
            } catch (error) {
                console.warn('Bootstrap system not available, room ID will be null');
            }
            eventManager.initialize(roomId);

            this.isInitialized = true;
            console.log('Game client initialization complete');

        } catch (error) {
            console.error('Failed to initialize GameClient:', error);
            this._handleInitializationError(error);
            throw error;
        }
    }

    /**
     * Handle initialization errors
     * @private
     */
    _handleInitializationError(error) {
        try {
            const toastManager = this.getService('ToastManager');
            if (toastManager && typeof toastManager.error === 'function') {
                toastManager.error('Failed to initialize game. Please refresh the page.');
            } else {
                console.error('ToastManager service not available or missing error method');
            }
        } catch (toastError) {
            console.error('Could not show error toast:', toastError);
        }
    }
    
    /**
     * Get current game state
     * @returns {Object} Current game state
     */
    getGameState() {
        const gameStateManager = this.getService('GameStateManager');
        return gameStateManager.getState();
    }

    /**
     * Get connection status
     * @returns {boolean} Whether client is connected
     */
    isConnected() {
        const socketManager = this.getService('SocketManager');
        return socketManager.getConnectionStatus();
    }

    /**
     * Get room information
     * @returns {Object} Room information
     */
    getRoomInfo() {
        const gameStateManager = this.getService('GameStateManager');
        return gameStateManager.roomInfo;
    }

    /**
     * Get players list
     * @returns {Array} Current players
     */
    getPlayers() {
        const gameStateManager = this.getService('GameStateManager');
        return gameStateManager.players;
    }

    /**
     * Force reconnection attempt
     */
    reconnect() {
        const socketManager = this.getService('SocketManager');
        socketManager.reconnect();
    }

    /**
     * Disconnect from server
     */
    disconnect() {
        const socketManager = this.getService('SocketManager');
        const timerManager = this.getService('TimerManager');
        socketManager.disconnect();
        timerManager.clearAllTimers();
    }
    
    /**
     * Join a specific room (programmatic API)
     * @param {string} roomId - Room ID
     * @param {string} playerName - Player name
     */
    joinRoom(roomId, playerName) {
        const eventManager = this.getService('EventManager');
        eventManager.joinRoom(roomId, playerName);
    }

    /**
     * Leave current room (programmatic API)
     */
    leaveRoom() {
        const eventManager = this.getService('EventManager');
        eventManager.leaveRoom();
    }

    /**
     * Start a new round (programmatic API)
     */
    startRound() {
        const eventManager = this.getService('EventManager');
        eventManager.startRound();
    }

    /**
     * Submit response (programmatic API)
     * @param {string} responseText - Response text
     */
    submitResponse(responseText) {
        const eventManager = this.getService('EventManager');
        eventManager.submitResponse(responseText);
    }

    /**
     * Submit guess (programmatic API)
     * @param {number} responseIndex - Response index
     */
    submitGuess(responseIndex) {
        const eventManager = this.getService('EventManager');
        eventManager.submitGuess(responseIndex);
    }

    /**
     * Show toast notification (programmatic API)
     * @param {string} message - Message to show
     * @param {string} type - Toast type (success, error, warning, info)
     * @param {boolean} persistent - Whether to auto-dismiss
     */
    showToast(message, type = 'info', persistent = false) {
        const toastManager = this.getService('ToastManager');
        toastManager.show(message, type, persistent);
    }

    /**
     * Clear all toast notifications
     */
    clearToasts() {
        const toastManager = this.getService('ToastManager');
        toastManager.clearAll();
    }
    
    /**
     * Get module references (for debugging/advanced usage)
     * @returns {Object} All module instances
     */
    getModules() {
        return {
            socket: this.getService('SocketManager'),
            gameState: this.getService('GameStateManager'),
            ui: this.getService('UIManager'),
            timer: this.getService('TimerManager'),
            toast: this.getService('ToastManager'),
            event: this.getService('EventManager')
        };
    }

    /**
     * Get service container health status
     * @returns {Object} Health status of all services
     */
    getHealthStatus() {
        return this.serviceContainer.getHealthStatus();
    }
    
    /**
     * Clean up resources and destroy the game client
     */
    destroy() {
        console.log('Destroying GameClient...');

        try {
            // Destroy services through the container - this handles cleanup properly
            this.serviceContainer.clear();

            this.isInitialized = false;
            console.log('GameClient destroyed');

        } catch (error) {
            console.error('Error during GameClient destruction:', error);
        }
    }
    
    // Private methods
    
    _setupConnectionFlow() {
        const socketManager = this.getService('SocketManager');
        const uiManager = this.getService('UIManager');
        const toastManager = this.getService('ToastManager');
        const gameStateManager = this.getService('GameStateManager');
        const eventManager = this.getService('EventManager');

        // Subscribe to socket connection events via EventBus
        this.eventBus.subscribe('socket:connected', () => {
            console.log('GameClient: Received socket connected event');

            // Prevent duplicate rejoin attempts
            if (this.isRejoining) {
                console.log('GameClient: Already attempting to rejoin, skipping');
                return;
            }

            // Prioritize current URL's room ID over saved session
            try {
                const currentRoomId = getBootstrapValue('roomId', null);
                const savedSession = gameStateManager.restoreFromStorage();

                // If we have a current room ID from URL, use it
                if (currentRoomId) {
                    // If saved session is for a different room, clear it and join current room
                    if (savedSession && savedSession.roomId !== currentRoomId) {
                        console.log(`URL room (${currentRoomId}) differs from saved session (${savedSession.roomId}), joining URL room`);
                        gameStateManager.clearStoredSession();
                    }
                    eventManager.autoJoinRoom(currentRoomId);
                    return;
                }

                // Fall back to saved session if no current room ID
                if (savedSession) {
                    console.log('No room ID in URL, attempting to rejoin room from saved session...');
                    this.isRejoining = true;
                    this._attemptRoomRejoin(savedSession);
                    return;
                }
            } catch (error) {
                console.warn('Bootstrap system not available during connection flow');
            }
        });

        socketManager.onDisconnect = () => {
            console.log('Disconnected from server');
            uiManager.updateConnectionStatus('disconnected', 'Disconnected');
            toastManager.warning('Connection lost. Attempting to reconnect...');
        };

        socketManager.onConnectionError = (error) => {
            console.error('Connection error:', error);
            uiManager.updateConnectionStatus('error', 'Connection Error');
            toastManager.error('Failed to connect to server');
        };

        socketManager.onReconnect = () => {
            console.log('Reconnected to server');
            uiManager.updateConnectionStatus('connected', 'Connected');
            toastManager.success('Reconnected successfully!');

            // Try current room info first, then saved session as fallback
            const roomInfo = gameStateManager.roomInfo;
            if (roomInfo.roomId && roomInfo.playerName) {
                console.log('Rejoining room from current state after reconnection...');
                eventManager.joinRoom(roomInfo.roomId, roomInfo.playerName);
            } else {
                // Fallback to saved session if current state is empty
                const savedSession = gameStateManager.restoreFromStorage();
                if (savedSession) {
                    console.log('Rejoining room from saved session after reconnection...');
                    eventManager.joinRoom(savedSession.roomId, savedSession.playerName);
                }
            }
        };
    }
    
    /**
     * Attempt to rejoin room with error handling for invalid sessions
     * @private
     * @param {Object} savedSession - Session data from storage
     */
    _attemptRoomRejoin(savedSession) {
        const socketManager = this.getService('SocketManager');
        const eventManager = this.getService('EventManager');
        const toastManager = this.getService('ToastManager');
        let rejoinTimeoutId;

        // Set up one-time listener for room join result
        const handleRoomJoined = (data) => {
            clearTimeout(rejoinTimeoutId);
            this.isRejoining = false; // Reset flag

            if (data && data.success) {
                console.log('Successfully rejoined room from saved session');
                toastManager.success('Welcome back! Rejoined your game.');
            } else {
                this._handleRejoinFailure(savedSession, 'Room join failed');
            }
        };

        // Set up timeout for join attempt
        rejoinTimeoutId = setTimeout(() => {
            this.isRejoining = false; // Reset flag
            this._handleRejoinFailure(savedSession, 'Room join timeout');
        }, 5000); // 5 second timeout

        // Listen for room join response (one-time)
        socketManager.socket.once('room_joined', handleRoomJoined);

        // Attempt to join
        try {
            eventManager.joinRoom(savedSession.roomId, savedSession.playerName);
        } catch (error) {
            clearTimeout(rejoinTimeoutId);
            this.isRejoining = false; // Reset flag
            this._handleRejoinFailure(savedSession, 'Failed to send join request');
        }
    }

    /**
     * Handle failed room rejoin attempts
     * @private
     * @param {Object} savedSession - Session data that failed
     * @param {string} reason - Reason for failure
     */
    _handleRejoinFailure(savedSession, reason) {
        const gameStateManager = this.getService('GameStateManager');
        const toastManager = this.getService('ToastManager');
        const eventManager = this.getService('EventManager');

        console.warn(`Room rejoin failed: ${reason}. Clearing invalid session.`);

        // Clear invalid session data
        gameStateManager.clearStoredSession();

        // Show user-friendly message
        toastManager.warning(`Couldn't rejoin your previous room. Starting fresh.`);

        // Fall back to bootstrap room ID if available
        try {
            const roomId = getBootstrapValue('roomId', null);
            if (roomId && roomId !== savedSession.roomId) {
                console.log('Falling back to bootstrap room ID');
                eventManager.autoJoinRoom(roomId);
            }
        } catch (error) {
            console.warn('Bootstrap system not available during rejoin failure handling');
        }
    }
}

export default GameClient;

