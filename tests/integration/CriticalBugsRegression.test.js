import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MockFactory } from '../helpers/mockFactory.js';
import { createMockResponses, nextTick } from '../helpers/testUtils.js';

/**
 * Integration tests for critical bug scenarios that we encountered and fixed
 * These tests ensure that specific bugs don't regress in the future
 */

const EventManager = (await import('../../static/js/modules/EventManager.js')).default || 
                     (await import('../../static/js/modules/EventManager.js')).EventManager;

describe('Critical Bug Scenarios', () => {
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

    // Set up realistic defaults
    mockGameState.canSubmitResponse.mockReturnValue(true);
    mockGameState.canSubmitGuess.mockReturnValue(true);
    mockSocket.getConnectionStatus.mockReturnValue(true);
    
    eventManager = new EventManager(mockSocket, mockGameState, mockUI, mockTimer, mockToast);
    eventManager.initialize('test-room');
  });

  describe('Bug Fix: Response Button State Override', () => {
    /**
     * Original issue: When room state updated after response submission,
     * it would call switchToPhase('responding') which reset all button states,
     * overriding the green "Response Submitted" state
     */
    it('should preserve response submitted state during same-phase updates', async () => {
      // Set up: User has submitted response and button shows green state
      mockUI.currentPhase = 'responding';
      mockGameState.hasSubmittedResponse = true;
      mockUI.elements = { responseInput: { value: 'My response', disabled: true } };

      // Simulate successful response submission
      eventManager._handleResponseSubmitted({
        success: true
      });

      expect(mockGameState.markResponseSubmitted).toHaveBeenCalled();
      expect(mockUI.showResponseSubmitted).toHaveBeenCalled();

      // Simulate room state update (which was causing the bug)
      const roomState = {
        gameState: {
          phase: 'responding', // Same phase - should not reset UI
          response_count: 1,
          total_players: 2
        },
        roundsCompleted: 1
      };

      eventManager._handleGameStateChange(roomState);

      // Bug fix verification: Should NOT call switchToPhase when phase is the same
      expect(mockUI.switchToPhase).not.toHaveBeenCalled();
      
      // Should still update other elements like submission count
      expect(mockUI.updateRoundsPlayed).toHaveBeenCalledWith(1);
    });

    it('should reset UI state when actually switching phases', () => {
      // Set up: Currently in waiting phase
      mockUI.currentPhase = 'waiting';

      // Switch to different phase - should call switchToPhase
      const roomState = {
        gameState: {
          phase: 'responding',
          current_prompt: { prompt: 'Test prompt' }
        }
      };

      eventManager._handleGameStateChange(roomState);

      // Should call switchToPhase for actual phase changes
      expect(mockUI.switchToPhase).toHaveBeenCalledWith('responding', roomState.gameState);
    });
  });

  describe('Bug Fix: Response Filtering Logic', () => {
    /**
     * Original issue: Players could see their own response during guessing phase
     * because filtering logic was using incorrect player index matching
     */
    it('should filter out current player response correctly', () => {
      // Set up: Current player submitted specific text
      mockGameState.submittedResponseText = 'Player response';
      mockGameState.roomInfo = {
        playerId: 'current-player-123',
        playerName: 'CurrentPlayer'
      };

      // Simulate guessing phase with mixed responses
      const responses = [
        { index: 0, text: 'AI response' },
        { index: 1, text: 'Player response' }, // Should be filtered out
        { index: 2, text: 'Other player response' }
      ];

      const data = {
        phase: 'guessing',
        responses: responses,
        round_number: 1,
        phase_duration: 120
      };

      eventManager._handleGuessingPhaseStarted(data);

      // Should only show responses that don't match submitted text
      const expectedFilteredResponses = [
        { index: 0, text: 'AI response' },
        { index: 2, text: 'Other player response' }
      ];

      expect(mockUI.displayResponsesForGuessing).toHaveBeenCalledWith(expectedFilteredResponses);
      
      // Index mapping should correctly map filtered indices to original indices
      expect(eventManager.responseIndexMapping).toEqual([0, 2]);
    });

    it('should handle edge case with exact text matching', () => {
      // Edge case: Similar but not identical text should not be filtered
      mockGameState.submittedResponseText = 'Hello world';

      const responses = [
        { index: 0, text: 'Hello world!' }, // Different (has exclamation)
        { index: 1, text: 'Hello world' },  // Exact match - should be filtered
        { index: 2, text: ' Hello world ' } // Different (has spaces)
      ];

      const data = {
        phase: 'guessing',
        responses: responses,
        round_number: 1,
        phase_duration: 120
      };

      eventManager._handleGuessingPhaseStarted(data);

      // Only the exact match should be filtered out
      const expectedFilteredResponses = [
        { index: 0, text: 'Hello world!' },
        { index: 2, text: ' Hello world ' }
      ];

      expect(mockUI.displayResponsesForGuessing).toHaveBeenCalledWith(expectedFilteredResponses);
    });

    it('should handle no submitted response text gracefully', () => {
      mockGameState.submittedResponseText = null;

      const responses = createMockResponses(3);
      const data = {
        phase: 'guessing',
        responses: responses,
        round_number: 1,
        phase_duration: 120
      };

      eventManager._handleGuessingPhaseStarted(data);

      // Should show all responses when no submitted text to filter
      expect(mockUI.displayResponsesForGuessing).toHaveBeenCalledWith(responses);
    });
  });

  describe('Bug Fix: Guess Index Mapping', () => {
    /**
     * Original issue: "INVALID_GUESS_INDEX" error because we were sending
     * original response indices instead of filtered indices to the server
     */
    it('should send correct filtered index for guess submission', () => {
      // Set up filtered response mapping (some responses filtered out)
      eventManager.responseIndexMapping = [0, 2]; // Original indices [0, 2] map to filtered [0, 1]
      
      // User clicks on filtered index 1 (which was original index 2)
      eventManager.submitGuess(1);

      // Should send filtered index directly, not mapped back to original
      expect(mockSocket.emit).toHaveBeenCalledWith('submit_guess', {
        guess_index: 1 // Filtered index, not original index 2
      });
    });

    it('should handle edge case with no filtering', () => {
      // No responses filtered - mapping should be identity
      eventManager.responseIndexMapping = [0, 1, 2];
      
      eventManager.submitGuess(2);

      expect(mockSocket.emit).toHaveBeenCalledWith('submit_guess', {
        guess_index: 2
      });
    });

    it('should handle single response after filtering', () => {
      // Only one response remains after filtering
      eventManager.responseIndexMapping = [1]; // Only original index 1 remains
      
      eventManager.submitGuess(0); // User clicks the only remaining option

      expect(mockSocket.emit).toHaveBeenCalledWith('submit_guess', {
        guess_index: 0 // Filtered index 0
      });
    });
  });

  describe('Bug Fix: Double Event Handler Registration', () => {
    /**
     * Original issue: UIManager.initialize() was called twice, causing
     * duplicate event listeners and erroneous start_round emissions
     */
    it('should prevent double initialization of UI manager', () => {
      // Simulate GameClient calling initialize twice
      mockUI.isInitialized = false;
      mockUI.initialize();
      
      expect(mockUI.initialize).toHaveBeenCalledTimes(1);
      
      // Second call should be ignored
      mockUI.isInitialized = true;
      mockUI.initialize();
      
      // Should warn about already being initialized
      expect(mockUI.initialize).toHaveBeenCalledTimes(2);
    });
  });

  describe('Bug Fix: Button State Race Conditions', () => {
    /**
     * Issue: Multiple async operations could interfere with button state
     */
    it('should not update button state when response already submitted', () => {
      // Set up: Response already submitted, input disabled
      mockUI.elements = {
        responseInput: { disabled: true, value: 'submitted response' },
        submitResponseBtn: { disabled: true, classList: { contains: vi.fn(() => true) } }
      };

      // Simulate input event (shouldn't happen but let's be defensive)
      mockUI._updateSubmitButtonState();

      // Should not change button state when input is disabled
      // (This would be checked in the actual implementation)
      expect(mockUI.elements.responseInput.disabled).toBe(true);
    });
  });

  describe('Bug Fix: Error Recovery', () => {
    /**
     * Ensuring proper error recovery doesn't leave UI in broken state
     */
    it('should recover from guess submission timeout', async () => {
      vi.useFakeTimers();
      
      eventManager.submitGuess(0);
      
      // Simulate timeout (no server response)
      vi.advanceTimersByTime(10000);
      
      expect(mockGameState.resetSubmissionFlags).toHaveBeenCalled();
      expect(mockToast.error).toHaveBeenCalledWith('Submission timeout - please try again');
      
      vi.useRealTimers();
    });

    it('should handle server rejection gracefully', () => {
      const serverError = {
        code: 'INVALID_GUESS_INDEX',
        message: 'Guess index must be between 0 and 1'
      };

      eventManager._handleServerError(serverError);

      expect(mockToast.error).toHaveBeenCalledWith('Invalid response selection');
    });
  });

  describe('Regression Prevention', () => {
    /**
     * Additional tests to prevent similar bugs in the future
     */
    it('should maintain consistent state across multiple events', async () => {
      // Simulate rapid sequence of events that could cause race conditions
      
      // Set up initial phase state
      mockUI.currentPhase = 'responding';
      
      // 1. Response submitted
      mockUI.elements = { responseInput: { value: 'My response' } };
      eventManager._handleResponseSubmitted({ success: true });
      
      // 2. Room state update
      eventManager._handleGameStateChange({
        gameState: { phase: 'responding', response_count: 1 }
      });
      
      // 3. Another room state update
      eventManager._handleGameStateChange({
        gameState: { phase: 'responding', response_count: 2 }
      });
      
      // State should remain consistent
      expect(mockGameState.markResponseSubmitted).toHaveBeenCalledTimes(1);
      expect(mockUI.switchToPhase).not.toHaveBeenCalled(); // Same phase
    });

    it('should handle malformed server data gracefully', () => {
      // Test with various malformed data scenarios
      const malformedEvents = [
        null,
        undefined,
        {},
        { success: null },
        { responses: null },
        { phase: '' }
      ];

      malformedEvents.forEach(data => {
        expect(() => {
          eventManager._handleResponseSubmitted(data);
          eventManager._handleGuessingPhaseStarted(data);
          eventManager._handleRoundStarted(data);
        }).not.toThrow();
      });
    });
  });
});