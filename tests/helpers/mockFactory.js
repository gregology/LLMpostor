import { vi } from 'vitest';

/**
 * Mock factory for creating test doubles of our modules
 */

export class MockFactory {
  
  /**
   * Create a mock SocketManager
   */
  static createSocketManager() {
    return {
      socket: null,
      connectionStatus: false,
      reconnectAttempts: 0,
      maxReconnectAttempts: 5,
      reconnectDelay: 1000,
      
      // Callbacks
      onConnect: null,
      onDisconnect: null,
      onConnectionError: null,
      onReconnect: null,
      
      // Methods
      initialize: vi.fn(),
      emit: vi.fn(),
      on: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
      getConnectionStatus: vi.fn(() => true),
      _setupEventHandlers: vi.fn(),
      _handleConnect: vi.fn(),
      _handleDisconnect: vi.fn(),
      _handleConnectionError: vi.fn(),
      _attemptReconnect: vi.fn()
    };
  }
  
  /**
   * Create a mock GameStateManager
   */
  static createGameStateManager() {
    return {
      gameState: null,
      players: [],
      roomInfo: {
        roomId: null,
        playerId: null,
        playerName: null,
        connectedCount: 0,
        totalCount: 0
      },
      roundsCompleted: 0,
      hasSubmittedResponse: false,
      hasSubmittedGuess: false,
      submittedResponseText: null,
      
      // Callbacks
      onStateChange: null,
      onPlayersUpdate: null,
      onRoomInfoUpdate: null,
      
      // Methods
      initialize: vi.fn(),
      updateGameState: vi.fn(),
      updateAfterRoomJoin: vi.fn(),
      updatePlayers: vi.fn(),
      updatePlayerCount: vi.fn(),
      updateRoomState: vi.fn(),
      markResponseSubmitted: vi.fn(),
      markGuessSubmitted: vi.fn(),
      resetSubmissionFlags: vi.fn(),
      canSubmitResponse: vi.fn(() => true),
      canSubmitGuess: vi.fn(() => true),
      canStartRound: vi.fn(() => true),
      getState: vi.fn(() => ({})),
      getPlayer: vi.fn(() => null),
      getCurrentPlayer: vi.fn(() => null),
      _notifyStateChange: vi.fn(),
      _notifyPlayersUpdate: vi.fn(),
      _notifyRoomInfoUpdate: vi.fn()
    };
  }
  
  /**
   * Create a mock UIManager
   */
  static createUIManager() {
    return {
      elements: {},
      maxResponseLength: 500,
      currentPhase: null,
      isInitialized: false,
      
      // Callbacks
      onSubmitResponse: null,
      onSubmitGuess: null,
      onStartRound: null,
      onLeaveRoom: null,
      onShareRoom: null,
      
      // Methods
      initialize: vi.fn(),
      updateConnectionStatus: vi.fn(),
      updateRoomInfo: vi.fn(),
      updatePlayersList: vi.fn(),
      updateRoundsPlayed: vi.fn(),
      switchToPhase: vi.fn(),
      updatePromptDisplay: vi.fn(),
      updateTimer: vi.fn(),
      flashTimer: vi.fn(),
      updateSubmissionCount: vi.fn(),
      updateGuessCount: vi.fn(),
      showResponseSubmitted: vi.fn(),
      showGuessSubmitted: vi.fn(),
      displayResponsesForGuessing: vi.fn(),
      displayRoundResults: vi.fn(),
      _cacheElements: vi.fn(),
      _setupEventListeners: vi.fn(),
      _hideAllGameStates: vi.fn(),
      _showWaitingState: vi.fn(),
      _showResponseState: vi.fn(),
      _showGuessingState: vi.fn(),
      _showResultsState: vi.fn(),
      _setButtonState: vi.fn(),
      _updateSubmitButtonState: vi.fn(),
      _escapeHtml: vi.fn(text => text)
    };
  }
  
  /**
   * Create a mock TimerManager
   */
  static createTimerManager() {
    return {
      activeTimers: new Map(),
      
      // Callbacks
      onTimerUpdate: null,
      onTimerWarning: null,
      
      // Methods
      startTimer: vi.fn(),
      updateTimer: vi.fn(),
      clearTimer: vi.fn(),
      clearAllTimers: vi.fn(),
      getActiveTimers: vi.fn(() => []),
      _formatTime: vi.fn(),
      _calculateProgress: vi.fn(() => 50),
      _getProgressColor: vi.fn(() => '#10b981'),
      _triggerWarning: vi.fn()
    };
  }
  
  /**
   * Create a mock ToastManager
   */
  static createToastManager() {
    return {
      container: null,
      toasts: [],
      
      // Methods
      initialize: vi.fn(),
      show: vi.fn(),
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
      clearAll: vi.fn(),
      getActiveCount: vi.fn(() => 0),
      _createToast: vi.fn(),
      _removeToast: vi.fn(),
      _createContainer: vi.fn(),
      _escapeHtml: vi.fn(text => text)
    };
  }
  
  /**
   * Create a mock EventManager with all dependencies
   */
  static createEventManager() {
    const socket = MockFactory.createSocketManager();
    const gameState = MockFactory.createGameStateManager();
    const ui = MockFactory.createUIManager();
    const timer = MockFactory.createTimerManager();
    const toast = MockFactory.createToastManager();
    
    return {
      socket,
      gameState,
      ui,
      timer,
      toast,
      
      isInitialized: false,
      guessSubmissionTimeout: null,
      responseIndexMapping: null,
      
      // Methods
      initialize: vi.fn(),
      autoJoinRoom: vi.fn(),
      joinRoom: vi.fn(),
      leaveRoom: vi.fn(),
      startRound: vi.fn(),
      submitResponse: vi.fn(),
      submitGuess: vi.fn(),
      shareRoom: vi.fn(),
      _setupSocketCallbacks: vi.fn(),
      _setupUICallbacks: vi.fn(),
      _setupGameStateCallbacks: vi.fn(),
      _setupTimerCallbacks: vi.fn(),
      _registerSocketEvents: vi.fn(),
      _handleRoomJoined: vi.fn(),
      _handleResponseSubmitted: vi.fn(),
      _handleGuessingPhaseStarted: vi.fn(),
      _handleGuessSubmitted: vi.fn()
    };
  }
}