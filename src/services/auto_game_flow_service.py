"""
Auto Game Flow Service - Manages automatic phase transitions and timing.

This service handles:
- Phase timeouts and automatic advancement
- Countdown broadcasting and time warnings  
- Room cleanup for inactive sessions
- Game state synchronization during phase changes
"""

import logging
import threading
import time
from typing import Dict
from src.services.room_state_presenter import RoomStatePresenter

logger = logging.getLogger(__name__)


class AutoGameFlowService:
    """Manages automatic phase transitions and timing for game rooms."""
    
    def __init__(self, broadcast_service, game_manager, room_manager):
        """Initialize the auto game flow service.
        
        Args:
            broadcast_service: Service for broadcasting messages to rooms
            game_manager: Game state management service
            room_manager: Room management service
        """
        self.broadcast_service = broadcast_service
        self.game_manager = game_manager
        self.room_manager = room_manager
        self.running = True
        self.check_interval = 1  # Check every second
        
        # Initialize room state presenter for consistent timeout phase broadcasts
        self.room_state_presenter = RoomStatePresenter(game_manager)
        
        # Start background thread for automatic phase management
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        
        logger.info("AutoGameFlowService started")
    
    def stop(self):
        """Stop the automatic game flow service."""
        self.running = False
        if self.timer_thread.is_alive():
            self.timer_thread.join(timeout=2)
        logger.info("AutoGameFlowService stopped")
    
    def _timer_loop(self):
        """Main timer loop that checks for phase transitions."""
        last_countdown_broadcast = {}  # room_id -> last_broadcast_time
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check for phase timeouts
                self._check_phase_timeouts()
                
                # Broadcast countdown updates (every 10 seconds for active phases)
                self._broadcast_countdown_updates(current_time, last_countdown_broadcast)
                
                # Clean up inactive rooms (less frequently)
                if int(current_time) % 60 == 0:  # Every minute
                    self._cleanup_inactive_rooms()
                
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in timer loop: {e}")
                time.sleep(self.check_interval)
    
    def _broadcast_countdown_updates(self, current_time: float, last_broadcast: Dict[str, float]):
        """Broadcast countdown updates to active rooms."""
        room_ids = self.room_manager.get_all_rooms()
        
        for room_id in room_ids:
            try:
                # Only broadcast every 10 seconds to avoid spam
                if room_id in last_broadcast and current_time - last_broadcast[room_id] < 10:
                    continue
                
                room_state = self.room_manager.get_room_state(room_id)
                if not room_state:
                    continue
                
                game_state = room_state["game_state"]
                current_phase = game_state["phase"]
                
                # Only broadcast for timed phases
                if current_phase in ["responding", "guessing"]:
                    time_remaining = self.game_manager.get_phase_time_remaining(room_id)
                    
                    # Broadcast countdown update
                    countdown_data = {
                        'phase': current_phase,
                        'time_remaining': time_remaining,
                        'phase_duration': game_state.get('phase_duration', 0)
                    }
                    
                    self.broadcast_service.emit_to_room('countdown_update', countdown_data, room_id)
                    last_broadcast[room_id] = current_time
                    
                    # Special warnings for low time
                    if time_remaining <= 30 and time_remaining > 25:
                        self.broadcast_service.emit_to_room('time_warning', {
                            'message': '30 seconds remaining!',
                            'time_remaining': time_remaining
                        }, room_id)
                    elif time_remaining <= 10 and time_remaining > 5:
                        self.broadcast_service.emit_to_room('time_warning', {
                            'message': '10 seconds remaining!',
                            'time_remaining': time_remaining
                        }, room_id)
                
            except Exception as e:
                logger.error(f"Error broadcasting countdown for room {room_id}: {e}")
    
    def _check_phase_timeouts(self):
        """Check all active rooms for phase timeouts and advance if needed."""
        room_ids = self.room_manager.get_all_rooms()
        
        for room_id in room_ids:
            try:
                is_expired = self.game_manager.is_phase_expired(room_id)
                if is_expired:
                    logger.info(f"Phase expired for room {room_id}, handling timeout")
                    self._handle_phase_timeout(room_id)
            except Exception as e:
                logger.error(f"Error checking phase timeout for room {room_id}: {e}")
    
    def _handle_phase_timeout(self, room_id: str):
        """Handle phase timeout by advancing to next phase."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            current_phase = room_state["game_state"]["phase"]
            logger.info(f"Phase timeout in room {room_id}, current phase: {current_phase}")
            
            # Advance phase
            new_phase = self.game_manager.advance_game_phase(room_id)
            
            if new_phase != current_phase:
                logger.info(f"Advanced room {room_id} from {current_phase} to {new_phase}")
                
                # Broadcast phase change to all players in room
                if new_phase == "guessing":
                    self._broadcast_guessing_phase_timeout_started(room_id)
                elif new_phase == "results":
                    self._broadcast_results_phase_timeout_started(room_id)
                elif new_phase == "waiting":
                    self._broadcast_round_ended(room_id)
                
                # Always broadcast room state update
                self.broadcast_service.broadcast_room_state_update(room_id)
                
        except Exception as e:
            logger.error(f"Error handling phase timeout for room {room_id}: {e}")
    
    def _cleanup_inactive_rooms(self):
        """Clean up rooms that have been inactive for too long."""
        try:
            # Clean up rooms inactive for more than 1 hour
            cleaned_count = self.room_manager.cleanup_inactive_rooms(max_inactive_minutes=60)
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive rooms")
        except Exception as e:
            logger.error(f"Error cleaning up inactive rooms: {e}")
    
    def _broadcast_guessing_phase_timeout_started(self, room_id: str):
        """Broadcast guessing phase start with timeout notification."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            # Use presenter to create consistent guessing phase data (no player filtering for timeout)
            guessing_info = self.room_state_presenter.create_guessing_phase_data(room_state, room_id)
            
            # Add timeout-specific information
            guessing_info['timeout_reason'] = 'Response time expired'
            
            self.broadcast_service.emit_to_room('guessing_phase_started', guessing_info, room_id)
            logger.debug(f'Broadcasted guessing phase start (timeout) to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting guessing phase start: {e}')
    
    def _broadcast_results_phase_timeout_started(self, room_id: str):
        """Broadcast results phase start with timeout notification."""
        try:
            round_results = self.game_manager.get_round_results(room_id)
            leaderboard = self.game_manager.get_leaderboard(room_id)
            
            if round_results:
                results_info = {
                    'phase': 'results',
                    'round_results': round_results,
                    'leaderboard': leaderboard,
                    'timeout_reason': 'Guessing time expired'
                }
                
                self.broadcast_service.emit_to_room('results_phase_started', results_info, room_id)
                
                # Broadcast updated player list with new scores
                self.broadcast_service.broadcast_player_list_update(room_id)
                
                logger.debug(f'Broadcasted results phase start (timeout) to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting results phase start: {e}')
    
    def _broadcast_round_ended(self, room_id: str):
        """Broadcast round end notification."""
        try:
            self.broadcast_service.emit_to_room('round_ended', {
                'phase': 'waiting',
                'message': 'Round completed. Ready for next round.'
            }, room_id)
            logger.debug(f'Broadcasted round end to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting round end: {e}')

    def handle_player_disconnect_game_impact(self, room_id: str, disconnected_player_id: str):
        """Handle the impact of player disconnection on game flow."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                logger.warning(f"Room {room_id} not found during disconnect handling")
                return
            
            game_state = room_state.get("game_state", {})
            current_phase = game_state.get("phase", "waiting")
            
            try:
                connected_players = self.room_manager.get_connected_players(room_id)
            except Exception as e:
                logger.error(f"Error getting connected players for room {room_id}: {e}")
                connected_players = []
            
            logger.info(f"Handling disconnect impact for player {disconnected_player_id} in room {room_id}, "
                       f"phase: {current_phase}, remaining players: {len(connected_players)}")
            
            # If only one player left, reset to waiting phase
            if len(connected_players) < 2:
                if current_phase != "waiting":
                    logger.info(f"Insufficient players in room {room_id}, resetting to waiting phase")
                    # Directly reset to waiting phase
                    new_phase = self.game_manager._advance_to_waiting_phase(room_id)
                    
                    # Send game_paused event with error response format
                    error_response = {
                        'success': False,
                        'error': {
                            'code': 'INSUFFICIENT_PLAYERS',
                            'message': 'Game paused - need at least 2 players to continue'
                        }
                    }
                    self.broadcast_service.broadcast_game_paused(room_id, error_response)
                    self.broadcast_service.broadcast_room_state_update(room_id)
                return
            
            # Check if we can auto-advance due to all remaining players having completed current phase
            if current_phase == "responding":
                responses = game_state.get("responses", [])
                if len(responses) >= len(connected_players):
                    logger.info(f"All remaining players have responded in room {room_id}, advancing to guessing")
                    new_phase = self.game_manager.advance_game_phase(room_id)
                    if new_phase == "guessing":
                        self.broadcast_service.broadcast_guessing_phase_started(room_id)
                        self.broadcast_service.broadcast_room_state_update(room_id)
            
            elif current_phase == "guessing":
                guesses = game_state.get("guesses", [])
                if len(guesses) >= len(connected_players):
                    logger.info(f"All remaining players have guessed in room {room_id}, advancing to results")
                    new_phase = self.game_manager.advance_game_phase(room_id)
                    if new_phase == "results":
                        self.broadcast_service.broadcast_results_phase_started(room_id)
                        self.broadcast_service.broadcast_room_state_update(room_id)
                        
        except Exception as e:
            logger.error(f"Error handling disconnect game impact for room {room_id}: {e}")