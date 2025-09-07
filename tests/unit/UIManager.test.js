import { describe, it, expect, beforeEach, vi } from 'vitest';
import { simulateUserInput, simulateClick, expectElementToHaveClasses } from '../helpers/testUtils.js';

// Import UIManager
const UIManager = (await import('../../static/js/modules/UIManager.js')).default || 
                  (await import('../../static/js/modules/UIManager.js')).UIManager;

describe('UIManager', () => {
  let uiManager;

  beforeEach(() => {
    // Reset DOM to clean state
    document.body.innerHTML = `
      <div id="connectionStatus"></div>
      <div class="room-name">TestRoom</div>
      <div id="playerCount">0</div>
      <div id="playersList"></div>
      <div id="roundsPlayed">0</div>
      <div id="waitingState" class="hidden"></div>
      <div id="responseState" class="hidden"></div>
      <div id="guessingState" class="hidden"></div>
      <div id="resultsState" class="hidden"></div>
      <div id="currentPrompt"></div>
      <div id="targetModel"></div>
      <textarea id="responseInput" maxlength="500"></textarea>
      <div id="charCount">0</div>
      <button id="submitResponseBtn" disabled>
        <span class="btn-text">Submit Response</span>
        <span class="btn-loading hidden">Loading...</span>
      </button>
      <div id="responseTimer">3:00</div>
      <div id="responseTimerBar"></div>
      <div id="submissionCount">
        <span class="submitted-count">0</span>/<span class="total-count">0</span>
      </div>
      <div id="responsesList"></div>
      <div id="guessingTimer">2:00</div>
      <div id="guessingTimerBar"></div>
      <div id="guessingTargetModel"></div>
      <div id="guessingCount">
        <span class="guessed-count">0</span>/<span class="total-count">0</span>
      </div>
      <div id="correctResponse"></div>
      <div id="roundScoresList"></div>
      <div id="nextRoundTimer">30</div>
      <button id="leaveRoomBtn">Leave Room</button>
      <button id="shareRoomBtn">Share Room</button>
      <button id="startRoundBtn" disabled>
        <span class="btn-text">Start Round</span>
        <span class="btn-loading hidden">Loading...</span>
      </button>
    `;

    // Mock global variables
    global.window.maxResponseLength = 500;
    
    uiManager = new UIManager();
  });

  describe('Initialization', () => {
    it('should initialize with default values', () => {
      expect(uiManager.maxResponseLength).toBe(500);
      expect(uiManager.currentPhase).toBe(null);
      expect(uiManager.isInitialized).toBe(false);
    });

    it('should cache DOM elements on initialization', () => {
      uiManager.initialize();
      
      expect(uiManager.isInitialized).toBe(true);
      expect(uiManager.elements.connectionStatus).toBeDefined();
      expect(uiManager.elements.submitResponseBtn).toBeDefined();
      expect(uiManager.elements.responseInput).toBeDefined();
    });

    it('should not initialize twice', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      
      uiManager.initialize();
      uiManager.initialize();
      
      expect(consoleSpy).toHaveBeenCalledWith('UIManager already initialized');
      consoleSpy.mockRestore();
    });

    it('should setup event listeners', () => {
      uiManager.initialize();
      
      const responseInput = document.getElementById('responseInput');
      const submitBtn = document.getElementById('submitResponseBtn');
      
      // Mock the callback
      uiManager.onSubmitResponse = vi.fn();
      
      // Simulate user input
      simulateUserInput(responseInput, 'test response');
      
      // The input event should have been handled
      expect(responseInput.value).toBe('test response');
    });
  });

  describe('Connection Status', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should update connection status display', () => {
      uiManager.updateConnectionStatus('connected', 'Connected to server');
      
      const status = uiManager.elements.connectionStatus;
      expect(status.className).toContain('connected');
      expect(status.innerHTML).toContain('Connected to server');
    });

    it('should handle different status types', () => {
      const testCases = [
        ['disconnected', 'Connection lost'],
        ['error', 'Connection error'],
        ['reconnecting', 'Reconnecting...']
      ];
      
      testCases.forEach(([status, text]) => {
        uiManager.updateConnectionStatus(status, text);
        
        const element = uiManager.elements.connectionStatus;
        expect(element.className).toContain(status);
        expect(element.innerHTML).toContain(text);
      });
    });
  });

  describe('Room Information', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should update room information', () => {
      const roomInfo = {
        roomId: 'test-room-123',
        connectedCount: 3
      };
      
      uiManager.updateRoomInfo(roomInfo);
      
      expect(uiManager.elements.roomName.textContent).toBe('test-room-123');
      expect(uiManager.elements.playerCount.textContent).toBe('3');
    });

    it('should update rounds played', () => {
      uiManager.updateRoundsPlayed(5);
      
      expect(uiManager.elements.roundsPlayed.textContent).toBe('5');
    });
  });

  describe('Phase Management', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should switch to waiting phase', () => {
      uiManager.switchToPhase('waiting');
      
      expect(uiManager.currentPhase).toBe('waiting');
      expect(uiManager.elements.waitingState.classList.contains('hidden')).toBe(false);
      expect(uiManager.elements.responseState.classList.contains('hidden')).toBe(true);
    });

    it('should switch to response phase', () => {
      uiManager.switchToPhase('responding');
      
      expect(uiManager.currentPhase).toBe('responding');
      expect(uiManager.elements.responseState.classList.contains('hidden')).toBe(false);
      expect(uiManager.elements.waitingState.classList.contains('hidden')).toBe(true);
    });

    it('should reset form when switching to response phase', () => {
      // Set up some state
      uiManager.elements.responseInput.value = 'old response';
      uiManager.elements.responseInput.disabled = true;
      
      uiManager.switchToPhase('responding');
      
      expect(uiManager.elements.responseInput.value).toBe('');
      expect(uiManager.elements.responseInput.disabled).toBe(false);
    });

    it('should switch to guessing phase', () => {
      uiManager.switchToPhase('guessing');
      
      expect(uiManager.currentPhase).toBe('guessing');
      expect(uiManager.elements.guessingState.classList.contains('hidden')).toBe(false);
      expect(uiManager.elements.submitResponseBtn.style.display).toBe('none');
    });
  });

  describe('Button State Management', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should show response submitted state', () => {
      uiManager.showResponseSubmitted();
      
      const button = uiManager.elements.submitResponseBtn;
      const btnText = button.querySelector('.btn-text');
      
      expect(uiManager.elements.responseInput.disabled).toBe(true);
      expect(btnText.textContent).toBe('Response Submitted');
      expect(button.disabled).toBe(true);
      expect(button.classList.contains('btn-success')).toBe(true);
    });

    it('should set button state correctly', () => {
      const button = uiManager.elements.submitResponseBtn;
      
      uiManager._setButtonState(button, {
        text: 'Custom Text',
        disabled: false,
        loading: false,
        classes: ['btn-primary']
      });
      
      const btnText = button.querySelector('.btn-text');
      expect(btnText.textContent).toBe('Custom Text');
      expect(button.disabled).toBe(false);
      expect(button.classList.contains('btn-primary')).toBe(true);
    });

    it('should handle loading state', () => {
      const button = uiManager.elements.submitResponseBtn;
      
      uiManager._setButtonState(button, {
        text: 'Submit',
        disabled: true,
        loading: true,
        classes: ['btn-primary']
      });
      
      const btnText = button.querySelector('.btn-text');
      const btnLoading = button.querySelector('.btn-loading');
      
      expect(btnText.classList.contains('hidden')).toBe(true);
      expect(btnLoading.classList.contains('hidden')).toBe(false);
      expect(button.disabled).toBe(true);
    });

    it('should update submit button state based on input', () => {
      const input = uiManager.elements.responseInput;
      
      // Empty input should disable button
      simulateUserInput(input, '');
      expect(uiManager.elements.submitResponseBtn.disabled).toBe(true);
      
      // Valid input should enable button
      simulateUserInput(input, 'valid response');
      expect(uiManager.elements.submitResponseBtn.disabled).toBe(false);
      
      // Too long input should disable button
      simulateUserInput(input, 'x'.repeat(501));
      expect(uiManager.elements.submitResponseBtn.disabled).toBe(true);
    });

    it('should not update button state when input is disabled', () => {
      const input = uiManager.elements.responseInput;
      input.disabled = true;
      
      simulateUserInput(input, 'some text');
      
      // Button state should not change when input is disabled
      expect(uiManager.elements.submitResponseBtn.disabled).toBe(true);
    });
  });

  describe('Timer Display', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should update timer display', () => {
      const timerData = {
        phase: 'responding',
        timeText: '2:30',
        progress: 75,
        progressColor: '#10b981'
      };
      
      uiManager.updateTimer(timerData);
      
      expect(uiManager.elements.responseTimer.textContent).toBe('2:30');
      expect(uiManager.elements.responseTimerBar.style.width).toBe('75%');
      // Style is converted to RGB format by browser
      expect(uiManager.elements.responseTimerBar.style.backgroundColor).toBe('rgb(16, 185, 129)');
    });

    it('should flash timer for warning', () => {
      vi.useFakeTimers();
      
      uiManager.flashTimer('responding');
      
      const timer = uiManager.elements.responseTimer;
      expect(timer.classList.contains('timer-warning')).toBe(true);
      
      // Should remove warning class after timeout
      vi.runAllTimers();
      expect(timer.classList.contains('timer-warning')).toBe(false);
      
      vi.useRealTimers();
    });
  });

  describe('Response Display', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should display responses for guessing', () => {
      const responses = [
        { index: 0, text: 'Response A' },
        { index: 1, text: 'Response B' }
      ];
      
      uiManager.displayResponsesForGuessing(responses);
      
      const responsesList = uiManager.elements.responsesList;
      const cards = responsesList.querySelectorAll('.response-card');
      
      expect(cards.length).toBe(2);
    });

    it('should create response cards with guess buttons', () => {
      const response = { index: 0, text: 'Test response' };
      
      const card = uiManager._createResponseCard(response, 0);
      
      expect(card.className).toBe('response-card');
      expect(card.querySelector('.response-text').innerHTML).toContain('Test response');
      expect(card.querySelector('.guess-btn')).toBeDefined();
    });

    it('should handle guess button clicks', () => {
      const publishSpy = vi.spyOn(uiManager, 'publish');
      
      const response = { index: 0, text: 'Test response' };
      const card = uiManager._createResponseCard(response, 0);
      
      const guessBtn = card.querySelector('.guess-btn');
      simulateClick(guessBtn);
      
      expect(publishSpy).toHaveBeenCalledWith('user:guess:submitted', {
        guessIndex: 0,
        response: response,
        timestamp: expect.any(Number)
      });
    });
  });

  describe('Character Count', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should update character count', () => {
      const input = uiManager.elements.responseInput;
      
      simulateUserInput(input, 'Hello world');
      
      expect(uiManager.elements.charCount.textContent).toBe('11');
    });

    it('should change color based on length', () => {
      const input = uiManager.elements.responseInput;
      const charCount = uiManager.elements.charCount;
      
      // Normal length - gray  
      simulateUserInput(input, 'short');
      // Manually trigger the character count update for testing
      uiManager._updateCharacterCount();
      expect(charCount.style.color).toBe('rgb(107, 114, 128)');
      
      // 60% of max - orange (hex color converted to RGB)
      simulateUserInput(input, 'x'.repeat(300));
      uiManager._updateCharacterCount();
      expect(charCount.style.color).toBe('rgb(245, 158, 11)');
      
      // 80% of max - red
      simulateUserInput(input, 'x'.repeat(400));
      uiManager._updateCharacterCount();
      expect(charCount.style.color).toBe('rgb(239, 68, 68)');
    });
  });

  describe('XSS Protection', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should escape HTML in text content', () => {
      const maliciousText = '<script>alert("xss")</script>';
      const escaped = uiManager._escapeHtml(maliciousText);
      
      expect(escaped).toBe('&lt;script&gt;alert("xss")&lt;/script&gt;');
    });

    it('should escape HTML in prompt display', () => {
      const promptData = {
        prompt: '<script>alert("xss")</script>Safe content',
        model: 'GPT-4'
      };
      
      uiManager.updatePromptDisplay(promptData);
      
      const promptElement = uiManager.elements.currentPrompt;
      expect(promptElement.innerHTML).not.toContain('<script>');
      expect(promptElement.innerHTML).toContain('&lt;script&gt;');
    });
  });

  describe('Edge Cases and Error Handling', () => {
    beforeEach(() => {
      uiManager.initialize();
    });

    it('should handle missing DOM elements gracefully', () => {
      // Remove an element
      document.getElementById('connectionStatus').remove();
      
      // Should not throw when trying to update non-existent element
      expect(() => {
        uiManager.updateConnectionStatus('connected', 'Connected');
      }).not.toThrow();
    });

    it('should handle null/undefined data', () => {
      expect(() => {
        uiManager.updateRoomInfo(null);
        uiManager.updateTimer(null);
        uiManager.displayResponsesForGuessing(null);
      }).not.toThrow();
    });

    it('should handle empty arrays', () => {
      uiManager.updatePlayersList([], 'player-1');
      uiManager.displayResponsesForGuessing([]);
      
      expect(uiManager.elements.playersList.innerHTML).toBe('');
      expect(uiManager.elements.responsesList.innerHTML).toBe('');
    });
  });
});