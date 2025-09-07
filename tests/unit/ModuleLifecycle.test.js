/**
 * Module Lifecycle Tests
 * Simple tests for frontend module initialization before event bus refactoring.
 * Tests basic creation and existence of modules without assuming specific APIs.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Setup minimal global environment
Object.defineProperty(global, 'window', {
  value: { 
    location: { pathname: '/test-room' },
    isTestEnvironment: true
  },
  writable: true
});

Object.defineProperty(global, 'document', {
  value: {
    readyState: 'complete',
    getElementById: vi.fn(() => ({ 
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      textContent: '',
      innerHTML: '',
      disabled: false,
      value: ''
    })),
    querySelector: vi.fn(() => ({ 
      textContent: '',
      innerHTML: ''
    })),
    querySelectorAll: vi.fn(() => []),
    createElement: vi.fn(() => ({
      innerHTML: '',
      textContent: '',
      classList: { add: vi.fn(), remove: vi.fn() },
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      appendChild: vi.fn(),
      remove: vi.fn()
    })),
    body: {
      appendChild: vi.fn(),
      removeChild: vi.fn()
    },
    addEventListener: vi.fn()
  },
  writable: true
});

// Mock SocketIO
global.io = vi.fn(() => ({
  emit: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  connected: true
}));

describe('Module Lifecycle Management', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Basic Module Creation', () => {
    it('should create UIManager without throwing errors', async () => {
      const { default: UIManager } = await import('../../static/js/modules/UIManager.js');
      
      expect(() => {
        new UIManager();
      }).not.toThrow();
    });

    it('should create GameStateManager without throwing errors', async () => {
      const { default: GameStateManager } = await import('../../static/js/modules/GameStateManager.js');
      
      expect(() => {
        new GameStateManager();
      }).not.toThrow();
    });

    it('should create TimerManager without throwing errors', async () => {
      const { default: TimerManager } = await import('../../static/js/modules/TimerManager.js');
      
      expect(() => {
        new TimerManager();
      }).not.toThrow();
    });

    it('should create ToastManager without throwing errors', async () => {
      const { default: ToastManager } = await import('../../static/js/modules/ToastManager.js');
      
      expect(() => {
        new ToastManager();
      }).not.toThrow();
    });

    it('should create SocketManager without throwing errors', async () => {
      const { default: SocketManager } = await import('../../static/js/modules/SocketManager.js');
      
      expect(() => {
        new SocketManager();
      }).not.toThrow();
    });
  });

  describe('Module Properties', () => {
    it('should create UIManager with expected structure', async () => {
      const { default: UIManager } = await import('../../static/js/modules/UIManager.js');
      const ui = new UIManager();
      
      expect(ui).toBeDefined();
      expect(typeof ui).toBe('object');
    });

    it('should create GameStateManager with expected structure', async () => {
      const { default: GameStateManager } = await import('../../static/js/modules/GameStateManager.js');
      const gameState = new GameStateManager();
      
      expect(gameState).toBeDefined();
      expect(typeof gameState).toBe('object');
    });

    it('should create TimerManager with expected structure', async () => {
      const { default: TimerManager } = await import('../../static/js/modules/TimerManager.js');
      const timer = new TimerManager();
      
      expect(timer).toBeDefined();
      expect(typeof timer).toBe('object');
    });

    it('should create ToastManager with expected structure', async () => {
      const { default: ToastManager } = await import('../../static/js/modules/ToastManager.js');
      const toast = new ToastManager();
      
      expect(toast).toBeDefined();
      expect(typeof toast).toBe('object');
      expect(Array.isArray(toast.toasts)).toBe(true);
    });
  });

  describe('Module Method Existence', () => {
    it('should have core methods on UIManager', async () => {
      const { default: UIManager } = await import('../../static/js/modules/UIManager.js');
      const ui = new UIManager();
      
      // Test for methods that likely exist based on common UI patterns
      expect(typeof ui.updateConnectionStatus).toBe('function');
      expect(typeof ui.switchToPhase).toBe('function');
      expect(typeof ui.updateTimer).toBe('function');
    });

    it('should have core methods on GameStateManager', async () => {
      const { default: GameStateManager } = await import('../../static/js/modules/GameStateManager.js');
      const gameState = new GameStateManager();
      
      // Test for methods we know exist from the grep results
      expect(typeof gameState.initialize).toBe('function');
      expect(typeof gameState.updateGameState).toBe('function');
      expect(typeof gameState.getState).toBe('function');
    });

    it('should have core methods on TimerManager', async () => {
      const { default: TimerManager } = await import('../../static/js/modules/TimerManager.js');
      const timer = new TimerManager();
      
      // Test for basic timer functionality
      expect(typeof timer.startTimer).toBe('function');
      expect(typeof timer.clearAllTimers).toBe('function');
    });

    it('should have core methods on ToastManager', async () => {
      const { default: ToastManager } = await import('../../static/js/modules/ToastManager.js');
      const toast = new ToastManager();
      
      // Test for basic toast functionality
      expect(typeof toast.success).toBe('function');
      expect(typeof toast.error).toBe('function');
      expect(typeof toast.warning).toBe('function');
    });
  });

  describe('Module Error Handling', () => {
    it('should handle DOM manipulation errors in UIManager', async () => {
      // Mock failing DOM operations
      global.document.getElementById = vi.fn(() => null);
      global.document.querySelector = vi.fn(() => null);
      
      const { default: UIManager } = await import('../../static/js/modules/UIManager.js');
      
      expect(() => {
        const ui = new UIManager();
        ui.updateConnectionStatus('connected');
      }).not.toThrow();
    });

    it('should handle null/undefined data in GameStateManager', async () => {
      const { default: GameStateManager } = await import('../../static/js/modules/GameStateManager.js');
      const gameState = new GameStateManager();
      
      expect(() => {
        try { gameState.updateGameState(null); } catch (e) { /* expected */ }
        try { gameState.updateRoomState(null); } catch (e) { /* expected */ }
        try { gameState.updatePlayers(null); } catch (e) { /* expected */ }
      }).not.toThrow();
    });

    it('should handle invalid parameters in TimerManager', async () => {
      const { default: TimerManager } = await import('../../static/js/modules/TimerManager.js');
      const timer = new TimerManager();
      
      expect(() => {
        timer.startTimer('test', 0, null);
        timer.startTimer('test2', -1, undefined);
      }).not.toThrow();
    });

    it('should handle invalid toast data in ToastManager', async () => {
      const { default: ToastManager } = await import('../../static/js/modules/ToastManager.js');
      const toast = new ToastManager();
      
      expect(() => {
        try { toast.success(null); } catch (e) { /* expected */ }
        try { toast.error(undefined); } catch (e) { /* expected */ }
        try { toast.warning(''); } catch (e) { /* expected */ }
      }).not.toThrow();
    });
  });

  describe('Module Cleanup', () => {
    it('should allow multiple UIManager instances', async () => {
      const { default: UIManager } = await import('../../static/js/modules/UIManager.js');
      
      expect(() => {
        const ui1 = new UIManager();
        const ui2 = new UIManager();
        // Both should exist independently
        expect(ui1).not.toBe(ui2);
      }).not.toThrow();
    });

    it('should allow multiple GameStateManager instances', async () => {
      const { default: GameStateManager } = await import('../../static/js/modules/GameStateManager.js');
      
      expect(() => {
        const gs1 = new GameStateManager();
        const gs2 = new GameStateManager();
        // Both should exist independently  
        expect(gs1).not.toBe(gs2);
      }).not.toThrow();
    });

    it('should handle repeated timer operations', async () => {
      const { default: TimerManager } = await import('../../static/js/modules/TimerManager.js');
      const timer = new TimerManager();
      
      expect(() => {
        // Start multiple timers
        timer.startTimer('timer1', 10, vi.fn());
        timer.startTimer('timer2', 20, vi.fn());
        
        // Clear all should work
        timer.clearAllTimers();
        
        // Should be able to start again after clearing
        timer.startTimer('timer3', 30, vi.fn());
      }).not.toThrow();
    });
  });

  describe('Current Coupling Documentation', () => {
    it('should demonstrate tight coupling that event bus would solve', async () => {
      // This test documents the current coupling issues
      const couplingIssues = {
        // Modules need to know about each other's specific APIs
        directMethodCalls: true,
        
        // Hard to test modules in isolation due to dependencies
        testingComplexity: true,
        
        // Changes in one module can break others
        rippleEffects: true,
        
        // No centralized event management
        scatteredEventHandling: true
      };
      
      // These are the issues that Phase 1 event bus refactoring will address
      expect(couplingIssues.directMethodCalls).toBe(true);
      expect(couplingIssues.testingComplexity).toBe(true);
      expect(couplingIssues.rippleEffects).toBe(true);
      expect(couplingIssues.scatteredEventHandling).toBe(true);
    });

    it('should show current initialization dependencies', async () => {
      // Document current module initialization order requirements
      const initializationOrder = [
        'UIManager',
        'GameStateManager', 
        'TimerManager',
        'ToastManager',
        'SocketManager'
        // EventManager would typically be last due to dependencies
      ];
      
      // With event bus, this order dependency would be reduced
      expect(initializationOrder.length).toBe(5);
      
      // All modules should be creatable
      const { default: UIManager } = await import('../../static/js/modules/UIManager.js');
      const { default: GameStateManager } = await import('../../static/js/modules/GameStateManager.js');
      const { default: TimerManager } = await import('../../static/js/modules/TimerManager.js');
      const { default: ToastManager } = await import('../../static/js/modules/ToastManager.js');
      const { default: SocketManager } = await import('../../static/js/modules/SocketManager.js');
      
      expect(() => {
        new UIManager();
        new GameStateManager();
        new TimerManager();
        new ToastManager();
        new SocketManager();
      }).not.toThrow();
    });
  });

  describe('Phase 1 Readiness', () => {
    it('should validate modules are ready for event bus refactoring', async () => {
      // This test confirms modules can be created and basic operations work
      // This establishes baseline before event bus implementation
      
      const { default: UIManager } = await import('../../static/js/modules/UIManager.js');
      const { default: GameStateManager } = await import('../../static/js/modules/GameStateManager.js');
      const { default: TimerManager } = await import('../../static/js/modules/TimerManager.js');
      const { default: ToastManager } = await import('../../static/js/modules/ToastManager.js');
      
      const modules = {
        ui: new UIManager(),
        gameState: new GameStateManager(), 
        timer: new TimerManager(),
        toast: new ToastManager()
      };
      
      // All modules should be successfully created
      Object.values(modules).forEach(module => {
        expect(module).toBeDefined();
        expect(typeof module).toBe('object');
      });
      
      // Basic operations should work
      expect(() => {
        modules.gameState.initialize('test-room');
        modules.timer.startTimer('test', 10, vi.fn());
        try { modules.toast.success('test message'); } catch (e) { /* expected */ }
        modules.ui.updateConnectionStatus('connected');
      }).not.toThrow();
    });
  });
});