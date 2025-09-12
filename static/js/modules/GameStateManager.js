/**
 * GameStateManager - Event-driven game state management system
 * 
 * Responsible for:
 * - Game state tracking and updates
 * - Player data management
 * - Room information management
 * - State validation and synchronization
 * - Event-based state change notifications
 * 
 * Migration Status: Updated to use EventBus with backward compatibility
 */

import { EventBusModule, migrationHelper } from './EventBusMigration.js';
import { Events } from './EventBus.js';

class GameStateManager extends EventBusModule {
    constructor() {
        super('GameStateManager');
        
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
        
        // Legacy callback support (for gradual migration)
        this.onStateChange = null;
        this.onPlayersUpdate = null;
        this.onRoomInfoUpdate = null;
        
        // Subscribe to user action events from UIManager
        this._setupEventSubscriptions();
        
        console.log('GameStateManager initialized with EventBus integration');
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
        
        // Publish room initialization event
        this.publish(Events.SOCKET.ROOM_JOINED, {
            roomId,
            playerId,
            playerName,
            timestamp: Date.now()
        });
    }
    
    /**
     * Setup event subscriptions for user actions and external events
     * @private
     */
    _setupEventSubscriptions() {
        // Subscribe to user action events from UIManager
        this.subscribe(Events.USER.RESPONSE_SUBMITTED, this._handleResponseSubmitted.bind(this));
        this.subscribe(Events.USER.GUESS_SUBMITTED, this._handleGuessSubmitted.bind(this));
        this.subscribe(Events.USER.ROUND_START, this._handleRoundStart.bind(this));
        
        // Subscribe to socket events for state synchronization
        this.subscribe(Events.SOCKET.ROOM_STATE_UPDATED, this._handleRoomStateUpdate.bind(this));
        this.subscribe(Events.SOCKET.PLAYERS_UPDATED, this._handlePlayersUpdate.bind(this));
        
        console.log('GameStateManager: Event subscriptions setup complete');
    }
    
