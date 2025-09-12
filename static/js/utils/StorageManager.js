/**
 * StorageManager - Utility for managing persistent reconnection data
 * 
 * Handles localStorage operations for minimal room reconnection data:
 * - roomId: Room identifier for rejoining
 * - playerId: Player's unique identifier  
 * - playerName: Player's display name
 * 
 * Design principles:
 * - Fail-safe: graceful degradation if localStorage unavailable
 * - Minimal: only stores essential reconnection data
 * - Clean: automatic cleanup of stale/invalid data
 */

class StorageManager {
    constructor() {
        this.STORAGE_KEY = 'llmpostor_room_session';
        this.isAvailable = this._checkStorageAvailability();
        
        if (!this.isAvailable) {
            console.warn('StorageManager: localStorage not available, persistence disabled');
        }
    }
    
    /**
     * Save room session data for reconnection
     * @param {string} roomId - Room identifier
     * @param {string} playerId - Player's unique identifier
     * @param {string} playerName - Player's display name
     * @returns {boolean} True if saved successfully
     */
    saveRoomSession(roomId, playerId, playerName) {
        if (!this.isAvailable) {
            return false;
        }
        
        try {
            // Validate required parameters
            if (!roomId || !playerId || !playerName) {
                console.warn('StorageManager: Cannot save incomplete session data');
                return false;
            }
            
            const sessionData = {
                roomId: String(roomId).trim(),
                playerId: String(playerId).trim(),
                playerName: String(playerName).trim(),
                timestamp: Date.now() // For potential cleanup of old sessions
            };
            
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(sessionData));
            console.log(`StorageManager: Saved session for ${playerName} in room ${roomId}`);
            return true;
            
        } catch (error) {
            console.error('StorageManager: Failed to save session data:', error);
            return false;
        }
    }
    
    /**
     * Retrieve saved room session data
     * @returns {Object|null} Session data or null if not available
     */
    getRoomSession() {
        if (!this.isAvailable) {
            return null;
        }
        
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            if (!stored) {
                return null;
            }
            
            const sessionData = JSON.parse(stored);
            
            // Validate session data structure
            if (!this._isValidSessionData(sessionData)) {
                console.warn('StorageManager: Invalid session data found, removing');
                this.clearRoomSession();
                return null;
            }
            
            console.log(`StorageManager: Retrieved session for ${sessionData.playerName} in room ${sessionData.roomId}`);
            return {
                roomId: sessionData.roomId,
                playerId: sessionData.playerId,
                playerName: sessionData.playerName
            };
            
        } catch (error) {
            console.error('StorageManager: Failed to retrieve session data:', error);
            // Clear corrupted data
            this.clearRoomSession();
            return null;
        }
    }
    
    /**
     * Check if there's a saved room session
     * @returns {boolean} True if session data exists and is valid
     */
    hasRoomSession() {
        return this.getRoomSession() !== null;
    }
    
    /**
     * Clear saved room session data
     * @returns {boolean} True if cleared successfully
     */
    clearRoomSession() {
        if (!this.isAvailable) {
            return false;
        }
        
        try {
            localStorage.removeItem(this.STORAGE_KEY);
            console.log('StorageManager: Cleared room session');
            return true;
            
        } catch (error) {
            console.error('StorageManager: Failed to clear session data:', error);
            return false;
        }
    }
    
    /**
     * Update player name in existing session (for name changes)
     * @param {string} newPlayerName - New player name
     * @returns {boolean} True if updated successfully
     */
    updatePlayerName(newPlayerName) {
        const session = this.getRoomSession();
        if (!session) {
            return false;
        }
        
        return this.saveRoomSession(session.roomId, session.playerId, newPlayerName);
    }
    
    /**
     * Get storage availability status
     * @returns {boolean} True if localStorage is available
     */
    isStorageAvailable() {
        return this.isAvailable;
    }
    
    // Private methods
    
    /**
     * Check if localStorage is available and functional
     * @private
     * @returns {boolean} True if localStorage is available
     */
    _checkStorageAvailability() {
        try {
            const testKey = '__storage_test__';
            localStorage.setItem(testKey, 'test');
            localStorage.removeItem(testKey);
            return true;
        } catch (error) {
            return false;
        }
    }
    
    /**
     * Validate session data structure and content
     * @private
     * @param {Object} data - Session data to validate
     * @returns {boolean} True if data is valid
     */
    _isValidSessionData(data) {
        if (!data || typeof data !== 'object') {
            return false;
        }
        
        const required = ['roomId', 'playerId', 'playerName'];
        for (const field of required) {
            if (!data[field] || typeof data[field] !== 'string' || !data[field].trim()) {
                return false;
            }
        }
        
        // Check for reasonable string lengths to prevent abuse
        if (data.roomId.length > 50 || data.playerId.length > 50 || data.playerName.length > 100) {
            return false;
        }
        
        return true;
    }
}

// Export singleton instance for consistent usage across modules
const storageManager = new StorageManager();
export default storageManager;