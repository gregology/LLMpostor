"""
Automatic game flow management for LLMposter.
"""

import threading
import time
import logging
from flask_socketio import SocketIO
from src.game_manager import GameManager
from src.room_manager import RoomManager
from src.broadcast_manager import BroadcastManager

logger = logging.getLogger(__name__)

class AutoGameFlowManager:
    """Manages automatic phase transitions and timing."""
    
    def __init__(self, socketio: SocketIO, game_manager: GameManager, room_manager: RoomManager, broadcast_manager: BroadcastManager):
        self.socketio = socketio
        self.game_manager = game_manager
        self.room_manager = room_manager
        self.broadcast_manager = broadcast_manager
        self.running = True
        self.check_interval = 1  # Check every second
        
        # Start background thread for automatic phase management
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        
        logger.info("AutoGameFlowManager started")
    
    def stop(self):
        """Stop the automatic game flow manager."""
        self.running = False
        if self.timer_thread.is_alive():
            self.timer_thread.join(timeout=2)
        logger.info("AutoGameFlowManager stopped")
    
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
    
    def _broadcast_countdown_updates(self, current_time: float, last_broadcast: dict):
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
                    
                    self.socketio.emit('countdown_update', countdown_data, room=room_id)
                    last_broadcast[room_id] = current_time
                    
                    # Special warnings for low time
                    if time_remaining <= 30 and time_remaining > 25:
                        self.socketio.emit('time_warning', {
                            'message': '30 seconds remaining!',
                            'time_remaining': time_remaining
                        }, room=room_id)
                    elif time_remaining <= 10 and time_remaining > 5:
                        self.socketio.emit('time_warning', {
                            'message': '10 seconds remaining!',
                            'time_remaining': time_remaining
                        }, room=room_id)
                
            except Exception as e:
                logger.error(f"Error broadcasting countdown for room {room_id}: {e}")
    
    def _check_phase_timeouts(self):
        """Check all active rooms for phase timeouts and advance if needed."""
        room_ids = self.room_manager.get_all_rooms()
        
        for room_id in room_ids:
            try:
                if self.game_manager.is_phase_expired(room_id):
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
                    self.broadcast_manager._broadcast_guessing_phase_started(room_id)
                elif new_phase == "results":
                    self.broadcast_manager._broadcast_results_phase_started(room_id)
                elif new_phase == "waiting":
                    self.broadcast_manager._broadcast_round_ended(room_id)
                
                # Always broadcast room state update
                self.broadcast_manager._broadcast_room_state_update(room_id)
                
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