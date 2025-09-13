/**
 * EventManager - Event-driven coordination and business logic orchestration
 *
 * Responsible for:
 * - Coordinating between event-driven modules via ServiceContainer
 * - Game event handling and routing via EventBus
 * - Error handling and user feedback coordination
 * - Connection management and socket event routing
 * - Business logic orchestration through events
 *
 * Migration Status: Refactored to use ServiceContainer and reduced dependencies
 */

import { EventBusModule, migrationHelper } from './EventBusMigration.js';
import { Events } from './EventBus.js';
import SocketEventDispatcher from './SocketEventDispatcher.js';
import { IServiceModule } from '../interfaces/IModule.js';

class EventManager extends IServiceModule {
    constructor(...args) {
        // Support both old and new constructor signatures for backward compatibility
        if (args.length === 5) {
            // Old signature: (socketManager, gameStateManager, uiManager, timerManager, toastManager)
            const [socketManager, gameStateManager, uiManager, timerManager, toastManager] = args;

            // Create a minimal service container for backward compatibility
            const mockServiceContainer = {
                get: (serviceName) => {
                    switch (serviceName) {
                        case 'SocketManager': return socketManager;
                        case 'GameStateManager': return gameStateManager;
                        case 'UIManager': return uiManager;
                        case 'TimerManager': return timerManager;
                        case 'ToastManager': return toastManager;
                        default: throw new Error(`Service '${serviceName}' not found in mock container`);
                    }
                },
                has: (serviceName) => {
                    return ['SocketManager', 'GameStateManager', 'UIManager', 'TimerManager', 'ToastManager'].includes(serviceName);
                },
                register: () => mockServiceContainer,
                remove: () => {},
                clear: () => {},
                getServiceNames: () => ['SocketManager', 'GameStateManager', 'UIManager', 'TimerManager', 'ToastManager'],
                setConfig: () => mockServiceContainer,
                getConfig: () => undefined,
                checkHealth: () => 'healthy',
                getHealthStatus: () => ({}),
                setDebugMode: () => {}
            };

            // Create a minimal EventBus for backward compatibility
            const eventBus = {
                subscribe: () => () => {}, // Return unsubscribe function
                publish: () => {},
                unsubscribe: () => {},
                once: () => () => {},
                getEventNames: () => [],
                getSubscriberCount: () => 0,
                setDebugMode: () => {},
                clear: () => {}
            };

            super('EventManager', eventBus, mockServiceContainer);

            // Store direct references for old signature
            this._socket = socketManager;
            this._gameState = gameStateManager;
            this._ui = uiManager;
            this._timer = timerManager;
            this._toast = toastManager;

        } else if (args.length === 2) {
            // New signature: (eventBus, serviceContainer)
            const [eventBus, serviceContainer] = args;
            super('EventManager', eventBus, serviceContainer);

            // Lazy-loaded services
            this._socket = null;
            this._gameState = null;
            this._ui = null;
            this._timer = null;
            this._toast = null;
        } else {
            throw new Error('EventManager constructor requires either 5 arguments (old signature) or 2 arguments (new signature)');
        }

        // Connection state
        this.isInitialized = false;

        // Timeout tracking
        this.guessSubmissionTimeout = null;

        // Response filtering
        this.responseIndexMapping = null;

        // Dispatcher will be initialized when socket service is available
        this.dispatcher = null;

        console.log('EventManager initialized with ServiceContainer pattern');
    }

    // Service getters with lazy loading and safety checks
    get socket() {
        if (!this._socket) {
            try {
                this._socket = this.getService('SocketManager');
            } catch (error) {
                console.error('Failed to get SocketManager service:', error);
                return null;
            }
        }
        return this._socket;
    }

    get gameState() {
        if (!this._gameState) {
            try {
                this._gameState = this.getService('GameStateManager');
            } catch (error) {
                console.error('Failed to get GameStateManager service:', error);
                return null;
            }
        }
        return this._gameState;
    }

    get ui() {
        if (!this._ui) {
            try {
                this._ui = this.getService('UIManager');
            } catch (error) {
                console.error('Failed to get UIManager service:', error);
                return null;
            }
        }
        return this._ui;
    }

