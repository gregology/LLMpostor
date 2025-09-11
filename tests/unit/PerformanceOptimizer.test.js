import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const PerformanceOptimizer = (await import('../../static/js/modules/ui/PerformanceOptimizer.js')).default;

describe('PerformanceOptimizer', () => {
  let opt;
  let memoryManager;

  beforeEach(() => {
    memoryManager = { trackTimer: vi.fn() };
    opt = new PerformanceOptimizer(memoryManager);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('batch queues updates and process executes them once', () => {
    const fn1 = vi.fn();
    const fn2 = vi.fn();
    opt.batch('a', fn1);
    opt.batch('b', fn2);
    opt.process();
    expect(fn1).toHaveBeenCalledTimes(1);
    expect(fn2).toHaveBeenCalledTimes(1);
    // re-process should not re-run since queue was emptied
    opt.process();
    expect(fn1).toHaveBeenCalledTimes(1);
  });

  it('debounce executes immediately in test environment', () => {
    global.window = global.window || {};
    global.window.isTestEnvironment = true;

    const fn = vi.fn();
    const debounced = opt.debounce(fn, 1000);
    debounced('x');
    expect(fn).toHaveBeenCalledWith('x');

    delete global.window.isTestEnvironment;
  });

  it('debounce delays calls when not in test env', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = opt.debounce(fn, 200);
    debounced();
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(200);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('getCached caches DOM query results', () => {
    document.body.innerHTML = '<div id="x"></div>';
    const el1 = opt.getCached('#x');
    const el2 = opt.getCached('#x');
    expect(el1).toBe(el2);
  });

  it('clear resets internal state', () => {
    vi.useFakeTimers();
    // set some timers and cache entries
    const fn = vi.fn();
    const debounced = opt.debounce(fn, 1000);
    debounced();
    opt.getCached('#missing');
    opt.batch('k', () => {});
    opt.clear();
    // advance timers, nothing should run
    vi.advanceTimersByTime(2000);
    expect(fn).not.toHaveBeenCalled();
  });
});
