/**
 * Event Bus Migration Helper
 * Utilities to help migrate from direct method calls to event-based communication
 */

import { EventBus, Events } from './EventBus.js';

/**
 * Module base class with event bus integration
 * All modules should extend this to get event bus functionality
 */
export class EventBusModule {
    constructor(moduleName) {
        this.moduleName = moduleName;
        this.eventBus = EventBus;
        this.subscriptions = new Set();
        
        // Bind common methods
        this.publish = this.publish.bind(this);
        this.subscribe = this.subscribe.bind(this);
        this.once = this.once.bind(this);
        this.cleanup = this.cleanup.bind(this);
        
        console.log(`${this.moduleName}: Initialized with EventBus integration`);
    }
    
    /**
     * Publish an event with module context
     * @param {string} eventName - Name of the event
     * @param {*} data - Event data
     */
    publish(eventName, data = null) {
        this.eventBus.publish(eventName, data, { source: this.moduleName });
    }
    
    /**
     * Subscribe to an event and track the subscription
     * @param {string} eventName - Event to subscribe to
     * @param {Function} handler - Event handler
     * @param {Object} options - Subscription options
     * @returns {Function} Unsubscribe function
     */
    subscribe(eventName, handler, options = {}) {
        const unsubscribe = this.eventBus.subscribe(eventName, handler, {
            ...options,
            context: this
        });
        
        // Track subscription for cleanup
        this.subscriptions.add(unsubscribe);
        
        // Return wrapped unsubscribe that also removes from tracking
        return () => {
            this.subscriptions.delete(unsubscribe);
            unsubscribe();
        };
    }
    
    /**
     * Subscribe to an event only once
     * @param {string} eventName - Event to subscribe to
     * @param {Function} handler - Event handler
     * @returns {Function} Unsubscribe function
     */
    once(eventName, handler) {
        return this.subscribe(eventName, handler, { once: true });
    }
    
    /**
     * Clean up all subscriptions (call in destructor/cleanup)
     */
    cleanup() {
        console.log(`${this.moduleName}: Cleaning up ${this.subscriptions.size} subscriptions`);
        
        for (const unsubscribe of this.subscriptions) {
            unsubscribe();
        }
        
        this.subscriptions.clear();
    }
    
    /**
     * Get module's subscription count
     * @returns {number} Number of active subscriptions
     */
    getSubscriptionCount() {
        return this.subscriptions.size;
    }
}

/**
 * Migration adapter for existing callback-based modules
 * Helps gradually convert modules to use events
 */
export class CallbackToEventAdapter {
    constructor(moduleName) {
        this.moduleName = moduleName;
        this.eventBus = EventBus;
        this.adapters = new Map();
        
        console.log(`${moduleName}: Callback-to-Event adapter initialized`);
    }
    
    /**
     * Create an event-publishing wrapper for a callback
     * @param {string} eventName - Event to publish
     * @param {Function} originalCallback - Original callback function
     * @returns {Function} New callback that publishes events
     */
    adaptCallback(eventName, originalCallback = null) {
        const adapter = (data) => {
            // Call original callback if provided
            if (originalCallback) {
                try {
                    originalCallback(data);
                } catch (error) {
                    console.error(`${this.moduleName}: Error in original callback:`, error);
                }
            }
            
            // Publish event
            this.eventBus.publish(eventName, data, { source: this.moduleName });
        };
        
        this.adapters.set(eventName, adapter);
        return adapter;
    }
    
    /**
     * Create an event subscriber that calls a callback
     * @param {string} eventName - Event to subscribe to
     * @param {Function} callback - Callback to call on event
     * @returns {Function} Unsubscribe function
     */
    adaptSubscription(eventName, callback) {
        return this.eventBus.subscribe(eventName, callback, {
            context: this
        });
    }
    
    /**
     * Get all adapted callbacks
     * @returns {Map} Map of event names to adapter functions
     */
    getAdapters() {
        return new Map(this.adapters);
    }
}

/**
 * Gradual migration helper
 * Allows running both old and new patterns simultaneously during migration
 */
export class GradualMigrationHelper {
    constructor() {
        this.migrationFlags = new Map();
        this.dualMode = true; // Run both old and new patterns
        
        console.log('GradualMigrationHelper: Initialized for seamless migration');
    }
    