    /**
     * Update complete game state
     * @param {Object} gameState - Complete game state from server
     */
    updateGameState(gameState) {
        const previousPhase = this.gameState?.phase;
        const previousState = { ...this.getState() };
        this.gameState = gameState;
        
        // Reset submission flags on phase changes
        if (previousPhase !== gameState.phase) {
            if (gameState.phase === 'responding') {
                this.hasSubmittedResponse = false;
                this.publish(Events.GAME.ROUND_STARTED, {
                    phase: gameState.phase,
                    prompt: gameState.prompt,
                    phase_duration: gameState.phase_duration,
                    round_number: gameState.round_number,
                    timestamp: Date.now()
                });
            } else if (gameState.phase === 'guessing') {
                this.hasSubmittedGuess = false;
                this.publish(Events.GAME.GUESSING_STARTED, {
                    phase: gameState.phase,
                    responses: gameState.responses,
                    phase_duration: gameState.phase_duration,
                    timestamp: Date.now()
                });
            } else if (gameState.phase === 'results') {
                this.roundsCompleted++;
                this.publish(Events.GAME.RESULTS_STARTED, {
                    phase: gameState.phase,
                    round_results: gameState.round_results,
                    phase_duration: gameState.phase_duration,
                    timestamp: Date.now()
                });
            }
            
            // Publish phase change event
            this.publish(Events.GAME.PHASE_CHANGED, {
                oldPhase: previousPhase,
                newPhase: gameState.phase,
                gameState: gameState,
                timestamp: Date.now()
            });
        }
        
        // Publish general state change event
        this.publish(Events.GAME.STATE_CHANGED, {
            previousState,
            newState: this.getState(),
            gameState: gameState,
            phaseChanged: previousPhase !== gameState.phase,
            roundsCompleted: this.roundsCompleted,
            timestamp: Date.now()
        });
        
        // Handle specific game state events
        if (gameState.prompt) {
            this.publish(Events.GAME.PROMPT_UPDATED, {
                prompt: gameState.prompt,
                model: gameState.model,
                phase: gameState.phase,
                timestamp: Date.now()
            });
        }
        
        if (gameState.responses && gameState.phase === 'guessing') {
            this.publish(Events.GAME.RESPONSES_AVAILABLE, {
                responses: gameState.responses,
                count: gameState.responses.length,
                timestamp: Date.now()
            });
        }
        
        if (gameState.round_results && gameState.phase === 'results') {
            this.publish(Events.GAME.RESULTS_AVAILABLE, {
                results: gameState.round_results,
                completed_round: gameState.round_number,
                timestamp: Date.now()
            });
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
        
        // Publish comprehensive room state update event
        this.publish(Events.SOCKET.ROOM_STATE_UPDATED, {
            roomState,
            gameState: roomState.game_state,
            players: roomState.players,
            connectedCount: roomState.connected_count,
            totalCount: roomState.total_count,
            timestamp: Date.now()
        });
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
        
        // Publish room join confirmation event
        this.publish(Events.SOCKET.ROOM_JOINED, {
            roomId: joinData.room_id,
            playerId: joinData.player_id,
            playerName: joinData.player_name,
            success: true,
            timestamp: Date.now()
        });
    }
    
    /**
     * Update players list
     * @param {Array} players - Players array from server
     */
    updatePlayers(players) {
        const previousPlayers = [...this.players];
        this.players = Array.isArray(players) ? players : [];
        
        // Publish players update event
        this.publish(Events.SOCKET.PLAYERS_UPDATED, {
            players: this.players,
            previousPlayers,
            playerCount: this.players.length,
            connectedCount: this.players.filter(p => p.connected).length,
            timestamp: Date.now()
        });
        
        this._notifyPlayersUpdate();
    }
    
    /**
     * Update player count
     * @param {number} connected - Connected players count
     * @param {number} total - Total players count
     */
    updatePlayerCount(connected, total) {
        const previousCount = {
            connected: this.roomInfo.connectedCount,
            total: this.roomInfo.totalCount
        };
        
        this.roomInfo.connectedCount = connected;
        this.roomInfo.totalCount = total;
        
        // Publish player count update event
        this.publish(Events.SOCKET.PLAYERS_UPDATED, {
            connectedCount: connected,
            totalCount: total,
            previousCount,
            roomInfo: { ...this.roomInfo },
            timestamp: Date.now()
        });
        
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
        
        // Publish response submission event
        this.publish(Events.USER.RESPONSE_SUBMITTED, {
            response: responseText,
            hasSubmitted: this.hasSubmittedResponse,
            playerId: this.roomInfo.playerId,
            playerName: this.roomInfo.playerName,
            phase: this.getCurrentPhase(),
            timestamp: Date.now()
        });
        
        this._notifyStateChange();
    }
    
    /**
     * Mark guess as submitted
     * @param {number} guessIndex - Index of the selected guess (optional)
     */
    markGuessSubmitted(guessIndex = null) {
        this.hasSubmittedGuess = true;
        
        // Publish guess submission event
        this.publish(Events.USER.GUESS_SUBMITTED, {
            guessIndex,
            hasSubmitted: this.hasSubmittedGuess,
            playerId: this.roomInfo.playerId,
            playerName: this.roomInfo.playerName,
            phase: this.getCurrentPhase(),
            timestamp: Date.now()
        });
        
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
    
    // Event handlers for user actions
    
    _handleResponseSubmitted(data) {
        console.log('GameStateManager: Handling response submitted event', data);
        // This handler can be used to coordinate between different modules
        // or trigger additional game state logic when responses are submitted
        // NOTE: Don't call markResponseSubmitted here to avoid circular events
        // The response submission is already handled by the UI layer
    }
    
    _handleGuessSubmitted(data) {
        console.log('GameStateManager: Handling guess submitted event', data);
        // NOTE: Don't call markGuessSubmitted here to avoid circular events
        // The guess submission is already handled by the UI layer
    }
    
    _handleRoundStart(data) {
        console.log('GameStateManager: Handling round start event', data);
        // This handler just logs the event - don't republish to avoid loops
        // The actual round start logic is handled by other modules
    }
    
    _handleRoomStateUpdate(data) {
        console.log('GameStateManager: Handling room state update event', data);
        // This prevents circular event publishing since updateRoomState already publishes
        if (data.roomState) {
            // Update without publishing duplicate events
            if (data.roomState.game_state) {
                this.gameState = data.roomState.game_state;
            }
            if (data.roomState.players) {
                this.players = data.roomState.players;
            }
            if (data.roomState.connected_count !== undefined) {
                this.roomInfo.connectedCount = data.roomState.connected_count;
            }
            if (data.roomState.total_count !== undefined) {
                this.roomInfo.totalCount = data.roomState.total_count;
            }
        }
    }
    
    _handlePlayersUpdate(data) {
        console.log('GameStateManager: Handling players update event', data);
        // Update internal state without publishing events to prevent loops
        if (data.players && Array.isArray(data.players)) {
            this.players = data.players;
        }
        if (data.connectedCount !== undefined) {
            this.roomInfo.connectedCount = data.connectedCount;
        }
        if (data.totalCount !== undefined) {
            this.roomInfo.totalCount = data.totalCount;
        }
        
        // Trigger legacy callback if needed
        if (this.onPlayersUpdate) {
            this.onPlayersUpdate(this.players);
        }
    }
    
    // Private methods
    
    _notifyStateChange() {
        const stateData = this.getState();
        
        // Modern event-based approach
        this.publish(Events.GAME.STATE_CHANGED, {
            state: stateData,
            timestamp: Date.now()
        });
        
        // Legacy callback support (for gradual migration)
        migrationHelper.execute(
            'game-state-updates',
            // Old pattern
            () => {
                if (this.onStateChange) {
                    this.onStateChange(stateData);
                }
            },
            // New pattern (events already published above)
            () => {
                // Events already published - this is just for dual-mode support
            },
            stateData
        );
    }
    
    _notifyPlayersUpdate() {
        // Legacy callback support only - event already published by updatePlayers
        migrationHelper.execute(
            'players-updates',
            // Old pattern
            () => {
                if (this.onPlayersUpdate) {
                    this.onPlayersUpdate(this.players);
                }
            },
            // New pattern (events already published)
            () => {
                // Events already published by updatePlayers
            },
            this.players
        );
    }
    
    _notifyRoomInfoUpdate() {
        const roomInfo = { ...this.roomInfo };
        
        // Modern event-based approach
        this.publish(Events.UI.ROOM_INFO_UPDATED, {
            roomInfo,
            timestamp: Date.now()
        });
        
        // Legacy callback support
        migrationHelper.execute(
            'room-info-updates',
            // Old pattern
            () => {
                if (this.onRoomInfoUpdate) {
                    this.onRoomInfoUpdate(roomInfo);
                }
            },
            // New pattern (events already published)
            () => {
                // Events already published
            },
            roomInfo
        );
    }
    
    /**
     * Clean up all subscriptions and state
     */
    destroy() {
        this.cleanup(); // Clean up event subscriptions
        console.log('GameStateManager destroyed');
    }
}


export default GameStateManager;