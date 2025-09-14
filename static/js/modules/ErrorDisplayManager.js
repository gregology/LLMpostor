/**
 * ErrorDisplayManager - Centralized error display and user feedback
 *
 * Responsible for:
 * - Displaying critical system errors to users
 * - Providing recovery options and user guidance
 * - Separating error presentation logic from business logic
 * - Managing error modal lifecycle and cleanup
 */

import { IUIModule } from '../interfaces/IGameModule.js';

class ErrorDisplayManager extends IUIModule {
    constructor(eventBus, serviceContainer) {
        super('ErrorDisplayManager', eventBus, serviceContainer);

        this.activeModals = new Map();
        this.errorHistory = [];
        this.maxHistorySize = 50;

        // Subscribe to system error events
        this.subscribe('system:error', (data) => this.handleSystemError(data));
        this.subscribe('system:fatal-error', (data) => this.handleFatalError(data));
    }

    initialize() {
        super.initialize();

        // Set up global error handlers
        this._setupGlobalErrorHandlers();

        console.log('ErrorDisplayManager initialized');
    }

    /**
     * Handle system errors (non-fatal)
     * @param {Object} errorData - Error information
     */
    handleSystemError(errorData) {
        const { error, context, recoverable = true } = errorData;

        this._addToHistory(error, context, 'system');

        // Try to use toast manager for non-fatal errors if available
        if (this.hasService('ToastManager')) {
            try {
                const toastManager = this.getService('ToastManager');
                toastManager.error(this._formatErrorMessage(error), 'error', true);
                return;
            } catch (toastError) {
                console.warn('Toast manager unavailable, falling back to modal');
            }
        }

        // Fallback to modal if toast is not available
        this.showErrorModal(error, { context, recoverable });
    }

    /**
     * Handle fatal errors that require user attention
     * @param {Object} errorData - Error information
     */
    handleFatalError(errorData) {
        const { error, context, recoveryActions = [] } = errorData;

        this._addToHistory(error, context, 'fatal');

        this.showFatalErrorModal(error, {
            context,
            recoveryActions: [
                ...recoveryActions,
                { label: 'Refresh Page', action: () => window.location.reload() }
            ]
        });
    }

    /**
     * Show error modal for recoverable errors
     * @param {Error} error - Error object
     * @param {Object} options - Display options
     */
    showErrorModal(error, options = {}) {
        const modalId = `error-modal-${Date.now()}`;
        const { context = '', recoverable = true } = options;

        const modalHTML = this._createErrorModalHTML(modalId, {
            title: 'Error Occurred',
            message: this._formatErrorMessage(error),
            context,
            recoverable,
            actions: recoverable ? [
                { label: 'Retry', action: () => this._handleRetry(error) },
                { label: 'Dismiss', action: () => this.closeModal(modalId) }
            ] : [
                { label: 'Refresh Page', action: () => window.location.reload() }
            ]
        });

        this._showModal(modalId, modalHTML);
    }

    /**
     * Show fatal error modal
     * @param {Error} error - Error object
     * @param {Object} options - Display options
     */
    showFatalErrorModal(error, options = {}) {
        const modalId = `fatal-error-modal-${Date.now()}`;
        const { context = '', recoveryActions = [] } = options;

        const modalHTML = this._createFatalErrorModalHTML(modalId, {
            title: 'Critical Error',
            message: this._formatErrorMessage(error),
            context,
            actions: recoveryActions.length > 0 ? recoveryActions : [
                { label: 'Refresh Page', action: () => window.location.reload() }
            ]
        });

        this._showModal(modalId, modalHTML);
    }

