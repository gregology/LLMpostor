/**
 * ToastManager - Event-driven toast notification system
 * 
 * Responsible for:
 * - Creating and displaying toast notifications
 * - Managing toast lifecycle
 * - Toast styling and animations
 * - Auto-dismiss functionality
 * - Event-based toast handling
 * 
 * Migration Status: Updated to use EventBus with backward compatibility
 */

import { EventBusModule, migrationHelper } from './EventBusMigration.js';
import { Events } from './EventBus.js';

class ToastManager extends EventBusModule {
    constructor() {
        super('ToastManager');
        
        this.container = null;
        this.toasts = [];
        this.activeToasts = new Set(); // Keep for internal tracking
        this.maxToasts = 10; // Limit number of concurrent toasts
        
        // Subscribe to toast events
        this.subscribe(Events.TOAST.SHOW_SUCCESS, this._handleShowSuccess.bind(this));
        this.subscribe(Events.TOAST.SHOW_ERROR, this._handleShowError.bind(this));
        this.subscribe(Events.TOAST.SHOW_WARNING, this._handleShowWarning.bind(this));
        this.subscribe(Events.TOAST.SHOW_INFO, this._handleShowInfo.bind(this));
        
        // Subscribe to system events for automatic toast display
        this.subscribe(Events.TIMER.WARNING, this._handleTimerWarning.bind(this));
        this.subscribe(Events.SYSTEM.ERROR, this._handleSystemError.bind(this));
        this.subscribe(Events.SYSTEM.WARNING, this._handleSystemWarning.bind(this));
        this.subscribe(Events.SYSTEM.INFO, this._handleSystemInfo.bind(this));
        this.subscribe(Events.SOCKET.ERROR, this._handleSocketError.bind(this));
        this.subscribe(Events.SOCKET.DISCONNECTED, this._handleSocketDisconnected.bind(this));
        
        console.log('ToastManager initialized with EventBus integration');
    }
    
    /**
     * Show a toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type (success, error, warning, info)
     * @param {boolean} persistent - Whether toast should auto-dismiss
     */
    show(message, type = 'info', persistent = false) {
        this._ensureContainer();
        
        // Limit number of toasts
        while (this.toasts.length >= this.maxToasts) {
            const oldestToast = this.toasts[0];
            this._removeToast(oldestToast);
        }
        
        const toast = this._createToast(message, type, persistent);
        this.container.appendChild(toast);
        this.toasts.push(toast);
        this.activeToasts.add(toast);
        
        // Store toast metadata for events
        const toastData = {
            id: toast.dataset.toastId || this._generateToastId(),
            message,
            type,
            persistent,
            timestamp: Date.now(),
            element: toast
        };
        
        toast.dataset.toastId = toastData.id;
        
        // Animate toast in
        setTimeout(() => {
            toast.classList.add('toast-show');
            
            // Publish toast shown event
            this.publish(Events.TOAST.SHOWN, toastData);
        }, 100);
        
        // Auto-remove after delay (unless persistent)
        if (!persistent) {
            const delay = this._getAutoCloseDelay(type);
            setTimeout(() => {
                this._removeToast(toast);
            }, delay);
        }
        
        return toast;
    }
    
    /**
     * Show success toast
     * @param {string} message - Message to display
     * @param {boolean} persistent - Whether toast should auto-dismiss
     */
    success(message, persistent = false) {
        return this.show(message, 'success', persistent);
    }
    
    /**
     * Show error toast
     * @param {string} message - Message to display
     * @param {boolean} persistent - Whether toast should auto-dismiss
     */
    error(message, persistent = false) {
        return this.show(message, 'error', persistent);
    }
    
    /**
     * Show warning toast
     * @param {string} message - Message to display
     * @param {boolean} persistent - Whether toast should auto-dismiss
     */
    warning(message, persistent = false) {
        return this.show(message, 'warning', persistent);
    }
    
    /**
     * Show info toast
     * @param {string} message - Message to display
     * @param {boolean} persistent - Whether toast should auto-dismiss
     */
    info(message, persistent = false) {
        return this.show(message, 'info', persistent);
    }
    