    get timer() {
        if (!this._timer) {
            try {
                this._timer = this.getService('TimerManager');
            } catch (error) {
                console.error('Failed to get TimerManager service:', error);
                return null;
            }
        }
        return this._timer;
    }

    get toast() {
        if (!this._toast) {
            try {
                this._toast = this.getService('ToastManager');
            } catch (error) {
                console.error('Failed to get ToastManager service:', error);
                return null;
            }
        }
        return this._toast;
    }

    initialize(roomId) {
        if (this.isInitialized) {
            console.warn('EventManager already initialized');
            return;
        }

        super.initialize();

        // Initialize dispatcher now that services are available
        const socket = this.socket;
        if (socket) {
            this.dispatcher = new SocketEventDispatcher(socket);
        } else {
            console.error('EventManager: SocketManager service not available, skipping dispatcher initialization');
        }

        // Subscribe to EventBus events from modules
        this._setupEventBusSubscriptions();

        // Setup callbacks and event handlers
        this._setupSocketCallbacks();
        this._setupGameStateCallbacks();
        this._setupTimerCallbacks();
        this._registerSocketEvents();

        console.log('Initializing EventManager for room:', roomId);

        const gameState = this.gameState;
        if (roomId && gameState) {
            gameState.initialize(roomId);
        }

        if (socket) {
            socket.initialize();
        }
        this.isInitialized = true;
    }

    destroy() {
        // Clear timeouts
        if (this.guessSubmissionTimeout) {
            clearTimeout(this.guessSubmissionTimeout);
            this.guessSubmissionTimeout = null;
        }

        // Cleanup dispatcher
        if (this.dispatcher) {
            this.dispatcher = null;
        }

        // Reset service references
        this._socket = null;
        this._gameState = null;
        this._ui = null;
        this._timer = null;
        this._toast = null;

        this.isInitialized = false;
        super.destroy();
    }
    
    /**
     * Auto-join room when connection is ready
     * @param {string} roomId - Room ID
     */
    autoJoinRoom(roomId) {
        if (!this.socket.getConnectionStatus()) {
            console.error('Cannot join room - not connected to server');
            return;
        }

        const storedName = sessionStorage.getItem('playerName');

        if (storedName) {
            this.joinRoom(roomId, storedName);
        } else {
            this._promptForPlayerName(roomId);
        }
    }
    
    /**
     * Join a room
     * @param {string} roomId - Room ID
     * @param {string} playerName - Player name
     */
    joinRoom(roomId, playerName) {
        try {
            this.socket.emit('join_room', {
                room_id: roomId,
                player_name: playerName
            });
        } catch (error) {
            if (typeof window === 'undefined' || !window.isTestEnvironment) {
                console.error('Failed to join room:', error);
            }
            this.toast.error('Failed to connect to server');
        }
    }
    
    /**
     * Leave current room
     */
    leaveRoom() {
        if (confirm('Are you sure you want to leave the room?')) {
            try {
                // Clear stored session when intentionally leaving room
                if (this.gameStateManager && this.gameStateManager.clearStoredSession) {
                    this.gameStateManager.clearStoredSession();
                }
                this.socket.emit('leave_room');
            } catch (error) {
                console.error('Failed to leave room:', error);
                // Fallback to redirect
                window.location.href = '/';
            }
        }
    }
    
    /**
     * Start a new round
     */
    startRound() {
        if (!this.gameState.canStartRound()) {
            this.toast.warning('Cannot start round at this time');
            return;
        }
        
        try {
            this.socket.emit('start_round');
        } catch (error) {
            console.error('Failed to start round:', error);
            this.toast.error('Failed to start round');
        }
    }
    
