/**
 * GameStateManager - Manages game state and synchronization
 * 
 * Responsible for:
 * - Game state tracking and updates
 * - Player data management
 * - Room information management
 * - State validation and synchronization
 */

class GameStateManager {
    constructor() {
        this.gameState = null;
        this.players = [];
        this.roomInfo = {
            roomId: null,
            playerId: null,
            playerName: null,
            connectedCount: 0,
            totalCount: 0
        };
        this.roundsCompleted = 0;
        
        // State flags
        this.hasSubmittedResponse = false;
        this.hasSubmittedGuess = false;
        
        // Track submitted content for filtering
        this.submittedResponseText = null;
        
        // State change callbacks
        this.onStateChange = null;
        this.onPlayersUpdate = null;
        this.onRoomInfoUpdate = null;
    }
    
    /**
     * Initialize game state with room information
     * @param {string} roomId - Room ID
     * @param {string} playerId - Player ID  
     * @param {string} playerName - Player name
     */
    initialize(roomId, playerId = null, playerName = null) {
        this.roomInfo.roomId = roomId;
        this.roomInfo.playerId = playerId;
        this.roomInfo.playerName = playerName;
        this._notifyRoomInfoUpdate();
    }
    
    /**
     * Update complete game state
     * @param {Object} gameState - Complete game state from server
     */
    updateGameState(gameState) {
        const previousPhase = this.gameState?.phase;
        this.gameState = gameState;
        
        // Reset submission flags on phase changes
        if (previousPhase !== gameState.phase) {
            if (gameState.phase === 'responding') {
                this.hasSubmittedResponse = false;
            } else if (gameState.phase === 'guessing') {
                this.hasSubmittedGuess = false;
            } else if (gameState.phase === 'results') {
                this.roundsCompleted++;
            }
        }
        
        this._notifyStateChange();
    }
    
    /**
     * Update room state (combines game state and players)
     * @param {Object} roomState - Complete room state from server
     */
    updateRoomState(roomState) {
        if (roomState.game_state) {
            this.updateGameState(roomState.game_state);
        }
        
        if (roomState.players) {
            this.updatePlayers(roomState.players);
        }
        
        if (roomState.connected_count !== undefined && roomState.total_count !== undefined) {
            this.updatePlayerCount(roomState.connected_count, roomState.total_count);
        }
    }
    
    /**
     * Update player information after room join
     * @param {Object} joinData - Room join response data
     */
    updateAfterRoomJoin(joinData) {
        this.roomInfo.roomId = joinData.room_id;
        this.roomInfo.playerId = joinData.player_id;
        this.roomInfo.playerName = joinData.player_name;
        this._notifyRoomInfoUpdate();
    }
    
    /**
     * Update players list
     * @param {Array} players - Players array from server
     */
    updatePlayers(players) {
        this.players = Array.isArray(players) ? players : [];
        this._notifyPlayersUpdate();
    }
    
    /**
     * Update player count
     * @param {number} connected - Connected players count
     * @param {number} total - Total players count
     */
    updatePlayerCount(connected, total) {
        this.roomInfo.connectedCount = connected;
        this.roomInfo.totalCount = total;
        this._notifyRoomInfoUpdate();
    }
    
    /**
     * Mark response as submitted
     * @param {string} responseText - The text that was submitted (optional)
     */
    markResponseSubmitted(responseText = null) {
        this.hasSubmittedResponse = true;
        if (responseText) {
            this.submittedResponseText = responseText.trim();
        }
        this._notifyStateChange();
    }
    
    /**
     * Mark guess as submitted
     */
    markGuessSubmitted() {
        this.hasSubmittedGuess = true;
        this._notifyStateChange();
    }
    
    /**
     * Reset submission flags (for error recovery)
     */
    resetSubmissionFlags() {
        this.hasSubmittedResponse = false;
        this.hasSubmittedGuess = false;
        this.submittedResponseText = null; // Reset for new round
        this._notifyStateChange();
    }
    
    /**
     * Get current game phase
     * @returns {string|null} Current phase
     */
    getCurrentPhase() {
        return this.gameState?.phase || null;
    }
    
    /**
     * Get current round number
     * @returns {number} Current round number
     */
    getCurrentRound() {
        return this.gameState?.round_number || 0;
    }
    
    /**
     * Get time remaining in current phase
     * @returns {number} Time remaining in seconds
     */
    getTimeRemaining() {
        return this.gameState?.time_remaining || 0;
    }
    
    /**
     * Get phase duration
     * @returns {number} Phase duration in seconds
     */
    getPhaseDuration() {
        return this.gameState?.phase_duration || 0;
    }
    
    /**
     * Check if player can start round
     * @returns {boolean} Whether player can start round
     */
    canStartRound() {
        return this.roomInfo.connectedCount >= 2 && 
               this.getCurrentPhase() === 'waiting';
    }
    
    /**
     * Check if player can submit response
     * @returns {boolean} Whether player can submit response
     */
    canSubmitResponse() {
        return this.getCurrentPhase() === 'responding' && 
               !this.hasSubmittedResponse;
    }
    
    /**
     * Check if player can submit guess
     * @returns {boolean} Whether player can submit guess
     */
    canSubmitGuess() {
        return this.getCurrentPhase() === 'guessing' && 
               !this.hasSubmittedGuess;
    }
    
    /**
     * Get player data by ID
     * @param {string} playerId - Player ID
     * @returns {Object|null} Player data
     */
    getPlayer(playerId) {
        return this.players.find(p => p.player_id === playerId) || null;
    }
    
    /**
     * Get current player data
     * @returns {Object|null} Current player data
     */
    getCurrentPlayer() {
        return this.roomInfo.playerId ? this.getPlayer(this.roomInfo.playerId) : null;
    }
    
    /**
     * Get sorted players by score
     * @returns {Array} Players sorted by score (highest first)
     */
    getSortedPlayers() {
        return [...this.players].sort((a, b) => {
            if (b.score !== a.score) {
                return b.score - a.score;
            }
            return a.name.localeCompare(b.name);
        });
    }
    
    /**
     * Get complete current state
     * @returns {Object} Complete state object
     */
    getState() {
        return {
            gameState: this.gameState,
            players: this.players,
            roomInfo: { ...this.roomInfo },
            roundsCompleted: this.roundsCompleted,
            hasSubmittedResponse: this.hasSubmittedResponse,
            hasSubmittedGuess: this.hasSubmittedGuess
        };
    }
    
    // Private methods
    
    _notifyStateChange() {
        if (this.onStateChange) {
            this.onStateChange(this.getState());
        }
    }
    
    _notifyPlayersUpdate() {
        if (this.onPlayersUpdate) {
            this.onPlayersUpdate(this.players);
        }
    }
    
    _notifyRoomInfoUpdate() {
        if (this.onRoomInfoUpdate) {
            this.onRoomInfoUpdate({ ...this.roomInfo });
        }
    }
}

// Export for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GameStateManager;
}