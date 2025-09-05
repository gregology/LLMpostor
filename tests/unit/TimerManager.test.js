import { describe, it, expect, beforeEach, vi } from 'vitest';

const TimerManager = (await import('../../static/js/modules/TimerManager.js')).default || 
                     (await import('../../static/js/modules/TimerManager.js')).TimerManager;

describe('TimerManager', () => {
  let timerManager;

  beforeEach(() => {
    vi.useFakeTimers();
    timerManager = new TimerManager();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Initialization', () => {
    it('should initialize with empty active timers', () => {
      expect(timerManager.activeTimers.size).toBe(0);
      expect(timerManager.onTimerUpdate).toBe(null);
      expect(timerManager.onTimerWarning).toBe(null);
    });
  });

  describe('Timer Management', () => {
    it('should start a timer', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      timerManager.startTimer('response', 180);

      expect(timerManager.activeTimers.has('response')).toBe(true);
      expect(updateCallback).toHaveBeenCalledWith({
        phase: 'response',
        timeText: '3:00',
        progress: 100,
        progressColor: '#10b981'
      });
    });

    it('should update existing timer', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      timerManager.startTimer('response', 180);
      updateCallback.mockClear();

      timerManager.updateTimer('response', 120, 180);

      expect(updateCallback).toHaveBeenCalledWith({
        phase: 'response',
        timeText: '2:00',
        progress: expect.closeTo(66.67, 1),
        progressColor: '#10b981'
      });
    });

    it('should clear specific timer', () => {
      timerManager.startTimer('response', 180);
      expect(timerManager.activeTimers.has('response')).toBe(true);

      timerManager.clearTimer('response');
      expect(timerManager.activeTimers.has('response')).toBe(false);
    });

    it('should clear all timers', () => {
      timerManager.startTimer('response', 180);
      timerManager.startTimer('guessing', 120);
      
      expect(timerManager.activeTimers.size).toBe(2);

      timerManager.clearAllTimers();
      expect(timerManager.activeTimers.size).toBe(0);
    });

    it('should get active timer names', () => {
      timerManager.startTimer('response', 180);
      timerManager.startTimer('guessing', 120);

      const activeTimers = timerManager.getActiveTimers();
      expect(activeTimers).toEqual(['response', 'guessing']);
    });
  });

  describe('Timer Progression', () => {
    it('should countdown timer over time', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      timerManager.startTimer('response', 60); // 1 minute
      updateCallback.mockClear();

      // Advance 30 seconds
      vi.advanceTimersByTime(30000);

      expect(updateCallback).toHaveBeenCalledWith({
        phase: 'response',
        timeText: '0:30',
        progress: 50,
        progressColor: '#f59e0b' // Should change to orange at 50%
      });
    });

    it('should trigger warning at 30 seconds remaining', () => {
      const warningCallback = vi.fn();
      timerManager.onTimerWarning = warningCallback;

      timerManager.startTimer('response', 60);
      
      // Advance to 30 seconds remaining
      vi.advanceTimersByTime(30000);

      expect(warningCallback).toHaveBeenCalledWith({
        phase: 'response',
        message: '30 seconds remaining!'
      });
    });

    it('should trigger warning at 10 seconds remaining', () => {
      const warningCallback = vi.fn();
      timerManager.onTimerWarning = warningCallback;

      timerManager.startTimer('response', 60);
      
      // Advance to 10 seconds remaining
      vi.advanceTimersByTime(50000);

      expect(warningCallback).toHaveBeenCalledWith({
        phase: 'response',
        message: '10 seconds remaining!'
      });
    });

    it('should handle timer expiration', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      timerManager.startTimer('response', 10);
      
      // Advance past timer duration
      vi.advanceTimersByTime(15000);

      expect(updateCallback).toHaveBeenLastCalledWith({
        phase: 'response',
        timeText: '0:00',
        progress: 0,
        progressColor: '#ef4444'
      });
      
      // Timer should be automatically cleared
      expect(timerManager.activeTimers.has('response')).toBe(false);
    });
  });

  describe('Progress Calculation', () => {
    it('should calculate progress correctly', () => {
      // Test various progress scenarios
      expect(timerManager._calculateProgress(180, 180)).toBe(100);
      expect(timerManager._calculateProgress(90, 180)).toBe(50);
      expect(timerManager._calculateProgress(0, 180)).toBe(0);
      expect(timerManager._calculateProgress(270, 180)).toBe(150); // Over 100%
    });

    it('should handle division by zero', () => {
      expect(timerManager._calculateProgress(0, 0)).toBe(0);
      expect(timerManager._calculateProgress(10, 0)).toBe(0);
    });
  });

  describe('Progress Color', () => {
    it('should return correct color based on progress', () => {
      expect(timerManager._getProgressColor(100)).toBe('#10b981'); // Green
      expect(timerManager._getProgressColor(75)).toBe('#10b981'); // Green
      expect(timerManager._getProgressColor(50)).toBe('#f59e0b'); // Orange  
      expect(timerManager._getProgressColor(25)).toBe('#f59e0b'); // Orange
      expect(timerManager._getProgressColor(10)).toBe('#ef4444'); // Red
      expect(timerManager._getProgressColor(0)).toBe('#ef4444'); // Red
    });
  });

  describe('Time Formatting', () => {
    it('should format time correctly', () => {
      expect(timerManager._formatTime(180)).toBe('3:00');
      expect(timerManager._formatTime(90)).toBe('1:30');
      expect(timerManager._formatTime(60)).toBe('1:00');
      expect(timerManager._formatTime(30)).toBe('0:30');
      expect(timerManager._formatTime(5)).toBe('0:05');
      expect(timerManager._formatTime(0)).toBe('0:00');
    });

    it('should handle negative time', () => {
      expect(timerManager._formatTime(-10)).toBe('0:00');
      expect(timerManager._formatTime(-60)).toBe('0:00');
    });

    it('should handle large times', () => {
      expect(timerManager._formatTime(3600)).toBe('60:00'); // 1 hour
      expect(timerManager._formatTime(3661)).toBe('61:01'); // 1 hour 1 minute 1 second
    });
  });

  describe('Multiple Concurrent Timers', () => {
    it('should handle multiple timers simultaneously', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      timerManager.startTimer('response', 180);
      timerManager.startTimer('guessing', 120);
      updateCallback.mockClear();

      // Advance time
      vi.advanceTimersByTime(30000);

      // Both timers should update
      expect(updateCallback).toHaveBeenCalledWith({
        phase: 'response',
        timeText: '2:30',
        progress: expect.any(Number),
        progressColor: expect.any(String)
      });
      
      expect(updateCallback).toHaveBeenCalledWith({
        phase: 'guessing',
        timeText: '1:30',
        progress: expect.any(Number),
        progressColor: expect.any(String)
      });
    });

    it('should clear individual timers without affecting others', () => {
      timerManager.startTimer('response', 180);
      timerManager.startTimer('guessing', 120);
      timerManager.startTimer('results', 30);

      timerManager.clearTimer('guessing');

      expect(timerManager.activeTimers.has('response')).toBe(true);
      expect(timerManager.activeTimers.has('guessing')).toBe(false);
      expect(timerManager.activeTimers.has('results')).toBe(true);
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle null callbacks gracefully', () => {
      timerManager.onTimerUpdate = null;
      timerManager.onTimerWarning = null;

      expect(() => {
        timerManager.startTimer('response', 60);
        vi.advanceTimersByTime(30000);
      }).not.toThrow();
    });

    it('should handle clearing non-existent timer', () => {
      expect(() => {
        timerManager.clearTimer('nonexistent');
      }).not.toThrow();
    });

    it('should handle updating non-existent timer', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      timerManager.updateTimer('nonexistent', 60, 120);

      // Should not crash, but also should not call update
      expect(updateCallback).not.toHaveBeenCalled();
    });

    it('should handle zero duration timer', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      timerManager.startTimer('instant', 0);

      expect(updateCallback).toHaveBeenCalledWith({
        phase: 'instant',
        timeText: '0:00',
        progress: 0,
        progressColor: '#ef4444'
      });
    });

    it('should handle very large duration', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      timerManager.startTimer('long', 999999);

      expect(updateCallback).toHaveBeenCalledWith({
        phase: 'long',
        timeText: '16666:39', // Very long time format
        progress: 100,
        progressColor: '#10b981'
      });
    });

    it('should restart timer if already exists', () => {
      const updateCallback = vi.fn();
      timerManager.onTimerUpdate = updateCallback;

      // Start timer
      timerManager.startTimer('response', 180);
      expect(timerManager.activeTimers.has('response')).toBe(true);
      
      // Start same timer again - should restart
      updateCallback.mockClear();
      timerManager.startTimer('response', 120);

      expect(updateCallback).toHaveBeenCalledWith({
        phase: 'response',
        timeText: '2:00',
        progress: 100,
        progressColor: '#10b981'
      });
    });
  });
});