    /**
     * Submit player response
     * @param {string} responseText - Player's response text
     */
    submitResponse(responseText) {
        if (!responseText || !responseText.trim()) {
            this.toast.warning('Please enter a response');
            return;
        }
        
        if (responseText.length > this.ui.maxResponseLength) {
            this.toast.warning(`Response is too long (max ${this.ui.maxResponseLength} characters)`);
            return;
        }
        
        if (!this.gameState.canSubmitResponse()) {
            // Don't show warning if already submitted (common race condition)
            if (!this.gameState.hasSubmittedResponse) {
                this.toast.warning('Cannot submit response right now');
            }
            return;
        }
        
        try {
            // Store the response text for filtering later
            const trimmedResponse = responseText.trim();
            
            // Show loading state
            this._setSubmitButtonLoading(true);
            
            this.socket.emit('submit_response', {
                response: trimmedResponse
            });
        } catch (error) {
            console.error('Failed to submit response:', error);
            this.toast.error('Failed to submit response');
            this._setSubmitButtonLoading(false);
        }
    }
    
    /**
     * Submit player guess
     * @param {number} responseIndex - Index of response to guess
     */
    submitGuess(responseIndex) {
        if (!this.gameState.canSubmitGuess()) {
            this.toast.warning('Cannot submit guess right now');
            return;
        }
        
        // Prevent multiple submissions
        if (this.gameState.hasSubmittedGuess) {
            console.log('Guess already submitted, ignoring');
            return;
        }
        
        this.gameState.markGuessSubmitted();
        
        // Immediately disable all guess buttons to prevent double-clicking
        this._disableGuessButtons(responseIndex);
        
        // Use the filtered index directly - server expects indices relative to filtered responses
        const filteredIndex = parseInt(responseIndex, 10);
        
        console.log(`Submitting guess for filtered response ${filteredIndex}`);
        
        // Add timeout to reset state if no response received
        this.guessSubmissionTimeout = setTimeout(() => {
            if (typeof window === 'undefined' || !window.isTestEnvironment) {
                console.error('Guess submission timeout - no response from server');
            }
            this.gameState.resetSubmissionFlags();
            this._enableGuessButtons();
            this.toast.error('Submission timeout - please try again');
        }, 10000);
        
        try {
            this.socket.emit('submit_guess', {
                guess_index: filteredIndex
            });
        } catch (error) {
            if (typeof window === 'undefined' || !window.isTestEnvironment) {
                console.error('Failed to submit guess:', error);
            }
            this.gameState.resetSubmissionFlags();
            this._enableGuessButtons();
            this.toast.error('Failed to submit guess');
            this._clearGuessSubmissionTimeout();
        }
    }
    
    /**
     * Share room via Web Share API or clipboard
     */
    async shareRoom() {
        if (navigator.share) {
            try {
                await navigator.share({
                    title: 'Join my LLMpostor game!',
                    text: `Join room "${this.gameState.roomInfo.roomId}" in LLMpostor`,
                    url: window.location.href
                });
            } catch (err) {
                console.log('Error sharing:', err);
                this._copyUrlToClipboard();
            }
        } else {
            this._copyUrlToClipboard();
        }
    }
    
    // EventBus subscription setup
    
    _setupEventBusSubscriptions() {
        // Subscribe to user action events from UI modules
        this.subscribe(Events.USER.RESPONSE_SUBMITTED, this._handleUserResponseSubmitted.bind(this));
        this.subscribe(Events.USER.GUESS_SUBMITTED, this._handleUserGuessSubmitted.bind(this));
        this.subscribe(Events.USER.ROUND_START, this._handleUserRoundStart.bind(this));
        this.subscribe(Events.USER.ROOM_LEAVE, this._handleUserRoomLeave.bind(this));
        this.subscribe(Events.USER.ROOM_SHARE, this._handleUserRoomShare.bind(this));
        
        // Subscribe to socket events for coordination
        this.subscribe(Events.SOCKET.CONNECTED, this._handleSocketConnectedEvent.bind(this));
        this.subscribe(Events.SOCKET.DISCONNECTED, this._handleSocketDisconnectedEvent.bind(this));
        this.subscribe(Events.SOCKET.ERROR, this._handleSocketErrorEvent.bind(this));
        
        // Subscribe to system events for error handling
        this.subscribe(Events.SYSTEM.ERROR, this._handleSystemError.bind(this));
        this.subscribe(Events.SYSTEM.WARNING, this._handleSystemWarning.bind(this));
    }
    
    // EventBus event handlers
    
