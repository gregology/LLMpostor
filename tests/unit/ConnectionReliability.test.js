/**
 * ConnectionReliability Unit Tests
 *
 * SCOPE: Unit testing of ConnectionReliability utility class only
 * FOCUS: Connection timeout, heartbeat intervals, recovery backoff algorithms
 * INTEGRATION: See ConnectionIntegration.test.js for full connection stack testing
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const ConnectionReliability = (await import('../../static/js/modules/connection/ConnectionReliability.js')).default;

describe('ConnectionReliability (Unit)', () => {
  let rel;

  beforeEach(() => {
    rel = new ConnectionReliability();
    vi.useFakeTimers();
  });

  afterEach(() => {
    rel.clearAll();
    vi.useRealTimers();
  });

  describe('connection timeout', () => {
    it('triggers onTimeout after the specified delay', () => {
      const onTimeout = vi.fn();
      rel.startConnectionTimeout(1000, onTimeout);
      vi.advanceTimersByTime(999);
      expect(onTimeout).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1);
      expect(onTimeout).toHaveBeenCalledTimes(1);
    });

    it('clearConnectionTimeout cancels pending timeout', () => {
      const onTimeout = vi.fn();
      rel.startConnectionTimeout(1000, onTimeout);
      rel.clearConnectionTimeout();
      vi.advanceTimersByTime(2000);
      expect(onTimeout).not.toHaveBeenCalled();
    });
  });

  describe('heartbeat', () => {
    it('emits ping periodically when connected', () => {
      const emitPing = vi.fn();
      const isConnected = () => true;
      rel.startHeartbeat(500, isConnected, emitPing);
      vi.advanceTimersByTime(1);
      expect(emitPing).toHaveBeenCalledTimes(0);
      vi.advanceTimersByTime(500);
      expect(emitPing).toHaveBeenCalledTimes(1);
      vi.advanceTimersByTime(500);
      expect(emitPing).toHaveBeenCalledTimes(2);
    });

    it('does not emit ping when not connected', () => {
      const emitPing = vi.fn();
      const isConnected = () => false;
      rel.startHeartbeat(500, isConnected, emitPing);
      vi.advanceTimersByTime(2000);
      expect(emitPing).not.toHaveBeenCalled();
    });

    it('stopHeartbeat cancels interval', () => {
      const emitPing = vi.fn();
      rel.startHeartbeat(200, () => true, emitPing);
      vi.advanceTimersByTime(200);
      expect(emitPing).toHaveBeenCalledTimes(1);
      rel.stopHeartbeat();
      vi.advanceTimersByTime(2000);
      expect(emitPing).toHaveBeenCalledTimes(1);
    });
  });

  describe('recovery backoff', () => {
    it('schedules recovery with exponential backoff and calls attemptReconnect', () => {
      const attemptReconnect = vi.fn();
      const isConnected = () => false;

      // attempt #1 -> 1000ms
      rel.startConnectionRecovery(1, isConnected, attemptReconnect, 10, 1000, 30000);
      vi.advanceTimersByTime(999);
      expect(attemptReconnect).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1);
      expect(attemptReconnect).toHaveBeenCalledTimes(1);

      // attempt #2 -> 2000ms
      rel.startConnectionRecovery(2, isConnected, attemptReconnect, 10, 1000, 30000);
      vi.advanceTimersByTime(2000);
      expect(attemptReconnect).toHaveBeenCalledTimes(2);

      // attempt #6 -> should clamp at 30000ms (since 2^5 * 1000 = 32000)
      attemptReconnect.mockClear();
      rel.startConnectionRecovery(6, isConnected, attemptReconnect, 10, 1000, 30000);
      vi.advanceTimersByTime(30000);
      expect(attemptReconnect).toHaveBeenCalledTimes(1);
    });

    it('clearRecoveryTimer cancels pending recovery', () => {
      const attemptReconnect = vi.fn();
      rel.startConnectionRecovery(1, () => false, attemptReconnect);
      rel.clearRecoveryTimer();
      vi.advanceTimersByTime(5000);
      expect(attemptReconnect).not.toHaveBeenCalled();
    });
  });
});
