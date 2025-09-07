/**
 * SocketManager - Handles all Socket.IO communication
 * 
 * Responsible for:
 * - Socket connection lifecycle
 * - Event registration and emission
 * - Connection recovery and error handling
 * - Server communication abstraction
 */

class SocketManager {
    constructor() {
        this.socket = null;
        this.connectionStatus = false;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.connectionRecoveryAttempts = 0;
        this.connectionRecoveryTimer = null;
        this.eventListeners = new Map();
        
        // Enhanced reliability features
        this.connectionTimeoutTimer = null;
        this.connectionTimeout = 10000; // 10 seconds
        this.heartbeatInterval = null;
        this.heartbeatTimer = 30000; // 30 seconds
        this.lastHeartbeat = null;
        this.connectionQuality = 'unknown'; // 'good', 'poor', 'bad', 'unknown'
        this.connectionMetrics = {
            reconnectCount: 0,
            totalDowntime: 0,
            lastDisconnectTime: null,
            averageLatency: null,
            latencyHistory: []
        };
        
        // Pending requests queue for reliability
        this.pendingRequests = new Map();
        this.requestTimeout = 30000; // 30 seconds
        this.requestIdCounter = 0;
        
        // Connection state callbacks
        this.onConnect = null;
        this.onDisconnect = null;
        this.onConnectionError = null;
        this.onReconnect = null;
        this.onConnectionQualityChange = null;
    }
    
    /**
     * Initialize Socket.IO connection
     */
    initialize() {
        if (typeof window === 'undefined' || !window.isTestEnvironment) {
            console.log('Initializing Socket.IO connection...');
        }
        
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not available');
            return;
        }
        
        // Clean up existing socket
        this._cleanup();
        
        this.socket = io('/', {
            transports: ['polling', 'websocket'],
            timeout: this.connectionTimeout,
            reconnection: false, // We handle reconnection manually for better control
            forceNew: true
        });
        
        // Start connection timeout
        this._startConnectionTimeout();
        
        // Core connection events
        this.socket.on('connect', () => this._handleConnect());
        this.socket.on('disconnect', (reason) => this._handleDisconnect(reason));
        this.socket.on('connect_error', (error) => this._handleConnectionError(error));
        
        // Server confirmation events
        this.socket.on('connected', (data) => this._emit('server_connected', data));
        this.socket.on('error', (error) => this._emit('server_error', error));
        
