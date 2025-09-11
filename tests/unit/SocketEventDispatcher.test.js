import { describe, it, expect, beforeEach, vi } from 'vitest';

const SocketEventDispatcher = (await import('../../static/js/modules/SocketEventDispatcher.js')).default;

describe('SocketEventDispatcher', () => {
  let dispatcher;
  let socket;

  beforeEach(() => {
    socket = {
      on: vi.fn(),
      off: vi.fn()
    };
    dispatcher = new SocketEventDispatcher(socket);
  });

  it('registers single handler with on()', () => {
    const handler = vi.fn();
    dispatcher.on('test_event', handler);
    expect(socket.on).toHaveBeenCalledWith('test_event', handler);
  });

  it('registers multiple handlers with register()', () => {
    const a = vi.fn();
    const b = vi.fn();
    dispatcher.register({
      'a': a,
      'b': b
    });
    expect(socket.on).toHaveBeenCalledWith('a', a);
    expect(socket.on).toHaveBeenCalledWith('b', b);
  });

  it('clears handlers with clear()', () => {
    const h = vi.fn();
    dispatcher.on('x', h);
    dispatcher.clear();
    expect(socket.off).toHaveBeenCalledWith('x', h);
  });
});