    _handleUserResponseSubmitted(data) {
        if (data.response) {
            this.submitResponse(data.response);
        }
    }
    
    _handleUserGuessSubmitted(data) {
        if (typeof data.guessIndex === 'number') {
            this.submitGuess(data.guessIndex);
        }
    }
    
    _handleUserRoundStart(data) {
        this.startRound();
    }
    
    _handleUserRoomLeave(data) {
        this.leaveRoom();
    }
    
    _handleUserRoomShare(data) {
        this.shareRoom();
    }
    
    _handleSocketConnectedEvent(data) {
        console.log('EventManager handling socket connected event:', data);
    }
    
    _handleSocketDisconnectedEvent(data) {
        console.log('EventManager handling socket disconnected event:', data);
    }
    
    _handleSocketErrorEvent(data) {
        console.error('EventManager handling socket error event:', data);
    }
    
    _handleSystemError(data) {
        console.error('System error:', data);
    }
    
    _handleSystemWarning(data) {
        console.warn('System warning:', data);
    }
    
    // Private methods - Socket event handlers
    
    _registerSocketEvents() {
        // Connection events are handled by socket callbacks
        if (!this.dispatcher) {
            console.warn('EventManager: Dispatcher not available, skipping socket event registration');
            return;
        }

        this.dispatcher.register({
            // Room event handlers
            'room_joined': (data) => this._handleRoomJoined(data),
            'room_left': (data) => this._handleRoomLeft(data),
            'player_list_updated': (data) => this._handlePlayerListUpdated(data),
            'room_state_updated': (data) => this._handleRoomStateUpdated(data),
            'room_state': (data) => this._handleRoomState(data),
            
            // Game phase event handlers
            'round_started': (data) => this._handleRoundStarted(data),
            'response_submitted': (data) => this._handleResponseSubmitted(data),
            'guessing_phase_started': (data) => this._handleGuessingPhaseStarted(data),
            'guess_submitted': (data) => this._handleGuessSubmitted(data),
            'results_phase_started': (data) => this._handleResultsPhaseStarted(data),
            
            // Timer and countdown handlers
            'countdown_update': (data) => this._handleCountdownUpdate(data),
            'time_warning': (data) => this._handleTimeWarning(data),
            
            // Game flow handlers
            'game_paused': (data) => this._handleGamePaused(data),
            'round_ended': (data) => this._handleRoundEnded(data),
            
            // Server events
            'server_connected': (data) => this._handleServerConnected(data),
            'server_error': (error) => this._handleServerError(error)
        });
    }
    
    _setupSocketCallbacks() {
        const socket = this.socket;
        if (!socket) {
            console.warn('EventManager: SocketManager not available, skipping socket callbacks setup');
            return;
        }

        socket.onConnect = () => {
            console.log('Connected to server');

            // Publish connection event for other modules to listen to
            this.eventBus.publish('socket:connected', {
                timestamp: Date.now(),
                status: 'connected'
            });

            // Use migration helper for dual-mode operation
            migrationHelper.execute(
                'socket-connected',
                // Old pattern (legacy callback-driven)
                () => {
                    this.ui.updateConnectionStatus('connected', 'Connected');
                    // Don't show toast here - let GameClient handle it
                },
                // New pattern (event-driven)
                () => {
                    this.publish(Events.SOCKET.CONNECTED, {
                        timestamp: Date.now(),
                        status: 'connected'
                    });
                }
            );
        };

        socket.onDisconnect = () => {
            console.log('Disconnected from server');
            
            this.publish(Events.SOCKET.DISCONNECTED, {
                timestamp: Date.now(),
                status: 'disconnected',
                message: 'Connection lost. Attempting to reconnect...'
            });
        };

        socket.onConnectionError = (error) => {
            console.error('Connection error:', error);
            
            this.publish(Events.SOCKET.ERROR, {
                error,
                timestamp: Date.now(),
                status: 'error',
                message: 'Failed to connect to server'
            });
        };

        socket.onReconnect = () => {
            console.log('Reconnected to server');
            
            this.publish(Events.SOCKET.CONNECTED, {
                timestamp: Date.now(),
                status: 'reconnected',
                message: 'Reconnected successfully!'
            });
            
            // Rejoin room if we were in one
            if (this.gameState.roomInfo.roomId && this.gameState.roomInfo.playerName) {
                console.log('Rejoining room after reconnection...');
                this.joinRoom(this.gameState.roomInfo.roomId, this.gameState.roomInfo.playerName);
            }
        };
    }
    
    
    _setupGameStateCallbacks() {
        const gameState = this.gameState;
        if (!gameState) {
            console.warn('EventManager: GameStateManager not available, skipping game state callbacks setup');
            return;
        }

        gameState.onStateChange = (state) => {
            this._handleGameStateChange(state);
        };

        gameState.onPlayersUpdate = (players) => {
            const ui = this.ui;
            if (ui) {
                ui.updatePlayersList(players, gameState.roomInfo.playerId);
            }
        };

        gameState.onRoomInfoUpdate = (roomInfo) => {
            const ui = this.ui;
            if (ui) {
                ui.updateRoomInfo(roomInfo);
            }
        };
    }
    
