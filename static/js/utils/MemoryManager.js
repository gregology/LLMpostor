/**
 * MemoryManager - Memory optimization and leak prevention system
 * 
 * Performance optimizations:
 * - Event listener cleanup tracking
 * - DOM reference management
 * - Timer and interval cleanup
 * - Memory usage monitoring
 * - Garbage collection optimization
 */

class MemoryManager {
    constructor() {
        this.eventListeners = new Map();
        this.timers = new Set();
        this.intervals = new Set();
        this.domReferences = new WeakMap();
        this.observers = new Set();
        
        // Memory monitoring
        this.memoryMetrics = {
            startTime: Date.now(),
            peakUsage: 0,
            gcCount: 0
        };
        
        // Start monitoring if available
        this.initializeMonitoring();
        
        console.log('MemoryManager initialized');
    }
    
    /**
     * Initialize memory monitoring
     * @private
     */
    initializeMonitoring() {
        // Monitor memory usage if Performance API is available
        if (window.performance && window.performance.memory) {
            this.memoryMonitorInterval = setInterval(() => {
                this.checkMemoryUsage();
            }, 30000); // Check every 30 seconds
            
            this.intervals.add(this.memoryMonitorInterval);
        }
        
        // Track garbage collection if available
        if (window.PerformanceObserver) {
            try {
                const gcObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    entries.forEach(entry => {
                        if (entry.entryType === 'garbage-collection') {
                            this.memoryMetrics.gcCount++;
                        }
                    });
                });
                gcObserver.observe({ entryTypes: ['garbage-collection'] });
                this.observers.add(gcObserver);
            } catch (e) {
                // Garbage collection monitoring not available
            }
        }
    }
    
    /**
     * Track event listener for cleanup
     * @param {EventTarget} element - Element with listener
     * @param {string} event - Event type
     * @param {Function} handler - Event handler
     * @param {Object} options - Event options
     */
    trackEventListener(element, event, handler, options = {}) {
        const key = this.generateListenerKey(element, event, handler);
        
        this.eventListeners.set(key, {
            element,
            event,
            handler,
            options,
            addedAt: Date.now()
        });
        
        // Add the event listener
        element.addEventListener(event, handler, options);
    }
    
    /**
     * Remove and untrack event listener
     * @param {EventTarget} element - Element with listener
     * @param {string} event - Event type
     * @param {Function} handler - Event handler
     * @param {Object} options - Event options
     */
    removeEventListener(element, event, handler, options = {}) {
        const key = this.generateListenerKey(element, event, handler);
        
        if (this.eventListeners.has(key)) {
            element.removeEventListener(event, handler, options);
            this.eventListeners.delete(key);
        }
    }
    
    /**
     * Remove all tracked event listeners
     */
    removeAllEventListeners() {
        for (const [key, listener] of this.eventListeners) {
            try {
                listener.element.removeEventListener(
                    listener.event,
                    listener.handler,
                    listener.options
                );
            } catch (e) {
                console.warn('Error removing event listener:', e);
            }
        }
        
        this.eventListeners.clear();
    }
    
    /**
     * Track timer for cleanup
     * @param {number} timerId - Timer ID from setTimeout
     */
    trackTimer(timerId) {
        this.timers.add(timerId);
        return timerId;
    }
    
    /**
     * Track interval for cleanup
     * @param {number} intervalId - Interval ID from setInterval
     */
    trackInterval(intervalId) {
        this.intervals.add(intervalId);
        return intervalId;
    }
    
    /**
     * Clear and untrack timer
     * @param {number} timerId - Timer ID
     */
    clearTimer(timerId) {
        clearTimeout(timerId);
        this.timers.delete(timerId);
    }
    
    /**
     * Clear and untrack interval
     * @param {number} intervalId - Interval ID
     */
    clearInterval(intervalId) {
        clearInterval(intervalId);
        this.intervals.delete(intervalId);
    }
    
    /**
     * Clear all tracked timers and intervals
     */
    clearAllTimers() {
        // Clear timers
        for (const timerId of this.timers) {
            clearTimeout(timerId);
        }
        this.timers.clear();
        
        // Clear intervals
        for (const intervalId of this.intervals) {
            clearInterval(intervalId);
        }
        this.intervals.clear();
    }
    
    /**
     * Track DOM references for cleanup
     * @param {HTMLElement} element - DOM element
     * @param {Object} metadata - Reference metadata
     */
    trackDOMReference(element, metadata = {}) {
        this.domReferences.set(element, {
            ...metadata,
            trackedAt: Date.now()
        });
    }
    
    /**
     * Clean up DOM references
     * @param {HTMLElement} element - DOM element to clean up
     */
    cleanupDOMReference(element) {
        if (this.domReferences.has(element)) {
            // Clean up any associated data
            const metadata = this.domReferences.get(element);
            
            // Remove event listeners if tracked
            if (metadata.hasEventListeners) {
                this.removeElementEventListeners(element);
            }
            
            // Clear any data attributes that might hold references
            if (element.dataset) {
                Object.keys(element.dataset).forEach(key => {
                    if (key.startsWith('ref')) {
                        delete element.dataset[key];
                    }
                });
            }
            
            this.domReferences.delete(element);
        }
    }
    
    /**
     * Remove all event listeners from an element
     * @private
     */
    removeElementEventListeners(element) {
        for (const [key, listener] of this.eventListeners) {
            if (listener.element === element) {
                try {
                    element.removeEventListener(
                        listener.event,
                        listener.handler,
                        listener.options
                    );
                    this.eventListeners.delete(key);
                } catch (e) {
                    console.warn('Error removing element event listener:', e);
                }
            }
        }
    }
    
    /**
     * Track observer for cleanup
     * @param {Observer} observer - Observer instance (MutationObserver, IntersectionObserver, etc.)
     */
    trackObserver(observer) {
        this.observers.add(observer);
        return observer;
    }
    
    /**
     * Disconnect and untrack observer
     * @param {Observer} observer - Observer instance
     */
    disconnectObserver(observer) {
        observer.disconnect();
        this.observers.delete(observer);
    }
    
    /**
     * Disconnect all tracked observers
     */
    disconnectAllObservers() {
        for (const observer of this.observers) {
            try {
                observer.disconnect();
            } catch (e) {
                console.warn('Error disconnecting observer:', e);
            }
        }
        this.observers.clear();
    }
    
    /**
     * Check memory usage and trigger optimization if needed
     * @private
     */
    checkMemoryUsage() {
        if (!window.performance || !window.performance.memory) {
            return;
        }
        
        const memory = window.performance.memory;
        const usedMemory = memory.usedJSHeapSize;
        const totalMemory = memory.totalJSHeapSize;
        const memoryUsagePercent = (usedMemory / totalMemory) * 100;
        
        // Update peak usage
        if (usedMemory > this.memoryMetrics.peakUsage) {
            this.memoryMetrics.peakUsage = usedMemory;
        }
        
        // Trigger cleanup if memory usage is high
        if (memoryUsagePercent > 80) {
            console.warn(`High memory usage detected: ${memoryUsagePercent.toFixed(1)}%`);
            this.optimizeMemoryUsage();
        }
        
        // Log memory metrics for debugging
        console.debug('Memory usage:', {
            used: Math.round(usedMemory / 1024 / 1024) + ' MB',
            total: Math.round(totalMemory / 1024 / 1024) + ' MB',
            percentage: memoryUsagePercent.toFixed(1) + '%'
        });
    }
    
    /**
     * Optimize memory usage
     * @private
     */
    optimizeMemoryUsage() {
        // Remove old event listeners (older than 10 minutes)
        const tenMinutesAgo = Date.now() - (10 * 60 * 1000);
        
        for (const [key, listener] of this.eventListeners) {
            if (listener.addedAt < tenMinutesAgo) {
                this.removeEventListener(
                    listener.element,
                    listener.event,
                    listener.handler,
                    listener.options
                );
            }
        }
        
        // Suggest garbage collection if available
        if (window.gc) {
            window.gc();
            this.memoryMetrics.gcCount++;
        }
        
        console.log('Memory optimization completed');
    }
    
    /**
     * Force garbage collection (if available)
     */
    forceGarbageCollection() {
        if (window.gc) {
            window.gc();
            this.memoryMetrics.gcCount++;
            console.log('Forced garbage collection');
        } else {
            console.warn('Garbage collection not available');
        }
    }
    
    /**
     * Generate unique key for event listener tracking
     * @private
     */
    generateListenerKey(element, event, handler) {
        // Use WeakMap if handler is an object/function, otherwise use string representation
        const handlerKey = typeof handler === 'function' ? 
            handler.toString().substring(0, 100) : String(handler);
        
        return `${element.tagName || 'unknown'}-${event}-${handlerKey.hashCode()}`;
    }
    
    /**
     * Get memory statistics
     * @returns {Object} Memory statistics
     */
    getMemoryStats() {
        const stats = {
            eventListeners: this.eventListeners.size,
            timers: this.timers.size,
            intervals: this.intervals.size,
            observers: this.observers.size,
            runTime: Date.now() - this.memoryMetrics.startTime,
            gcCount: this.memoryMetrics.gcCount,
            peakUsage: this.memoryMetrics.peakUsage
        };
        
        // Add current memory usage if available
        if (window.performance && window.performance.memory) {
            const memory = window.performance.memory;
            stats.currentUsage = memory.usedJSHeapSize;
            stats.totalAvailable = memory.totalJSHeapSize;
            stats.usagePercentage = (memory.usedJSHeapSize / memory.totalJSHeapSize) * 100;
        }
        
        return stats;
    }
    
    /**
     * Clean up all tracked resources
     */
    cleanup() {
        this.removeAllEventListeners();
        this.clearAllTimers();
        this.disconnectAllObservers();
        
        console.log('MemoryManager cleanup completed');
    }
    
    /**
     * Destroy the memory manager
     */
    destroy() {
        this.cleanup();
        
        if (this.memoryMonitorInterval) {
            clearInterval(this.memoryMonitorInterval);
        }
        
        console.log('MemoryManager destroyed');
    }
}

// Helper function for string hashing
String.prototype.hashCode = function() {
    let hash = 0;
    if (this.length === 0) return hash;
    for (let i = 0; i < this.length; i++) {
        const char = this.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32-bit integer
    }
    return hash;
};


export default MemoryManager;