    /**
     * Clear all active toasts
     */
    clearAll() {
        // In test environment, remove immediately
        if (typeof window !== 'undefined' && window.isTestEnvironment) {
            [...this.toasts].forEach(toast => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
                this.activeToasts.delete(toast);
            });
            this.toasts = [];
        } else {
            // Normal operation with animation
            [...this.toasts].forEach(toast => {
                this._removeToast(toast);
            });
        }
    }
    
    /**
     * Remove specific toast
     * @param {HTMLElement} toast - Toast element to remove
     */
    remove(toast) {
        this._removeToast(toast);
    }

    /**
     * Get count of active toasts
     * @returns {number} Number of active toasts
     */
    getActiveCount() {
        return this.activeToasts.size;
    }
    
    // Private methods
    
    _ensureContainer() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    }
    
    _createToast(message, type, persistent) {
        // Handle invalid types by defaulting to 'info'
        if (!['success', 'error', 'warning', 'info'].includes(type)) {
            type = 'info';
        }
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type} toast-enter`;
        
        // Add ARIA attributes for accessibility
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
        toast.setAttribute('tabindex', '0');
        
        const escapedMessage = this._escapeHtml(message);
        
        toast.innerHTML = `
            <div class="toast-content">
                <span class="toast-message">${escapedMessage}</span>
                <button class="toast-close" aria-label="Close notification">&times;</button>
            </div>
        `;
        
        // Add close functionality
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this._removeToast(toast, 'manual_close');
        });
        
        // Add click to dismiss (optional)
        toast.addEventListener('click', (e) => {
            if (e.target === toast || e.target.classList.contains('toast-message')) {
                this._removeToast(toast, 'manual_dismiss');
            }
        });
        
        return toast;
    }
    
    _removeToast(toast, reason = 'auto_dismiss') {
        if (!this.activeToasts.has(toast)) {
            return;
        }
        
        // Create dismissal event data
        const dismissalData = {
            id: toast.dataset.toastId,
            message: toast.querySelector('.toast-message')?.textContent || '',
            type: this._getToastType(toast),
            timestamp: Date.now(),
            reason
        };
        
        // Always add exit classes for proper testing
        toast.classList.add('toast-exit');
        toast.classList.add('toast-hide');
        
        // Publish dismissal event
        this.publish(Events.TOAST.DISMISSED, dismissalData);
        
        // In test environment, remove immediately after adding classes
        if (typeof window !== 'undefined' && window.isTestEnvironment) {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            this.activeToasts.delete(toast);
            const index = this.toasts.indexOf(toast);
            if (index > -1) {
                this.toasts.splice(index, 1);
            }
        } else {
            // Normal operation with animation delay
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
                this.activeToasts.delete(toast);
                const index = this.toasts.indexOf(toast);
                if (index > -1) {
                    this.toasts.splice(index, 1);
                }
            }, 300); // Match CSS transition duration
        }
    }
    
    _getAutoCloseDelay(type) {
        const delays = {
            error: 8000,
            warning: 6000,
            success: 4000,
            info: 4000
        };
        
        return delays[type] || 4000;
    }
    
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    _generateToastId() {
        return `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    _getToastType(toast) {
        if (toast.classList.contains('toast-success')) return 'success';
        if (toast.classList.contains('toast-error')) return 'error';
        if (toast.classList.contains('toast-warning')) return 'warning';
        return 'info';
    }
    
    // Event handlers for toast events
    
    _handleShowSuccess(data) {
        if (typeof data === 'string') {
            this.success(data);
        } else if (data && data.message) {
            this.success(data.message, data.persistent);
        }
    }
    
    _handleShowError(data) {
        if (typeof data === 'string') {
            this.error(data);
        } else if (data && data.message) {
            this.error(data.message, data.persistent);
        }
    }
    
    _handleShowWarning(data) {
        if (typeof data === 'string') {
            this.warning(data);
        } else if (data && data.message) {
            this.warning(data.message, data.persistent);
        }
    }
    
    _handleShowInfo(data) {
        if (typeof data === 'string') {
            this.info(data);
        } else if (data && data.message) {
            this.info(data.message, data.persistent);
        }
    }
    
    // System event handlers for automatic toast display
    
    _handleTimerWarning(data) {
        if (data && data.message) {
            const message = `Timer Warning: ${data.message}`;
            this.warning(message, false);
        }
    }
    
    _handleSystemError(data) {
        let message = 'System Error';
        if (typeof data === 'string') {
            message = data;
        } else if (data && data.error) {
            message = typeof data.error === 'string' ? data.error : data.error.message || 'Unknown system error';
        } else if (data && data.message) {
            message = data.message;
        }
        
        this.error(message, true); // System errors are persistent
    }
    
    _handleSystemWarning(data) {
        let message = 'System Warning';
        if (typeof data === 'string') {
            message = data;
        } else if (data && data.message) {
            message = data.message;
        }
        
        this.warning(message, false);
    }
    
    _handleSystemInfo(data) {
        let message = 'System Info';
        if (typeof data === 'string') {
            message = data;
        } else if (data && data.message) {
            message = data.message;
        }
        
        this.info(message, false);
    }
    
    _handleSocketError(data) {
        let message = 'Connection Error';
        if (data && data.error) {
            message = `Connection Error: ${data.error}`;
        }
        
        this.error(message, false);
    }
    
    _handleSocketDisconnected(data) {
        let message = 'Connection Lost';
        if (data && data.reason) {
            message = `Connection Lost: ${data.reason}`;
        }
        
        this.warning(message, false);
    }
    
    /**
     * Clean up all toasts and subscriptions
     */
    destroy() {
        this.clearAll();
        this.cleanup(); // Clean up event subscriptions
        
        // Remove toast container
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
            this.container = null;
        }
    }
}


export default ToastManager;