    _setupTimerCallbacks() {
        const timer = this.timer;
        if (!timer) {
            console.warn('EventManager: TimerManager not available, skipping timer callbacks setup');
            return;
        }

        timer.onTimerUpdate = (timerData) => {
            const ui = this.ui;
            if (ui) {
                ui.updateTimer(timerData);
            }
        };

        timer.onTimerWarning = (warningData) => {
            const ui = this.ui;
            if (ui) {
                ui.flashTimer(warningData.phase);
            }
        };
    }
    
    _handleGameStateChange(state) {
        const phase = state.gameState?.phase;
        
        if (phase) {
            // Only switch phase if it's actually different to avoid resetting UI state
            if (this.ui.currentPhase !== phase) {
                console.log('Phase change detected:', this.ui.currentPhase, '->', phase);
                this.ui.switchToPhase(phase, state.gameState);
            } else {
                console.log('Staying in same phase:', phase, '- not resetting UI');
            }
            
            // Update rounds display
            this.ui.updateRoundsPlayed(state.roundsCompleted);
            
            // Handle phase-specific logic
            switch (phase) {
                case 'responding':
                    if (state.gameState.current_prompt) {
                        this.ui.updatePromptDisplay(state.gameState.current_prompt);
                    }
                    // Initialize submission counter while respecting server-provided counts
                    // Prefer response_count from room_state updates to avoid overwriting broadcast increments
                    {
                        const totalPlayers = state.roomInfo?.totalCount || state.roomInfo?.connectedCount || (Array.isArray(state.players) ? state.players.length : 0) || 0;
                        const serverCount = typeof state.gameState?.response_count === 'number' ? state.gameState.response_count : null;
                        const submittedSoFar = serverCount !== null ? serverCount : (state.hasSubmittedResponse ? 1 : 0);
                        this.ui.updateSubmissionCount(submittedSoFar, totalPlayers);
                    }
                    break;
                case 'guessing':
                    // Initialize guess counter while respecting server-provided counts
                    {
                        const totalPlayers = state.roomInfo?.totalCount || state.roomInfo?.connectedCount || (Array.isArray(state.players) ? state.players.length : 0) || 0;
                        const serverGuessCount = typeof state.gameState?.guess_count === 'number' ? state.gameState.guess_count : null;
                        const guessedSoFar = serverGuessCount !== null ? serverGuessCount : (state.hasSubmittedGuess ? 1 : 0);
                        this.ui.updateGuessCount(guessedSoFar, totalPlayers);
                    }
                    if (state.gameState.responses && !state.hasSubmittedGuess) {
                        // Filter out current player's response based on submitted text
                        const submittedResponseText = this.gameState.submittedResponseText;
                        const filteredResponses = [];
                        const originalIndexMapping = [];
                        
                        state.gameState.responses.forEach((response, originalIndex) => {
                            // Filter based on response text matching what player submitted
                            const isCurrentPlayerResponse = submittedResponseText && 
                                response.text === submittedResponseText;
                            
                            if (!isCurrentPlayerResponse) {
                                filteredResponses.push(response);
                                originalIndexMapping.push(originalIndex);
                            }
                        });
                        
                        // Store the mapping for guess submission
                        this.responseIndexMapping = originalIndexMapping;
                        this.ui.displayResponsesForGuessing(filteredResponses);
                    }
                    break;
            }
        }
    }
    
