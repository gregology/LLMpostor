// ConnectionReliability.js - Handles heartbeat and reconnection strategy
// This module encapsulates timers and backoff logic while delegating actual socket operations

export default class ConnectionReliability {
  constructor() {
    this.connectionTimeoutTimer = null;
    this.heartbeatInterval = null;
    this.recoveryTimer = null;
  }

  // Connection timeout
  startConnectionTimeout(timeoutMs, onTimeout) {
    this.clearConnectionTimeout();
    this.connectionTimeoutTimer = setTimeout(() => {
      try { onTimeout && onTimeout(); } catch (e) { console.error(e); }
    }, timeoutMs);
  }

  clearConnectionTimeout() {
    if (this.connectionTimeoutTimer) {
      clearTimeout(this.connectionTimeoutTimer);
      this.connectionTimeoutTimer = null;
    }
  }

  // Heartbeat ping loop
  startHeartbeat(intervalMs, isConnectedFn, emitPing, onOverdue) {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      try {
        if (isConnectedFn && isConnectedFn()) {
          const timestamp = Date.now();
          emitPing && emitPing(timestamp);
          // Let caller track last heartbeat and detect overdue; we provide optional callback
          if (onOverdue && onOverdue()) {
            // onOverdue can itself update quality when overdue
          }
        }
      } catch (e) {
        console.error('Heartbeat error:', e);
      }
    }, intervalMs);
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  // Exponential backoff reconnection attempts
  startConnectionRecovery(attemptNumber, isConnectedFn, attemptReconnectFn, maxAttempts = 10, baseDelayMs = 1000, maxDelayMs = 30000, onScheduled) {
    this.clearRecoveryTimer();

    // Compute delay: 1s,2s,4s,8s,16s, then clamp to maxDelay
    const delay = Math.min(Math.pow(2, Math.max(0, attemptNumber - 1)) * baseDelayMs, maxDelayMs);
    onScheduled && onScheduled(delay, attemptNumber);

    this.recoveryTimer = setTimeout(() => {
      try {
        if (!isConnectedFn || !isConnectedFn()) {
          attemptReconnectFn && attemptReconnectFn();
          if (attemptNumber < maxAttempts) {
            // Caller should call startConnectionRecovery again with incremented attemptNumber
          }
        }
      } catch (e) {
        console.error('Recovery attempt error:', e);
      }
    }, delay);
  }

  clearRecoveryTimer() {
    if (this.recoveryTimer) {
      clearTimeout(this.recoveryTimer);
      this.recoveryTimer = null;
    }
  }

  clearAll() {
    this.clearConnectionTimeout();
    this.stopHeartbeat();
    this.clearRecoveryTimer();
  }
}