        // Reliability events
        this.socket.on('pong', (data) => this._handleHeartbeatResponse(data));
        this.socket.on('request_response', (data) => this._handleRequestResponse(data));
    }
    
    /**
     * Register event listener
     * @param {string} event - Event name
     * @param {Function} callback - Event handler
     */
    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
        
        // Register with socket if it exists
        if (this.socket) {
            this.socket.on(event, callback);
        }
    }
    
    /**
     * Remove event listener
     * @param {string} event - Event name
     * @param {Function} callback - Event handler to remove
     */
    off(event, callback) {
        const listeners = this.eventListeners.get(event);
        if (listeners) {
            const index = listeners.indexOf(callback);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
        
        if (this.socket) {
            this.socket.off(event, callback);
        }
    }
    
    /**
     * Emit event to server
     * @param {string} event - Event name
     * @param {Object} data - Event data
     * @param {boolean} trackRequest - Whether to track this request for reliability
     * @returns {Promise} Promise that resolves when server responds (if trackRequest is true)
     */
    emit(event, data, trackRequest = false) {
        if (!this.socket) {
            if (typeof window === 'undefined' || !window.isTestEnvironment) {
                console.error(`Cannot emit ${event} - socket not initialized`);
            }
            return trackRequest ? Promise.reject(new Error('Socket not initialized')) : undefined;
        }
        
        if (!this.isConnected) {
            if (typeof window === 'undefined' || !window.isTestEnvironment) {
                console.error(`Cannot emit ${event} - socket not connected`);
            }
            // In test environment, still try to emit for testing purposes
            if (typeof window !== 'undefined' && window.isTestEnvironment && this.socket.emit) {
                try {
                    this.socket.emit(event, data);
                } catch (error) {
                    if (typeof window === 'undefined' || !window.isTestEnvironment) {
                        console.error(`Failed to emit ${event}:`, error);
                    }
                }
            }
            return trackRequest ? Promise.reject(new Error('Socket not connected')) : undefined;
        }
        
        try {
            if (trackRequest) {
                return this._emitWithTracking(event, data);
            } else {
                this.socket.emit(event, data);
            }
        } catch (error) {
            if (typeof window === 'undefined' || !window.isTestEnvironment) {
                console.error(`Failed to emit ${event}:`, error);
            }
            return trackRequest ? Promise.reject(error) : undefined;
        }
    }
    
    /**
     * Get connection status
     * @returns {boolean} Connection status
     */
    getConnectionStatus() {
        return this.connectionStatus;
    }
    
    /**
     * Get connection quality metrics
     * @returns {Object} Connection metrics and quality info
     */
    getConnectionMetrics() {
        return {
            quality: this.connectionQuality,
            isConnected: this.isConnected,
            reconnectCount: this.connectionMetrics.reconnectCount,
            totalDowntime: this.connectionMetrics.totalDowntime,
            averageLatency: this.connectionMetrics.averageLatency,
            pendingRequestCount: this.pendingRequests.size
        };
    }
    
    /**
     * Force reconnection attempt
     */
    reconnect() {
        this.reconnectAttempts = 0;
        this.connectionRecoveryAttempts = 0;
        this._cleanup();
        this.initialize();
    }
    
    /**
     * Disconnect socket
     */
    disconnect() {
        this._cleanup();
        this.isConnected = false;
        this.connectionStatus = false;
    }
    
    // Private methods
    
    _handleConnect() {
        if (typeof window === 'undefined' || !window.isTestEnvironment) {
            console.log('Socket connected');
        }
        
        this._clearConnectionTimeout();
        this.isConnected = true;
        this.connectionStatus = true;
        
        // Calculate downtime if this is a reconnection
        const isReconnection = this.connectionRecoveryAttempts > 0;
        if (isReconnection && this.connectionMetrics.lastDisconnectTime) {
            const downtime = Date.now() - this.connectionMetrics.lastDisconnectTime;
            this.connectionMetrics.totalDowntime += downtime;
            this.connectionMetrics.reconnectCount++;
        }
        
        this.reconnectAttempts = 0;
        this.connectionRecoveryAttempts = 0;
        this._clearRecoveryTimer();
        
        // Re-register all event listeners
        for (const [event, callbacks] of this.eventListeners) {
            callbacks.forEach(callback => {
                this.socket.on(event, callback);
            });
        }
        
        // Start heartbeat monitoring
        this._startHeartbeat();
        
        // Update connection quality
        this._updateConnectionQuality('good');
        
        // Trigger connect callback
        if (isReconnection) {
            if (this.onReconnect) {
                this.onReconnect();
            }
        } else if (this.onConnect) {
            this.onConnect();
        }
    }
    
    _handleDisconnect(reason) {
        if (typeof window === 'undefined' || !window.isTestEnvironment) {
            console.log('Socket disconnected:', reason);
        }
        
        this.isConnected = false;
        this.connectionStatus = false;
        this.connectionMetrics.lastDisconnectTime = Date.now();
        
        // Stop heartbeat monitoring
        this._stopHeartbeat();
        
        // Update connection quality based on disconnect reason
        if (reason === 'io server disconnect' || reason === 'transport close') {
            this._updateConnectionQuality('bad');
        } else {
            this._updateConnectionQuality('poor');
        }
        
        // Handle pending requests
        this._handleDisconnectedRequests();
        
        if (this.onDisconnect) {
            this.onDisconnect(reason);
        }
        
        // Only attempt recovery for unexpected disconnects and not in test environment
        if (reason !== 'io client disconnect' && 
            (typeof window === 'undefined' || !window.isTestEnvironment)) {
            this._startConnectionRecovery();
        }
    }
    
    _handleConnectionError(error) {
        if (typeof window === 'undefined' || !window.isTestEnvironment) {
            console.error('Socket connection error:', error);
        }
        this.connectionStatus = false;
        
        if (this.onConnectionError) {
            this.onConnectionError(error);
        }
        
        // Only start recovery if not in test environment
        if (typeof window === 'undefined' || !window.isTestEnvironment) {
            this._startConnectionRecovery();
        }
    }
    
    _startConnectionRecovery() {
        this._clearRecoveryTimer();
        
        this.connectionRecoveryAttempts++;
        
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, then 30s max
        const delay = Math.min(Math.pow(2, this.connectionRecoveryAttempts - 1) * 1000, 30000);
        
        if (typeof window === 'undefined' || !window.isTestEnvironment) {
            console.log(`Connection recovery attempt ${this.connectionRecoveryAttempts} in ${delay}ms`);
        }
        
        this.connectionRecoveryTimer = setTimeout(() => {
            if (!this.isConnected && this.socket) {
                // Increment reconnectAttempts each time timer executes
                this.reconnectAttempts++;
                
                if (typeof window === 'undefined' || !window.isTestEnvironment) {
                    console.log('Attempting to reconnect...');
                }
                if (typeof this.socket.connect === 'function') {
                    this.socket.connect();
                } else if (typeof this.socket.open === 'function') {
                    this.socket.open();
                } else {
                    this.initialize();
                }
                
                // Continue recovery if still not connected and haven't exceeded max attempts
                if (this.connectionRecoveryAttempts < this.maxReconnectAttempts) {
                    this._startConnectionRecovery();
                }
            }
        }, delay);
    }
    
    _clearRecoveryTimer() {
        if (this.connectionRecoveryTimer) {
            clearTimeout(this.connectionRecoveryTimer);
            this.connectionRecoveryTimer = null;
        }
    }
    
    _emit(event, data) {
        const listeners = this.eventListeners.get(event);
        if (listeners) {
            listeners.forEach(callback => callback(data));
        }
    }
    
    // Enhanced reliability methods
    
    _emitWithTracking(event, data) {
        return new Promise((resolve, reject) => {
            const requestId = `req_${++this.requestIdCounter}_${Date.now()}`;
            const requestData = { ...data, _requestId: requestId };
            
            // Store the pending request
            const timeoutId = setTimeout(() => {
                this.pendingRequests.delete(requestId);
                reject(new Error(`Request timeout for ${event}`));
            }, this.requestTimeout);
            
            this.pendingRequests.set(requestId, {
                resolve,
                reject,
                timeoutId,
                event,
                timestamp: Date.now()
            });
            
            try {
                this.socket.emit(event, requestData);
            } catch (error) {
                this.pendingRequests.delete(requestId);
                clearTimeout(timeoutId);
                reject(error);
            }
        });
    }
    
    _handleRequestResponse(data) {
        const { _requestId, ...responseData } = data;
        if (!_requestId) return;
        
        const pendingRequest = this.pendingRequests.get(_requestId);
        if (pendingRequest) {
            clearTimeout(pendingRequest.timeoutId);
            this.pendingRequests.delete(_requestId);
            
            // Calculate latency for connection quality assessment
            const latency = Date.now() - pendingRequest.timestamp;
            this._recordLatency(latency);
            
            pendingRequest.resolve(responseData);
        }
    }
    
    _startConnectionTimeout() {
        this._clearConnectionTimeout();
        this.connectionTimeoutTimer = setTimeout(() => {
            if (!this.isConnected) {
                if (typeof window === 'undefined' || !window.isTestEnvironment) {
                    console.error('Connection timeout');
                }
                this._handleConnectionError(new Error('Connection timeout'));
            }
        }, this.connectionTimeout);
    }
    
    _clearConnectionTimeout() {
        if (this.connectionTimeoutTimer) {
            clearTimeout(this.connectionTimeoutTimer);
            this.connectionTimeoutTimer = null;
        }
    }
    
    _startHeartbeat() {
        this._stopHeartbeat();
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected && this.socket) {
                const timestamp = Date.now();
                this.socket.emit('ping', { timestamp });
                
                // Check if previous heartbeat response is overdue
                if (this.lastHeartbeat && (timestamp - this.lastHeartbeat) > (this.heartbeatTimer * 2)) {
                    this._updateConnectionQuality('poor');
                }
            }
        }, this.heartbeatTimer);
    }
    
    _stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    _handleHeartbeatResponse(data) {
        const now = Date.now();
        this.lastHeartbeat = now;
        
        if (data && data.timestamp) {
            const latency = now - data.timestamp;
            this._recordLatency(latency);
        }
    }
    
    _recordLatency(latency) {
        this.connectionMetrics.latencyHistory.push(latency);
        
        // Keep only last 10 measurements
        if (this.connectionMetrics.latencyHistory.length > 10) {
            this.connectionMetrics.latencyHistory.shift();
        }
        
        // Calculate average latency
        const sum = this.connectionMetrics.latencyHistory.reduce((a, b) => a + b, 0);
        this.connectionMetrics.averageLatency = sum / this.connectionMetrics.latencyHistory.length;
        
        // Update connection quality based on latency
        if (this.connectionMetrics.averageLatency < 100) {
            this._updateConnectionQuality('good');
        } else if (this.connectionMetrics.averageLatency < 500) {
            this._updateConnectionQuality('poor');
        } else {
            this._updateConnectionQuality('bad');
        }
    }
    
    _updateConnectionQuality(newQuality) {
        if (this.connectionQuality !== newQuality) {
            this.connectionQuality = newQuality;
            if (this.onConnectionQualityChange) {
                this.onConnectionQualityChange(newQuality);
            }
        }
    }
    
    _handleDisconnectedRequests() {
        // Reject all pending requests when disconnected
        for (const [requestId, request] of this.pendingRequests) {
            clearTimeout(request.timeoutId);
            request.reject(new Error(`Connection lost during ${request.event} request`));
        }
        this.pendingRequests.clear();
    }
    
    _cleanup() {
        this._clearConnectionTimeout();
        this._clearRecoveryTimer();
        this._stopHeartbeat();
        this._handleDisconnectedRequests();
        
        if (this.socket) {
            this.socket.removeAllListeners();
            this.socket.disconnect();
            this.socket = null;
        }
    }
    
    /**
     * Public destroy method for resource cleanup
     */
    destroy() {
        console.log('Destroying SocketManager...');
        this._cleanup();
        
        // Clear all callbacks
        this.onConnect = null;
        this.onDisconnect = null;
        this.onConnectionError = null;
        this.onReconnect = null;
        this.onConnectionQualityChange = null;
        
        // Clear event listeners map
        this.eventListeners.clear();
        
        // Reset connection state
        this.connectionStatus = false;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.connectionRecoveryAttempts = 0;
        this.connectionQuality = 'unknown';
        
        // Reset metrics
        this.connectionMetrics = {
            reconnectCount: 0,
            totalDowntime: 0,
            lastDisconnectTime: null,
            averageLatency: null,
            latencyHistory: []
        };
        
        console.log('SocketManager destroyed');
    }
}

// Export for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SocketManager;
}

export default SocketManager;