    /**
     * Show initialization error (for when modules fail to load)
     * @param {Error} error - Error object
     * @param {Object} options - Display options
     */
    showInitializationError(error, options = {}) {
        const modalId = 'init-error-modal';
        const { modules = [] } = options;

        const contextInfo = modules.length > 0
            ? `Failed modules: ${modules.join(', ')}`
            : 'Could not initialize game modules';

        const modalHTML = `
            <div id="${modalId}" style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        background: #fee; border: 2px solid #f00; padding: 20px; border-radius: 8px;
                        font-family: Arial, sans-serif; text-align: center; z-index: 10000;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); max-width: 500px;">
                <h3 style="color: #c00; margin-top: 0;">Failed to Load Game</h3>
                <p>${contextInfo}: ${this._formatErrorMessage(error)}</p>
                <div style="margin-top: 15px;">
                    <button onclick="window.location.reload()"
                            style="padding: 8px 16px; background: #007cba; color: white; border: none;
                                   border-radius: 4px; cursor: pointer; margin: 0 5px;">
                        Refresh Page
                    </button>
                    <button onclick="this.parentElement.parentElement.style.display='none'"
                            style="padding: 8px 16px; background: #666; color: white; border: none;
                                   border-radius: 4px; cursor: pointer; margin: 0 5px;">
                        Dismiss
                    </button>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.activeModals.set(modalId, { element: document.getElementById(modalId) });
    }

    /**
     * Close a specific modal
     * @param {string} modalId - Modal ID
     */
    closeModal(modalId) {
        const modal = this.activeModals.get(modalId);
        if (modal && modal.element) {
            modal.element.remove();
            this.activeModals.delete(modalId);
        }
    }

    /**
     * Close all active modals
     */
    closeAllModals() {
        for (const [modalId] of this.activeModals) {
            this.closeModal(modalId);
        }
    }

    /**
     * Get error history for debugging
     * @param {number} limit - Maximum number of errors to return
     * @returns {Array} Error history
     */
    getErrorHistory(limit = 10) {
        return this.errorHistory.slice(-limit);
    }

    /**
     * Clear error history
     */
    clearErrorHistory() {
        this.errorHistory = [];
    }

    destroy() {
        this.closeAllModals();
        this.clearErrorHistory();
        this._removeGlobalErrorHandlers();
        super.destroy();
    }

    // Private methods

    _setupGlobalErrorHandlers() {
        // Handle uncaught JavaScript errors
        this._originalErrorHandler = window.onerror;
        window.onerror = (message, source, lineno, colno, error) => {
            this.handleSystemError({
                error: error || new Error(message),
                context: `${source}:${lineno}:${colno}`,
                recoverable: true
            });

            // Call original handler if it exists
            if (this._originalErrorHandler) {
                return this._originalErrorHandler(message, source, lineno, colno, error);
            }
        };

        // Handle promise rejections
        this._originalUnhandledRejection = window.onunhandledrejection;
        window.onunhandledrejection = (event) => {
            this.handleSystemError({
                error: event.reason instanceof Error ? event.reason : new Error(event.reason),
                context: 'Unhandled Promise Rejection',
                recoverable: true
            });

            // Call original handler if it exists
            if (this._originalUnhandledRejection) {
                return this._originalUnhandledRejection(event);
            }
        };
    }

    _removeGlobalErrorHandlers() {
        window.onerror = this._originalErrorHandler;
        window.onunhandledrejection = this._originalUnhandledRejection;
    }

    _formatErrorMessage(error) {
        if (typeof error === 'string') {
            return error;
        }

        if (error instanceof Error) {
            return error.message || error.toString();
        }

        return String(error);
    }

    _createErrorModalHTML(modalId, options) {
        const { title, message, context, actions } = options;

        const actionsHTML = actions.map((action, index) => `
            <button onclick="window.errorDisplayManager._handleAction('${modalId}', ${index})"
                    style="padding: 8px 16px; background: ${index === 0 ? '#007cba' : '#666'};
                           color: white; border: none; border-radius: 4px; cursor: pointer; margin: 0 5px;">
                ${action.label}
            </button>
        `).join('');

        return `
            <div id="${modalId}" style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        background: #fff; border: 2px solid #f80; padding: 20px; border-radius: 8px;
                        font-family: Arial, sans-serif; text-align: center; z-index: 10000;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); max-width: 500px;">
                <h3 style="color: #e60; margin-top: 0;">${title}</h3>
                <p>${message}</p>
                ${context ? `<p style="font-size: 0.9em; color: #666;">Context: ${context}</p>` : ''}
                <div style="margin-top: 15px;">
                    ${actionsHTML}
                </div>
            </div>
        `;
    }

    _createFatalErrorModalHTML(modalId, options) {
        const { title, message, context, actions } = options;

        const actionsHTML = actions.map((action, index) => `
            <button onclick="window.errorDisplayManager._handleAction('${modalId}', ${index})"
                    style="padding: 8px 16px; background: ${index === 0 ? '#d32f2f' : '#666'};
                           color: white; border: none; border-radius: 4px; cursor: pointer; margin: 0 5px;">
                ${action.label}
            </button>
        `).join('');

        return `
            <div id="${modalId}" style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        background: #fee; border: 2px solid #f00; padding: 20px; border-radius: 8px;
                        font-family: Arial, sans-serif; text-align: center; z-index: 10000;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); max-width: 500px;">
                <h3 style="color: #c00; margin-top: 0;">${title}</h3>
                <p>${message}</p>
                ${context ? `<p style="font-size: 0.9em; color: #666;">Context: ${context}</p>` : ''}
                <div style="margin-top: 15px;">
                    ${actionsHTML}
                </div>
            </div>
        `;
    }

    _showModal(modalId, modalHTML) {
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const element = document.getElementById(modalId);

        this.activeModals.set(modalId, {
            element,
            actions: [] // Will be set when actions are registered
        });

        // Make this instance globally available for action handling
        window.errorDisplayManager = this;
    }

    _handleAction(modalId, actionIndex) {
        const modal = this.activeModals.get(modalId);
        if (modal && modal.actions && modal.actions[actionIndex]) {
            try {
                modal.actions[actionIndex].action();
            } catch (error) {
                console.error('Error handling action:', error);
            }
        }

        this.closeModal(modalId);
    }

    _handleRetry(originalError) {
        // Publish retry event that other modules can listen to
        this.publish('error-display:retry', {
            originalError,
            timestamp: Date.now()
        });
    }

    _addToHistory(error, context, type) {
        this.errorHistory.push({
            error: this._formatErrorMessage(error),
            context,
            type,
            timestamp: Date.now()
        });

        // Limit history size
        if (this.errorHistory.length > this.maxHistorySize) {
            this.errorHistory = this.errorHistory.slice(-this.maxHistorySize);
        }
    }
}

export default ErrorDisplayManager;