    /**
     * Set migration flag for a specific feature
     * @param {string} feature - Feature being migrated
     * @param {boolean} useEvents - Whether to use events for this feature
     */
    setMigrationFlag(feature, useEvents) {
        this.migrationFlags.set(feature, useEvents);
        console.log(`Migration: ${feature} -> ${useEvents ? 'Events' : 'Direct calls'}`);
    }
    
    /**
     * Check if a feature should use events
     * @param {string} feature - Feature to check
     * @returns {boolean} Whether to use events
     */
    shouldUseEvents(feature) {
        return this.migrationFlags.get(feature) || false;
    }
    
    /**
     * Execute either old or new pattern based on migration flag
     * @param {string} feature - Feature being executed
     * @param {Function} oldPattern - Original implementation
     * @param {Function} newPattern - Event-based implementation
     * @param {*} data - Data to pass to implementations
     */
    execute(feature, oldPattern, newPattern, data = null) {
        const useEvents = this.shouldUseEvents(feature);
        
        if (this.dualMode) {
            // Run both patterns during migration for safety
            try {
                if (useEvents) {
                    newPattern(data);
                    if (oldPattern) oldPattern(data);
                } else {
                    if (oldPattern) oldPattern(data);
                    newPattern(data);
                }
            } catch (error) {
                console.error(`Migration error in ${feature}:`, error);
                // Fallback to old pattern
                if (oldPattern && !useEvents) {
                    oldPattern(data);
                }
            }
        } else {
            // Run only the selected pattern
            if (useEvents) {
                newPattern(data);
            } else if (oldPattern) {
                oldPattern(data);
            }
        }
    }
    
    /**
     * Disable dual mode (only run selected pattern)
     */
    disableDualMode() {
        this.dualMode = false;
        console.log('Migration: Dual mode disabled - running only selected patterns');
    }
    
    /**
     * Get migration status report
     * @returns {Object} Status of all migrated features
     */
    getStatus() {
        return {
            dualMode: this.dualMode,
            features: Object.fromEntries(this.migrationFlags),
            totalFeatures: this.migrationFlags.size
        };
    }
}

/**
 * Event validation helper
 * Helps ensure event data is properly structured
 */
export class EventValidator {
    constructor() {
        this.schemas = new Map();
    }
    
    /**
     * Register an event schema for validation
     * @param {string} eventName - Event name
     * @param {Object} schema - Validation schema
     */
    registerSchema(eventName, schema) {
        this.schemas.set(eventName, schema);
    }
    
    /**
     * Validate event data against schema
     * @param {string} eventName - Event name
     * @param {*} data - Event data
     * @returns {boolean} Whether data is valid
     */
    validate(eventName, data) {
        const schema = this.schemas.get(eventName);
        if (!schema) {
            return true; // No schema means no validation required
        }
        
        try {
            return this._validateAgainstSchema(data, schema);
        } catch (error) {
            console.error(`Event validation error for ${eventName}:`, error);
            return false;
        }
    }
    
    _validateAgainstSchema(data, schema) {
        // Simple validation - could be enhanced with a proper schema library
        if (schema.required && data == null) {
            return false;
        }
        
        if (schema.type && typeof data !== schema.type) {
            return false;
        }
        
        if (schema.properties && typeof data === 'object') {
            for (const [prop, propSchema] of Object.entries(schema.properties)) {
                if (!this._validateAgainstSchema(data[prop], propSchema)) {
                    return false;
                }
            }
        }
        
        return true;
    }
}

// Create global migration helper instances
export const migrationHelper = new GradualMigrationHelper();
export const eventValidator = new EventValidator();

// Register common event schemas
eventValidator.registerSchema(Events.USER.RESPONSE_SUBMITTED, {
    type: 'object',
    properties: {
        response: { type: 'string', required: true }
    }
});

eventValidator.registerSchema(Events.USER.GUESS_SUBMITTED, {
    type: 'object', 
    properties: {
        guessIndex: { type: 'number', required: true }
    }
});

eventValidator.registerSchema(Events.TIMER.UPDATED, {
    type: 'object',
    properties: {
        timeRemaining: { type: 'number', required: true },
        totalTime: { type: 'number', required: true },
        phase: { type: 'string', required: true }
    }
});

console.log('EventBus Migration utilities loaded');