    _handleServerConnected(data) {
        console.log('Server connection confirmed:', data);
    }
    
    _handleServerError(error) {
        // Don't log ALREADY_IN_ROOM as an error since it's handled gracefully
        if (error?.error?.code !== 'ALREADY_IN_ROOM') {
            if (typeof window === 'undefined' || !window.isTestEnvironment) {
                console.error('Server error:', error);
            }
        }

        const userMessage = this._getUserFriendlyErrorMessage(error);

        // Don't show toast for ALREADY_IN_ROOM since it's handled silently
        if (error?.error?.code !== 'ALREADY_IN_ROOM') {
            this.toast.error(userMessage);
        }
        
        // Handle specific error recovery
        this._handleSpecificErrors(error);
    }
    
    _handleRoomJoined(data) {
        console.log('Joined room:', data);
        // Extract the actual room data from the success wrapper
        const roomData = data.success ? data.data : data;
        this.gameState.updateAfterRoomJoin(roomData);
        this.toast.success(`Joined room ${roomData.room_id}`);
    }
    
    _handleRoomLeft(data) {
        console.log('Left room:', data);
        this.toast.info(data.message);
        
        // Redirect to home page
        setTimeout(() => {
            window.location.href = '/';
        }, 1000);
    }
    
    _handlePlayerListUpdated(data) {
        console.log('Player list updated:', data);
        this.gameState.updatePlayers(data.players);
        this.gameState.updatePlayerCount(data.connected_count, data.total_count);
    }
    
    _handleRoomStateUpdated(data) {
        console.log('Room state updated:', data);
        this.gameState.updateGameState(data);
    }
    
    _handleRoomState(data) {
        console.log('Received room state:', data);
        this.gameState.updateRoomState(data);
    }
    
    _handleRoundStarted(data) {
        console.log('Round started:', data);
        
        if (!data) return;
        
        if (data.success) {
            // Success confirmation, ignore
            return;
        }
        
        if (!data.prompt || !data.phase_duration) {
            console.warn('Invalid round data received:', data);
            return;
        }
        
        this.toast.info(`Round ${data.round_number} started!`);
        this.ui.updatePromptDisplay(data);
        this.ui.switchToPhase('responding', data);
        // Initialize submission counts at the start of the responding phase
        // Prevents showing 0/0 on first round and avoids carrying over previous round's values
        {
            const roomInfo = this.gameState.roomInfo || {};
            const totalPlayers = roomInfo.totalCount || roomInfo.connectedCount || (Array.isArray(this.gameState.players) ? this.gameState.players.length : 0) || 0;
            this.ui.updateSubmissionCount(0, totalPlayers);
        }
        this.timer.startTimer('response', data.phase_duration);
    }
    
    _handleResponseSubmitted(data) {
        console.log('Response submitted:', data);
        
        if (!data) return;
        
        if (data.success) {
            // Get the response text that was submitted
            const submittedText = this.ui.elements.responseInput?.value?.trim();
            this.gameState.markResponseSubmitted(submittedText);
            this._setSubmitButtonLoading(false);
            this.ui.showResponseSubmitted();
            console.log('Button state set to green "Response Submitted"');
            console.log('Stored submitted response text:', submittedText);
        }
        
        if (data.response_count !== undefined && data.total_players !== undefined) {
            this.ui.updateSubmissionCount(data.response_count, data.total_players);
        }
    }
    
