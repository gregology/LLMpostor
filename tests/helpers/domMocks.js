/**
 * DOM Mock utilities for JavaScript tests
 * Provides standardized DOM mock setups to reduce boilerplate across tests.
 */

import { vi } from 'vitest';

/**
 * Create a comprehensive mock document with all common properties
 * @returns {Object} Mock document object
 */
export function createMockDocument() {
  return {
    readyState: 'complete',
    body: {
      innerHTML: '',
      appendChild: vi.fn(),
      removeChild: vi.fn(),
      querySelector: vi.fn(),
      querySelectorAll: vi.fn(() => []),
      classList: {
        add: vi.fn(),
        remove: vi.fn(),
        contains: vi.fn(() => false),
        toggle: vi.fn()
      }
    },
    getElementById: vi.fn(() => createMockElement()),
    querySelector: vi.fn(() => createMockElement()),
    querySelectorAll: vi.fn(() => []),
    createElement: vi.fn(() => createMockElement()),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn()
  };
}

/**
 * Create a comprehensive mock window with common properties
 * @returns {Object} Mock window object
 */
export function createMockWindow() {
  return {
    location: {
      pathname: '/test-room',
      origin: 'http://localhost',
      href: 'http://localhost/test-room'
    },
    navigator: {
      share: undefined,
      clipboard: { writeText: vi.fn() },
      userAgent: 'Test Browser'
    },
    isTestEnvironment: true,
    requestAnimationFrame: vi.fn(cb => setTimeout(cb, 16)),
    cancelAnimationFrame: vi.fn(),
    setTimeout: global.setTimeout,
    clearTimeout: global.clearTimeout,
    setInterval: global.setInterval,
    clearInterval: global.clearInterval,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn()
  };
}

/**
 * Create a mock DOM element with common methods and properties
 * @param {string} tagName - The tag name for the element
 * @param {Object} properties - Additional properties to set
 * @returns {Object} Mock DOM element
 */
export function createMockElement(tagName = 'div', properties = {}) {
  const element = {
    tagName: tagName.toUpperCase(),
    id: '',
    className: '',
    innerHTML: '',
    textContent: '',
    value: '',
    disabled: false,
    style: {},
    dataset: {},

    // Methods
    appendChild: vi.fn(),
    removeChild: vi.fn(),
    querySelector: vi.fn(() => createMockElement()),
    querySelectorAll: vi.fn(() => []),
    getElementById: vi.fn(() => createMockElement()),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
    focus: vi.fn(),
    blur: vi.fn(),
    click: vi.fn(),

    // classList mock
    classList: {
      add: vi.fn(),
      remove: vi.fn(),
      contains: vi.fn(() => false),
      toggle: vi.fn()
    },

    // Attributes
    getAttribute: vi.fn(),
    setAttribute: vi.fn(),
    removeAttribute: vi.fn(),
    hasAttribute: vi.fn(() => false),

    // Apply custom properties
    ...properties
  };

  return element;
}

/**
 * Set up basic DOM environment for UI testing
 * Creates the most common DOM structure used across tests.
 */
export function setupBasicDOM() {
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
}

/**
 * Set up minimal DOM environment for simple tests
 */
export function setupMinimalDOM() {
  document.body.innerHTML = '<div id="toast-container"></div>';
}

/**
 * Set up comprehensive global environment with mocked window and document
 */
export function setupGlobalEnvironment() {
  // Set up window mock
  Object.defineProperty(global, 'window', {
    value: createMockWindow(),
    writable: true
  });

  // Set up document mock
  Object.defineProperty(global, 'document', {
    value: createMockDocument(),
    writable: true
  });
}

/**
 * Clean up DOM after tests
 */
export function cleanupDOM() {
  document.body.innerHTML = '';
}

/**
 * Create a DOM mock helper class for more complex DOM interactions
 */
export class DOMTestHelper {
  constructor() {
    this.elements = new Map();
    this.setupMockDocument();
  }

  setupMockDocument() {
    // Override document.getElementById to return our controlled elements
    document.getElementById = vi.fn((id) => {
      if (!this.elements.has(id)) {
        this.elements.set(id, createMockElement('div', { id }));
      }
      return this.elements.get(id);
    });
  }

  // Create and track an element
  createElement(id, tagName = 'div', properties = {}) {
    const element = createMockElement(tagName, { id, ...properties });
    this.elements.set(id, element);
    return element;
  }

  // Get a tracked element
  getElement(id) {
    return this.elements.get(id);
  }

  // Simulate element interactions
  simulateClick(id) {
    const element = this.getElement(id);
    if (element && element.click) {
      element.click();
    }
  }

  // Clean up all tracked elements
  cleanup() {
    this.elements.clear();
  }
}