/**
 * UIManager - Optimized event-driven UI rendering and DOM manipulation
 * 
 * Responsible for:
 * - Efficient DOM element caching and management
 * - Batch DOM updates and Virtual DOM operations
 * - UI state transitions with performance optimizations
 * - Content rendering with lazy loading
 * - Form state management with debouncing
 * - Visual feedback and optimized animations
 * - Memory-efficient event handling
 * 
 * Performance Optimizations:
 * - DOM query result caching
 * - Batch DOM updates using DocumentFragment
 * - Debounced input handlers
 * - Lazy rendering of non-critical UI
 * - Memory-efficient event listener management
 * - Optimized animation with requestAnimationFrame
 * 
 * Migration Status: Updated to use EventBus with backward compatibility
 */

import { EventBusModule } from './EventBusMigration.js';
import { Events } from './EventBus.js';
import MemoryManager from '../utils/MemoryManager.js';
import { getBootstrapValue } from '../utils/Bootstrap.js';
import StateRenderer from './ui/StateRenderer.js';
import PerformanceOptimizer from './ui/PerformanceOptimizer.js';

class UIManager extends EventBusModule {
    constructor() {
        super('UIManager');
        
        this.elements = {};
        this.maxResponseLength = getBootstrapValue('maxResponseLength', 500);
        
        // Performance optimizations
        this.memoryManager = new MemoryManager();
        this.domCache = new Map();
        this.updateQueue = [];
        this.isUpdating = false;
        this.debounceTimers = new Map();
        
        // Batch update tracking
        this.pendingUpdates = new Set();
        this.animationFrameId = null;
        
        // UI state
        this.currentPhase = null;
        this.isInitialized = false;

        // Rendering helpers
        this.renderer = new StateRenderer();
        this.optimizer = new PerformanceOptimizer(this.memoryManager);
        
        
        // Subscribe to events that trigger UI updates
        this._setupEventSubscriptions();
        
        // Initialize when DOM is ready (skip in test environment)
        if (typeof window !== 'undefined' && !window.isTestEnvironment) {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.initialize());
            } else {
                this.initialize();
            }
        }
        
        console.log('UIManager initialized with EventBus integration');
    }
    
    /**
     * Initialize UI manager
     */
    initialize() {
        if (this.isInitialized) {
            console.warn('UIManager already initialized');
            return;
        }
        
        this._cacheElements();
        this._setupEventListeners();
        this.isInitialized = true;
        
        // Publish initialization event
        this.publish(Events.UI.CONNECTION_STATUS_CHANGED, {
            status: 'initialized',
            message: 'UI Manager ready'
        });
        
        console.log('UIManager initialized');
    }
    
    /**
     * Update connection status display with optimized DOM updates
     * @param {string} status - Status type (connected, disconnected, error, reconnecting)
     * @param {string} text - Status text to display
     */
    updateConnectionStatus(status, text) {
        this._batchUpdate('connectionStatus', () => {
            if (!this.elements.connectionStatus) return;
            
            this.elements.connectionStatus.className = `status-indicator ${status}`;
            this.elements.connectionStatus.innerHTML = `
                <span class="status-dot"></span>
                ${this._escapeHtml(text)}
            `;
        });
        
        // Publish connection status change event
        this.publish(Events.UI.CONNECTION_STATUS_CHANGED, {
            status,
            text,
            timestamp: Date.now()
        });
    }
    
    /**
     * Update room information display
     * @param {Object} roomInfo - Room information
     */
    updateRoomInfo(roomInfo) {
        if (!roomInfo) return;
        
        if (this.elements.roomName && roomInfo.roomId) {
            this.elements.roomName.textContent = roomInfo.roomId;
        }
        
        if (this.elements.playerCount) {
            this.elements.playerCount.textContent = roomInfo.connectedCount || 0;
        }
        
        this._updateStartRoundButton(roomInfo.connectedCount || 0);
        
        // Publish room info update event
        this.publish(Events.UI.ROOM_INFO_UPDATED, {
            roomInfo,
            timestamp: Date.now()
        });
    }
    
    /**
     * Update players list display
     * @param {Array} players - Players array
     * @param {string} currentPlayerId - Current player ID for highlighting
     */
    updatePlayersList(players, currentPlayerId) {
        if (!this.elements.playersList) return;
        
        this.elements.playersList.innerHTML = '';
        
        const sortedPlayers = this._sortPlayersByScore(players);
        
        // Calculate positions accounting for ties
        let currentPosition = 1;
        let previousScore = null;
        
        sortedPlayers.forEach((player, index) => {
            const playerElement = this._createPlayerElement(player, index, currentPlayerId, currentPosition, previousScore);
            
            // Update position only if score is different from previous player
            if (previousScore !== null && player.score < previousScore) {
                currentPosition = index + 1;
            }
            previousScore = player.score;
            
            this.elements.playersList.appendChild(playerElement);
        });
        
        // Publish players list update event
        this.publish(Events.UI.PLAYERS_UPDATED, {
            players: sortedPlayers,
            currentPlayerId,
            playerCount: players.length,
            timestamp: Date.now()
        });
    }
    
    /**
     * Update rounds played display
     * @param {number} roundsCompleted - Number of completed rounds
     */
    updateRoundsPlayed(roundsCompleted) {
        if (this.elements.roundsPlayed) {
            this.elements.roundsPlayed.textContent = roundsCompleted;
        }
    }
    
    /**
     * Switch to game phase
     * @param {string} phase - Game phase (waiting, responding, guessing, results)
     * @param {Object} data - Phase-specific data
     */
    switchToPhase(phase, data = {}) {
        this.currentPhase = phase;
        this._hideAllGameStates();
        
        switch (phase) {
            case 'waiting':
                this._showWaitingState();
                break;
            case 'responding':
                this._showResponseState(data);
                break;
            case 'guessing':
                this._showGuessingState(data);
                break;
            case 'results':
                this._showResultsState(data);
                break;
        }
    }
    
    /**
     * Update prompt display
     * @param {Object} promptData - Prompt data from server
     */
    updatePromptDisplay(promptData) {
        if (promptData.prompt) {
            const promptWithBreaks = this._escapeHtml(promptData.prompt).replace(/\n/g, '<br>');
            
            // Update response phase prompt
            if (this.elements.currentPrompt) {
                this.elements.currentPrompt.innerHTML = promptWithBreaks;
            }
            
            // Update guessing phase prompt
            if (this.elements.guessingPrompt) {
                this.elements.guessingPrompt.innerHTML = promptWithBreaks;
            }
        }
        
        if (promptData.model) {
            if (this.elements.targetModel) {
                this.elements.targetModel.textContent = promptData.model;
            }
            
            if (this.elements.guessingModelName) {
                this.elements.guessingModelName.textContent = promptData.model;
            }
        }
    }
    
    /**
     * Update timer display
     * @param {Object} timerData - Timer data from TimerManager
     */
    updateTimer(timerData) {
        if (!timerData) return;
        
        const { phase, timeText, progress, progressColor } = timerData;
        
        let timerElement, progressElement;
        
        switch (phase) {
            case 'response':
            case 'responding':
                timerElement = this.elements.responseTimer;
                progressElement = this.elements.responseTimerBar;
                break;
            case 'guessing':
                timerElement = this.elements.guessingTimer;
                progressElement = this.elements.guessingTimerBar;
                break;
            case 'results':
                timerElement = this.elements.nextRoundTimer;
                break;
        }
        
        if (timerElement) {
            timerElement.textContent = timeText;
        }
        
        if (progressElement) {
            progressElement.style.width = `${progress}%`;
            progressElement.style.backgroundColor = progressColor;
        }
    }
    
    /**
     * Flash timer for warning
     * @param {string} phase - Phase to flash timer for
     */
    flashTimer(phase) {
        let timerElement;
        
        switch (phase) {
            case 'response':
            case 'responding':
                timerElement = this.elements.responseTimer;
                break;
            case 'guessing':
                timerElement = this.elements.guessingTimer;
                break;
        }
        
        if (timerElement) {
            timerElement.classList.add('timer-warning');
            setTimeout(() => {
                timerElement.classList.remove('timer-warning');
            }, 1000);
        }
    }
    
    /**
     * Update submission count display
     * @param {number} submitted - Number of submitted responses
     * @param {number} total - Total number of players
     */
    updateSubmissionCount(submitted, total) {
        if (this.elements.submissionCount) {
            const submittedSpan = this.elements.submissionCount.querySelector('.submitted-count');
            const totalSpan = this.elements.submissionCount.querySelector('.total-count');
            
            if (submittedSpan) submittedSpan.textContent = submitted;
            if (totalSpan) totalSpan.textContent = total;
        }
    }
    
    /**
     * Update guess count display
     * @param {number} guessed - Number of submitted guesses
     * @param {number} total - Total number of players
     */
    updateGuessCount(guessed, total) {
        if (this.elements.guessingCount) {
            const guessedSpan = this.elements.guessingCount.querySelector('.guessed-count');
            const totalSpan = this.elements.guessingCount.querySelector('.total-count');
            
            if (guessedSpan) guessedSpan.textContent = guessed;
            if (totalSpan) totalSpan.textContent = total;
        }
    }
    
    /**
     * Show response submitted state
     */
    showResponseSubmitted() {
        if (this.elements.responseInput) {
            this.elements.responseInput.disabled = true;
        }
        
        if (this.elements.submitResponseBtn) {
            this._setButtonState(this.elements.submitResponseBtn, {
                text: 'Response Submitted',
                disabled: true,
                loading: false,
                classes: ['btn-success']
            });
        }
    }
    
    /**
     * Show guess submitted state
     * @param {number} guessIndex - Index of selected guess
     */
    showGuessSubmitted(guessIndex) {
        const responseCards = this.elements.responsesList?.querySelectorAll('.response-card');
        if (!responseCards) return;
        
        responseCards.forEach((card, index) => {
            const guessBtn = card.querySelector('.guess-btn');
            if (index === guessIndex) {
                card.classList.add('selected');
                guessBtn.textContent = 'Selected';
                guessBtn.classList.remove('btn-outline');
                guessBtn.classList.add('btn-success');
                guessBtn.disabled = true;
            } else {
                guessBtn.disabled = true;
                guessBtn.classList.add('btn-disabled');
                if (guessBtn.textContent === 'Submitting...') {
                    guessBtn.textContent = 'Select This Response';
                }
            }
        });
    }
    
    /**
     * Display responses for guessing phase
     * @param {Array} responses - Responses array
     */
    displayResponsesForGuessing(responses) {
        if (!this.elements.responsesList) return;
        if (!responses) return;
        
        this.elements.responsesList.innerHTML = '';
        
        responses.forEach((response, index) => {
            const responseCard = this._createResponseCard(response, index);
            this.elements.responsesList.appendChild(responseCard);
        });
    }
    
    /**
     * Display round results
     * @param {Object} resultsData - Results data from server
     */
    displayRoundResults(resultsData) {
        const results = resultsData.round_results;
        if (!results) return;
        
        this._displayCorrectResponse(results);
        this._displayPlayerResults(results);
    }
    
    // Event subscription setup
    
    _setupEventSubscriptions() {
        // Subscribe to timer updates to update UI
        this.subscribe(Events.TIMER.UPDATED, this._handleTimerUpdate.bind(this));
        this.subscribe(Events.TIMER.WARNING, this._handleTimerWarning.bind(this));
        
        // Subscribe to game state changes
        this.subscribe(Events.GAME.PHASE_CHANGED, this._handlePhaseChange.bind(this));
        this.subscribe(Events.GAME.STATE_CHANGED, this._handleGameStateChange.bind(this));
        this.subscribe(Events.GAME.PROMPT_UPDATED, this._handlePromptUpdate.bind(this));
        
        // Subscribe to socket events for UI updates
        this.subscribe(Events.SOCKET.CONNECTED, this._handleSocketConnected.bind(this));
        this.subscribe(Events.SOCKET.DISCONNECTED, this._handleSocketDisconnected.bind(this));
        this.subscribe(Events.SOCKET.ERROR, this._handleSocketError.bind(this));
    }
    
    _handleTimerUpdate(timerData) {
        this.updateTimer(timerData);
    }
    
    _handleTimerWarning(warningData) {
        this.flashTimer(warningData.phase);
    }
    
    _handlePhaseChange(data) {
        if (data.newPhase !== this.currentPhase) {
            this.switchToPhase(data.newPhase, data);
        }
    }
    
    _handleGameStateChange(stateData) {
        // Handle general game state changes
        if (stateData.roundsCompleted !== undefined) {
            this.updateRoundsPlayed(stateData.roundsCompleted);
        }
    }
    
    _handlePromptUpdate(promptData) {
        this.updatePromptDisplay(promptData);
    }
    
    _handleSocketConnected(data) {
        this.updateConnectionStatus('connected', 'Connected');
    }
    
    _handleSocketDisconnected(data) {
        this.updateConnectionStatus('disconnected', 'Disconnected');
    }
    
    _handleSocketError(data) {
        this.updateConnectionStatus('error', 'Connection Error');
    }
    
    // Private methods
    
    _cacheElements() {
        // Connection status
        this.elements.connectionStatus = document.getElementById('connectionStatus');
        
        // Room info
        this.elements.roomName = document.querySelector('.room-name');
        this.elements.playerCount = document.getElementById('playerCount');
        this.elements.playersList = document.getElementById('playersList');
        this.elements.roundsPlayed = document.getElementById('roundsPlayed');
        
        // Game states
        this.elements.waitingState = document.getElementById('waitingState');
        this.elements.responseState = document.getElementById('responseState');
        this.elements.guessingState = document.getElementById('guessingState');
        this.elements.resultsState = document.getElementById('resultsState');
        
        // Response phase elements
        this.elements.currentPrompt = document.getElementById('currentPrompt');
        this.elements.targetModel = document.getElementById('targetModel');
        this.elements.responseInput = document.getElementById('responseInput');
        this.elements.charCount = document.getElementById('charCount');
        this.elements.submitResponseBtn = document.getElementById('submitResponseBtn');
        this.elements.responseTimer = document.getElementById('responseTimer');
        this.elements.responseTimerBar = document.getElementById('responseTimerBar');
        this.elements.submissionCount = document.getElementById('submissionCount');
        
        // Guessing phase elements
        this.elements.responsesList = document.getElementById('responsesList');
        this.elements.guessingTimer = document.getElementById('guessingTimer');
        this.elements.guessingTimerBar = document.getElementById('guessingTimerBar');
        this.elements.guessingPrompt = document.getElementById('guessingPrompt');
        this.elements.guessingModelName = document.getElementById('guessingModelName');
        this.elements.guessingCount = document.getElementById('guessingCount');
        
        // Results phase elements
        this.elements.correctResponse = document.getElementById('correctResponse');
        this.elements.roundScoresList = document.getElementById('roundScoresList');
        this.elements.nextRoundTimer = document.getElementById('nextRoundTimer');
        
        // Room actions
        this.elements.leaveRoomBtn = document.getElementById('leaveRoomBtn');
        this.elements.shareRoomBtn = document.getElementById('shareRoomBtn');
        this.elements.startRoundBtn = document.getElementById('startRoundBtn');
    }
    
    _setupEventListeners() {
        // Leave room
        if (this.elements.leaveRoomBtn) {
            this.elements.leaveRoomBtn.addEventListener('click', () => {
                this.publish(Events.USER.ROOM_LEAVE, {
                    timestamp: Date.now()
                });
            });
        }
        
        // Share room
        if (this.elements.shareRoomBtn) {
            this.elements.shareRoomBtn.addEventListener('click', () => {
                this.publish(Events.USER.ROOM_SHARE, {
                    timestamp: Date.now()
                });
            });
        }
        
        // Response input handling with debouncing
        if (this.elements.responseInput) {
            this.memoryManager.trackEventListener(
                this.elements.responseInput, 
                'input', 
                this._debounce(() => {
                    this._handleResponseInput();
                    
                    // Publish input change event
                    this.publish(Events.USER.INPUT_CHANGED, {
                        inputType: 'response',
                        value: this.elements.responseInput.value,
                        length: this.elements.responseInput.value.length,
                        maxLength: this.maxResponseLength,
                        isValid: this._isResponseValid(),
                        timestamp: Date.now()
                    });
                }, 100)
            );
            
            this.memoryManager.trackEventListener(
                this.elements.responseInput, 
                'keydown', 
                (e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                        this._submitResponse();
                    }
                }
            );
        }
        
        // Submit response button
        if (this.elements.submitResponseBtn) {
            this.elements.submitResponseBtn.addEventListener('click', () => {
                this._submitResponse();
            });
        }
        
        // Start round button
        if (this.elements.startRoundBtn) {
            this.elements.startRoundBtn.addEventListener('click', () => {
                this.publish(Events.USER.ROUND_START, {
                    timestamp: Date.now()
                });
            });
        }
    }
    
    _submitResponse() {
        const responseText = this.elements.responseInput?.value?.trim();
        
        this.publish(Events.USER.RESPONSE_SUBMITTED, {
            response: responseText,
            length: responseText?.length || 0,
            timestamp: Date.now()
        });
    }
    
    _isResponseValid() {
        if (!this.elements.responseInput) return false;
        const text = this.elements.responseInput.value.trim();
        return text.length > 0 && text.length <= this.maxResponseLength;
    }
    
    _hideAllGameStates() {
        const states = [
            this.elements.waitingState,
            this.elements.responseState,
            this.elements.guessingState,
            this.elements.resultsState
        ];
        
        states.forEach(state => {
            if (state) {
                state.classList.add('hidden');
            }
        });
    }
    
    _showWaitingState() {
        if (this.elements.waitingState) {
            this.elements.waitingState.classList.remove('hidden');
        }
    }
    
    _showResponseState(data) {
        if (this.elements.responseState) {
            this.elements.responseState.classList.remove('hidden');
        }
        
        // Reset response form for new round
        if (this.elements.responseInput) {
            this.elements.responseInput.value = '';
            this.elements.responseInput.disabled = false;
        }
        
        if (this.elements.submitResponseBtn) {
            this._setButtonState(this.elements.submitResponseBtn, {
                text: 'Submit Response',
                disabled: true, // Will be enabled when text is entered
                loading: false,
                classes: ['btn-primary']
            });
            this.elements.submitResponseBtn.style.display = '';
        }
        
        this._updateCharacterCount();
    }
    
    _showGuessingState(data) {
        if (this.elements.guessingState) {
            this.elements.guessingState.classList.remove('hidden');
        }
        
        // Hide response submit button
        if (this.elements.submitResponseBtn) {
            this.elements.submitResponseBtn.style.display = 'none';
        }
    }
    
    _showResultsState(data) {
        if (this.elements.resultsState) {
            this.elements.resultsState.classList.remove('hidden');
        }
    }
    
    _handleResponseInput() {
        this._updateCharacterCount();
        this._updateSubmitButtonState();
    }
    
    _updateCharacterCount() {
        if (!this.elements.responseInput || !this.elements.charCount) return;
        
        const count = this.elements.responseInput.value.length;
        this.elements.charCount.textContent = count;
        
        // Update character count color
        if (count >= this.maxResponseLength * 0.8) {
            this.elements.charCount.style.color = '#ef4444'; // red
        } else if (count >= this.maxResponseLength * 0.6) {
            this.elements.charCount.style.color = '#f59e0b'; // orange
        } else {
            this.elements.charCount.style.color = '#6b7280'; // gray
        }
    }
    
    _updateSubmitButtonState() {
        if (!this.elements.submitResponseBtn || !this.elements.responseInput) return;
        
        // Don't update button state if response is already submitted
        if (this.elements.responseInput.disabled) {
            return;
        }
        
        const text = this.elements.responseInput.value.trim();
        const isValid = text.length > 0 && text.length <= this.maxResponseLength;
        
        this.elements.submitResponseBtn.disabled = !isValid;
    }
    
    _updateStartRoundButton(playerCount) {
        if (!this.elements.startRoundBtn) return;
        
        const canStart = playerCount >= 2;
        this.elements.startRoundBtn.disabled = !canStart;
        
        const hint = document.querySelector('.start-hint');
        if (hint) {
            if (canStart) {
                hint.textContent = 'Ready to start!';
                hint.style.color = '#10b981'; // green
            } else {
                hint.textContent = 'Need at least 2 players to start';
                hint.style.color = '#6b7280'; // gray
            }
        }
    }
    
    _sortPlayersByScore(players) {
        return [...players].sort((a, b) => {
            if (b.score !== a.score) {
                return b.score - a.score;
            }
            return a.name.localeCompare(b.name);
        });
    }
    
    _createPlayerElement(player, index, currentPlayerId, currentPosition, previousScore) {
        return this.renderer.createPlayerElement(
            player,
            index,
            currentPlayerId,
            currentPosition,
            previousScore
        );
    }
    
    _createResponseCard(response, index) {
        return this.renderer.createResponseCard(response, index, (guessIndex, resp) => {
            this.publish(Events.USER.GUESS_SUBMITTED, {
                guessIndex,
                response: resp,
                timestamp: Date.now()
            });
        });
    }
    
    _displayCorrectResponse(results) {
        this.renderer.renderCorrectResponse(this.elements.correctResponse, results);
    }
    
    _displayPlayerResults(results) {
        this.renderer.renderPlayerResults(this.elements.roundScoresList, results, (t) => this._escapeHtml(t));
    }
    
    _createPlayerResultElement(player, results) {
        const scoreItem = document.createElement('div');
        scoreItem.className = 'score-item';
        
        // Determine what they voted for
        let votedForText = '';
        if (player.guess_target !== null && player.guess_target !== undefined) {
            if (player.guess_target === results.llm_response_index) {
                votedForText = 'Voted: 🤖 (AI)';
            } else {
                const votedResponse = results.responses[player.guess_target];
                if (votedResponse && votedResponse.author_name) {
                    votedForText = `Voted: ${this._escapeHtml(votedResponse.author_name)}`;
                } else {
                    votedForText = 'Voted: Unknown';
                }
            }
        } else {
            votedForText = 'No vote';
        }
        
        // Build scoring breakdown
        const scoringDetails = [];
        if (player.correct_guess) {
            scoringDetails.push('Correct guess: +1 pt');
        }
        if (player.deception_points > 0) {
            const voteCount = player.response_votes;
            scoringDetails.push(`Fooled ${voteCount} player${voteCount !== 1 ? 's' : ''}: +${player.deception_points} pts`);
        }
        if (scoringDetails.length === 0) {
            scoringDetails.push('No points this round');
        }
        
        scoreItem.innerHTML = `
            <div class="player-result">
                <div class="player-header">
                    <span class="player-name">${this._escapeHtml(player.name)}</span>
                    <span class="round-points">+${player.round_points} pts</span>
                </div>
                <div class="player-details">
                    <div class="vote-info">${votedForText}</div>
                    <div class="votes-received">Votes received: ${player.response_votes}</div>
                    <div class="scoring-breakdown">${scoringDetails.join(' • ')}</div>
                </div>
            </div>
        `;
        
        return scoreItem;
    }
    
    _setButtonState(button, state) {
        const btnText = button.querySelector('.btn-text');
        const btnLoading = button.querySelector('.btn-loading');
        
        // Update text
        if (btnText && state.text) {
            btnText.textContent = state.text;
        }
        
        // Update loading state
        if (state.loading) {
            btnText?.classList.add('hidden');
            btnLoading?.classList.remove('hidden');
        } else {
            btnText?.classList.remove('hidden');
            btnLoading?.classList.add('hidden');
        }
        
        // Update disabled state
        button.disabled = !!state.disabled;
        
        // Update classes
        if (state.classes) {
            // Remove existing button style classes
            button.classList.remove('btn-primary', 'btn-secondary', 'btn-success', 'btn-disabled', 'btn-outline');
            // Add new classes
            state.classes.forEach(cls => button.classList.add(cls));
        }
    }
    
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Performance optimization methods
    
    /**
     * Batch DOM updates for better performance
     * @private
     */
    _batchUpdate(updateKey, updateFn) {
        if (this.pendingUpdates.has(updateKey)) {
            return;
        }
        
        this.pendingUpdates.add(updateKey);
        this.updateQueue.push({ key: updateKey, fn: updateFn });
        
        // In test environment, execute immediately for synchronous behavior
        if (typeof window !== 'undefined' && window.isTestEnvironment) {
            this._processBatchedUpdates();
            return;
        }
        
        // In production, use requestAnimationFrame for optimal performance
        if (this.animationFrameId === null) {
            this.animationFrameId = requestAnimationFrame(() => {
                this._processBatchedUpdates();
            });
        }
    }
    
    /**
     * Process batched DOM updates
     * @private
     */
    _processBatchedUpdates() {
        // Prefer using optimizer if present to process queue uniformly
        if (this.optimizer) {
            // migrate queued updates into optimizer and let it process
            const queue = [...this.updateQueue];
            this.updateQueue.length = 0;
            this.pendingUpdates.clear();
            queue.forEach(({ key, fn }) => this.optimizer.batch(key, fn));
            this.optimizer.process();
        } else {
            while (this.updateQueue.length > 0) {
                const update = this.updateQueue.shift();
                try {
                    update.fn();
                } catch (error) {
                    console.error(`Error in batched update ${update.key}:`, error);
                }
            }
            this.pendingUpdates.clear();
        }
        this.animationFrameId = null;
    }
    
    /**
     * Debounce function execution
     * @private
     */
    _debounce(fn, delay) {
        if (this.optimizer) {
            const debounced = this.optimizer.debounce(fn, delay);
            return (...args) => debounced.apply(this, args);
        }
        return (...args) => {
            if (typeof window !== 'undefined' && window.isTestEnvironment) {
                fn.apply(this, args);
                return;
            }
            const key = fn.name || 'anonymous';
            if (this.debounceTimers.has(key)) {
                clearTimeout(this.debounceTimers.get(key));
            }
            const timerId = setTimeout(() => {
                fn.apply(this, args);
                this.debounceTimers.delete(key);
            }, delay);
            this.debounceTimers.set(key, timerId);
            this.memoryManager.trackTimer(timerId);
        };
    }
    
    /**
     * Cache DOM query results for performance
     * @private
     */
    _getCachedElement(selector) {
        if (this.domCache.has(selector)) {
            const cached = this.domCache.get(selector);
            
            // Verify element is still in DOM
            if (cached && document.contains(cached)) {
                return cached;
            } else {
                this.domCache.delete(selector);
            }
        }
        
        const element = document.querySelector(selector);
        if (element) {
            this.domCache.set(selector, element);
        }
        
        return element;
    }
    
    /**
     * Optimized element creation with DocumentFragment
     * @private
     */
    _createElementsFragment(elementsData) {
        const fragment = document.createDocumentFragment();
        
        elementsData.forEach(data => {
            const element = document.createElement(data.tag);
            
            if (data.className) {
                element.className = data.className;
            }
            
            if (data.innerHTML) {
                element.innerHTML = data.innerHTML;
            }
            
            if (data.textContent) {
                element.textContent = data.textContent;
            }
            
            if (data.attributes) {
                Object.entries(data.attributes).forEach(([key, value]) => {
                    element.setAttribute(key, value);
                });
            }
            
            fragment.appendChild(element);
        });
        
        return fragment;
    }
    
    /**
     * Clear performance caches
     * @private
     */
    _clearCaches() {
        this.domCache.clear();
        this.pendingUpdates.clear();
        
        for (const timerId of this.debounceTimers.values()) {
            clearTimeout(timerId);
        }
        this.debounceTimers.clear();
        
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }
    
    /**
     * Clean up event subscriptions and DOM listeners
     */
    destroy() {
        this.cleanup(); // Clean up event bus subscriptions
        
        // Clean up memory manager and performance optimizations
        this.memoryManager.destroy();
        this._clearCaches();
        
        console.log('UIManager destroyed');
    }
    
}

export default UIManager;