/**
 * IGameModule - Interface for game-specific modules
 *
 * Defines contracts specific to LLMpostor game modules including
 * socket communication, state management, and UI interaction patterns.
 */

import { IServiceModule } from './IModule.js';

/**
 * ISocketModule - Interface for modules that handle socket communication
 */
export class ISocketModule extends IServiceModule {
    constructor(name, eventBus, serviceContainer) {
        super(name, eventBus, serviceContainer);
        this._socketHandlers = new Map();
    }

    /**
     * Register a socket event handler
     * @param {string} eventName - Socket event name
     * @param {Function} handler - Event handler function
     */
    onSocket(eventName, handler) {
        if (this._socketHandlers.has(eventName)) {
            console.warn(`Socket handler for '${eventName}' already registered in module ${this.name}`);
        }

        this._socketHandlers.set(eventName, handler);
    }

    /**
     * Emit a socket event
     * @param {string} eventName - Socket event name
     * @param {*} data - Event data
     */
    emitSocket(eventName, data) {
        // This should be implemented by concrete classes
        throw new Error('emitSocket must be implemented by concrete module');
    }

    /**
     * Get all registered socket handlers
     * @returns {Map} Socket handlers map
     */
    getSocketHandlers() {
        return new Map(this._socketHandlers);
    }

    destroy() {
        this._socketHandlers.clear();
        super.destroy();
    }
}

/**
 * IUIModule - Interface for modules that handle UI updates
 */
export class IUIModule extends IServiceModule {
    constructor(name, eventBus, serviceContainer) {
        super(name, eventBus, serviceContainer);
        this._elements = new Map();
        this._eventListeners = [];
    }

    /**
     * Cache DOM element reference
     * @param {string} key - Element key
     * @param {string} selector - CSS selector
     * @returns {Element|null} DOM element
     */
    getElement(key, selector) {
        if (!this._elements.has(key)) {
            const element = document.querySelector(selector);
            if (element) {
                this._elements.set(key, element);
            } else {
                console.warn(`Element not found for selector '${selector}' in module ${this.name}`);
                return null;
            }
        }
        return this._elements.get(key);
    }

    /**
     * Add event listener and track for cleanup
     * @param {Element} element - DOM element
     * @param {string} event - Event type
     * @param {Function} handler - Event handler
     * @param {Object} options - Event options
     */
    addEventListener(element, event, handler, options = {}) {
        if (!element) {
            console.error(`Cannot add event listener: element is null in module ${this.name}`);
            return;
        }

        element.addEventListener(event, handler, options);
        this._eventListeners.push({ element, event, handler, options });
    }

    /**
     * Update UI based on state changes
     * @param {Object} state - New state
     */
    updateUI(state) {
        // This should be implemented by concrete classes
        console.warn(`updateUI not implemented in module ${this.name}`);
    }

    /**
     * Show loading state
     */
    showLoading() {
        // This can be overridden by concrete classes
        console.log(`${this.name}: Showing loading state`);
    }

    /**
     * Hide loading state
     */
    hideLoading() {
        // This can be overridden by concrete classes
        console.log(`${this.name}: Hiding loading state`);
    }

    destroy() {
        // Remove all event listeners
        this._eventListeners.forEach(({ element, event, handler, options }) => {
            try {
                element.removeEventListener(event, handler, options);
            } catch (error) {
                console.error(`Error removing event listener in module ${this.name}:`, error);
            }
        });

        this._eventListeners = [];
        this._elements.clear();
        super.destroy();
    }
}

/**
 * IGameStateModule - Interface for modules that manage game state
 */
export class IGameStateModule extends IServiceModule {
    constructor(name, eventBus, serviceContainer) {
        super(name, eventBus, serviceContainer);
        this._state = {};
        this._stateHistory = [];
        this._maxHistorySize = 50;
    }

    /**
     * Get current state
     * @returns {Object} Current state
     */
    getState() {
        return { ...this._state };
    }

    /**
     * Update state and notify subscribers
     * @param {Object} newState - New state object
     * @param {Object} options - Update options
     */
    updateState(newState, options = {}) {
        const previousState = { ...this._state };
        this._state = { ...this._state, ...newState };

        // Add to history
        this._addToHistory(previousState, this._state);

        // Publish state change event
        if (!options.silent) {
            this.publish(`${this.name.toLowerCase()}:state:changed`, {
                previousState,
                newState: this._state,
                changes: newState
            });
        }
    }

    /**
     * Reset state to initial values
     * @param {Object} initialState - Initial state
     */
    resetState(initialState = {}) {
        this._state = { ...initialState };
        this._stateHistory = [];

        this.publish(`${this.name.toLowerCase()}:state:reset`, {
            newState: this._state
        });
    }

    /**
     * Get state history
     * @param {number} limit - Maximum number of history entries
     * @returns {Array} State history
     */
    getStateHistory(limit = 10) {
        return this._stateHistory.slice(-limit);
    }

    /**
     * Validate state changes
     * @param {Object} newState - New state to validate
     * @returns {boolean} True if valid
     */
    validateState(newState) {
        // This should be implemented by concrete classes
        return true;
    }

    _addToHistory(previousState, newState) {
        this._stateHistory.push({
            timestamp: Date.now(),
            previousState,
            newState: { ...newState }
        });

        // Limit history size
        if (this._stateHistory.length > this._maxHistorySize) {
            this._stateHistory = this._stateHistory.slice(-this._maxHistorySize);
        }
    }

    destroy() {
        this._state = {};
        this._stateHistory = [];
        super.destroy();
    }
}

/**
 * ITimerModule - Interface for modules that handle timing functionality
 */
export class ITimerModule extends IServiceModule {
    constructor(name, eventBus, serviceContainer) {
        super(name, eventBus, serviceContainer);
        this._timers = new Map();
    }

    /**
     * Start a timer
     * @param {string} name - Timer name
     * @param {number} duration - Duration in milliseconds
     * @param {Function} callback - Callback when timer expires
     * @param {Object} options - Timer options
     */
    startTimer(name, duration, callback, options = {}) {
        this.clearTimer(name); // Clear existing timer

        const timerId = setTimeout(() => {
            this._timers.delete(name);
            if (callback) callback();

            this.publish('timer:expired', {
                name,
                duration,
                source: this.name
            });
        }, duration);

        this._timers.set(name, {
            id: timerId,
            startTime: Date.now(),
            duration,
            callback,
            options
        });

        this.publish('timer:started', {
            name,
            duration,
            source: this.name
        });
    }

    /**
     * Clear a timer
     * @param {string} name - Timer name
     */
    clearTimer(name) {
        const timer = this._timers.get(name);
        if (timer) {
            clearTimeout(timer.id);
            this._timers.delete(name);

            this.publish('timer:stopped', {
                name,
                source: this.name
            });
        }
    }

    /**
     * Get remaining time for a timer
     * @param {string} name - Timer name
     * @returns {number} Remaining time in milliseconds
     */
    getRemainingTime(name) {
        const timer = this._timers.get(name);
        if (!timer) return 0;

        const elapsed = Date.now() - timer.startTime;
        return Math.max(0, timer.duration - elapsed);
    }

    /**
     * Check if timer is running
     * @param {string} name - Timer name
     * @returns {boolean}
     */
    isTimerRunning(name) {
        return this._timers.has(name);
    }

    /**
     * Get all active timers
     * @returns {Array} Active timer names
     */
    getActiveTimers() {
        return Array.from(this._timers.keys());
    }

    destroy() {
        // Clear all timers
        for (const [name] of this._timers) {
            this.clearTimer(name);
        }
        super.destroy();
    }
}