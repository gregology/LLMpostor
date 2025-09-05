/**
 * LLMposter Game Client JavaScript
 * Handles Socket.IO communication and UI interactions for the multiplayer guessing game
 */

class LLMposterGameClient {
    constructor() {
        this.socket = null;
        this.roomId = null;
        this.playerId = null;
        this.playerName = null;
        this.gameState = null;
        this.timers = {};
        this.isConnected = false;
        this.hasSubmittedGuess = false; // Flag to prevent multiple guess submissions
        this.roundsCompleted = 0; // Track completed rounds
        
        // UI element references
        this.elements = {};
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }
    
    init() {
        console.log('Initializing LLMposter game client');
        
        // Cache DOM elements
        this.cacheElements();
        
        // Set up basic UI interactions
        this.setupBasicUI();
        
        // Initialize Socket.IO connection
        this.initializeSocket();
        
        // Note: autoJoinRoom() will be called from handleConnect() when connection is ready
    }
    
    cacheElements() {
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
        
        // Debug element caching
        console.log('Cached prompt elements:', {
            currentPrompt: this.elements.currentPrompt,
            targetModel: this.elements.targetModel
        });
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
    
    setupBasicUI() {

        
        // Leave room functionality
        if (this.elements.leaveRoomBtn) {
            this.elements.leaveRoomBtn.addEventListener('click', () => this.leaveRoom());
        }
        
        // Share room functionality
        if (this.elements.shareRoomBtn) {
            this.elements.shareRoomBtn.addEventListener('click', () => this.shareRoom());
        }
        
        // Response input handling
        if (this.elements.responseInput) {
            this.elements.responseInput.addEventListener('input', () => this.handleResponseInput());
            this.elements.responseInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    this.submitResponse();
                }
            });
        }
        
        // Submit response button
        if (this.elements.submitResponseBtn) {
            this.elements.submitResponseBtn.addEventListener('click', () => this.submitResponse());
        }
        
        // Start round button
        if (this.elements.startRoundBtn) {
            this.elements.startRoundBtn.addEventListener('click', () => this.startRound());
        }
    }
    
    initializeSocket() {
        console.log('Connecting to Socket.IO server...');
        
        // Initialize Socket.IO connection
        this.socket = io({
            transports: ['polling', 'websocket'],  // Try polling first in development
            upgrade: true,
            rememberUpgrade: true
        });
        
        // Connection event handlers
        this.socket.on('connect', () => this.handleConnect());
        this.socket.on('disconnect', () => this.handleDisconnect());
        this.socket.on('connect_error', (error) => this.handleConnectionError(error));
        
        // Game event handlers
        this.socket.on('connected', (data) => this.handleServerConnected(data));
        this.socket.on('error', (error) => this.handleServerError(error));
        
        // Room event handlers
        this.socket.on('room_joined', (data) => this.handleRoomJoined(data));
        this.socket.on('room_left', (data) => this.handleRoomLeft(data));
        this.socket.on('player_list_updated', (data) => this.handlePlayerListUpdated(data));
        this.socket.on('room_state_updated', (data) => this.handleRoomStateUpdated(data));
        this.socket.on('room_state', (data) => this.handleRoomState(data));
        
        // Game phase event handlers
        this.socket.on('round_started', (data) => this.handleRoundStarted(data));
        this.socket.on('response_submitted', (data) => this.handleResponseSubmitted(data));
        this.socket.on('guessing_phase_started', (data) => this.handleGuessingPhaseStarted(data));
        this.socket.on('guess_submitted', (data) => this.handleGuessSubmitted(data));
        this.socket.on('results_phase_started', (data) => this.handleResultsPhaseStarted(data));
        
        // Timer and countdown handlers
        this.socket.on('countdown_update', (data) => this.handleCountdownUpdate(data));
        this.socket.on('time_warning', (data) => this.handleTimeWarning(data));
        
        // Game flow handlers
        this.socket.on('game_paused', (data) => this.handleGamePaused(data));
        this.socket.on('round_ended', (data) => this.handleRoundEnded(data));
    }
    
    autoJoinRoom() {
        console.log('autoJoinRoom called, roomId:', typeof roomId !== 'undefined' ? roomId : 'undefined');
        
        // Check if we're on a room page and have room ID from global config
        if (typeof roomId !== 'undefined' && roomId) {
            this.roomId = roomId;
            
            // Get player name from session storage or prompt
            const storedName = sessionStorage.getItem('playerName');
            console.log('Stored player name:', storedName);
            
            if (storedName) {
                this.playerName = storedName;
                console.log('Joining room with stored name:', this.playerName);
                this.joinRoom(this.roomId, this.playerName);
            } else {
                console.log('No stored name, prompting user');
                this.promptForPlayerName();
            }
        }
    }
    
    promptForPlayerName() {
        const name = prompt('Enter your display name:');
        if (name && name.trim()) {
            this.playerName = name.trim();
            sessionStorage.setItem('playerName', this.playerName);
            this.joinRoom(this.roomId, this.playerName);
        } else {
            // Redirect to home if no name provided
            window.location.href = '/';
        }
    }
    
    // Socket.IO Event Handlers
    handleConnect() {
        console.log('Connected to server');
        this.isConnected = true;
        this.updateConnectionStatus('connected', 'Connected');
        
        // Clear connection recovery state on successful connection
        if (this.connectionRecoveryTimer) {
            clearTimeout(this.connectionRecoveryTimer);
            this.connectionRecoveryTimer = null;
        }
        
        // Show reconnection success message if this was a recovery
        if (this.connectionRecoveryAttempts > 0) {
            this.showToast('Reconnected successfully!', 'success');
            this.connectionRecoveryAttempts = 0;
            
            // Hide connection error modal if visible
            const modal = document.getElementById('connectionErrorModal');
            if (modal) {
                modal.style.display = 'none';
            }
            
            // Rejoin room if we were in one
            if (this.roomId && this.playerName) {
                console.log('Rejoining room after reconnection...');
                this.joinRoom(this.roomId, this.playerName);
            }
        } else {
            // Initial connection - try to auto-join room
            this.autoJoinRoom();
        }
    }
    
    handleDisconnect() {
        console.log('Disconnected from server');
        this.isConnected = false;
        this.updateConnectionStatus('disconnected', 'Disconnected');
        this.showToast('Connection lost. Attempting to reconnect...', 'warning');
        
        // Start connection recovery process
        this.startConnectionRecovery();
    }
    
    handleConnectionError(error) {
        console.error('Connection error:', error);
        this.updateConnectionStatus('error', 'Connection Error');
        this.showToast('Failed to connect to server', 'error');
        
        // Start connection recovery process
        this.startConnectionRecovery();
    }
    
    startConnectionRecovery() {
        // Clear any existing recovery timer
        if (this.connectionRecoveryTimer) {
            clearTimeout(this.connectionRecoveryTimer);
        }
        
        // Initialize recovery attempt counter if not exists
        if (!this.connectionRecoveryAttempts) {
            this.connectionRecoveryAttempts = 0;
        }
        
        this.connectionRecoveryAttempts++;
        
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, then 30s max
        const delay = Math.min(Math.pow(2, this.connectionRecoveryAttempts - 1) * 1000, 30000);
        
        console.log(`Connection recovery attempt ${this.connectionRecoveryAttempts} in ${delay}ms`);
        
        this.connectionRecoveryTimer = setTimeout(() => {
            if (!this.isConnected && this.socket) {
                console.log('Attempting to reconnect...');
                this.updateConnectionStatus('reconnecting', 'Reconnecting...');
                
                // Force reconnection
                this.socket.connect();
                
                // If still not connected after max attempts, show persistent error
                if (this.connectionRecoveryAttempts >= 10) {
                    this.showPersistentConnectionError();
                } else {
                    // Schedule next attempt
                    this.startConnectionRecovery();
                }
            }
        }, delay);
    }
    
    showPersistentConnectionError() {
        this.updateConnectionStatus('error', 'Connection Failed');
        this.showToast('Unable to connect to server. Please refresh the page.', 'error', true);
        
        // Show a modal or persistent error message
        this.showConnectionErrorModal();
    }
    
    showConnectionErrorModal() {
        // Create error modal if it doesn't exist
        let modal = document.getElementById('connectionErrorModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'connectionErrorModal';
            modal.className = 'error-modal';
            modal.innerHTML = `
                <div class="error-modal-content">
                    <h3>Connection Lost</h3>
                    <p>Unable to connect to the game server. Please check your internet connection and try again.</p>
                    <div class="error-modal-actions">
                        <button class="btn btn-primary" onclick="window.location.reload()">Refresh Page</button>
                        <button class="btn btn-secondary" onclick="this.parentElement.parentElement.parentElement.style.display='none'">Dismiss</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        modal.style.display = 'flex';
    }
    
    handleServerConnected(data) {
        console.log('Server connection confirmed:', data);
    }
    
    handleServerError(error) {
        console.error('Server error:', error);
        
        // Show user-friendly error message
        const userMessage = this.getUserFriendlyErrorMessage(error);
        this.showToast(userMessage, 'error');
        
        // Reset guess submission flag if there was an error submitting guess
        if (error.code && (error.code.includes('GUESS') || error.code === 'SUBMIT_GUESS_FAILED')) {
            this.hasSubmittedGuess = false;
            
            // Clear submission timeout if it exists
            if (this.guessSubmissionTimeout) {
                clearTimeout(this.guessSubmissionTimeout);
                this.guessSubmissionTimeout = null;
            }
            
            // Re-enable buttons
            const responseCards = this.elements.responsesList?.querySelectorAll('.response-card');
            if (responseCards) {
                responseCards.forEach((card) => {
                    const guessBtn = card.querySelector('.guess-btn');
                    guessBtn.disabled = false;
                    guessBtn.classList.remove('btn-disabled', 'btn-primary');
                    guessBtn.textContent = 'Select This Response';
                });
            }
        }
        
        // Handle specific error codes with appropriate actions
        switch (error.code) {
            case 'PLAYER_NAME_TAKEN':
                this.promptForPlayerName();
                break;
            case 'ROOM_NOT_FOUND':
                this.showToast('Room not found. Redirecting to home...', 'error');
                setTimeout(() => window.location.href = '/', 2000);
                break;
            case 'ALREADY_IN_ROOM':
                // Already in room, request current state
                if (this.roomId && this.playerId) {
                    this.socket.emit('get_room_state');
                }
                break;
            case 'INVALID_ROOM_ID':
                this.showToast('Invalid room name. Please use only letters, numbers, and hyphens.', 'error');
                break;
            case 'PLAYER_NAME_TOO_LONG':
                this.showToast('Player name is too long. Please choose a shorter name.', 'error');
                this.promptForPlayerName();
                break;
            case 'WRONG_PHASE':
                // Refresh game state to sync with server
                if (this.roomId && this.playerId) {
                    this.socket.emit('get_room_state');
                }
                break;
            case 'PHASE_EXPIRED':
                this.showToast('Time expired for this action', 'warning');
                if (this.roomId && this.playerId) {
                    this.socket.emit('get_room_state');
                }
                break;
            case 'RESPONSE_TOO_LONG':
                this.showToast(`Response is too long. Please shorten it to ${maxResponseLength} characters or less.`, 'error');
                break;
            case 'EMPTY_RESPONSE':
                this.showToast('Please enter a response before submitting.', 'warning');
                break;
            case 'NO_PROMPTS_AVAILABLE':
                this.showToast('No prompts available. Please contact the administrator.', 'error');
                break;
            case 'INTERNAL_ERROR':
                this.showToast('An internal error occurred. Please try again.', 'error');
                break;
            default:
                // Log unknown errors for debugging
                console.warn('Unknown error code:', error.code);
        }
    }
    
    getUserFriendlyErrorMessage(error) {
        const friendlyMessages = {
            'INVALID_DATA': 'Invalid data sent to server',
            'MISSING_ROOM_ID': 'Room name is required',
            'MISSING_PLAYER_NAME': 'Player name is required',
            'INVALID_ROOM_ID': 'Room name can only contain letters, numbers, and hyphens',
            'PLAYER_NAME_TOO_LONG': 'Player name is too long (max 20 characters)',
            'ALREADY_IN_ROOM': 'You are already in a room',
            'PLAYER_NAME_TAKEN': 'This player name is already taken',
            'NOT_IN_ROOM': 'You are not in a room',
            'LEAVE_FAILED': 'Failed to leave room',
            'CANNOT_START_ROUND': 'Cannot start round at this time',
            'NO_PROMPTS_AVAILABLE': 'No game content available',
            'PROMPT_ERROR': 'Failed to load game content',
            'START_ROUND_FAILED': 'Failed to start round',
            'EMPTY_RESPONSE': 'Response cannot be empty',
            'RESPONSE_TOO_LONG': 'Response is too long',
            'WRONG_PHASE': 'Action not allowed in current game phase',
            'PHASE_EXPIRED': 'Time limit expired',
            'SUBMIT_FAILED': 'Failed to submit response',
            'MISSING_GUESS': 'Please select a response',
            'INVALID_GUESS_FORMAT': 'Invalid selection format',
            'INVALID_GUESS_INDEX': 'Invalid response selection',
            'SUBMIT_GUESS_FAILED': 'Failed to submit guess',
            'ALREADY_GUESSED': 'You have already submitted a guess',
            'NO_RESULTS_AVAILABLE': 'Results not available',
            'INTERNAL_ERROR': 'Server error occurred'
        };
        
        return friendlyMessages[error.code] || error.message || 'An unexpected error occurred';
    }
    
    handleRoomJoined(data) {
        console.log('Joined room:', data);
        this.playerId = data.player_id;
        this.playerName = data.player_name;
        this.roomId = data.room_id;
        
        this.showToast(`Joined room ${data.room_id}`, 'success');
        this.updateConnectionStatus('connected', 'Connected');
        
        // Update room name display
        if (this.elements.roomName && data.room_id) {
            this.elements.roomName.textContent = data.room_id;
        }
    }
    
    handleRoomLeft(data) {
        console.log('Left room:', data);
        this.showToast(data.message, 'info');
        
        // Redirect to home page
        setTimeout(() => {
            window.location.href = '/';
        }, 1000);
    }
    
    handlePlayerListUpdated(data) {
        console.log('Player list updated:', data);
        this.updatePlayersList(data.players);
        this.updatePlayerCount(data.connected_count, data.total_count);
    }
    
    handleRoomStateUpdated(data) {
        console.log('Room state updated:', data);
        this.gameState = data;
        this.updateGameState(data);
    }
    
    handleRoomState(data) {
        console.log('Received room state:', data);
        this.gameState = data.game_state;
        this.updatePlayersList(data.players);
        this.updatePlayerCount(data.connected_count, data.total_count);
        this.updateGameState(data.game_state);
    }
    
    handleRoundStarted(data) {
        console.log('Round started:', data);
        
        // Handle two different round_started event structures:
        // 1. Success response: {success: true, data: {message: "..."}}
        // 2. Broadcast data: {id: "...", prompt: "...", model: "...", round_number: 1, phase_duration: 180}
        
        if (data.success) {
            // This is just a success confirmation, ignore it
            console.log('Round start confirmation received');
            return;
        }
        
        // This is the actual round data broadcast
        if (!data.prompt || !data.phase_duration) {
            console.warn('Invalid round data received:', data);
            return;
        }
        
        this.showToast(`Round ${data.round_number} started!`, 'info');
        this.updatePromptDisplay(data);
        this.switchToResponsePhase();
        this.startTimer('response', data.phase_duration);
    }
    
    handleResponseSubmitted(data) {
        console.log('Response submitted:', data);
        if (data.success) {
            this.showResponseSubmittedState();
        }
        this.updateSubmissionCount(data.response_count, data.total_players);
    }
    
    handleGuessingPhaseStarted(data) {
        console.log('Guessing phase started:', data);
        this.showToast('Time to guess which response is from AI!', 'info');
        this.displayResponsesForGuessing(data.responses);
        this.switchToGuessingPhase();
        this.startTimer('guessing', data.phase_duration);
    }
    
    handleGuessSubmitted(data) {
        console.log('Guess submitted:', data);
        
        // Handle success response (sent only to submitting player)
        if (data.success && data.data) {
            console.log('Success response data:', data.data);
            // Extract guess_index from the success response
            const guessIndex = data.data.guess_index;
            if (typeof guessIndex !== 'undefined') {
                console.log('Calling showGuessSubmittedState with index:', guessIndex);
                this.showGuessSubmittedState(guessIndex);
            } else {
                console.log('No guess_index found in success response');
            }
            this.showToast(data.data.message || 'Guess submitted successfully!', 'success');
            // Don't reset hasSubmittedGuess here - keep it true to prevent multiple submissions
        }
        // Handle broadcast data (sent to all players) - this has different structure
        else if (typeof data.guess_count !== 'undefined' && typeof data.total_players !== 'undefined') {
            console.log('Broadcast data:', data);
            this.updateGuessCount(data.guess_count, data.total_players);
        }
        // Handle case where it's just the broadcast without success wrapper
        else if (data.message && data.message.includes('submitted')) {
            console.log('Broadcast message:', data);
            // This might be a broadcast message, just update the count if available
            if (typeof data.guess_count !== 'undefined') {
                this.updateGuessCount(data.guess_count, data.total_players || 0);
            }
        } else {
            console.log('Unhandled guess submitted data structure:', data);
        }
    }
    
    handleResultsPhaseStarted(data) {
        console.log('Results phase started:', data);
        this.showToast('Round complete! See the results', 'success');
        this.displayRoundResults(data);
        this.switchToResultsPhase();
        this.startTimer('results', data.phase_duration || 30);
        
        // Increment completed rounds counter
        this.roundsCompleted++;
        this.updateRoundsPlayedDisplay();
    }
    
    handleCountdownUpdate(data) {
        this.updateTimer(data.phase, data.time_remaining, data.phase_duration);
    }
    
    handleTimeWarning(data) {
        this.showToast(data.message, 'warning');
        this.flashTimer(data.phase);
    }
    
    handleGamePaused(data) {
        console.log('Game paused:', data);
        this.showToast(data.message, 'warning');
        this.switchToWaitingState();
    }
    
    handleRoundEnded(data) {
        console.log('Round ended:', data);
        this.switchToWaitingState();
    }
    
    // Game Actions
    joinRoom(roomId, playerName) {
        if (!this.socket || !this.isConnected) {
            console.error('Cannot join room - not connected to server');
            this.showToast('Not connected to server', 'error');
            return;
        }
        
        console.log(`Joining room ${roomId} as ${playerName}`);
        this.socket.emit('join_room', {
            room_id: roomId,
            player_name: playerName
        });
    }
    
    leaveRoom() {
        if (confirm('Are you sure you want to leave the room?')) {
            if (this.socket && this.isConnected) {
                this.socket.emit('leave_room');
            } else {
                window.location.href = '/';
            }
        }
    }
    
    startRound() {
        if (!this.socket || !this.isConnected) {
            this.showToast('Not connected to server', 'error');
            return;
        }
        
        this.socket.emit('start_round');
    }
    
    submitResponse() {
        const responseText = this.elements.responseInput?.value?.trim();
        
        if (!responseText) {
            this.showToast('Please enter a response', 'warning');
            return;
        }
        
        if (responseText.length > maxResponseLength) {
            this.showToast(`Response is too long (max ${maxResponseLength} characters)`, 'warning');
            return;
        }
        
        if (!this.socket || !this.isConnected) {
            this.showToast('Not connected to server', 'error');
            return;
        }
        
        // Show loading state
        this.setSubmitButtonLoading(true);
        
        this.socket.emit('submit_response', {
            response: responseText
        });
    }
    
    submitGuess(responseIndex) {
        // Prevent multiple submissions
        if (this.hasSubmittedGuess) {
            console.log('Guess already submitted, ignoring');
            return;
        }
        
        if (!this.socket || !this.isConnected) {
            this.showToast('Not connected to server', 'error');
            return;
        }
        
        // Check if we're in the guessing phase
        if (!this.gameState || this.gameState.phase !== 'guessing') {
            this.showToast('Guessing is not available right now', 'warning');
            this.hasSubmittedGuess = false; // Reset flag
            return;
        }
        
        // Set flag to prevent multiple submissions
        this.hasSubmittedGuess = true;
        
        // Immediately disable all buttons to prevent double-clicking
        const responseCards = this.elements.responsesList?.querySelectorAll('.response-card');
        console.log(`Disabling ${responseCards?.length || 0} response cards`);
        if (responseCards) {
            responseCards.forEach((card, index) => {
                const guessBtn = card.querySelector('.guess-btn');
                console.log(`Disabling button ${index}, current text: "${guessBtn.textContent}"`);
                guessBtn.disabled = true;
                if (index === parseInt(responseIndex, 10)) {
                    guessBtn.textContent = 'Submitting...';
                    guessBtn.classList.add('btn-primary');
                    console.log(`Set button ${index} to "Submitting..."`);
                } else {
                    guessBtn.classList.add('btn-disabled');
                }
            });
        }
        
        const guessIndex = parseInt(responseIndex, 10);
        console.log(`Submitting guess for response ${responseIndex} (parsed: ${guessIndex})`, typeof guessIndex);
        
        // Add timeout to reset state if no response received
        const timeoutId = setTimeout(() => {
            console.error('Guess submission timeout - no response from server');
            this.hasSubmittedGuess = false;
            // Re-enable buttons
            const responseCards = this.elements.responsesList?.querySelectorAll('.response-card');
            if (responseCards) {
                responseCards.forEach((card) => {
                    const guessBtn = card.querySelector('.guess-btn');
                    guessBtn.disabled = false;
                    guessBtn.textContent = 'Select This Response';
                    guessBtn.classList.remove('btn-primary', 'btn-disabled');
                    guessBtn.classList.add('btn-outline');
                });
            }
            this.showToast('Submission timeout - please try again', 'error');
        }, 10000); // 10 second timeout
        
        // Store timeout ID so we can clear it when we get a response
        this.guessSubmissionTimeout = timeoutId;
        
        this.socket.emit('submit_guess', {
            guess_index: guessIndex
        });
    }
    
    // UI Update Methods
    updateConnectionStatus(status, text) {
        if (!this.elements.connectionStatus) return;
        
        this.elements.connectionStatus.className = `status-indicator ${status}`;
        this.elements.connectionStatus.innerHTML = `
            <span class="status-dot"></span>
            ${text}
        `;
    }
    
    updatePlayersList(players) {
        if (!this.elements.playersList) return;
        
        this.elements.playersList.innerHTML = '';
        
        // Sort players by score (highest first), then by name for ties
        const sortedPlayers = [...players].sort((a, b) => {
            if (b.score !== a.score) {
                return b.score - a.score;
            }
            return a.name.localeCompare(b.name);
        });
        
        // Calculate actual positions accounting for ties
        let currentPosition = 1;
        let previousScore = null;
        
        sortedPlayers.forEach((player, index) => {
            const playerElement = document.createElement('div');
            playerElement.className = `player-item ${player.connected ? 'connected' : 'disconnected'} ${player.player_id === this.playerId ? 'current-player' : ''}`;
            
            // Update position only if score is different from previous player
            if (previousScore !== null && player.score < previousScore) {
                currentPosition = index + 1;
            }
            previousScore = player.score;
            
            // Add position indicator for top players (only show if there are actual scores)
            const hasScores = sortedPlayers.some(p => p.score > 0);
            const positionBadge = (hasScores && currentPosition <= 3) ? `<span class="position-badge position-${currentPosition}">${currentPosition}</span>` : '';
            
            playerElement.innerHTML = `
                <div class="player-info">
                    <div class="player-name-row">
                        ${positionBadge}
                        <span class="player-name">${this.escapeHtml(player.name)}</span>
                    </div>
                    <span class="player-score">${player.score} pts</span>
                </div>
                <div class="player-status ${player.connected ? 'online' : 'offline'}">
                    ${player.connected ? '●' : '○'}
                </div>
            `;
            this.elements.playersList.appendChild(playerElement);
        });
    }
    
    updatePlayerCount(connected, total) {
        if (this.elements.playerCount) {
            this.elements.playerCount.textContent = connected;
        }
        
        // Update start round button state
        this.updateStartRoundButton(connected);
    }
    
    updateRoundsPlayedDisplay() {
        if (this.elements.roundsPlayed) {
            this.elements.roundsPlayed.textContent = this.roundsCompleted;
        }
    }
    
    updateStartRoundButton(playerCount) {
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
    

    
    updateGameState(gameState) {
        if (!gameState) return;
        
        // Update rounds played display is handled separately when rounds complete
        
        // Switch to appropriate game phase
        switch (gameState.phase) {
            case 'waiting':
                this.switchToWaitingState();
                break;
            case 'responding':
                this.switchToResponsePhase();
                if (gameState.current_prompt) {
                    this.updatePromptDisplay(gameState.current_prompt);
                }
                if (gameState.time_remaining) {
                    this.updateTimer('response', gameState.time_remaining, gameState.phase_duration);
                }
                break;
            case 'guessing':
                // Only switch to guessing phase if we're not already there
                // This prevents resetting the UI when we've already submitted a guess
                if (this.gameState?.phase !== 'guessing') {
                    this.switchToGuessingPhase();
                    if (gameState.responses) {
                        this.displayResponsesForGuessing(gameState.responses);
                    }
                } else {
                    // We're already in guessing phase, just update the guess count if needed
                    if (gameState.guess_count !== undefined && gameState.total_players !== undefined) {
                        this.updateGuessCount(gameState.guess_count, gameState.total_players);
                    }
                }
                if (gameState.time_remaining) {
                    this.updateTimer('guessing', gameState.time_remaining, gameState.phase_duration);
                }
                break;
            case 'results':
                this.switchToResultsPhase();
                if (gameState.round_results) {
                    this.displayRoundResults({ round_results: gameState.round_results });
                }
                break;
        }
    }
    
    switchToWaitingState() {
        this.hideAllGameStates();
        if (this.elements.waitingState) {
            this.elements.waitingState.classList.remove('hidden');
        }
        this.clearAllTimers();
    }
    
    switchToResponsePhase() {
        // Check if we're already in response phase to avoid clearing input
        const wasAlreadyInResponsePhase = this.elements.responseState && 
            !this.elements.responseState.classList.contains('hidden');
        
        this.hideAllGameStates();
        if (this.elements.responseState) {
            this.elements.responseState.classList.remove('hidden');
        }
        
        // Reset response form for new round (even if we're already in response phase)
        if (this.elements.responseInput) {
            // Only clear the input if it's a genuinely new round/phase transition
            // Don't clear if user is just typing
            if (!wasAlreadyInResponsePhase || this.elements.responseInput.disabled) {
                this.elements.responseInput.value = '';
            }
            this.elements.responseInput.disabled = false;
        }
        
        // Ensure submit button is visible for response phase
        if (this.elements.submitResponseBtn) {
            this.elements.submitResponseBtn.style.display = '';
            
            // Only reset button state if we're transitioning FROM another phase or if button was disabled due to invalid input
            // Don't reset if user has already submitted (button shows "Response Submitted")
            const isAlreadySubmitted = this.elements.submitResponseBtn.textContent === 'Response Submitted';
            
            if (!wasAlreadyInResponsePhase && !isAlreadySubmitted) {
                this.elements.submitResponseBtn.textContent = 'Submit Response';
                this.elements.submitResponseBtn.disabled = false;
                this.elements.submitResponseBtn.classList.remove('btn-success');
                this.elements.submitResponseBtn.classList.add('btn-primary');
            }
        }
        
        this.setSubmitButtonLoading(false);
        this.updateCharacterCount();
    }
    
    switchToGuessingPhase() {
        this.hideAllGameStates();
        if (this.elements.guessingState) {
            this.elements.guessingState.classList.remove('hidden');
        }
        // Reset guess submission flag for new guessing phase
        this.hasSubmittedGuess = false;
        
        // Ensure response phase button is hidden (in case of UI state issues)
        if (this.elements.submitResponseBtn) {
            this.elements.submitResponseBtn.style.display = 'none';
        }
    }
    
    switchToResultsPhase() {
        this.hideAllGameStates();
        if (this.elements.resultsState) {
            this.elements.resultsState.classList.remove('hidden');
        }
    }
    
    hideAllGameStates() {
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
    
    updatePromptDisplay(promptData) {
        console.log('updatePromptDisplay called with:', promptData);
        console.log('DOM elements:', {
            currentPrompt: this.elements.currentPrompt,
            targetModel: this.elements.targetModel,
            guessingTargetModel: this.elements.guessingTargetModel
        });
        
        if (this.elements.currentPrompt) {
            // Preserve newlines by converting them to <br> tags
            const promptWithBreaks = this.escapeHtml(promptData.prompt).replace(/\n/g, '<br>');
            this.elements.currentPrompt.innerHTML = promptWithBreaks;
        } else {
            console.warn('currentPrompt element not found');
        }
        
        if (this.elements.targetModel) {
            this.elements.targetModel.textContent = promptData.model;
        } else {
            console.warn('targetModel element not found');
        }
        
        if (this.elements.guessingTargetModel) {
            this.elements.guessingTargetModel.textContent = promptData.model;
        }
    }
    
    displayResponsesForGuessing(responses) {
        if (!this.elements.responsesList) return;
        
        this.elements.responsesList.innerHTML = '';
        
        responses.forEach((response, index) => {
            const responseCard = document.createElement('div');
            responseCard.className = 'response-card';
            // Preserve newlines by converting them to <br> tags
            const responseTextWithBreaks = this.escapeHtml(response.text).replace(/\n/g, '<br>');
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
                // Prevent multiple clicks
                if (guessBtn.disabled || this.hasSubmittedGuess) {
                    event.preventDefault();
                    return;
                }
                this.submitGuess(index);
            });
            
            this.elements.responsesList.appendChild(responseCard);
        });
    }
    
    displayRoundResults(data) {
        if (!data.round_results) return;
        
        const results = data.round_results;
        
        // Display correct response
        if (this.elements.correctResponse && results.correct_response) {
            // Preserve newlines by converting them to <br> tags
            const correctResponseWithBreaks = this.escapeHtml(results.correct_response.text).replace(/\n/g, '<br>');
            this.elements.correctResponse.innerHTML = `
                <div class="response-header">
                    <span class="response-label">AI Response (${results.correct_response.model})</span>
                </div>
                <div class="response-text">${correctResponseWithBreaks}</div>
            `;
        }
        
        // Display enhanced round scores
        if (this.elements.roundScoresList && results.player_results) {
            this.elements.roundScoresList.innerHTML = '';
            
            // Convert player_results to array and sort by round_points (descending)
            const playerArray = Object.values(results.player_results)
                .sort((a, b) => b.round_points - a.round_points);
            
            playerArray.forEach((player) => {
                const scoreItem = document.createElement('div');
                scoreItem.className = 'score-item';
                
                // Determine what they voted for
                let votedForText = '';
                if (player.guess_target !== null && player.guess_target !== undefined) {
                    if (player.guess_target === results.llm_response_index) {
                        votedForText = 'Voted: 🤖 (AI)';
                    } else {
                        // Find who they voted for
                        const votedResponse = results.responses[player.guess_target];
                        if (votedResponse && votedResponse.author_name) {
                            votedForText = `Voted: ${this.escapeHtml(votedResponse.author_name)}`;
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
                            <span class="player-name">${this.escapeHtml(player.name)}</span>
                            <span class="round-points">+${player.round_points} pts</span>
                        </div>
                        <div class="player-details">
                            <div class="vote-info">${votedForText}</div>
                            <div class="votes-received">Votes received: ${player.response_votes}</div>
                            <div class="scoring-breakdown">${scoringDetails.join(' • ')}</div>
                        </div>
                    </div>
                `;
                this.elements.roundScoresList.appendChild(scoreItem);
            });
        }
    }
    
    // Timer Management
    startTimer(phase, duration) {
        console.log('startTimer called:', phase, duration);
        
        if (duration === undefined || duration === null || isNaN(duration)) {
            console.warn('startTimer called with invalid duration:', duration);
            return;
        }
        
        this.clearTimer(phase);
        
        const startTime = Date.now();
        const endTime = startTime + (duration * 1000);
        
        this.timers[phase] = setInterval(() => {
            const now = Date.now();
            const remaining = Math.max(0, Math.ceil((endTime - now) / 1000));
            
            this.updateTimer(phase, remaining, duration);
            
            if (remaining <= 0) {
                this.clearTimer(phase);
            }
        }, 1000);
        
        // Initial update
        this.updateTimer(phase, duration, duration);
    }
    
    updateTimer(phase, timeRemaining, totalDuration) {
        // Add debugging for NaN issues
        if (timeRemaining === undefined || timeRemaining === null || isNaN(timeRemaining)) {
            console.warn('updateTimer called with invalid timeRemaining:', timeRemaining, 'phase:', phase);
            timeRemaining = 0;
        }
        
        const minutes = Math.floor(timeRemaining / 60);
        const seconds = timeRemaining % 60;
        const timeText = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
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
        
        if (progressElement && totalDuration > 0) {
            const progress = (timeRemaining / totalDuration) * 100;
            progressElement.style.width = `${progress}%`;
            
            // Change color based on remaining time
            if (progress <= 25) {
                progressElement.style.backgroundColor = '#ef4444'; // red
            } else if (progress <= 50) {
                progressElement.style.backgroundColor = '#f59e0b'; // orange
            } else {
                progressElement.style.backgroundColor = '#10b981'; // green
            }
        }
    }
    
    clearTimer(phase) {
        if (this.timers[phase]) {
            clearInterval(this.timers[phase]);
            delete this.timers[phase];
        }
    }
    
    clearAllTimers() {
        Object.keys(this.timers).forEach(phase => {
            this.clearTimer(phase);
        });
    }
    
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
    
    // Form Handling
    handleResponseInput() {
        this.updateCharacterCount();
        this.updateSubmitButtonState();
    }
    
    updateCharacterCount() {
        if (!this.elements.responseInput || !this.elements.charCount) return;
        
        const count = this.elements.responseInput.value.length;
        this.elements.charCount.textContent = count;
        
        // Update character count color (80% and 60% thresholds)
        if (count > maxResponseLength * 0.8) {
            this.elements.charCount.style.color = '#ef4444'; // red
        } else if (count > maxResponseLength * 0.6) {
            this.elements.charCount.style.color = '#f59e0b'; // orange
        } else {
            this.elements.charCount.style.color = '#6b7280'; // gray
        }
    }
    
    updateSubmitButtonState() {
        if (!this.elements.submitResponseBtn || !this.elements.responseInput) return;
        
        const text = this.elements.responseInput.value.trim();
        const isValid = text.length > 0 && text.length <= maxResponseLength;
        
        this.elements.submitResponseBtn.disabled = !isValid;
    }
    
    setSubmitButtonLoading(loading) {
        if (!this.elements.submitResponseBtn) return;
        
        const btnText = this.elements.submitResponseBtn.querySelector('.btn-text');
        const btnLoading = this.elements.submitResponseBtn.querySelector('.btn-loading');
        
        if (loading) {
            btnText?.classList.add('hidden');
            btnLoading?.classList.remove('hidden');
            this.elements.submitResponseBtn.disabled = true;
        } else {
            btnText?.classList.remove('hidden');
            btnLoading?.classList.add('hidden');
            this.updateSubmitButtonState();
        }
    }
    
    showResponseSubmittedState() {
        if (this.elements.responseInput) {
            this.elements.responseInput.disabled = true;
        }
        
        if (this.elements.submitResponseBtn) {
            this.elements.submitResponseBtn.textContent = 'Response Submitted';
            this.elements.submitResponseBtn.disabled = true;
            this.elements.submitResponseBtn.classList.add('btn-success');
        }
    }
    
    showGuessSubmittedState(guessIndex) {
        console.log(`Showing guess submitted state for index: ${guessIndex}`);
        
        // Clear submission timeout if it exists
        if (this.guessSubmissionTimeout) {
            clearTimeout(this.guessSubmissionTimeout);
            this.guessSubmissionTimeout = null;
        }
        
        // Highlight selected response
        const responseCards = this.elements.responsesList?.querySelectorAll('.response-card');
        if (responseCards) {
            console.log(`Found ${responseCards.length} response cards`);
            responseCards.forEach((card, index) => {
                const guessBtn = card.querySelector('.guess-btn');
                if (index === guessIndex) {
                    console.log(`Marking card ${index} as selected`);
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
        } else {
            console.log('No response cards found');
        }
    }
    
    updateSubmissionCount(submitted, total) {
        if (this.elements.submissionCount) {
            const submittedSpan = this.elements.submissionCount.querySelector('.submitted-count');
            const totalSpan = this.elements.submissionCount.querySelector('.total-count');
            
            if (submittedSpan) submittedSpan.textContent = submitted;
            if (totalSpan) totalSpan.textContent = total;
        }
    }
    
    updateGuessCount(guessed, total) {
        if (this.elements.guessingCount) {
            const guessedSpan = this.elements.guessingCount.querySelector('.guessed-count');
            const totalSpan = this.elements.guessingCount.querySelector('.total-count');
            
            if (guessedSpan) guessedSpan.textContent = guessed;
            if (totalSpan) totalSpan.textContent = total;
        }
    }
    
    // Utility Methods

    
    shareRoom() {
        if (navigator.share) {
            navigator.share({
                title: 'Join my LLMposter game!',
                text: `Join room "${this.roomId}" in LLMposter`,
                url: window.location.href
            }).catch(err => {
                console.log('Error sharing:', err);
                this.copyUrlToClipboard();
            });
        } else {
            this.copyUrlToClipboard();
        }
    }
    
    copyUrlToClipboard() {
        navigator.clipboard.writeText(window.location.href).then(() => {
            this.showToast('Room link copied to clipboard', 'success');
        }).catch(err => {
            console.error('Failed to copy URL:', err);
            this.showToast('Failed to copy room link', 'error');
        });
    }
    
    showToast(message, type = 'info', persistent = false) {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <span class="toast-message">${this.escapeHtml(message)}</span>
                <button class="toast-close">&times;</button>
            </div>
        `;
        
        // Add close functionality
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            toast.remove();
        });
        
        toastContainer.appendChild(toast);
        
        // Animate toast in
        setTimeout(() => {
            toast.classList.add('toast-show');
        }, 100);
        
        // Auto-remove after delay (unless persistent)
        if (!persistent) {
            const delay = type === 'error' ? 8000 : type === 'warning' ? 6000 : 4000;
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.classList.add('toast-hide');
                    setTimeout(() => {
                        if (toast.parentNode) {
                            toast.remove();
                        }
                    }, 300);
                }
            }, delay);
        }
    }
    
    clearToasts() {
        const toastContainer = document.getElementById('toastContainer');
        if (toastContainer) {
            toastContainer.innerHTML = '';
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the game client when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const gameClient = new LLMposterGameClient();
    
    // Expose globally for debugging
    window.gameClient = gameClient;
});