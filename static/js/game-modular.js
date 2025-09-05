/**
 * LLMposter Game Client - Modular Entry Point
 * 
 * This is the new modular version of the LLMposter game client.
 * It replaces the monolithic game.js with a clean, maintainable architecture.
 * 
 * Architecture:
 * - SocketManager: WebSocket communication
 * - GameStateManager: Game state and synchronization
 * - UIManager: DOM manipulation and rendering
 * - TimerManager: Timer functionality
 * - ToastManager: Notification system
 * - EventManager: Event coordination and business logic
 * - GameClient: Main coordinator
 */

// Module loading and initialization
(function() {
    'use strict';
    
    // Check if we're in a module environment
    const isModuleEnvironment = typeof module !== 'undefined' && module.exports;
    
    // Module loader for browser environment
    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    
    // Load all modules in sequence
    async function loadModules() {
        const baseUrl = '/static/js/modules/';
        const modules = [
            'SocketManager.js',
            'GameStateManager.js',
            'TimerManager.js', 
            'ToastManager.js',
            'UIManager.js',
            'EventManager.js',
            'GameClient.js'
        ];
        
        try {
            for (const module of modules) {
                await loadScript(baseUrl + module);
            }
            console.log('All modules loaded successfully');
            return true;
        } catch (error) {
            console.error('Failed to load modules:', error);
            return false;
        }
    }
    
    // Initialize game client
    function initializeGameClient() {
        // Create global game client instance
        const gameClient = new GameClient();
        
        // Expose globally for debugging and compatibility
        window.gameClient = gameClient;
        
        // For backward compatibility, expose some methods on window
        window.LLMposterGame = {
            getState: () => gameClient.getGameState(),
            isConnected: () => gameClient.isConnected(),
            getRoomInfo: () => gameClient.getRoomInfo(),
            showToast: (message, type, persistent) => gameClient.showToast(message, type, persistent),
            reconnect: () => gameClient.reconnect(),
            disconnect: () => gameClient.disconnect()
        };
        
        console.log('Modular LLMposter game client initialized');
        return gameClient;
    }
    
    // Main initialization
    async function initialize() {
        console.log('Loading modular LLMposter game client...');
        
        // Load all modules
        const modulesLoaded = await loadModules();
        if (!modulesLoaded) {
            console.error('Failed to load game modules');
            // Fallback error display
            document.body.insertAdjacentHTML('beforeend', `
                <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                            background: #fee; border: 2px solid #f00; padding: 20px; border-radius: 8px; 
                            font-family: Arial, sans-serif; text-align: center; z-index: 10000;">
                    <h3 style="color: #c00; margin-top: 0;">Failed to Load Game</h3>
                    <p>Could not load game modules. Please refresh the page.</p>
                    <button onclick="window.location.reload()" style="padding: 8px 16px; 
                            background: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Refresh Page
                    </button>
                </div>
            `);
            return;
        }
        
        // Initialize game client
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
    
})();