    _handleGuessingPhaseStarted(data) {
        console.log('Guessing phase started:', data);
        
        if (!data || !data.responses) return;
        
        console.log('Current player ID:', this.gameState.roomInfo.playerId);
        console.log('Player name:', this.gameState.roomInfo.playerName);
        console.log('All room info:', this.gameState.roomInfo);
        console.log('Responses structure:', data.responses);
        console.log('All players:', this.gameState.players);
        this.toast.info('Time to guess which response is from AI!');
        
        // Filter out current player's response - they should only see other players' + LLM response
        const currentPlayerId = this.gameState.roomInfo.playerId;
        console.log('Current player ID for filtering:', currentPlayerId);
        
        // Get the current player's position in the players list to determine their response index
        const currentPlayer = this.gameState.getCurrentPlayer();
        console.log('Current player object:', currentPlayer);
        
        // Filter out current player's response based on the text they submitted
        const submittedResponseText = this.gameState.submittedResponseText;
        console.log('Current player submitted response text:', submittedResponseText);
        
        const filteredResponses = [];
        const originalIndexMapping = [];
        
        console.log('Total responses in guessing phase:', data.responses.length);
        
        data.responses.forEach((response, originalIndex) => {
            console.log(`Response ${originalIndex}:`, response);
            console.log(`  - Response text: "${response.text}"`);
            
            // Filter out the response that matches what the current player submitted
            const isCurrentPlayerResponse = submittedResponseText && 
                response.text === submittedResponseText;
            
            console.log(`  - Is current player's response: ${isCurrentPlayerResponse}`);
            
            if (!isCurrentPlayerResponse) {
                filteredResponses.push(response);
                originalIndexMapping.push(originalIndex);
                console.log(`  - Including response (index ${response.index})`);
            } else {
                console.log(`  - Filtered out current player's response (index ${response.index})`);
            }
        });
        
        console.log('Responses after filtering:', filteredResponses.map(r => `index ${r.index}: "${r.text.substring(0, 30)}..."`));
        
        // Store the mapping so we can use it when submitting guesses
        this.responseIndexMapping = originalIndexMapping;
        
        console.log('Filtered responses for guessing:', filteredResponses.length, 'out of', data.responses.length);
        console.log('Index mapping:', originalIndexMapping);
        this.ui.displayResponsesForGuessing(filteredResponses);
        this.ui.switchToPhase('guessing', data);
        // Initialize guess counts at the start of the guessing phase
        // Prevents showing 0/0 and avoids carrying over previous round values
        {
            const roomInfo = this.gameState.roomInfo || {};
            const totalPlayers = roomInfo.totalCount || roomInfo.connectedCount || (Array.isArray(this.gameState.players) ? this.gameState.players.length : 0) || 0;
            const guessedSoFar = this.gameState.hasSubmittedGuess ? 1 : 0;
            this.ui.updateGuessCount(guessedSoFar, totalPlayers);
        }
        this.timer.startTimer('guessing', data.phase_duration);
    }
    
    _handleGuessSubmitted(data) {
        console.log('Guess submitted:', data);
        
        // Handle success response (sent only to submitting player)
        if (data.success && data.data) {
            const guessIndex = data.data.guess_index;
            if (typeof guessIndex !== 'undefined') {
                this.ui.showGuessSubmitted(guessIndex);
            }
            this.toast.success(data.data.message || 'Guess submitted successfully!');
            this._clearGuessSubmissionTimeout();
        }
        // Handle broadcast data (sent to all players)
        else if (typeof data.guess_count !== 'undefined' && typeof data.total_players !== 'undefined') {
            this.ui.updateGuessCount(data.guess_count, data.total_players);
        }
    }
    
    _handleResultsPhaseStarted(data) {
        console.log('Results phase started:', data);
        this.toast.success('Round complete! See the results');
        this.ui.displayRoundResults(data);
        this.ui.switchToPhase('results', data);
        this.timer.startTimer('results', data.phase_duration || 30);
    }
    
    _handleCountdownUpdate(data) {
        this.timer.updateTimer(data.phase, data.time_remaining, data.phase_duration);
    }
    
    _handleTimeWarning(data) {
        this.toast.warning(data.message);
        this.ui.flashTimer(data.phase);
    }
    
    _handleGamePaused(data) {
        console.log('Game paused:', data);
        
        let message = 'Game paused';
        if (data.error?.message) {
            message = data.error.message;
        } else if (data.message) {
            message = data.message;
        }
        
        this.toast.warning(message);
        this.ui.switchToPhase('waiting');
    }
    
