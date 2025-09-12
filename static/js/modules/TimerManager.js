/**
 * TimerManager - Event-driven timer management system
 * 
 * Responsible for:
 * - Phase timer management
 * - Event-based timer notifications
 * - Timer synchronization with server
 * - Timer warning notifications
 * 
 * Migration Status: Updated to use EventBus with backward compatibility
 */

import { EventBusModule, migrationHelper } from './EventBusMigration.js';
import { Events } from './EventBus.js';

class TimerManager extends EventBusModule {
    constructor() {
        super('TimerManager');
        
        this.activeTimers = new Map();
        
        // Legacy callback support (for gradual migration)
        this.onTimerUpdate = null;
        this.onTimerWarning = null;
        
        // Subscribe to game events to start appropriate timers
        this.subscribe(Events.GAME.ROUND_STARTED, this._handleRoundStarted.bind(this));
        this.subscribe(Events.GAME.GUESSING_STARTED, this._handleGuessingStarted.bind(this));
        this.subscribe(Events.GAME.RESULTS_STARTED, this._handleResultsStarted.bind(this));
        this.subscribe(Events.GAME.PHASE_CHANGED, this._handlePhaseChanged.bind(this));
        
        console.log('TimerManager initialized with EventBus integration');
    }
    
    /**
     * Start a new timer for a phase
     * @param {string} phase - Phase name (response, guessing, results)
     * @param {number} duration - Duration in seconds
     * @param {Function} callback - Legacy callback (optional)
     */
    startTimer(phase, duration, callback = null) {
        console.log('Starting timer for phase:', phase, 'duration:', duration);
        
        if (duration === undefined || duration === null || isNaN(duration)) {
            console.warn('startTimer called with invalid duration:', duration);
            this.publish(Events.SYSTEM.ERROR, {
                source: 'TimerManager',
                error: 'Invalid timer duration',
                phase,
                duration
            });
            return;
        }
        
        this.clearTimer(phase);
        
        const startTime = Date.now();
        const endTime = startTime + (duration * 1000);
        
        const interval = setInterval(() => {
            const now = Date.now();
            const remaining = Math.max(0, Math.ceil((endTime - now) / 1000));
            
            this._updateTimer(phase, remaining, duration);
            
            // Check for warnings at 30 seconds and 10 seconds
            if (remaining === 30 || remaining === 10) {
                this._triggerWarning(phase, remaining);
            }
            
            if (remaining <= 0) {
                this.clearTimer(phase);
                this._handleTimerExpired(phase);
                if (callback) callback();
            }
        }, 1000);
        
        this.activeTimers.set(phase, interval);
        
        // Publish timer started event
        this.publish(Events.TIMER.STARTED, {
            phase,
            duration,
            startTime
        });
        
        // Initial update
        this._updateTimer(phase, duration, duration);
    }
    
    /**
     * Update timer with server-provided data
     * @param {string} phase - Phase name
     * @param {number} timeRemaining - Time remaining in seconds
     * @param {number} totalDuration - Total phase duration
     */
    updateTimer(phase, timeRemaining, totalDuration) {
        if (timeRemaining === undefined || timeRemaining === null || isNaN(timeRemaining)) {
            console.warn('updateTimer called with invalid timeRemaining:', timeRemaining);
            timeRemaining = 0;
        }
        
        // Only update if timer exists for this phase
        if (this.activeTimers.has(phase)) {
            this._updateTimer(phase, timeRemaining, totalDuration);
        }
    }
    
    /**
     * Clear timer for specific phase
     * @param {string} phase - Phase name
     */
    clearTimer(phase) {
        const interval = this.activeTimers.get(phase);
        if (interval) {
            clearInterval(interval);
            this.activeTimers.delete(phase);
            
            this.publish(Events.TIMER.STOPPED, {
                phase,
                reason: 'manually_cleared'
            });
        }
    }
    
    /**
     * Clear all active timers
     */
    clearAllTimers() {
        const phases = Array.from(this.activeTimers.keys());
        
        for (const phase of phases) {
            this.clearTimer(phase);
        }
        
        this.publish(Events.TIMER.STOPPED, {
            phase: 'all',
            reason: 'all_cleared',
            clearedPhases: phases
        });
    }
    
    /**
     * Check if timer exists for phase
     * @param {string} phase - Phase name
     * @returns {boolean} Whether timer exists
     */
    hasTimer(phase) {
        return this.activeTimers.has(phase);
    }
    
