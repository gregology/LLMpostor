/**
 * ServiceContainer - Dependency Injection Container for Frontend Modules
 *
 * Responsible for:
 * - Service registration and lifecycle management
 * - Dependency resolution with circular dependency detection
 * - Service health checking and error boundaries
 * - Centralized configuration and initialization
 */

class ServiceContainer {
    constructor() {
        this.services = new Map();
        this.singletons = new Map();
        this.config = new Map();
        this.initializing = new Set();
        this.debugMode = false;

        console.log('ServiceContainer initialized');
    }

    /**
     * Register a service with the container
     * @param {string} name - Service name
     * @param {Function} factory - Factory function that creates the service
     * @param {Object} options - Registration options
     */
    register(name, factory, options = {}) {
        if (typeof name !== 'string' || !name) {
            throw new Error('Service name must be a non-empty string');
        }

        if (typeof factory !== 'function') {
            throw new Error('Service factory must be a function');
        }

        const serviceConfig = {
            name,
            factory,
            singleton: options.singleton !== false, // Default to singleton
            dependencies: options.dependencies || [],
            initialized: false,
            instance: null,
            health: 'unknown'
        };

        this.services.set(name, serviceConfig);

        if (this.debugMode) {
            console.log(`ServiceContainer: Registered '${name}' service`);
        }

        return this;
    }

    /**
     * Get a service instance, creating it if needed
     * @param {string} name - Service name
     * @returns {*} Service instance
     */
    get(name) {
        if (!this.services.has(name)) {
            throw new Error(`Service '${name}' is not registered`);
        }

        const serviceConfig = this.services.get(name);

        // Return existing singleton instance if available
        if (serviceConfig.singleton && serviceConfig.instance) {
            return serviceConfig.instance;
        }

        // Check for circular dependencies
        if (this.initializing.has(name)) {
            throw new Error(`Circular dependency detected for service '${name}'`);
        }

        return this._createInstance(serviceConfig);
    }

    /**
     * Check if a service is registered
     * @param {string} name - Service name
     * @returns {boolean}
     */
    has(name) {
        return this.services.has(name);
    }

    /**
     * Remove a service from the container
     * @param {string} name - Service name
     */
    remove(name) {
        const serviceConfig = this.services.get(name);
        if (serviceConfig && serviceConfig.instance) {
            // Call destroy method if it exists
            if (typeof serviceConfig.instance.destroy === 'function') {
                try {
                    serviceConfig.instance.destroy();
                } catch (error) {
                    console.error(`Error destroying service '${name}':`, error);
                }
            }
        }

        this.services.delete(name);
        this.singletons.delete(name);

        if (this.debugMode) {
            console.log(`ServiceContainer: Removed '${name}' service`);
        }
    }

    /**
     * Get all registered service names
     * @returns {Array<string>}
     */
    getServiceNames() {
        return Array.from(this.services.keys());
    }

    /**
     * Set configuration value
     * @param {string} key - Configuration key
     * @param {*} value - Configuration value
     */
    setConfig(key, value) {
        this.config.set(key, value);
        return this;
    }

    /**
     * Get configuration value
     * @param {string} key - Configuration key
     * @param {*} defaultValue - Default value if key doesn't exist
     * @returns {*}
     */
    getConfig(key, defaultValue = undefined) {
        return this.config.get(key) ?? defaultValue;
    }

    /**
     * Check health of a specific service
     * @param {string} name - Service name
     * @returns {string} Health status: 'healthy', 'unhealthy', 'unknown'
     */
    checkHealth(name) {
        const serviceConfig = this.services.get(name);
        if (!serviceConfig) {
            return 'unknown';
        }

        if (!serviceConfig.instance) {
            return 'unknown';
        }

        // Check if service has health check method
        if (typeof serviceConfig.instance.healthCheck === 'function') {
            try {
                const healthy = serviceConfig.instance.healthCheck();
                serviceConfig.health = healthy ? 'healthy' : 'unhealthy';
            } catch (error) {
                console.error(`Health check failed for service '${name}':`, error);
                serviceConfig.health = 'unhealthy';
            }
        } else {
            // Basic health check - service exists and has no errors
            serviceConfig.health = 'healthy';
        }

        return serviceConfig.health;
    }

    /**
     * Get health status of all services
     * @returns {Object} Health status for all services
     */
    getHealthStatus() {
        const status = {};

        for (const [name, config] of this.services) {
            status[name] = {
                health: this.checkHealth(name),
                initialized: config.initialized,
                singleton: config.singleton,
                dependencies: config.dependencies
            };
        }

        return status;
    }

    /**
     * Enable or disable debug mode
     * @param {boolean} enabled
     */
    setDebugMode(enabled) {
        this.debugMode = !!enabled;
        console.log(`ServiceContainer: Debug mode ${enabled ? 'enabled' : 'disabled'}`);
    }

    /**
     * Clear all services and reset container
     */
    clear() {
        // Destroy all instances
        for (const [name] of this.services) {
            this.remove(name);
        }

        this.services.clear();
        this.singletons.clear();
        this.config.clear();
        this.initializing.clear();

        console.log('ServiceContainer: All services cleared');
    }

    /**
     * Initialize all registered services
     * @returns {Promise<void>}
     */
    async initializeAll() {
        const promises = [];

        for (const [name] of this.services) {
            promises.push(this._initializeService(name));
        }

        await Promise.all(promises);
        console.log('ServiceContainer: All services initialized');
    }

    // Private methods

    _createInstance(serviceConfig) {
        const { name, factory, dependencies } = serviceConfig;

        this.initializing.add(name);

        try {
            // Resolve dependencies
            const resolvedDeps = dependencies.map(depName => {
                if (!this.services.has(depName)) {
                    throw new Error(`Dependency '${depName}' for service '${name}' is not registered`);
                }
                return this.get(depName);
            });

            // Create instance
            const instance = factory(...resolvedDeps, this);

            if (serviceConfig.singleton) {
                serviceConfig.instance = instance;
                this.singletons.set(name, instance);
            }

            serviceConfig.initialized = true;
            serviceConfig.health = 'healthy';

            if (this.debugMode) {
                console.log(`ServiceContainer: Created instance of '${name}'`);
            }

            return instance;

        } catch (error) {
            console.error(`Failed to create service '${name}':`, error);
            serviceConfig.health = 'unhealthy';
            throw error;
        } finally {
            this.initializing.delete(name);
        }
    }

    async _initializeService(name) {
        try {
            const instance = this.get(name);

            // Call initialize method if it exists
            if (typeof instance.initialize === 'function') {
                await instance.initialize();
            }

            return instance;
        } catch (error) {
            console.error(`Failed to initialize service '${name}':`, error);
            throw error;
        }
    }
}

// Create and export global service container instance
const serviceContainer = new ServiceContainer();

export { ServiceContainer };
export default serviceContainer;