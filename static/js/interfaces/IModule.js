/**
 * IModule - Base interface for all frontend modules
 *
 * Defines the standard lifecycle methods and contracts that all modules must implement
 * to ensure consistent behavior across the application.
 */

export class IModule {
    constructor(name) {
        this.name = name;
        this.initialized = false;
        this.destroyed = false;
        this._initTime = null;
        this._destroyTime = null;
    }

    /**
     * Initialize the module
     * Should be idempotent - calling multiple times should be safe
     * @returns {Promise<void>|void}
     */
    initialize() {
        if (this.initialized) {
            console.warn(`Module ${this.name} already initialized`);
            return;
        }

        this.initialized = true;
        this._initTime = Date.now();
        console.log(`Module ${this.name} initialized`);
    }

    /**
     * Destroy the module and clean up resources
     * Should be idempotent - calling multiple times should be safe
     * @returns {Promise<void>|void}
     */
    destroy() {
        if (this.destroyed) {
            console.warn(`Module ${this.name} already destroyed`);
            return;
        }

        this.destroyed = true;
        this._destroyTime = Date.now();
        console.log(`Module ${this.name} destroyed`);
    }

    /**
     * Check if the module is healthy and functioning correctly
     * @returns {boolean} True if healthy, false if issues detected
     */
    healthCheck() {
        return this.initialized && !this.destroyed;
    }

    /**
     * Get module status information for debugging
     * @returns {Object} Status information
     */
    getStatus() {
        return {
            name: this.name,
            initialized: this.initialized,
            destroyed: this.destroyed,
            healthy: this.healthCheck(),
            initTime: this._initTime,
            destroyTime: this._destroyTime,
            uptime: this._initTime ? Date.now() - this._initTime : 0
        };
    }

    /**
     * Reset the module to initial state (useful for testing)
     * @returns {Promise<void>|void}
     */
    reset() {
        this.destroy();
        this.initialized = false;
        this.destroyed = false;
        this._initTime = null;
        this._destroyTime = null;
        this.initialize();
    }
}

/**
 * IEventModule - Interface for modules that use EventBus
 */
export class IEventModule extends IModule {
    constructor(name, eventBus) {
        super(name);
        this.eventBus = eventBus;
        this._subscriptions = [];
    }

    /**
     * Subscribe to an event and track the subscription for cleanup
     * @param {string} eventName - Event name
     * @param {Function} handler - Event handler
     * @param {Object} options - Subscription options
     * @returns {Function} Unsubscribe function
     */
    subscribe(eventName, handler, options = {}) {
        if (!this.eventBus) {
            throw new Error(`Module ${this.name} does not have access to EventBus`);
        }

        const unsubscribe = this.eventBus.subscribe(eventName, handler, {
            ...options,
            context: this
        });

        this._subscriptions.push({ eventName, unsubscribe });
        return unsubscribe;
    }

    /**
     * Publish an event through the EventBus
     * @param {string} eventName - Event name
     * @param {*} data - Event data
     * @param {Object} options - Publish options
     */
    publish(eventName, data, options = {}) {
        if (!this.eventBus) {
            throw new Error(`Module ${this.name} does not have access to EventBus`);
        }

        this.eventBus.publish(eventName, data, {
            ...options,
            source: this.name
        });
    }

    /**
     * Clean up all event subscriptions
     */
    destroy() {
        // Unsubscribe from all events
        this._subscriptions.forEach(({ unsubscribe }) => {
            try {
                unsubscribe();
            } catch (error) {
                console.error(`Error unsubscribing from event in module ${this.name}:`, error);
            }
        });

        this._subscriptions = [];
        super.destroy();
    }
}

/**
 * IServiceModule - Interface for modules that can be registered as services
 */
export class IServiceModule extends IEventModule {
    constructor(name, eventBus, serviceContainer) {
        super(name, eventBus);
        this.serviceContainer = serviceContainer;
        this._dependencies = [];
    }

    /**
     * Get a service dependency
     * @param {string} serviceName - Service name
     * @returns {*} Service instance
     */
    getService(serviceName) {
        if (!this.serviceContainer) {
            throw new Error(`Module ${this.name} does not have access to ServiceContainer`);
        }

        const service = this.serviceContainer.get(serviceName);
        this._dependencies.push(serviceName);
        return service;
    }

    /**
     * Check if a service is available
     * @param {string} serviceName - Service name
     * @returns {boolean}
     */
    hasService(serviceName) {
        return this.serviceContainer && this.serviceContainer.has(serviceName);
    }

    /**
     * Get dependencies for this module
     * @returns {Array<string>} List of service dependencies
     */
    getDependencies() {
        return [...this._dependencies];
    }

    /**
     * Enhanced health check that includes dependency health
     * @returns {boolean}
     */
    healthCheck() {
        const baseHealth = super.healthCheck();

        if (!baseHealth) {
            return false;
        }

        // Check if all dependencies are healthy
        for (const depName of this._dependencies) {
            try {
                const service = this.serviceContainer.get(depName);
                if (service && typeof service.healthCheck === 'function') {
                    if (!service.healthCheck()) {
                        return false;
                    }
                }
            } catch (error) {
                console.error(`Health check failed for dependency ${depName} in module ${this.name}:`, error);
                return false;
            }
        }

        return true;
    }

    /**
     * Enhanced status that includes dependency information
     * @returns {Object}
     */
    getStatus() {
        return {
            ...super.getStatus(),
            dependencies: this.getDependencies(),
            dependenciesHealthy: this._dependencies.every(dep => {
                try {
                    const service = this.serviceContainer.get(dep);
                    return !service || typeof service.healthCheck !== 'function' || service.healthCheck();
                } catch (error) {
                    return false;
                }
            })
        };
    }
}