import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MockFactory } from '../helpers/mockFactory.js';
import { createMockGameState, createMockPlayer, createMockRoomData, createMockResponses, nextTick } from '../helpers/testUtils.js';

// Import EventManager
const EventManager = (await import('../../static/js/modules/EventManager.js')).default || 
                     (await import('../../static/js/modules/EventManager.js')).EventManager;

describe('EventManager', () => {
  let eventManager;
  let mockSocket;
  let mockGameState;
  let mockUI;
  let mockTimer;
  let mockToast;

  beforeEach(() => {
    // Create mock dependencies
    mockSocket = MockFactory.createSocketManager();
    mockGameState = MockFactory.createGameStateManager();
    mockUI = MockFactory.createUIManager();
    mockTimer = MockFactory.createTimerManager();
    mockToast = MockFactory.createToastManager();

    // Set up default return values
    mockGameState.canSubmitResponse.mockReturnValue(true);
    mockGameState.canSubmitGuess.mockReturnValue(true);
    mockGameState.canStartRound.mockReturnValue(true);
    mockSocket.getConnectionStatus.mockReturnValue(true);

    eventManager = new EventManager(mockSocket, mockGameState, mockUI, mockTimer, mockToast);
  });

  describe('Counters initialization and updates', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
      // Set up totals so EventManager can compute total players
      eventManager.gameState.roomInfo = { totalCount: 2, connectedCount: 2 };
      eventManager.gameState.players = [createMockPlayer(), createMockPlayer({ player_id: 'p2' })];
    });

    it('initializes submission counter to 0/total on round start', () => {
      const data = {
        id: 'prompt_001',
        prompt: 'Test prompt',
        model: 'GPT-4',
        round_number: 1,
        phase_duration: 180
      };

      eventManager._handleRoundStarted(data);

      expect(mockUI.updateSubmissionCount).toHaveBeenCalledWith(0, 2);
    });

    it('prefers server response_count during responding state updates', () => {
      const state = {
        gameState: createMockGameState({ phase: 'responding', response_count: 1 }),
        roomInfo: { totalCount: 2, connectedCount: 2 },
        players: [createMockPlayer(), createMockPlayer({ player_id: 'p2' })],
        hasSubmittedResponse: false,
        roundsCompleted: 0
      };

      // Ensure a phase change occurs
      mockUI.currentPhase = 'waiting';
      eventManager._handleGameStateChange(state);

      expect(mockUI.updateSubmissionCount).toHaveBeenCalledWith(1, 2);
    });

    it('falls back to local hasSubmittedResponse when server response_count is absent', () => {
      const state = {
        gameState: createMockGameState({ phase: 'responding' }), // default includes response_count: 0
        roomInfo: { totalCount: 2, connectedCount: 2 },
        players: [createMockPlayer(), createMockPlayer({ player_id: 'p2' })],
        hasSubmittedResponse: true,
        roundsCompleted: 0
      };

      mockUI.currentPhase = 'waiting';
      // Simulate absence of server-provided count
      delete state.gameState.response_count;
      eventManager._handleGameStateChange(state);

      expect(mockUI.updateSubmissionCount).toHaveBeenCalledWith(1, 2);
    });

    it('initializes guess counter to 0/total on guessing phase start', () => {
      // No guess submitted yet
      eventManager.gameState.hasSubmittedGuess = false;

      const responses = createMockResponses(2);
      const data = {
        phase: 'guessing',
        responses,
        round_number: 1,
        phase_duration: 120
      };

      eventManager._handleGuessingPhaseStarted(data);

      expect(mockUI.updateGuessCount).toHaveBeenCalledWith(0, 2);
    });

    it('prefers server guess_count during guessing state updates', () => {
      const state = {
        gameState: createMockGameState({ phase: 'guessing', guess_count: 1 }),
        roomInfo: { totalCount: 2, connectedCount: 2 },
        players: [createMockPlayer(), createMockPlayer({ player_id: 'p2' })],
        hasSubmittedGuess: false,
        roundsCompleted: 0
      };

      mockUI.currentPhase = 'responding';
      eventManager._handleGameStateChange(state);

      expect(mockUI.updateGuessCount).toHaveBeenCalledWith(1, 2);
    });

    it('falls back to local hasSubmittedGuess when server guess_count is absent', () => {
      const state = {
        gameState: createMockGameState({ phase: 'guessing' }), // default includes guess_count: 0
        roomInfo: { totalCount: 2, connectedCount: 2 },
        players: [createMockPlayer(), createMockPlayer({ player_id: 'p2' })],
        hasSubmittedGuess: true,
        roundsCompleted: 0
      };

      mockUI.currentPhase = 'responding';
      // Simulate absence of server-provided count
      delete state.gameState.guess_count;
      eventManager._handleGameStateChange(state);

      expect(mockUI.updateGuessCount).toHaveBeenCalledWith(1, 2);
    });
  });

  describe('Initialization', () => {
    it('should initialize with default state', () => {
      expect(eventManager.isInitialized).toBe(false);
      expect(eventManager.guessSubmissionTimeout).toBe(null);
      expect(eventManager.responseIndexMapping).toBe(null);
    });

    it('should initialize socket and game state', () => {
      eventManager.initialize('test-room');

      expect(mockGameState.initialize).toHaveBeenCalledWith('test-room');
      expect(mockSocket.initialize).toHaveBeenCalled();
      expect(eventManager.isInitialized).toBe(true);
    });
  });

  describe('Room Management', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
    });

    it('should join room with player name', () => {
      eventManager.joinRoom('room-123', 'PlayerName');

      expect(mockSocket.emit).toHaveBeenCalledWith('join_room', {
        room_id: 'room-123',
        player_name: 'PlayerName'
      });
    });

    it('should handle join room error', () => {
      mockSocket.emit.mockImplementation(() => {
        throw new Error('Socket error');
      });

      eventManager.joinRoom('room-123', 'PlayerName');

      expect(mockToast.error).toHaveBeenCalledWith('Failed to connect to server');
    });

    it('should leave room with confirmation', () => {
      global.confirm = vi.fn(() => true);

      eventManager.leaveRoom();

      expect(mockSocket.emit).toHaveBeenCalledWith('leave_room');
    });

    it('should not leave room without confirmation', () => {
      global.confirm = vi.fn(() => false);

      eventManager.leaveRoom();

      expect(mockSocket.emit).not.toHaveBeenCalled();
    });

    it('should auto-join room when connected', () => {
      global.sessionStorage.getItem = vi.fn(() => 'StoredPlayerName');

      eventManager.autoJoinRoom('test-room');

      expect(mockSocket.emit).toHaveBeenCalledWith('join_room', {
        room_id: 'test-room',
        player_name: 'StoredPlayerName'
      });
    });

    it('should prompt for name if not stored', () => {
      global.sessionStorage.getItem = vi.fn(() => null);
      global.prompt = vi.fn(() => 'PromptedName');
      global.sessionStorage.setItem = vi.fn();

      eventManager.autoJoinRoom('test-room');

      expect(global.prompt).toHaveBeenCalledWith('Enter your display name:');
      expect(global.sessionStorage.setItem).toHaveBeenCalledWith('playerName', 'PromptedName');
      expect(mockSocket.emit).toHaveBeenCalledWith('join_room', {
        room_id: 'test-room',
        player_name: 'PromptedName'
      });
    });
  });

  describe('Game Actions', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
    });

    it('should start round when allowed', () => {
      eventManager.startRound();

      expect(mockSocket.emit).toHaveBeenCalledWith('start_round');
    });

    it('should not start round when not allowed', () => {
      mockGameState.canStartRound.mockReturnValue(false);

      eventManager.startRound();

      expect(mockSocket.emit).not.toHaveBeenCalled();
      expect(mockToast.warning).toHaveBeenCalledWith('Cannot start round at this time');
    });

    it('should submit valid response', () => {
      mockUI.elements = { responseInput: { value: 'Valid response' } };

      eventManager.submitResponse('Valid response');

      expect(mockSocket.emit).toHaveBeenCalledWith('submit_response', {
        response: 'Valid response'
      });
    });

    it('should reject empty response', () => {
      eventManager.submitResponse('');

      expect(mockSocket.emit).not.toHaveBeenCalled();
      expect(mockToast.warning).toHaveBeenCalledWith('Please enter a response');
    });

    it('should reject response that is too long', () => {
      mockUI.maxResponseLength = 100;
      const longResponse = 'x'.repeat(101);

      eventManager.submitResponse(longResponse);

      expect(mockSocket.emit).not.toHaveBeenCalled();
      expect(mockToast.warning).toHaveBeenCalledWith('Response is too long (max 100 characters)');
    });

    it('should not submit response when not allowed', () => {
      mockGameState.canSubmitResponse.mockReturnValue(false);

      eventManager.submitResponse('Valid response');

      expect(mockSocket.emit).not.toHaveBeenCalled();
      expect(mockToast.warning).toHaveBeenCalledWith('Cannot submit response right now');
    });
  });

  describe('Response Filtering', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
      
      // Set up player info for filtering
      mockGameState.roomInfo = {
        playerId: 'current-player-123',
        playerName: 'CurrentPlayer'
      };
      
      // Set up submitted response text
      mockGameState.submittedResponseText = 'My submitted response';
    });

    it('should filter out current player response during guessing phase', () => {
      const responses = [
        { index: 0, text: 'Other player response' },
        { index: 1, text: 'My submitted response' }, // Should be filtered out
        { index: 2, text: 'AI response' }
      ];

      const data = {
        phase: 'guessing',
        responses: responses,
        round_number: 1,
        phase_duration: 120
      };

      eventManager._handleGuessingPhaseStarted(data);

      // Should only display 2 responses (filtered out the current player's)
      expect(mockUI.displayResponsesForGuessing).toHaveBeenCalledWith([
        { index: 0, text: 'Other player response' },
        { index: 2, text: 'AI response' }
      ]);

      // Should set correct index mapping
      expect(eventManager.responseIndexMapping).toEqual([0, 2]);
    });

    it('should handle no submitted response text', () => {
      mockGameState.submittedResponseText = null;

      const responses = createMockResponses(3);
      const data = {
        phase: 'guessing',
        responses: responses,
        round_number: 1,
        phase_duration: 120
      };

      eventManager._handleGuessingPhaseStarted(data);

      // Should display all responses when no submitted text to filter
      expect(mockUI.displayResponsesForGuessing).toHaveBeenCalledWith(responses);
    });

    it('should handle empty responses array', () => {
      const data = {
        phase: 'guessing',
        responses: [],
        round_number: 1,
        phase_duration: 120
      };

      eventManager._handleGuessingPhaseStarted(data);

      expect(mockUI.displayResponsesForGuessing).toHaveBeenCalledWith([]);
      expect(eventManager.responseIndexMapping).toEqual([]);
    });
  });

  describe('Guess Submission', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
      eventManager.responseIndexMapping = [0, 2]; // Filtered mapping
    });

    it('should submit guess with filtered index', () => {
      eventManager.submitGuess(1); // Filtered index 1

      expect(mockSocket.emit).toHaveBeenCalledWith('submit_guess', {
        guess_index: 1 // Should use filtered index directly
      });
      
      expect(mockGameState.markGuessSubmitted).toHaveBeenCalled();
    });

    it('should not submit guess when not allowed', () => {
      mockGameState.canSubmitGuess.mockReturnValue(false);

      eventManager.submitGuess(0);

      expect(mockSocket.emit).not.toHaveBeenCalled();
      expect(mockToast.warning).toHaveBeenCalledWith('Cannot submit guess right now');
    });

    it('should not submit guess if already submitted', () => {
      mockGameState.hasSubmittedGuess = true;

      eventManager.submitGuess(0);

      expect(mockSocket.emit).not.toHaveBeenCalled();
    });

    it('should handle guess submission error', () => {
      mockSocket.emit.mockImplementation(() => {
        throw new Error('Network error');
      });

      eventManager.submitGuess(0);

      expect(mockToast.error).toHaveBeenCalledWith('Failed to submit guess');
      expect(mockGameState.resetSubmissionFlags).toHaveBeenCalled();
    });

    it('should set timeout for guess submission', () => {
      vi.useFakeTimers();

      eventManager.submitGuess(0);

      expect(eventManager.guessSubmissionTimeout).toBeDefined();

      // Fast forward time to trigger timeout
      vi.advanceTimersByTime(10000);

      expect(mockToast.error).toHaveBeenCalledWith('Submission timeout - please try again');
      expect(mockGameState.resetSubmissionFlags).toHaveBeenCalled();

      vi.useRealTimers();
    });
  });

  describe('Event Handling', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
    });

    it('should handle room joined event', () => {
      const roomData = {
        success: true,
        data: createMockRoomData({
          room_id: 'joined-room',
          player_id: 'player-123'
        })
      };

      eventManager._handleRoomJoined(roomData);

      expect(mockGameState.updateAfterRoomJoin).toHaveBeenCalledWith(roomData.data);
      expect(mockToast.success).toHaveBeenCalledWith('Joined room joined-room');
    });

    it('should handle response submitted event - success', () => {
      mockUI.elements = {
        responseInput: { value: '  My response  ' }
      };

      const data = { success: true };

      eventManager._handleResponseSubmitted(data);

      expect(mockGameState.markResponseSubmitted).toHaveBeenCalledWith('My response');
      expect(mockUI.showResponseSubmitted).toHaveBeenCalled();
    });

    it('should handle response submitted event - broadcast', () => {
      const data = {
        response_count: 2,
        total_players: 3,
        time_remaining: 120
      };

      eventManager._handleResponseSubmitted(data);

      expect(mockUI.updateSubmissionCount).toHaveBeenCalledWith(2, 3);
    });

    it('should handle round started event', () => {
      const data = {
        id: 'prompt_001',
        prompt: 'Test prompt',
        model: 'GPT-4',
        round_number: 1,
        phase_duration: 180
      };

      eventManager._handleRoundStarted(data);

      expect(mockToast.info).toHaveBeenCalledWith('Round 1 started!');
      expect(mockUI.updatePromptDisplay).toHaveBeenCalledWith(data);
      expect(mockUI.switchToPhase).toHaveBeenCalledWith('responding', data);
      expect(mockTimer.startTimer).toHaveBeenCalledWith('response', 180);
    });

    it('should ignore success-only round started events', () => {
      const data = { success: true, data: {} };

      eventManager._handleRoundStarted(data);

      expect(mockToast.info).not.toHaveBeenCalled();
    });

    it('should handle guess submitted event - success', () => {
      const data = {
        success: true,
        data: {
          guess_index: 1,
          message: 'Guess submitted!'
        }
      };

      eventManager._handleGuessSubmitted(data);

      expect(mockUI.showGuessSubmitted).toHaveBeenCalledWith(1);
      expect(mockToast.success).toHaveBeenCalledWith('Guess submitted!');
    });

    it('should handle guess submitted event - broadcast', () => {
      const data = {
        guess_count: 2,
        total_players: 3
      };

      eventManager._handleGuessSubmitted(data);

      expect(mockUI.updateGuessCount).toHaveBeenCalledWith(2, 3);
    });
  });

  describe('Phase Management', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
      mockUI.currentPhase = 'waiting';
    });

    it('should switch phases when different', () => {
      const state = {
        gameState: createMockGameState({ phase: 'responding' }),
        roundsCompleted: 1
      };

      eventManager._handleGameStateChange(state);

      expect(mockUI.switchToPhase).toHaveBeenCalledWith('responding', state.gameState);
      expect(mockUI.updateRoundsPlayed).toHaveBeenCalledWith(1);
    });

    it('should not switch phases when same', () => {
      mockUI.currentPhase = 'responding';
      
      const state = {
        gameState: createMockGameState({ phase: 'responding' }),
        roundsCompleted: 1
      };

      eventManager._handleGameStateChange(state);

      expect(mockUI.switchToPhase).not.toHaveBeenCalled();
      expect(mockUI.updateRoundsPlayed).toHaveBeenCalledWith(1);
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
    });

    it('should handle server errors', () => {
      const error = {
        code: 'INVALID_GUESS_INDEX',
        message: 'Guess index must be between 0 and 1',
        details: {}
      };

      eventManager._handleServerError(error);

      expect(mockToast.error).toHaveBeenCalledWith('Invalid response selection');
    });

    it('should handle unknown error codes', () => {
      const error = {
        code: 'UNKNOWN_ERROR',
        message: 'Something went wrong'
      };

      eventManager._handleServerError(error);

      expect(mockToast.error).toHaveBeenCalledWith('Something went wrong');
    });

    it('should handle player name taken error', () => {
      const error = { code: 'PLAYER_NAME_TAKEN' };

      global.prompt = vi.fn(() => 'NewPlayerName');
      global.sessionStorage.setItem = vi.fn();
      mockGameState.roomInfo = { roomId: 'test-room' };

      eventManager._handleSpecificErrors(error);

      expect(global.prompt).toHaveBeenCalledWith('Enter your display name:');
    });

    it('should handle room not found error', () => {
      const error = { code: 'ROOM_NOT_FOUND' };

      eventManager._handleSpecificErrors(error);

      expect(mockToast.error).toHaveBeenCalledWith('Room not found. Redirecting to home...');
    });
  });

  describe('Share Room', () => {
    beforeEach(() => {
      eventManager.initialize('test-room');
      mockGameState.roomInfo = { roomId: 'test-room-123' };
    });

    it('should share room using Web Share API', async () => {
      global.navigator.share = vi.fn(() => Promise.resolve());

      await eventManager.shareRoom();

      expect(global.navigator.share).toHaveBeenCalledWith({
        title: 'Join my LLMpostor game!',
        text: 'Join room "test-room-123" in LLMpostor',
        url: window.location.href
      });
    });

    it('should fallback to clipboard when share fails', async () => {
      global.navigator.share = vi.fn(() => Promise.reject(new Error('Share failed')));
      global.navigator.clipboard.writeText = vi.fn(() => Promise.resolve());

      await eventManager.shareRoom();

      expect(global.navigator.clipboard.writeText).toHaveBeenCalledWith(window.location.href);
    });

    it('should use clipboard when Web Share API not available', async () => {
      global.navigator.share = undefined;
      global.navigator.clipboard.writeText = vi.fn(() => Promise.resolve());

      await eventManager.shareRoom();

      expect(global.navigator.clipboard.writeText).toHaveBeenCalledWith(window.location.href);
    });
  });
});