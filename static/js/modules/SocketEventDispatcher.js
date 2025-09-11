// SocketEventDispatcher.js - Dedicated dispatcher to register and manage socket event handlers

export default class SocketEventDispatcher {
  constructor(socket) {
    this.socket = socket;
    this.handlers = new Map();
  }

  // Register a single event handler
  on(eventName, handler) {
    if (!this.socket) return;
    this.handlers.set(eventName, handler);
    this.socket.on(eventName, handler);
  }

  // Bulk register from a map: { eventName: handlerFn }
  register(handlersMap) {
    Object.entries(handlersMap).forEach(([event, handler]) => this.on(event, handler));
  }

  // Remove all handlers (useful for teardown)
  clear() {
    if (!this.socket) return;
    for (const [event, handler] of this.handlers.entries()) {
      this.socket.off(event, handler);
    }
    this.handlers.clear();
  }
}
