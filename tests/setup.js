// Global test setup
import { vi } from 'vitest';

// Set test environment flag to prevent auto-initialization
global.window.isTestEnvironment = true;

// Mock Socket.IO globally
global.io = vi.fn(() => ({
  on: vi.fn(),
  emit: vi.fn(),
  disconnect: vi.fn(),
  connected: false
}));

// Mock browser APIs that might not be available in jsdom
global.navigator = {
  ...global.navigator,
  share: vi.fn(),
  clipboard: {
    writeText: vi.fn(() => Promise.resolve())
  }
};

// Mock sessionStorage
Object.defineProperty(window, 'sessionStorage', {
  value: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn()
  },
  writable: true
});

// Mock window.confirm and window.prompt
global.confirm = vi.fn(() => true);
global.prompt = vi.fn(() => 'test-input');

// Setup DOM structure that modules expect
document.body.innerHTML = `
  <div id="connectionStatus"></div>
  <div id="playerCount"></div>
  <div id="playersList"></div>
  <div id="roundsPlayed"></div>
  <div id="waitingState"></div>
  <div id="responseState"></div>
  <div id="guessingState"></div>
  <div id="resultsState"></div>
  <div id="currentPrompt"></div>
  <div id="targetModel"></div>
  <textarea id="responseInput"></textarea>
  <div id="charCount"></div>
  <button id="submitResponseBtn">
    <span class="btn-text">Submit Response</span>
    <span class="btn-loading hidden">Loading...</span>
  </button>
  <div id="responseTimer"></div>
  <div id="responseTimerBar"></div>
  <div id="submissionCount">
    <span class="submitted-count">0</span>/<span class="total-count">0</span>
  </div>
  <div id="responsesList"></div>
  <div id="guessingTimer"></div>
  <div id="guessingTimerBar"></div>
  <div id="guessingTargetModel"></div>
  <div id="guessingCount">
    <span class="guessed-count">0</span>/<span class="total-count">0</span>
  </div>
  <div id="correctResponse"></div>
  <div id="roundScoresList"></div>
  <div id="nextRoundTimer"></div>
  <button id="leaveRoomBtn">Leave Room</button>
  <button id="shareRoomBtn">Share Room</button>
  <button id="startRoundBtn">
    <span class="btn-text">Start Round</span>
    <span class="btn-loading hidden">Loading...</span>
  </button>
`;

// Mock global window variables used by modules
global.window.roomId = 'test-room';
global.window.maxResponseLength = 500;

// Clean up after each test
afterEach(() => {
  vi.clearAllMocks();
  vi.clearAllTimers();
});