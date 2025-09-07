/**
 * Event Bus - Centralized event system for frontend module communication
 * Implements publish/subscribe pattern to decouple modules
 */

class EventBus {
    constructor() {
        this.events = new Map();
        this.debugMode = false;
        this.eventHistory = [];
        this.maxHistorySize = 100;
        
        // Bind methods to preserve context
        this.publish = this.publish.bind(this);
        this.subscribe = this.subscribe.bind(this);
        this.unsubscribe = this.unsubscribe.bind(this);
        
        console.log('EventBus initialized');
    }
    
    /**
     * Subscribe to an event
     * @param {string} eventName - Name of the event to subscribe to
     * @param {Function} handler - Function to call when event is published
     * @param {Object} options - Subscription options
     * @returns {Function} Unsubscribe function
     */
    subscribe(eventName, handler, options = {}) {
        if (typeof eventName !== 'string' || !eventName) {
            throw new Error('Event name must be a non-empty string');
        }
        
        if (typeof handler !== 'function') {
            throw new Error('Event handler must be a function');
        }
        
        // Create subscription object
        const subscription = {
            handler,
            once: options.once || false,
            priority: options.priority || 0,
            id: this._generateSubscriptionId(),
            subscribedAt: Date.now(),
            context: options.context || null
        };
        
        // Initialize event array if needed
        if (!this.events.has(eventName)) {
            this.events.set(eventName, []);
        }
        
        // Add subscription and sort by priority (higher priority first)
        const subscribers = this.events.get(eventName);
        subscribers.push(subscription);
        subscribers.sort((a, b) => b.priority - a.priority);
        
        if (this.debugMode) {
            console.log(`EventBus: Subscribed to '${eventName}' (${subscribers.length} total subscribers)`);
        }
        
        // Return unsubscribe function
        return () => this._removeSubscription(eventName, subscription.id);
    }
    
    /**
     * Subscribe to an event only once
     * @param {string} eventName - Name of the event
     * @param {Function} handler - Function to call
     * @returns {Function} Unsubscribe function
     */
    once(eventName, handler) {
        return this.subscribe(eventName, handler, { once: true });
    }
    
    /**
     * Publish an event to all subscribers
     * @param {string} eventName - Name of the event to publish
     * @param {*} data - Data to pass to subscribers
     * @param {Object} options - Publishing options
     */
    publish(eventName, data = null, options = {}) {
        if (typeof eventName !== 'string' || !eventName) {
            throw new Error('Event name must be a non-empty string');
        }
        
        const eventData = {
            name: eventName,
            data: data,
            timestamp: Date.now(),
            publishedBy: options.source || 'unknown',
            id: this._generateEventId()
        };
        
        // Add to history
        this._addToHistory(eventData);
        
        if (this.debugMode) {
            console.log(`EventBus: Publishing '${eventName}'`, data);
        }
        
        // Get subscribers for this event
        const subscribers = this.events.get(eventName);
        if (!subscribers || subscribers.length === 0) {
            if (this.debugMode) {
                console.log(`EventBus: No subscribers for '${eventName}'`);
            }
            return;
        }
        
        // Publish to all subscribers
        const subscribersToRemove = [];
        
        for (const subscription of subscribers) {
            try {
                // Call handler with proper context
                if (subscription.context) {
                    subscription.handler.call(subscription.context, data, eventData);
                } else {
                    subscription.handler(data, eventData);
                }
                
                // Mark one-time subscriptions for removal
                if (subscription.once) {
                    subscribersToRemove.push(subscription.id);
                }
                
            } catch (error) {
                console.error(`EventBus: Error in event handler for '${eventName}':`, error);
                
                // Publish error event (avoid infinite loops)
                if (eventName !== 'eventbus:error') {
                    this.publish('eventbus:error', {
                        originalEvent: eventName,
                        error: error,
                        subscription: subscription
                    }, { source: 'EventBus' });
                }
            }
        }
        
        // Remove one-time subscriptions
        subscribersToRemove.forEach(id => {
            this._removeSubscription(eventName, id);
        });
    }
    
    /**
     * Unsubscribe from an event
     * @param {string} eventName - Name of the event
     * @param {Function|null} handler - Handler to remove (if null, removes all)
     */
    unsubscribe(eventName, handler = null) {
        if (!this.events.has(eventName)) {
            return;
        }
        
        if (handler === null) {
            // Remove all subscriptions for this event
            this.events.delete(eventName);
            if (this.debugMode) {
                console.log(`EventBus: Unsubscribed all handlers from '${eventName}'`);
            }
        } else {
            // Remove specific handler
            const subscribers = this.events.get(eventName);
            const originalLength = subscribers.length;
            
            for (let i = subscribers.length - 1; i >= 0; i--) {
                if (subscribers[i].handler === handler) {
                    subscribers.splice(i, 1);
                }
            }
            
            if (subscribers.length === 0) {
                this.events.delete(eventName);
            }
            
            if (this.debugMode && subscribers.length !== originalLength) {
                console.log(`EventBus: Unsubscribed handler from '${eventName}'`);
            }
        }
    }
    
    /**
     * Get list of all event names with subscribers
     * @returns {Array} Array of event names
     */
    getEventNames() {
        return Array.from(this.events.keys());
    }
    
