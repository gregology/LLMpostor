/**
 * ToastManager - Handles notification toasts
 * 
 * Responsible for:
 * - Creating and displaying toast notifications
 * - Managing toast lifecycle
 * - Toast styling and animations
 * - Auto-dismiss functionality
 */

class ToastManager {
    constructor() {
        this.container = null;
        this.toasts = [];
        this.activeToasts = new Set(); // Keep for internal tracking
        this.maxToasts = 10; // Limit number of concurrent toasts
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
        
        // Animate toast in
        setTimeout(() => {
            toast.classList.add('toast-show');
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
            this._removeToast(toast);
        });
        
        // Add click to dismiss (optional)
        toast.addEventListener('click', (e) => {
            if (e.target === toast || e.target.classList.contains('toast-message')) {
                this._removeToast(toast);
            }
        });
        
        return toast;
    }
    
    _removeToast(toast) {
        if (!this.activeToasts.has(toast)) {
            return;
        }
        
        // Always add exit classes for proper testing
        toast.classList.add('toast-exit');
        toast.classList.add('toast-hide');
        
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
}

// Export for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ToastManager;
}