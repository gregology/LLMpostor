// PerformanceOptimizer.js - batching, debouncing, and caching utilities for UI

export default class PerformanceOptimizer {
  constructor(memoryManager) {
    this.memoryManager = memoryManager;
    this.domCache = new Map();
    this.updateQueue = [];
    this.pendingUpdates = new Set();
    this.animationFrameId = null;
    this.debounceTimers = new Map();
  }

  batch(updateKey, fn) {
    if (this.pendingUpdates.has(updateKey)) return;
    this.pendingUpdates.add(updateKey);
    this.updateQueue.push({ key: updateKey, fn });

    if (typeof window !== 'undefined' && window.isTestEnvironment) {
      this.process();
      return;
    }

    if (this.animationFrameId === null) {
      this.animationFrameId = requestAnimationFrame(() => this.process());
    }
  }

  process() {
    while (this.updateQueue.length > 0) {
      const update = this.updateQueue.shift();
      try { update.fn(); } catch (e) { console.error(`Error in batched update ${update.key}:`, e); }
    }
    this.pendingUpdates.clear();
    this.animationFrameId = null;
  }

  debounce(fn, delay) {
    return (...args) => {
      if (typeof window !== 'undefined' && window.isTestEnvironment) {
        fn.apply(this, args);
        return;
      }
      const key = fn.name || 'anonymous';
      if (this.debounceTimers.has(key)) clearTimeout(this.debounceTimers.get(key));
      const id = setTimeout(() => { fn.apply(this, args); this.debounceTimers.delete(key); }, delay);
      this.debounceTimers.set(key, id);
      this.memoryManager?.trackTimer?.(id);
    };
  }

  getCached(selector) {
    if (this.domCache.has(selector)) {
      const cached = this.domCache.get(selector);
      if (cached && document.contains(cached)) return cached;
      this.domCache.delete(selector);
    }
    const el = document.querySelector(selector);
    if (el) this.domCache.set(selector, el);
    return el;
  }

  clear() {
    this.domCache.clear();
    this.pendingUpdates.clear();
    for (const id of this.debounceTimers.values()) clearTimeout(id);
    this.debounceTimers.clear();
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }
}
