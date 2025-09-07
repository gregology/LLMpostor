import { vi } from 'vitest';

/**
 * Test utilities for LLMpostor game testing
 */

/**
 * Create a mock socket with common methods
 */
export function createMockSocket() {
  return {
    on: vi.fn(),
    emit: vi.fn(),
    disconnect: vi.fn(),
    connect: vi.fn(), // Add connect method for reconnection tests
    open: vi.fn(), // Add open method as alternative
    removeAllListeners: vi.fn(), // Add for cleanup operations
    connected: false,
    id: 'test-socket-id'
  };
}

/**
 * Create a mock DOM element with common properties
 */
export function createMockElement(tagName = 'div', properties = {}) {
  const element = document.createElement(tagName);
  Object.assign(element, properties);
  
  // Mock additional methods that might be called
  element.querySelector = vi.fn();
  element.querySelectorAll = vi.fn(() => []);
  element.addEventListener = vi.fn();
  element.removeEventListener = vi.fn();
  
  return element;
}

/**
 * Create mock game state data
 */
export function createMockGameState(overrides = {}) {
  return {
    phase: 'waiting',
    round_number: 1,
    phase_duration: 180,
    current_prompt: {
      id: 'prompt_001',
      prompt: 'Test prompt',
      model: 'GPT-4'
    },
    response_count: 0,
    guess_count: 0,
    responses: [],
    ...overrides
  };
}

/**
 * Create mock player data
 */
export function createMockPlayer(overrides = {}) {
  return {
    player_id: 'test-player-123',
    name: 'TestPlayer',
    score: 0,
    connected: true,
    ...overrides
  };
}

/**
 * Create mock room data
 */
export function createMockRoomData(overrides = {}) {
  return {
    room_id: 'test-room',
    player_id: 'test-player-123',
    player_name: 'TestPlayer',
    message: 'Successfully joined room test-room',
    ...overrides
  };
}

/**
 * Create mock response data for guessing phase
 */
export function createMockResponses(count = 3) {
  const responses = [];
  for (let i = 0; i < count; i++) {
    responses.push({
      index: i,
      text: `Response ${i}`
    });
  }
  return responses;
}

/**
 * Wait for next tick (useful for async operations)
 */
export function nextTick() {
  return new Promise(resolve => setTimeout(resolve, 0));
}

/**
 * Simulate user input in a textarea/input element
 */
export function simulateUserInput(element, value) {
  element.value = value;
  const inputEvent = new Event('input', { bubbles: true });
  element.dispatchEvent(inputEvent);
}

/**
 * Simulate button click
 */
export function simulateClick(element) {
  const clickEvent = new Event('click', { bubbles: true });
  element.dispatchEvent(clickEvent);
}

/**
 * Assert that an element has specific classes
 */
export function expectElementToHaveClasses(element, classes) {
  classes.forEach(className => {
    expect(element.classList.contains(className)).toBe(true);
  });
}

/**
 * Assert that an element does not have specific classes
 */
export function expectElementToNotHaveClasses(element, classes) {
  classes.forEach(className => {
    expect(element.classList.contains(className)).toBe(false);
  });
}

/**
 * Create a mock timer that can be controlled in tests
 */
export function createMockTimer() {
  const callbacks = [];
  
  return {
    setTimeout: vi.fn((callback, delay) => {
      const id = callbacks.length;
      callbacks.push({ callback, delay, id });
      return id;
    }),
    clearTimeout: vi.fn((id) => {
      callbacks[id] = null;
    }),
    runTimers: () => {
      callbacks.forEach(timer => {
        if (timer) timer.callback();
      });
    }
  };
}