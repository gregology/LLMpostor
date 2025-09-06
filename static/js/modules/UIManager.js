/**
 * UIManager - Handles all UI rendering and DOM manipulation
 * 
 * Responsible for:
 * - DOM element caching and management
 * - UI state transitions
 * - Content rendering and updates
 * - Form state management
 * - Visual feedback and animations
 */

class UIManager {
    constructor() {
        this.elements = {};
        this.maxResponseLength = window.maxResponseLength || 500;
        
        // UI state
        this.currentPhase = null;
        this.isInitialized = false;
        
        // Callbacks
        this.onSubmitResponse = null;
        this.onSubmitGuess = null;
        this.onStartRound = null;
        this.onLeaveRoom = null;
        this.onShareRoom = null;
        
        // Initialize when DOM is ready (skip in test environment)
        if (typeof window !== 'undefined' && !window.isTestEnvironment) {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.initialize());
            } else {
                this.initialize();
            }
        }
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
        console.log('UIManager initialized');
    }
    
    /**
     * Update connection status display
     * @param {string} status - Status type (connected, disconnected, error, reconnecting)
     * @param {string} text - Status text to display
     */
    updateConnectionStatus(status, text) {
        if (!this.elements.connectionStatus) return;
        
        this.elements.connectionStatus.className = `status-indicator ${status}`;
        this.elements.connectionStatus.innerHTML = `
            <span class="status-dot"></span>
            ${text}
        `;
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
        if (this.elements.currentPrompt && promptData.prompt) {
            const promptWithBreaks = this._escapeHtml(promptData.prompt).replace(/\n/g, '<br>');
            this.elements.currentPrompt.innerHTML = promptWithBreaks;
        }
        
        if (this.elements.targetModel && promptData.model) {
            this.elements.targetModel.textContent = promptData.model;
        }
        
        if (this.elements.guessingTargetModel && promptData.model) {
            this.elements.guessingTargetModel.textContent = promptData.model;
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
        this.elements.guessingTargetModel = document.getElementById('guessingTargetModel');
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
                if (this.onLeaveRoom) this.onLeaveRoom();
            });
        }
        
        // Share room
        if (this.elements.shareRoomBtn) {
            this.elements.shareRoomBtn.addEventListener('click', () => {
                if (this.onShareRoom) this.onShareRoom();
            });
        }
        
        // Response input handling
        if (this.elements.responseInput) {
            this.elements.responseInput.addEventListener('input', () => this._handleResponseInput());
            this.elements.responseInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    if (this.onSubmitResponse) this.onSubmitResponse();
                }
            });
        }
        
        // Submit response button
        if (this.elements.submitResponseBtn) {
            this.elements.submitResponseBtn.addEventListener('click', () => {
                if (this.onSubmitResponse) this.onSubmitResponse();
            });
        }
        
        // Start round button
        if (this.elements.startRoundBtn) {
            this.elements.startRoundBtn.addEventListener('click', () => {
                if (this.onStartRound) this.onStartRound();
            });
        }
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
        const playerElement = document.createElement('div');
        playerElement.className = `player-item ${player.connected ? 'connected' : 'disconnected'} ${player.player_id === currentPlayerId ? 'current-player' : ''}`;
        
        // Update position only if score is different from previous player
        if (previousScore !== null && player.score < previousScore) {
            currentPosition = index + 1;
        }
        
        // Add position indicator for top players (only show if there are actual scores)
        const hasScores = player.score > 0;
        const positionBadge = (hasScores && currentPosition <= 3) ? 
            `<span class="position-badge position-${currentPosition}">${currentPosition}</span>` : '';
        
        playerElement.innerHTML = `
            <div class="player-info">
                <div class="player-name-row">
                    ${positionBadge}
                    <span class="player-name">${this._escapeHtml(player.name)}</span>
                </div>
                <span class="player-score">${player.score} pts</span>
            </div>
            <div class="player-status ${player.connected ? 'online' : 'offline'}">
                ${player.connected ? '●' : '○'}
            </div>
        `;
        
        return playerElement;
    }
    
    _createResponseCard(response, index) {
        const responseCard = document.createElement('div');
        responseCard.className = 'response-card';
        
        const responseTextWithBreaks = this._escapeHtml(response.text).replace(/\n/g, '<br>');
        
        responseCard.innerHTML = `
            <div class="response-header">
                <span class="response-label">Response ${String.fromCharCode(65 + index)}</span>
            </div>
            <div class="response-text">${responseTextWithBreaks}</div>
            <button class="guess-btn btn btn-outline" data-index="${index}">
                Select This Response
            </button>
        `;
        
        // Add click handler for guess button
        const guessBtn = responseCard.querySelector('.guess-btn');
        guessBtn.addEventListener('click', (event) => {
            event.preventDefault();
            if (!guessBtn.disabled && this.onSubmitGuess) {
                this.onSubmitGuess(index);
            }
        });
        
        return responseCard;
    }
    
    _displayCorrectResponse(results) {
        if (!this.elements.correctResponse || !results.correct_response) return;
        
        const correctResponseWithBreaks = this._escapeHtml(results.correct_response.text).replace(/\n/g, '<br>');
        this.elements.correctResponse.innerHTML = `
            <div class="response-header">
                <span class="response-label">AI Response (${results.correct_response.model})</span>
            </div>
            <div class="response-text">${correctResponseWithBreaks}</div>
        `;
    }
    
    _displayPlayerResults(results) {
        if (!this.elements.roundScoresList || !results.player_results) return;
        
        this.elements.roundScoresList.innerHTML = '';
        
        // Convert player_results to array and sort by round_points (descending)
        const playerArray = Object.values(results.player_results)
            .sort((a, b) => b.round_points - a.round_points);
        
        playerArray.forEach((player) => {
            const scoreItem = this._createPlayerResultElement(player, results);
            this.elements.roundScoresList.appendChild(scoreItem);
        });
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
}

// Export for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIManager;
}