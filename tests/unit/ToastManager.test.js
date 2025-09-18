import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setupMinimalDOM, cleanupDOM } from '../helpers/domMocks.js';

const ToastManager = (await import('../../static/js/modules/ToastManager.js')).default ||
                     (await import('../../static/js/modules/ToastManager.js')).ToastManager;

describe('ToastManager', () => {
  let toastManager;
  let mockContainer;

  beforeEach(() => {
    vi.useFakeTimers();

    // Set up DOM using shared helper
    setupMinimalDOM();
    mockContainer = document.getElementById('toast-container');

    toastManager = new ToastManager();
  });

  afterEach(() => {
    // Clean up toasts and EventBus subscriptions
    if (toastManager && typeof toastManager.destroy === 'function') {
      toastManager.destroy();
    } else if (toastManager && typeof toastManager.clearAll === 'function') {
      toastManager.clearAll();
    }
    cleanupDOM();
    vi.useRealTimers();
  });

  describe('Initialization', () => {
    it('should initialize with empty toast list', () => {
      expect(toastManager.toasts).toEqual([]);
      expect(toastManager.container).toBe(null);
    });

    it('should create container when showing first toast', () => {
      toastManager.show('Test message');
      
      expect(toastManager.container).toBeDefined();
      expect(document.querySelector('.toast-container')).toBeTruthy();
    });

    it('should reuse existing container', () => {
      toastManager.show('First toast');
      const firstContainer = toastManager.container;
      
      toastManager.show('Second toast');
      const secondContainer = toastManager.container;
      
      expect(firstContainer).toBe(secondContainer);
    });
  });

  describe('Toast Creation', () => {
    it('should show basic toast message', () => {
      toastManager.show('Test message');
      
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.textContent).toContain('Test message');
      expect(toastManager.toasts.length).toBe(1);
    });

    it('should show success toast', () => {
      toastManager.success('Success message');
      
      const toast = document.querySelector('.toast');
      expect(toast.classList.contains('toast-success')).toBe(true);
      expect(toast.textContent).toContain('Success message');
    });

    it('should show error toast', () => {
      toastManager.error('Error message');
      
      const toast = document.querySelector('.toast');
      expect(toast.classList.contains('toast-error')).toBe(true);
      expect(toast.textContent).toContain('Error message');
    });

    it('should show warning toast', () => {
      toastManager.warning('Warning message');
      
      const toast = document.querySelector('.toast');
      expect(toast.classList.contains('toast-warning')).toBe(true);
      expect(toast.textContent).toContain('Warning message');
    });

    it('should show info toast', () => {
      toastManager.info('Info message');
      
      const toast = document.querySelector('.toast');
      expect(toast.classList.contains('toast-info')).toBe(true);
      expect(toast.textContent).toContain('Info message');
    });
  });

  describe('Toast Lifecycle', () => {
    it('should auto-dismiss toast after default delay', () => {
      toastManager.show('Auto dismiss message');
      
      expect(toastManager.toasts.length).toBe(1);
      expect(document.querySelector('.toast')).toBeTruthy();
      
      // Fast forward past default auto-dismiss time (5000ms)
      vi.advanceTimersByTime(5000);
      
      expect(toastManager.toasts.length).toBe(0);
      expect(document.querySelector('.toast')).toBeFalsy();
    });

    it('should auto-dismiss error toast after longer delay', () => {
      toastManager.error('Error message');
      
      // Error toasts have 8 second delay
      vi.advanceTimersByTime(7999);
      expect(document.querySelector('.toast')).toBeTruthy();
      
      vi.advanceTimersByTime(1);
      expect(document.querySelector('.toast')).toBeFalsy();
    });

    it('should not auto-dismiss persistent toast', () => {
      toastManager.show('Persistent message', 'info', true);
      
      // Fast forward well past normal dismiss time
      vi.advanceTimersByTime(10000);
      
      expect(toastManager.toasts.length).toBe(1);
      expect(document.querySelector('.toast')).toBeTruthy();
    });

    it('should dismiss toast on click', () => {
      toastManager.show('Clickable message');
      
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      
      // Click the toast
      toast.click();
      
      expect(toastManager.toasts.length).toBe(0);
      expect(document.querySelector('.toast')).toBeFalsy();
    });
  });

  describe('Multiple Toasts', () => {
    it('should show multiple toasts simultaneously', () => {
      toastManager.show('First toast');
      toastManager.show('Second toast');
      toastManager.show('Third toast');
      
      expect(toastManager.toasts.length).toBe(3);
      expect(document.querySelectorAll('.toast').length).toBe(3);
    });

    it('should dismiss toasts individually', () => {
      toastManager.show('First toast');
      toastManager.show('Second toast', 'info', true); // persistent
      toastManager.show('Third toast');
      
      // Auto-dismiss first and third toasts
      vi.advanceTimersByTime(5000);
      
      expect(toastManager.toasts.length).toBe(1);
      expect(document.querySelectorAll('.toast').length).toBe(1);
      expect(document.querySelector('.toast').textContent).toContain('Second toast');
    });

    it('should maintain correct order of toasts', () => {
      toastManager.show('First toast');
      toastManager.show('Second toast');
      toastManager.show('Third toast');
      
      const toasts = document.querySelectorAll('.toast');
      expect(toasts[0].textContent).toContain('First toast');
      expect(toasts[1].textContent).toContain('Second toast');
      expect(toasts[2].textContent).toContain('Third toast');
    });
  });

  describe('Toast Management', () => {
    it('should clear all toasts', () => {
      toastManager.show('Toast 1');
      toastManager.show('Toast 2', 'info', true);
      toastManager.show('Toast 3');
      
      expect(toastManager.toasts.length).toBe(3);
      
      toastManager.clearAll();
      
      expect(toastManager.toasts.length).toBe(0);
      expect(document.querySelectorAll('.toast').length).toBe(0);
    });

    it('should get active toast count', () => {
      expect(toastManager.getActiveCount()).toBe(0);
      
      toastManager.show('Toast 1');
      expect(toastManager.getActiveCount()).toBe(1);
      
      toastManager.show('Toast 2');
      expect(toastManager.getActiveCount()).toBe(2);
      
      toastManager.clearAll();
      expect(toastManager.getActiveCount()).toBe(0);
    });

    it('should limit maximum number of toasts', () => {
      // Show many toasts
      for (let i = 0; i < 20; i++) {
        toastManager.show(`Toast ${i}`);
      }
      
      // Should be limited to reasonable number (e.g., 10)
      expect(toastManager.toasts.length).toBeLessThanOrEqual(10);
    });
  });

  describe('XSS Protection', () => {
    it('should escape HTML in toast messages', () => {
      const maliciousMessage = '<script>alert("xss")</script>Malicious content';
      
      toastManager.show(maliciousMessage);
      
      const toast = document.querySelector('.toast');
      expect(toast.innerHTML).not.toContain('<script>');
      expect(toast.innerHTML).toContain('&lt;script&gt;');
      expect(toast.textContent).toContain('Malicious content');
    });

    it('should escape HTML in different toast types', () => {
      const malicious = '<img src=x onerror=alert(1)>';
      
      toastManager.error(malicious);
      toastManager.success(malicious);
      toastManager.warning(malicious);
      toastManager.info(malicious);
      
      document.querySelectorAll('.toast').forEach(toast => {
        expect(toast.innerHTML).not.toContain('<img');
        expect(toast.innerHTML).toContain('&lt;img');
      });
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle empty message', () => {
      toastManager.show('');
      
      expect(toastManager.toasts.length).toBe(1);
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
    });

    it('should handle null/undefined message', () => {
      expect(() => {
        toastManager.show(null);
        toastManager.show(undefined);
      }).not.toThrow();
    });

    it('should handle very long message', () => {
      const longMessage = 'x'.repeat(1000);
      
      toastManager.show(longMessage);
      
      const toast = document.querySelector('.toast');
      const messageElement = toast.querySelector('.toast-message');
      expect(messageElement.textContent).toBe(longMessage);
    });

    it('should handle invalid toast type', () => {
      toastManager.show('Message', 'invalid-type');
      
      const toast = document.querySelector('.toast');
      expect(toast.classList.contains('toast-info')).toBe(true); // Should default to info
    });

    it('should handle rapid toast creation', () => {
      // Create many toasts rapidly
      for (let i = 0; i < 50; i++) {
        toastManager.show(`Rapid toast ${i}`);
      }
      
      // Should handle without errors
      expect(toastManager.toasts.length).toBeGreaterThan(0);
      expect(toastManager.toasts.length).toBeLessThanOrEqual(10); // Limited
    });

    it('should handle DOM container removal', () => {
      toastManager.show('Test toast');
      
      // Remove container from DOM
      toastManager.container.remove();
      toastManager.container = null;
      
      // Should recreate container for new toast
      expect(() => {
        toastManager.show('New toast after container removal');
      }).not.toThrow();
      
      expect(document.querySelector('.toast')).toBeTruthy();
    });

    it('should handle clearing toasts when none exist', () => {
      expect(() => {
        toastManager.clearAll();
      }).not.toThrow();
      
      expect(toastManager.getActiveCount()).toBe(0);
    });
  });

  describe('Animation and Transitions', () => {
    it('should apply entrance animation class', () => {
      toastManager.show('Animated toast');
      
      const toast = document.querySelector('.toast');
      expect(toast.classList.contains('toast-enter')).toBe(true);
    });

    it('should apply exit animation before removal', () => {
      toastManager.show('Exit animation toast');
      
      const toast = document.querySelector('.toast');
      toast.click(); // Trigger removal
      
      expect(toast.classList.contains('toast-exit')).toBe(true);
    });
  });

  describe('Accessibility', () => {
    it('should have appropriate ARIA attributes', () => {
      toastManager.show('Accessible toast');
      
      const toast = document.querySelector('.toast');
      expect(toast.getAttribute('role')).toBe('alert');
      expect(toast.getAttribute('aria-live')).toBe('polite');
    });

    it('should use assertive aria-live for errors', () => {
      toastManager.error('Error toast');
      
      const toast = document.querySelector('.toast');
      expect(toast.getAttribute('aria-live')).toBe('assertive');
    });

    it('should be focusable with keyboard', () => {
      toastManager.show('Keyboard accessible toast');
      
      const toast = document.querySelector('.toast');
      expect(toast.getAttribute('tabindex')).toBe('0');
    });
  });
});