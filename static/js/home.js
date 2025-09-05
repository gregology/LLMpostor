/**
 * LLMposter Home Page JavaScript
 * 
 * Handles room joining, quick join functionality, and form interactions
 * on the home page. Extracted from inline script in index.html template.
 */

(function() {
    'use strict';
    
    /**
     * Home page controller
     */
    class HomePageController {
        constructor() {
            this.elements = {};
            this.isLoading = false;
            
            // Initialize when DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.initialize());
            } else {
                this.initialize();
            }
        }
        
        initialize() {
            console.log('Initializing home page controller');
            this._cacheElements();
            this._setupEventListeners();
            this._setupInitialState();
        }
        
        _cacheElements() {
            this.elements = {
                joinRoomForm: document.getElementById('joinRoomForm'),
                playerNameInput: document.getElementById('playerName'),
                roomInput: document.getElementById('roomInput'),
                quickJoinBtn: document.getElementById('quickJoinBtn')
            };
        }
        
        _setupEventListeners() {
            // Join room form submission
            if (this.elements.joinRoomForm) {
                this.elements.joinRoomForm.addEventListener('submit', (e) => {
                    this._handleJoinRoomSubmit(e);
                });
            }
            
            // Quick join button
            if (this.elements.quickJoinBtn) {
                this.elements.quickJoinBtn.addEventListener('click', () => {
                    this._handleQuickJoin();
                });
            }
            
            // Enter key handling for inputs
            if (this.elements.playerNameInput) {
                this.elements.playerNameInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        this.elements.roomInput?.focus();
                    }
                });
            }
            
            if (this.elements.roomInput) {
                this.elements.roomInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        this.elements.joinRoomForm?.requestSubmit();
                    }
                });
            }
        }
        
        _setupInitialState() {
            // Auto-focus first input
            if (this.elements.playerNameInput) {
                this.elements.playerNameInput.focus();
            }
            
            // Pre-fill player name from session storage
            const storedName = sessionStorage.getItem('playerName');
            if (storedName && this.elements.playerNameInput) {
                this.elements.playerNameInput.value = storedName;
                // Focus room input if name is already filled
                if (this.elements.roomInput) {
                    this.elements.roomInput.focus();
                }
            }
        }
        
        async _handleJoinRoomSubmit(e) {
            e.preventDefault();
            
            if (this.isLoading) return;
            
            const playerName = this.elements.playerNameInput?.value?.trim();
            const roomName = this.elements.roomInput?.value?.trim();
            
            if (!this._validateInputs(playerName, roomName)) {
                return;
            }
            
            try {
                this._setFormLoading(true);
                
                // Store player name for future use
                sessionStorage.setItem('playerName', playerName);
                
                // Small delay for UX (loading state visibility)
                await this._delay(300);
                
                // Navigate to room
                const encodedRoomName = encodeURIComponent(roomName);
                window.location.href = `/${encodedRoomName}`;
                
            } catch (error) {
                console.error('Error joining room:', error);
                this._showError('Failed to join room. Please try again.');
                this._setFormLoading(false);
            }
        }
        
        async _handleQuickJoin() {
            if (this.isLoading) return;
            
            const playerName = this.elements.playerNameInput?.value?.trim();
            
            if (!playerName) {
                this._showError('Please enter your name first');
                this.elements.playerNameInput?.focus();
                return;
            }
            
            if (!this._validatePlayerName(playerName)) {
                return;
            }
            
            try {
                this._setQuickJoinLoading(true);
                
                console.log('Finding available room...');
                
                // Try to find an available room
                const response = await fetch('/api/find-available-room');
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                console.log('Find room API response:', data);
                
                if (data.room_id) {
                    // Found a room with players waiting
                    console.log('Found available room:', data.room_id);
                    sessionStorage.setItem('playerName', playerName);
                    window.location.href = `/${encodeURIComponent(data.room_id)}`;
                } else {
                    // No available rooms, create a new one
                    console.log('No available rooms found, creating new room');
                    this._createRandomRoom(playerName);
                }
                
            } catch (error) {
                console.error('Error in quick join:', error);
                
                // Fallback: create random room
                console.log('Quick join failed, falling back to random room creation');
                this._createRandomRoom(playerName);
            }
        }
        
        _createRandomRoom(playerName) {
            try {
                // Generate random room name
                const randomRoom = 'room-' + Math.random().toString(36).substr(2, 6);
                console.log('Creating random room:', randomRoom);
                
                sessionStorage.setItem('playerName', playerName);
                window.location.href = `/${encodeURIComponent(randomRoom)}`;
                
            } catch (error) {
                console.error('Failed to create random room:', error);
                this._showError('Failed to create room. Please try manually joining a room.');
                this._setQuickJoinLoading(false);
            }
        }
        
        _validateInputs(playerName, roomName) {
            if (!this._validatePlayerName(playerName)) {
                return false;
            }
            
            if (!roomName) {
                this._showError('Please enter a room name');
                this.elements.roomInput?.focus();
                return false;
            }
            
            if (roomName.length > 30) {
                this._showError('Room name is too long (max 30 characters)');
                this.elements.roomInput?.focus();
                return false;
            }
            
            // Basic validation for room name (alphanumeric, hyphens, underscores)
            if (!/^[a-zA-Z0-9_-]+$/.test(roomName)) {
                this._showError('Room name can only contain letters, numbers, hyphens, and underscores');
                this.elements.roomInput?.focus();
                return false;
            }
            
            return true;
        }
        
        _validatePlayerName(playerName) {
            if (!playerName) {
                this._showError('Please enter your name');
                this.elements.playerNameInput?.focus();
                return false;
            }
            
            if (playerName.length > 20) {
                this._showError('Player name is too long (max 20 characters)');
                this.elements.playerNameInput?.focus();
                return false;
            }
            
            return true;
        }
        
        _setFormLoading(loading) {
            this.isLoading = loading;
            
            const submitBtn = this.elements.joinRoomForm?.querySelector('button[type="submit"]');
            if (!submitBtn) return;
            
            const btnText = submitBtn.querySelector('.btn-text');
            const btnLoading = submitBtn.querySelector('.btn-loading');
            
            if (loading) {
                btnText?.classList.add('hidden');
                btnLoading?.classList.remove('hidden');
                submitBtn.disabled = true;
            } else {
                btnText?.classList.remove('hidden');
                btnLoading?.classList.add('hidden');
                submitBtn.disabled = false;
            }
        }
        
        _setQuickJoinLoading(loading) {
            if (!this.elements.quickJoinBtn) return;
            
            if (loading) {
                this.elements.quickJoinBtn.disabled = true;
                this.elements.quickJoinBtn.textContent = 'Finding Room...';
            } else {
                this.elements.quickJoinBtn.disabled = false;
                this.elements.quickJoinBtn.textContent = 'Join Random Room';
            }
        }
        
        _showError(message) {
            // Create or update error display
            let errorDiv = document.getElementById('homePageError');
            
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.id = 'homePageError';
                errorDiv.style.cssText = `
                    position: fixed;
                    top: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #fee;
                    color: #c00;
                    padding: 12px 20px;
                    border: 1px solid #fcc;
                    border-radius: 6px;
                    font-size: 14px;
                    z-index: 1000;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                    max-width: 400px;
                    text-align: center;
                `;
                document.body.appendChild(errorDiv);
            }
            
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                if (errorDiv && errorDiv.parentNode) {
                    errorDiv.style.display = 'none';
                }
            }, 5000);
        }
        
        _delay(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
    }
    
    // Initialize home page controller
    new HomePageController();
    
})();