    _handleRoundEnded(data) {
        console.log('Round ended:', data);
        this.ui.switchToPhase('waiting');
    }
    
    _handleSpecificErrors(error) {
        switch (error.code) {
            case 'PLAYER_NAME_TAKEN':
                this._promptForPlayerName(this.gameState.roomInfo.roomId);
                break;
            case 'ROOM_NOT_FOUND':
                this.toast.error('Room not found. Redirecting to home...');
                setTimeout(() => window.location.href = '/', 2000);
                break;
            case 'ALREADY_IN_ROOM':
                // Request current state
                if (this.gameState.roomInfo.roomId) {
                    try {
                        this.socket.emit('get_room_state');
                    } catch (e) {
                        console.error('Failed to get room state:', e);
                    }
                }
                break;
            case 'SUBMIT_GUESS_FAILED':
                this.gameState.resetSubmissionFlags();
                this._enableGuessButtons();
                this._clearGuessSubmissionTimeout();
                break;
        }
    }
    
    _getUserFriendlyErrorMessage(error) {
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
    
    _promptForPlayerName(roomId) {
        const name = prompt('Enter your display name:');
        if (name && name.trim()) {
            const playerName = name.trim();
            sessionStorage.setItem('playerName', playerName);
            this.joinRoom(roomId, playerName);
        } else {
            // Redirect to home if no name provided
            window.location.href = '/';
        }
    }
    
    _copyUrlToClipboard() {
        navigator.clipboard.writeText(window.location.href).then(() => {
            this.toast.success('Room link copied to clipboard');
        }).catch(err => {
            console.error('Failed to copy URL:', err);
            this.toast.error('Failed to copy room link');
        });
    }
    
    _setSubmitButtonLoading(loading) {
        if (!this.ui.elements.submitResponseBtn) return;
        
        const btnText = this.ui.elements.submitResponseBtn.querySelector('.btn-text');
        const btnLoading = this.ui.elements.submitResponseBtn.querySelector('.btn-loading');
        
        if (loading) {
            btnText?.classList.add('hidden');
            btnLoading?.classList.remove('hidden');
            this.ui.elements.submitResponseBtn.disabled = true;
        } else {
            btnText?.classList.remove('hidden');
            btnLoading?.classList.add('hidden');
            // Let UI manager handle button state
        }
    }
    
    _disableGuessButtons(selectedIndex) {
        const responseCards = this.ui.elements.responsesList?.querySelectorAll('.response-card');
        if (!responseCards) return;
        
        responseCards.forEach((card, index) => {
            const guessBtn = card.querySelector('.guess-btn');
            guessBtn.disabled = true;
            if (index === parseInt(selectedIndex, 10)) {
                guessBtn.textContent = 'Submitting...';
                guessBtn.classList.add('btn-primary');
            } else {
                guessBtn.classList.add('btn-disabled');
            }
        });
    }
    
    _enableGuessButtons() {
        const responseCards = this.ui.elements.responsesList?.querySelectorAll('.response-card');
        if (!responseCards) return;
        
        responseCards.forEach((card) => {
            const guessBtn = card.querySelector('.guess-btn');
            guessBtn.disabled = false;
            guessBtn.textContent = 'Select This Response';
            guessBtn.classList.remove('btn-primary', 'btn-disabled');
            guessBtn.classList.add('btn-outline');
        });
    }
    
    _clearGuessSubmissionTimeout() {
        if (this.guessSubmissionTimeout) {
            clearTimeout(this.guessSubmissionTimeout);
            this.guessSubmissionTimeout = null;
        }
    }
    
    /**
     * Clean up event subscriptions and timeouts
     */
    destroy() {
        // Clear timeouts
        this._clearGuessSubmissionTimeout();

        // Cleanup dispatcher
        if (this.dispatcher) {
            this.dispatcher = null;
        }

        // Reset service references
        this._socket = null;
        this._gameState = null;
        this._ui = null;
        this._timer = null;
        this._toast = null;

        this.isInitialized = false;

        // Call parent destroy
        super.destroy();

        console.log('EventManager destroyed');
    }
}


export default EventManager;