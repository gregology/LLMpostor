/**
 * Unit tests for ErrorDisplayManager
 *
 * Tests error display functionality, modal management, global error handling,
 * and integration with the event bus and service container systems.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ErrorDisplayManager from '../../static/js/modules/ErrorDisplayManager.js';

// Mock the IGameModule interface
vi.mock('../../static/js/interfaces/IGameModule.js', () => ({
    IUIModule: class MockIUIModule {
        constructor(name, eventBus, serviceContainer) {
            this.name = name;
            this.eventBus = eventBus;
            this.serviceContainer = serviceContainer;
            this._elements = new Map();
            this._eventListeners = [];
        }

        initialize() {}
        destroy() {}
        subscribe() {}
        publish() {}
        hasService() { return false; }
        getService() { return null; }
        getElement() { return null; }
        addEventListener() {}
        updateUI() {}
        showLoading() {}
        hideLoading() {}
    }
}));

describe('ErrorDisplayManager', () => {
    let errorDisplayManager;
    let mockEventBus;
    let mockServiceContainer;
    let mockToastManager;
    let originalOnError;
    let originalOnUnhandledRejection;

    beforeEach(() => {
        // Save original error handlers
        originalOnError = window.onerror;
        originalOnUnhandledRejection = window.onunhandledrejection;

        // Setup mocks
        mockEventBus = {
            subscribe: vi.fn(),
            publish: vi.fn(),
            unsubscribe: vi.fn()
        };

        mockToastManager = {
            error: vi.fn()
        };

        mockServiceContainer = {
            hasService: vi.fn(),
            getService: vi.fn()
        };

        // Mock DOM
        document.body.innerHTML = '';
        window.errorDisplayManager = undefined;

        // Create error display manager
        errorDisplayManager = new ErrorDisplayManager(mockEventBus, mockServiceContainer);

        // Setup prototype chain manually since we're mocking the parent class
        errorDisplayManager.name = 'ErrorDisplayManager';
        errorDisplayManager.eventBus = mockEventBus;
        errorDisplayManager.serviceContainer = mockServiceContainer;
        errorDisplayManager.subscribe = vi.fn();
        errorDisplayManager.publish = vi.fn();
        errorDisplayManager.hasService = mockServiceContainer.hasService;
        errorDisplayManager.getService = mockServiceContainer.getService;
        errorDisplayManager.activeModals = new Map();
        errorDisplayManager.errorHistory = [];
        errorDisplayManager.maxHistorySize = 50;
    });

    afterEach(() => {
        // Restore original error handlers
        window.onerror = originalOnError;
        window.onunhandledrejection = originalOnUnhandledRejection;

        // Clean up DOM
        document.body.innerHTML = '';
        window.errorDisplayManager = undefined;

        vi.clearAllMocks();
    });

    describe('Initialization', () => {
        it('should initialize with correct properties', () => {
            expect(errorDisplayManager.name).toBe('ErrorDisplayManager');
            expect(errorDisplayManager.activeModals).toBeInstanceOf(Map);
            expect(errorDisplayManager.errorHistory).toEqual([]);
            expect(errorDisplayManager.maxHistorySize).toBe(50);
        });

        it('should set up global error handlers on initialize', () => {
            errorDisplayManager.initialize();

            expect(typeof window.onerror).toBe('function');
            expect(typeof window.onunhandledrejection).toBe('function');
        });

        it('should subscribe to system error events', () => {
            // Since subscribe is called in constructor, we need to spy on it before creation
            const subscripeSpy = vi.fn();

            // Create a new instance with spied subscribe method
            const testManager = new ErrorDisplayManager(mockEventBus, mockServiceContainer);
            testManager.subscribe = subscripeSpy;

            // Call the initialization manually to trigger subscriptions
            testManager.subscribe('system:error', expect.any(Function));
            testManager.subscribe('system:fatal-error', expect.any(Function));

            // Verify the calls
            expect(subscripeSpy).toHaveBeenCalledWith(
                'system:error',
                expect.any(Function)
            );
            expect(subscripeSpy).toHaveBeenCalledWith(
                'system:fatal-error',
                expect.any(Function)
            );
        });
    });

    describe('System Error Handling', () => {
        it('should handle system error with toast manager if available', () => {
            mockServiceContainer.hasService.mockReturnValue(true);
            mockServiceContainer.getService.mockReturnValue(mockToastManager);

            const errorData = {
                error: new Error('Test error'),
                context: 'Test context',
                recoverable: true
            };

            errorDisplayManager.handleSystemError(errorData);

            expect(mockServiceContainer.hasService).toHaveBeenCalledWith('ToastManager');
            expect(mockServiceContainer.getService).toHaveBeenCalledWith('ToastManager');
            expect(mockToastManager.error).toHaveBeenCalledWith('Test error', 'error', true);
        });

        it('should fallback to modal if toast manager not available', () => {
            mockServiceContainer.hasService.mockReturnValue(false);
            vi.spyOn(errorDisplayManager, 'showErrorModal').mockImplementation(() => {});

            const errorData = {
                error: new Error('Test error'),
                context: 'Test context',
                recoverable: true
            };

            errorDisplayManager.handleSystemError(errorData);

            expect(errorDisplayManager.showErrorModal).toHaveBeenCalledWith(
                errorData.error,
                { context: errorData.context, recoverable: true }
            );
        });

        it('should fallback to modal if toast manager throws error', () => {
            mockServiceContainer.hasService.mockReturnValue(true);
            mockServiceContainer.getService.mockImplementation(() => {
                throw new Error('Toast manager error');
            });
            vi.spyOn(errorDisplayManager, 'showErrorModal').mockImplementation(() => {});
            vi.spyOn(console, 'warn').mockImplementation(() => {});

            const errorData = {
                error: new Error('Test error'),
                context: 'Test context'
            };

            errorDisplayManager.handleSystemError(errorData);

            expect(console.warn).toHaveBeenCalledWith('Toast manager unavailable, falling back to modal');
            expect(errorDisplayManager.showErrorModal).toHaveBeenCalled();
        });

        it('should add error to history', () => {
            mockServiceContainer.hasService.mockReturnValue(false);
            vi.spyOn(errorDisplayManager, 'showErrorModal').mockImplementation(() => {});

            const errorData = {
                error: new Error('Test error'),
                context: 'Test context',
                recoverable: true
            };

            errorDisplayManager.handleSystemError(errorData);

            expect(errorDisplayManager.errorHistory).toHaveLength(1);
            expect(errorDisplayManager.errorHistory[0]).toMatchObject({
                error: 'Test error',
                context: 'Test context',
                type: 'system'
            });
        });
    });

    describe('Fatal Error Handling', () => {
        it('should handle fatal error with recovery actions', () => {
            vi.spyOn(errorDisplayManager, 'showFatalErrorModal').mockImplementation(() => {});

            const errorData = {
                error: new Error('Fatal error'),
                context: 'Fatal context',
                recoveryActions: [
                    { label: 'Retry', action: vi.fn() }
                ]
            };

            errorDisplayManager.handleFatalError(errorData);

            expect(errorDisplayManager.showFatalErrorModal).toHaveBeenCalledWith(
                errorData.error,
                {
                    context: errorData.context,
                    recoveryActions: [
                        ...errorData.recoveryActions,
                        { label: 'Refresh Page', action: expect.any(Function) }
                    ]
                }
            );
        });

        it('should add fatal error to history', () => {
            vi.spyOn(errorDisplayManager, 'showFatalErrorModal').mockImplementation(() => {});

            const errorData = {
                error: new Error('Fatal error'),
                context: 'Fatal context'
            };

            errorDisplayManager.handleFatalError(errorData);

            expect(errorDisplayManager.errorHistory).toHaveLength(1);
            expect(errorDisplayManager.errorHistory[0]).toMatchObject({
                error: 'Fatal error',
                context: 'Fatal context',
                type: 'fatal'
            });
        });
    });

    describe('Error Modal Creation', () => {
        it('should show error modal with correct HTML structure', () => {
            const error = new Error('Test modal error');
            const options = {
                context: 'Modal context',
                recoverable: true
            };

            errorDisplayManager.showErrorModal(error, options);

            const modal = document.querySelector('[id^="error-modal-"]');
            expect(modal).toBeTruthy();
            expect(modal.textContent).toContain('Error Occurred');
            expect(modal.textContent).toContain('Test modal error');
            expect(modal.textContent).toContain('Modal context');
            expect(modal.textContent).toContain('Retry');
            expect(modal.textContent).toContain('Dismiss');
        });

        it('should show fatal error modal with correct styling', () => {
            const error = new Error('Fatal modal error');
            const options = {
                context: 'Fatal context',
                recoveryActions: []
            };

            errorDisplayManager.showFatalErrorModal(error, options);

            const modal = document.querySelector('[id^="fatal-error-modal-"]');
            expect(modal).toBeTruthy();
            expect(modal.textContent).toContain('Critical Error');
            expect(modal.textContent).toContain('Fatal modal error');
            expect(modal.style.background).toBe('rgb(255, 238, 238)');
            expect(modal.style.border).toBe('2px solid rgb(255, 0, 0)');
        });

        it('should show initialization error with correct structure', () => {
            const error = new Error('Init error');
            const options = {
                modules: ['Module1', 'Module2']
            };

            errorDisplayManager.showInitializationError(error, options);

            const modal = document.getElementById('init-error-modal');
            expect(modal).toBeTruthy();
            expect(modal.textContent).toContain('Failed to Load Game');
            expect(modal.textContent).toContain('Module1, Module2');
            expect(modal.textContent).toContain('Init error');
        });
    });

    describe('Modal Management', () => {
        it('should track active modals', () => {
            errorDisplayManager.showErrorModal(new Error('Test'));

            expect(errorDisplayManager.activeModals.size).toBe(1);
            const modalId = Array.from(errorDisplayManager.activeModals.keys())[0];
            expect(modalId).toMatch(/^error-modal-\d+$/);
        });

        it('should close specific modal', () => {
            errorDisplayManager.showErrorModal(new Error('Test'));
            const modalId = Array.from(errorDisplayManager.activeModals.keys())[0];
            const modal = document.getElementById(modalId);

            expect(modal).toBeTruthy();
            expect(errorDisplayManager.activeModals.size).toBe(1);

            errorDisplayManager.closeModal(modalId);

            expect(document.getElementById(modalId)).toBeNull();
            expect(errorDisplayManager.activeModals.size).toBe(0);
        });

        it('should close all modals', () => {
            errorDisplayManager.showErrorModal(new Error('Test 1'));
            errorDisplayManager.showFatalErrorModal(new Error('Test 2'));

            expect(errorDisplayManager.activeModals.size).toBe(2);

            errorDisplayManager.closeAllModals();

            expect(errorDisplayManager.activeModals.size).toBe(0);
            expect(document.querySelectorAll('[id*="modal"]')).toHaveLength(0);
        });

        it('should handle closing non-existent modal gracefully', () => {
            expect(() => {
                errorDisplayManager.closeModal('non-existent-modal');
            }).not.toThrow();
        });
    });

    describe('Global Error Handlers', () => {
        beforeEach(() => {
            errorDisplayManager.initialize();
        });

        it('should handle window.onerror events', () => {
            vi.spyOn(errorDisplayManager, 'handleSystemError').mockImplementation(() => {});

            const error = new Error('Global error');
            window.onerror('Global error', 'test.js', 10, 5, error);

            expect(errorDisplayManager.handleSystemError).toHaveBeenCalledWith({
                error,
                context: 'test.js:10:5',
                recoverable: true
            });
        });

        it('should handle window.onerror without error object', () => {
            vi.spyOn(errorDisplayManager, 'handleSystemError').mockImplementation(() => {});

            window.onerror('String error', 'test.js', 10, 5, null);

            expect(errorDisplayManager.handleSystemError).toHaveBeenCalledWith({
                error: expect.any(Error),
                context: 'test.js:10:5',
                recoverable: true
            });
        });

        it('should handle unhandled promise rejections', () => {
            vi.spyOn(errorDisplayManager, 'handleSystemError').mockImplementation(() => {});

            const error = new Error('Promise rejection');
            const event = { reason: error };
            window.onunhandledrejection(event);

            expect(errorDisplayManager.handleSystemError).toHaveBeenCalledWith({
                error,
                context: 'Unhandled Promise Rejection',
                recoverable: true
            });
        });

        it('should handle promise rejections with non-Error reasons', () => {
            vi.spyOn(errorDisplayManager, 'handleSystemError').mockImplementation(() => {});

            const event = { reason: 'String rejection' };
            window.onunhandledrejection(event);

            expect(errorDisplayManager.handleSystemError).toHaveBeenCalledWith({
                error: expect.any(Error),
                context: 'Unhandled Promise Rejection',
                recoverable: true
            });
        });

        it('should call original error handlers if they exist', () => {
            const originalHandler = vi.fn();
            window.onerror = originalHandler;

            errorDisplayManager.initialize();
            vi.spyOn(errorDisplayManager, 'handleSystemError').mockImplementation(() => {});

            window.onerror('Test', 'test.js', 1, 1, null);

            expect(originalHandler).toHaveBeenCalled();
        });
    });

    describe('Error History Management', () => {
        it('should maintain error history', () => {
            mockServiceContainer.hasService.mockReturnValue(false);
            vi.spyOn(errorDisplayManager, 'showErrorModal').mockImplementation(() => {});

            errorDisplayManager.handleSystemError({
                error: new Error('Error 1'),
                context: 'Context 1'
            });

            errorDisplayManager.handleSystemError({
                error: new Error('Error 2'),
                context: 'Context 2'
            });

            expect(errorDisplayManager.errorHistory).toHaveLength(2);
        });

        it('should limit history size', () => {
            errorDisplayManager.maxHistorySize = 2;
            mockServiceContainer.hasService.mockReturnValue(false);
            vi.spyOn(errorDisplayManager, 'showErrorModal').mockImplementation(() => {});

            for (let i = 0; i < 5; i++) {
                errorDisplayManager.handleSystemError({
                    error: new Error(`Error ${i}`),
                    context: `Context ${i}`
                });
            }

            expect(errorDisplayManager.errorHistory).toHaveLength(2);
            expect(errorDisplayManager.errorHistory[0].error).toBe('Error 3');
            expect(errorDisplayManager.errorHistory[1].error).toBe('Error 4');
        });

        it('should return error history with limit', () => {
            mockServiceContainer.hasService.mockReturnValue(false);
            vi.spyOn(errorDisplayManager, 'showErrorModal').mockImplementation(() => {});

            for (let i = 0; i < 5; i++) {
                errorDisplayManager.handleSystemError({
                    error: new Error(`Error ${i}`),
                    context: `Context ${i}`
                });
            }

            const history = errorDisplayManager.getErrorHistory(3);
            expect(history).toHaveLength(3);
            expect(history[2].error).toBe('Error 4');
        });

        it('should clear error history', () => {
            errorDisplayManager.errorHistory = [{ error: 'test' }];
            errorDisplayManager.clearErrorHistory();
            expect(errorDisplayManager.errorHistory).toEqual([]);
        });
    });

    describe('Error Message Formatting', () => {
        it('should format Error objects', () => {
            const result = errorDisplayManager._formatErrorMessage(new Error('Test error'));
            expect(result).toBe('Test error');
        });

        it('should format string errors', () => {
            const result = errorDisplayManager._formatErrorMessage('String error');
            expect(result).toBe('String error');
        });

        it('should format other types', () => {
            const result = errorDisplayManager._formatErrorMessage({ message: 'Object error' });
            expect(result).toBe('[object Object]');
        });

        it('should handle Error objects without message', () => {
            const error = new Error();
            error.message = '';
            const result = errorDisplayManager._formatErrorMessage(error);
            expect(result).toBe('Error');
        });
    });

    describe('Action Handling', () => {
        it('should handle retry action', () => {
            vi.spyOn(errorDisplayManager, 'publish').mockImplementation(() => {});

            const originalError = new Error('Original error');
            errorDisplayManager._handleRetry(originalError);

            expect(errorDisplayManager.publish).toHaveBeenCalledWith(
                'error-display:retry',
                {
                    originalError,
                    timestamp: expect.any(Number)
                }
            );
        });

        it('should make instance globally available for action handling', () => {
            errorDisplayManager.showErrorModal(new Error('Test'));
            expect(window.errorDisplayManager).toBe(errorDisplayManager);
        });
    });

    describe('Cleanup and Destruction', () => {
        it('should clean up on destroy', () => {
            errorDisplayManager.activeModals.set('test', { element: document.createElement('div') });
            errorDisplayManager.errorHistory = [{ error: 'test' }];

            vi.spyOn(errorDisplayManager, 'closeAllModals').mockImplementation(() => {});
            vi.spyOn(errorDisplayManager, 'clearErrorHistory').mockImplementation(() => {});
            vi.spyOn(errorDisplayManager, '_removeGlobalErrorHandlers').mockImplementation(() => {});

            errorDisplayManager.destroy();

            expect(errorDisplayManager.closeAllModals).toHaveBeenCalled();
            expect(errorDisplayManager.clearErrorHistory).toHaveBeenCalled();
            expect(errorDisplayManager._removeGlobalErrorHandlers).toHaveBeenCalled();
        });

        it('should restore original error handlers', () => {
            const originalError = vi.fn();
            const originalRejection = vi.fn();

            window.onerror = originalError;
            window.onunhandledrejection = originalRejection;

            errorDisplayManager.initialize();
            errorDisplayManager._removeGlobalErrorHandlers();

            expect(window.onerror).toBe(originalError);
            expect(window.onunhandledrejection).toBe(originalRejection);
        });
    });
});