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

class GameClient {
    constructor() {
        // Initialize all modules
        this.socketManager = new SocketManager();
        this.gameStateManager = new GameStateManager();
        this.timerManager = new TimerManager();
        this.toastManager = new ToastManager();
        this.uiManager = new UIManager();
        
        // Initialize event manager with all dependencies
        this.eventManager = new EventManager(
            this.socketManager,
            this.gameStateManager,
            this.uiManager,
            this.timerManager,
            this.toastManager
        );
        
        this.isInitialized = false;
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initialize());
        } else {
            this.initialize();
        }
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
        
        // Wait for UI to be ready
        this.uiManager.initialize();
        
        // Set up connection handling
        this._setupConnectionFlow();
        
        // Initialize event manager
        const roomId = typeof window.roomId !== 'undefined' ? window.roomId : null;
        this.eventManager.initialize(roomId);
        
        this.isInitialized = true;
        console.log('Game client initialization complete');
    }
    
    /**
     * Get current game state
     * @returns {Object} Current game state
     */
    getGameState() {
        return this.gameStateManager.getState();
    }
    
    /**
     * Get connection status
     * @returns {boolean} Whether client is connected
     */
    isConnected() {
        return this.socketManager.getConnectionStatus();
    }
    
    /**
     * Get room information
     * @returns {Object} Room information
     */
    getRoomInfo() {
        return this.gameStateManager.roomInfo;
    }
    
    /**
     * Get players list
     * @returns {Array} Current players
     */
    getPlayers() {
        return this.gameStateManager.players;
    }
    
    /**
     * Force reconnection attempt
     */
    reconnect() {
        this.socketManager.reconnect();
    }
    
    /**
     * Disconnect from server
     */
    disconnect() {
        this.socketManager.disconnect();
        this.timerManager.clearAllTimers();
    }
    
    /**
     * Join a specific room (programmatic API)
     * @param {string} roomId - Room ID
     * @param {string} playerName - Player name
     */
    joinRoom(roomId, playerName) {
        this.eventManager.joinRoom(roomId, playerName);
    }
    
    /**
     * Leave current room (programmatic API)
     */
    leaveRoom() {
        this.eventManager.leaveRoom();
    }
    
    /**
     * Start a new round (programmatic API)
     */
    startRound() {
        this.eventManager.startRound();
    }
    
    /**
     * Submit response (programmatic API)
     * @param {string} responseText - Response text
     */
    submitResponse(responseText) {
        this.eventManager.submitResponse(responseText);
    }
    
    /**
     * Submit guess (programmatic API)
     * @param {number} responseIndex - Response index
     */
    submitGuess(responseIndex) {
        this.eventManager.submitGuess(responseIndex);
    }
    
    /**
     * Show toast notification (programmatic API)
     * @param {string} message - Message to show
     * @param {string} type - Toast type (success, error, warning, info)
     * @param {boolean} persistent - Whether to auto-dismiss
     */
    showToast(message, type = 'info', persistent = false) {
        this.toastManager.show(message, type, persistent);
    }
    
    /**
     * Clear all toast notifications
     */
    clearToasts() {
        this.toastManager.clearAll();
    }
    
    /**
     * Get module references (for debugging/advanced usage)
     * @returns {Object} All module instances
     */
    getModules() {
        return {
            socket: this.socketManager,
            gameState: this.gameStateManager,
            ui: this.uiManager,
            timer: this.timerManager,
            toast: this.toastManager,
            event: this.eventManager
        };
    }
    
    /**
     * Clean up resources and destroy the game client
     */
    destroy() {
        console.log('Destroying GameClient...');
        
        // Destroy all modules that have destroy methods
        if (this.timerManager && this.timerManager.destroy) {
            this.timerManager.destroy();
        }
        if (this.toastManager && this.toastManager.destroy) {
            this.toastManager.destroy();
        }
        if (this.gameStateManager && this.gameStateManager.destroy) {
            this.gameStateManager.destroy();
        }
        if (this.eventManager && this.eventManager.destroy) {
            this.eventManager.destroy();
        }
        if (this.uiManager && this.uiManager.destroy) {
            this.uiManager.destroy();
        }
        if (this.socketManager && this.socketManager.destroy) {
            this.socketManager.destroy();
        }
        
        // Clear references
        this.socketManager = null;
        this.gameStateManager = null;
        this.timerManager = null;
        this.toastManager = null;
        this.uiManager = null;
        this.eventManager = null;
        
        this.isInitialized = false;
        
        console.log('GameClient destroyed');
    }
    
    // Private methods
    
    _setupConnectionFlow() {
        // Set up auto-join flow after connection
        this.socketManager.onConnect = () => {
            console.log('Connected to server');
            this.uiManager.updateConnectionStatus('connected', 'Connected');
            
            // Auto-join room if we have room ID
            const roomId = typeof window.roomId !== 'undefined' ? window.roomId : null;
            if (roomId) {
                this.eventManager.autoJoinRoom(roomId);
            }
        };
        
        this.socketManager.onDisconnect = () => {
            console.log('Disconnected from server');
            this.uiManager.updateConnectionStatus('disconnected', 'Disconnected');
            this.toastManager.warning('Connection lost. Attempting to reconnect...');
        };
        
        this.socketManager.onConnectionError = (error) => {
            console.error('Connection error:', error);
            this.uiManager.updateConnectionStatus('error', 'Connection Error');
            this.toastManager.error('Failed to connect to server');
        };
        
        this.socketManager.onReconnect = () => {
            console.log('Reconnected to server');
            this.uiManager.updateConnectionStatus('connected', 'Connected');
            this.toastManager.success('Reconnected successfully!');
            
            // Auto-rejoin room after reconnection
            const roomInfo = this.gameStateManager.roomInfo;
            if (roomInfo.roomId && roomInfo.playerName) {
                console.log('Rejoining room after reconnection...');
                this.eventManager.joinRoom(roomInfo.roomId, roomInfo.playerName);
            }
        };
    }
}

export default GameClient;