    /**
     * Get all active timer phases
     * @returns {Array<string>} Active timer phases
     */
    getActiveTimers() {
        return Array.from(this.activeTimers.keys());
    }
    
    /**
     * Format time for display
     * @param {number} seconds - Time in seconds
     * @returns {string} Formatted time string (M:SS)
     */
    formatTime(seconds) {
        if (isNaN(seconds) || seconds < 0) {
            seconds = 0;
        }
        
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
    
    /**
     * Calculate progress percentage
     * @param {number} timeRemaining - Time remaining in seconds
     * @param {number} totalDuration - Total duration in seconds
     * @returns {number} Progress percentage (0-100)
     */
    calculateProgress(timeRemaining, totalDuration) {
        if (!totalDuration || totalDuration <= 0) {
            return 0;
        }
        
        return Math.max(0, Math.min(100, (timeRemaining / totalDuration) * 100));
    }
    
    /**
     * Get progress bar color based on remaining time
     * @param {number} progressPercent - Progress percentage
     * @returns {string} CSS color value
     */
    getProgressColor(progressPercent) {
        if (progressPercent <= 25) {
            return '#ef4444'; // red
        } else if (progressPercent <= 50) {
            return '#f59e0b'; // orange
        } else {
            return '#10b981'; // green
        }
    }
    
    // Event handlers for game state changes
    
    _handleRoundStarted(data) {
        if (data && data.phase_duration) {
            this.startTimer('response', data.phase_duration);
        }
    }
    
    _handleGuessingStarted(data) {
        if (data && data.phase_duration) {
            this.startTimer('guessing', data.phase_duration);
        }
    }
    
    _handleResultsStarted(data) {
        const resultsDuration = data?.phase_duration || 30; // Default 30 seconds for results
        this.startTimer('results', resultsDuration);
    }
    
    _handlePhaseChanged(data) {
        if (!data || !data.newPhase) return;
        
        const { newPhase, oldPhase } = data;
        
        // Clear old phase timer
        if (oldPhase) {
            this.clearTimer(oldPhase);
        }
        
        // Start new phase timer if duration provided
        if (data.duration) {
            this.startTimer(newPhase, data.duration);
        }
    }
    
    _handleTimerExpired(phase) {
        console.log(`Timer expired for phase: ${phase}`);
        
        this.publish(Events.TIMER.EXPIRED, {
            phase,
            expiredAt: Date.now()
        });
    }
    
    // Private methods
    
    _updateTimer(phase, timeRemaining, totalDuration) {
        const progress = this.calculateProgress(timeRemaining, totalDuration);
        const timerData = {
            phase,
            timeRemaining,
            totalDuration,
            timeText: this.formatTime(timeRemaining),
            progress: Math.round(progress * 100) / 100, // Round to 2 decimal places
            progressColor: this.getProgressColor(progress),
            timestamp: Date.now()
        };
        
        // Modern event-based approach
        this.publish(Events.TIMER.UPDATED, timerData);
        
        // Legacy callback support (for gradual migration)
        migrationHelper.execute(
            'timer-updates',
            // Old pattern
            () => {
                if (this.onTimerUpdate) {
                    this.onTimerUpdate(timerData);
                }
            },
            // New pattern (events already published above)
            () => {
                // Events already published - this is just for dual-mode support
            },
            timerData
        );
    }
    
    _triggerWarning(phase, timeRemaining) {
        let message;
        if (timeRemaining === 30) {
            message = '30 seconds remaining!';
        } else if (timeRemaining === 10) {
            message = '10 seconds remaining!';
        }
        
        const warningData = {
            phase,
            timeRemaining,
            message,
            severity: timeRemaining <= 10 ? 'high' : 'medium',
            timestamp: Date.now()
        };
        
        // Modern event-based approach
        this.publish(Events.TIMER.WARNING, warningData);
        
        // Legacy callback support
        migrationHelper.execute(
            'timer-warnings',
            // Old pattern
            () => {
                if (this.onTimerWarning) {
                    this.onTimerWarning(warningData);
                }
            },
            // New pattern (events already published)
            () => {
                // Events already published
            },
            warningData
        );
    }
    
    /**
     * Clean up all timers and subscriptions
     */
    destroy() {
        this.clearAllTimers();
        this.cleanup(); // Clean up event subscriptions
    }
}


export default TimerManager;