    /**
     * Get subscriber count for an event
     * @param {string} eventName - Name of the event
     * @returns {number} Number of subscribers
     */
    getSubscriberCount(eventName) {
        const subscribers = this.events.get(eventName);
        return subscribers ? subscribers.length : 0;
    }
    
    /**
     * Enable or disable debug mode
     * @param {boolean} enabled - Whether to enable debug mode
     */
    setDebugMode(enabled) {
        this.debugMode = !!enabled;
        console.log(`EventBus: Debug mode ${enabled ? 'enabled' : 'disabled'}`);
    }
    
    /**
     * Get event history (for debugging)
     * @param {number} limit - Maximum number of events to return
     * @returns {Array} Recent events
     */
    getEventHistory(limit = 50) {
        return this.eventHistory.slice(-limit);
    }
    
    /**
     * Clear event history
     */
    clearHistory() {
        this.eventHistory = [];
    }
    
    /**
     * Clear all subscriptions (useful for testing)
     */
    clear() {
        this.events.clear();
        this.eventHistory = [];
        console.log('EventBus: All subscriptions cleared');
    }
    
    /**
     * Get debug information about the event bus
     * @returns {Object} Debug information
     */
    getDebugInfo() {
        const info = {
            totalEvents: this.events.size,
            totalSubscriptions: 0,
            events: {},
            recentEvents: this.getEventHistory(10)
        };
        
        for (const [eventName, subscribers] of this.events) {
            info.totalSubscriptions += subscribers.length;
            info.events[eventName] = {
                subscriberCount: subscribers.length,
                subscribers: subscribers.map(sub => ({
                    priority: sub.priority,
                    once: sub.once,
                    subscribedAt: new Date(sub.subscribedAt).toISOString(),
                    context: sub.context ? sub.context.constructor.name : null
                }))
            };
        }
        
        return info;
    }
    
    // Private methods
    
    _generateEventId() {
        return `event_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    _generateSubscriptionId() {
        return `sub_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    _removeSubscription(eventName, subscriptionId) {
        const subscribers = this.events.get(eventName);
        if (!subscribers) return;
        
        const index = subscribers.findIndex(sub => sub.id === subscriptionId);
        if (index >= 0) {
            subscribers.splice(index, 1);
            
            if (subscribers.length === 0) {
                this.events.delete(eventName);
            }
            
            if (this.debugMode) {
                console.log(`EventBus: Removed subscription from '${eventName}'`);
            }
        }
    }
    
    _addToHistory(eventData) {
        this.eventHistory.push(eventData);
        
        // Limit history size
        if (this.eventHistory.length > this.maxHistorySize) {
            this.eventHistory = this.eventHistory.slice(-this.maxHistorySize);
        }
    }
}

// Create global event bus instance
const eventBus = new EventBus();

// Event name constants to prevent typos
export const Events = {
    // User interaction events
    USER: {
        RESPONSE_SUBMITTED: 'user:response:submitted',
        GUESS_SUBMITTED: 'user:guess:submitted',
        ROUND_START: 'user:round:start',
        ROOM_LEAVE: 'user:room:leave',
        ROOM_SHARE: 'user:room:share',
        INPUT_CHANGED: 'user:input:changed'
    },
    
    // Game state events
    GAME: {
        STATE_CHANGED: 'game:state:changed',
        PHASE_CHANGED: 'game:phase:changed',
        ROUND_STARTED: 'game:round:started',
        ROUND_COMPLETED: 'game:round:completed',
        PROMPT_UPDATED: 'game:prompt:updated',
        RESPONSES_AVAILABLE: 'game:responses:available',
        RESULTS_AVAILABLE: 'game:results:available',
        GUESSING_STARTED: 'game:guessing:started',
        RESULTS_STARTED: 'game:results:started'
    },
    
    // Socket/Network events
    SOCKET: {
        CONNECTED: 'socket:connected',
        DISCONNECTED: 'socket:disconnected',
        ERROR: 'socket:error',
        ROOM_JOINED: 'socket:room:joined',
        ROOM_LEFT: 'socket:room:left',
        ROOM_STATE_UPDATED: 'socket:room:state:updated',
        PLAYERS_UPDATED: 'socket:players:updated'
    },
    
    // Timer events
    TIMER: {
        UPDATED: 'timer:updated',
        WARNING: 'timer:warning',
        EXPIRED: 'timer:expired',
        STARTED: 'timer:started',
        STOPPED: 'timer:stopped'
    },
    
    // UI events
    UI: {
        CONNECTION_STATUS_CHANGED: 'ui:connection:status:changed',
        ROOM_INFO_UPDATED: 'ui:room:info:updated',
        PLAYERS_UPDATED: 'ui:players:updated'
    },
    
    // Toast/Notification events
    TOAST: {
        SHOW_SUCCESS: 'toast:show:success',
        SHOW_ERROR: 'toast:show:error',
        SHOW_WARNING: 'toast:show:warning',
        SHOW_INFO: 'toast:show:info',
        SHOWN: 'toast:shown',
        DISMISSED: 'toast:dismissed'
    },
    
    // System events
    SYSTEM: {
        ERROR: 'system:error',
        WARNING: 'system:warning',
        INFO: 'system:info'
    },
    
    // EventBus internal events
    EVENTBUS: {
        ERROR: 'eventbus:error'
    }
};

export { eventBus as EventBus };
export default eventBus;