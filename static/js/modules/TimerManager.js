/**
 * TimerManager - Handles all timer functionality
 * 
 * Responsible for:
 * - Phase timer management
 * - Timer UI updates
 * - Timer synchronization with server
 * - Timer warning notifications
 */

class TimerManager {
    constructor() {
        this.activeTimers = new Map();
        this.timers = this.activeTimers; // Backward compatibility
        this.onTimerUpdate = null;
        this.onTimerWarning = null;
    }
    
    /**
     * Start a new timer for a phase
     * @param {string} phase - Phase name (response, guessing, results)
     * @param {number} duration - Duration in seconds
     */
    startTimer(phase, duration) {
        console.log('Starting timer for phase:', phase, 'duration:', duration);
        
        if (duration === undefined || duration === null || isNaN(duration)) {
            console.warn('startTimer called with invalid duration:', duration);
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
            }
        }, 1000);
        
        this.timers.set(phase, interval);
        
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
        if (this.timers.has(phase)) {
            this._updateTimer(phase, timeRemaining, totalDuration);
        }
    }
    
    /**
     * Clear timer for specific phase
     * @param {string} phase - Phase name
     */
    clearTimer(phase) {
        const interval = this.timers.get(phase);
        if (interval) {
            clearInterval(interval);
            this.timers.delete(phase);
        }
    }
    
    /**
     * Clear all active timers
     */
    clearAllTimers() {
        for (const [phase] of this.timers) {
            this.clearTimer(phase);
        }
    }
    
    /**
     * Check if timer exists for phase
     * @param {string} phase - Phase name
     * @returns {boolean} Whether timer exists
     */
    hasTimer(phase) {
        return this.timers.has(phase);
    }
    
    /**
     * Get all active timer phases
     * @returns {Array<string>} Active timer phases
     */
    getActiveTimers() {
        return Array.from(this.timers.keys());
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

    // Private methods for testing compatibility
    _calculateProgress(timeRemaining, totalDuration) {
        if (!totalDuration || totalDuration <= 0) {
            return 0;
        }
        
        // Allow progress over 100% for cases where timeRemaining > totalDuration
        return Math.max(0, (timeRemaining / totalDuration) * 100);
    }

    _formatTime(seconds) {
        if (isNaN(seconds) || seconds < 0) {
            seconds = 0;
        }
        
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    _getProgressColor(progress) {
        if (progress <= 20) {
            return '#ef4444'; // red
        } else if (progress <= 50) {
            return '#f59e0b'; // orange  
        } else {
            return '#10b981'; // green
        }
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
    
    // Private methods
    
    _updateTimer(phase, timeRemaining, totalDuration) {
        if (this.onTimerUpdate) {
            const progress = this.calculateProgress(timeRemaining, totalDuration);
            this.onTimerUpdate({
                phase,
                timeText: this.formatTime(timeRemaining),
                progress: Math.round(progress * 100) / 100, // Round to 2 decimal places
                progressColor: this._getProgressColor(progress)
            });
        }
    }
    
    _triggerWarning(phase, timeRemaining) {
        if (this.onTimerWarning) {
            let message;
            if (timeRemaining === 30) {
                message = '30 seconds remaining!';
            } else if (timeRemaining === 10) {
                message = '10 seconds remaining!';
            }
            
            this.onTimerWarning({
                phase,
                message
            });
        }
    }
}

// Export for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TimerManager;
}