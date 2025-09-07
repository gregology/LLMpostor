/**
 * LLMpostor Game Client - Modular Entry Point
 * 
 * This is the new modular version of the LLMpostor game client.
 * It replaces the monolithic game.js with a clean, maintainable architecture.
 * 
 * Architecture:
 * - EventBus: Centralized event communication system
 * - SocketManager: WebSocket communication
 * - GameStateManager: Game state and synchronization
 * - UIManager: DOM manipulation and rendering
 * - TimerManager: Timer functionality
 * - ToastManager: Notification system
 * - EventManager: Event coordination and business logic
 * - GameClient: Main coordinator
 */

// Import all modules using ES6 imports
import SocketManager from './modules/SocketManager.js';
import GameStateManager from './modules/GameStateManager.js';
import TimerManager from './modules/TimerManager.js';
import ToastManager from './modules/ToastManager.js';
import UIManager from './modules/UIManager.js';
import EventManager from './modules/EventManager.js';
import GameClient from './modules/GameClient.js';

// Initialize game client
function initializeGameClient() {
    try {
        // Create global game client instance
        const gameClient = new GameClient();
        
        // Expose globally for debugging
        window.gameClient = gameClient;
        
        console.log('Modular LLMpostor game client initialized');
        return gameClient;
    } catch (error) {
        console.error('Failed to initialize game client:', error);
        
        // Show error to user
        document.body.insertAdjacentHTML('beforeend', `
            <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                        background: #fee; border: 2px solid #f00; padding: 20px; border-radius: 8px; 
                        font-family: Arial, sans-serif; text-align: center; z-index: 10000;">
                <h3 style="color: #c00; margin-top: 0;">Failed to Load Game</h3>
                <p>Could not initialize game modules: ${error.message}</p>
                <button onclick="window.location.reload()" style="padding: 8px 16px; 
                        background: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Refresh Page
                </button>
            </div>
        `);
        
        throw error;
    }
}

// Main initialization
function initialize() {
    console.log('Loading modular LLMpostor game client...');
    
    try {
        const gameClient = initializeGameClient();
        console.log('Game client ready');
    } catch (error) {
        console.error('Failed to initialize game client:', error);
    }
}

// Start initialization when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    // DOM already loaded, initialize immediately
    initialize();
}