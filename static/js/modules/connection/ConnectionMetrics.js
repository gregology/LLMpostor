// ConnectionMetrics.js - Track and compute connection quality metrics

export default class ConnectionMetrics {
  constructor() {
    this.reset();
  }

  reset() {
    this.reconnectCount = 0;
    this.totalDowntime = 0;
    this.lastDisconnectTime = null;
    this.averageLatency = null;
    this.latencyHistory = [];
  }

  markDisconnected() {
    this.lastDisconnectTime = Date.now();
  }

  markReconnected() {
    if (this.lastDisconnectTime) {
      const downtime = Date.now() - this.lastDisconnectTime;
      this.totalDowntime += downtime;
      this.reconnectCount++;
      this.lastDisconnectTime = null;
    }
  }

  recordLatency(latency) {
    this.latencyHistory.push(latency);
    if (this.latencyHistory.length > 10) this.latencyHistory.shift();
    const sum = this.latencyHistory.reduce((a, b) => a + b, 0);
    this.averageLatency = sum / this.latencyHistory.length;
    return this.averageLatency;
  }

  getSummary(pendingRequestCount = 0, quality = 'unknown', isConnected = false) {
    return {
      quality,
      isConnected,
      reconnectCount: this.reconnectCount,
      totalDowntime: this.totalDowntime,
      averageLatency: this.averageLatency,
      pendingRequestCount,
    };
  }
}
