import { describe, it, expect } from 'vitest';

const ConnectionMetrics = (await import('../../static/js/modules/connection/ConnectionMetrics.js')).default;

describe('ConnectionMetrics', () => {
  it('tracks disconnect and reconnection downtime and count', () => {
    const m = new ConnectionMetrics();
    m.markDisconnected();
    // simulate 100ms downtime
    const now = Date.now;
    Date.now = () => 1000; // set an earlier time
    m.lastDisconnectTime = 900; // pretend disconnect happened at 900
    m.markReconnected();
    expect(m.totalDowntime).toBe(100);
    expect(m.reconnectCount).toBe(1);
    Date.now = now;
  });

  it('records latency and computes average', () => {
    const m = new ConnectionMetrics();
    expect(m.averageLatency).toBe(null);
    m.recordLatency(100);
    m.recordLatency(200);
    expect(Math.round(m.averageLatency)).toBe(150);
  });

  it('getSummary returns snapshot with provided args', () => {
    const m = new ConnectionMetrics();
    m.recordLatency(50);
    const s = m.getSummary(2, 'good', true);
    expect(s.quality).toBe('good');
    expect(s.isConnected).toBe(true);
    expect(s.pendingRequestCount).toBe(2);
    expect(s.averageLatency).toBe(50);
  });
});
