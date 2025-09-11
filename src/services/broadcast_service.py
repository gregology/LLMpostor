"""
Broadcast Service - Centralized Socket.IO message broadcasting.

This service handles all Socket.IO emissions in a centralized way:
- Room-wide broadcasts
- Individual player messages  
- Game state updates
- Phase transition notifications
- Error handling and validation
"""

import logging
from typing import Dict, Any
from src.services.payload_optimizer import get_payload_optimizer
from src.services.room_state_presenter import RoomStatePresenter
from config_factory import get_config

logger = logging.getLogger(__name__)


class BroadcastService:
    """Centralized service for all Socket.IO broadcasting operations."""
    
    def __init__(self, socketio, room_manager, game_manager, error_handler):
        """Initialize the broadcast service.
        
        Args:
            socketio: Flask-SocketIO instance for emitting messages
            room_manager: Room management service
            game_manager: Game state management service  
            error_handler: Error handling service
        """
        self.socketio = socketio
        self.room_manager = room_manager
        self.game_manager = game_manager
        self.error_handler = error_handler
        
        # Initialize room state presenter for consistent payload transformations
        self.room_state_presenter = RoomStatePresenter(game_manager)
        
        # Performance optimization: Initialize payload optimizer (optional)
        try:
            config = get_config()
            self.payload_optimizer = get_payload_optimizer({
                'compression_threshold': config.compression_threshold_bytes,
                'enable_caching': True
            })
            self.optimization_enabled = True
        except Exception:
            # Fallback: disable optimization if service unavailable
            self.payload_optimizer = None
            self.optimization_enabled = False
    
    # Core emission methods
    
    def emit_to_room(self, event: str, data: Dict[str, Any], room_id: str):
        """Emit an event to all players in a room."""
        try:
            self.socketio.emit(event, data, room=room_id)
            logger.debug(f'Emitted {event} to room {room_id}')
        except Exception as e:
            logger.error(f'Error emitting {event} to room {room_id}: {e}')
    
    def emit_to_player(self, event: str, data: Dict[str, Any], socket_id: str):
        """Emit an event to a specific player."""
        try:
            self.socketio.emit(event, data, room=socket_id)
            logger.debug(f'Emitted {event} to player {socket_id}')
        except Exception as e:
            logger.error(f'Error emitting {event} to player {socket_id}: {e}')
    
    def emit_error_to_player(self, error_response: Dict[str, Any], socket_id: str):
        """Emit an error message to a specific player."""
        try:
            self.socketio.emit('error', error_response, room=socket_id)
            logger.debug(f'Emitted error to player {socket_id}: {error_response.get("error_code", "unknown")}')
        except Exception as e:
            logger.error(f'Error emitting error to player {socket_id}: {e}')
    
    # High-level broadcast methods
    
    def broadcast_player_list_update(self, room_id: str):
        """Broadcast updated player list to all players in room."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            connected_players = self.room_manager.get_connected_players(room_id)
            
            # Use presenter to create consistent player list payload
            player_info = self.room_state_presenter.create_player_list_update(room_state, connected_players)
            
            self.emit_to_room('player_list_updated', player_info, room_id)
            logger.debug(f'Broadcasted player list update to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting player list update: {e}')
    
    def broadcast_room_state_update(self, room_id: str):
        """Broadcast optimized room state update to all players in room."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            # Use presenter to create consistent safe game state
            safe_game_state = self.room_state_presenter.create_safe_game_state(room_state, room_id)
            
            # Keep original format for backward compatibility
            # TODO: Enable payload optimization in future version with client support
            # optimized_payload, metadata = self.payload_optimizer.optimize_room_state(
            #     safe_game_state, room_id
            # )
            
            # Broadcast the game state directly (maintaining backward compatibility)
            self.emit_to_room('room_state_updated', safe_game_state, room_id)
            logger.debug(f'Broadcasted room state update to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting room state update: {e}')
    
    def send_room_state_to_player(self, room_id: str, socket_id: str):
        """Send complete room state to a specific player (for initial join/reconnect)."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                error_response = self.error_handler.create_error_response(
                    'ROOM_NOT_FOUND',
                    f'Room {room_id} not found',
                    {'room_id': room_id}
                )
                self.emit_error_to_player(error_response, socket_id)
                return
            
            connected_players = self.room_manager.get_connected_players(room_id)
            
            # Use presenter to create consistent room state payload
            room_state_data = self.room_state_presenter.create_room_state_for_player(room_state, room_id, connected_players)
            
            self.emit_to_player('room_state', room_state_data, socket_id)
            logger.debug(f'Sent room state to player {socket_id} in room {room_id}')
            
        except Exception as e:
            logger.error(f'Error sending room state to player: {e}')
    
    def broadcast_round_started(self, room_id: str):
        """Broadcast round start notification to all players in room."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            game_state = room_state['game_state']
            if game_state['current_prompt']:
                prompt_info = {
                    'id': game_state['current_prompt']['id'],
                    'prompt': game_state['current_prompt']['prompt'],
                    'model': game_state['current_prompt']['model'],
                    'round_number': game_state['round_number'],
                    'phase_duration': game_state['phase_duration']
                }
                
                self.emit_to_room('round_started', prompt_info, room_id)
                logger.debug(f'Broadcasted round start to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting round start: {e}')
    
    def broadcast_response_submitted(self, room_id: str):
        """Broadcast response submission notification to all players in room."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            game_state = room_state['game_state']
            connected_players = self.room_manager.get_connected_players(room_id)
            
            response_info = {
                'response_count': len(game_state['responses']),
                'total_players': len(connected_players),
                'time_remaining': self.game_manager.get_phase_time_remaining(room_id)
            }
            
            self.emit_to_room('response_submitted', response_info, room_id)
            logger.debug(f'Broadcasted response submission to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting response submission: {e}')
    
    def broadcast_guess_submitted(self, room_id: str):
        """Broadcast guess submission notification to all players in room."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            game_state = room_state['game_state']
            connected_players = self.room_manager.get_connected_players(room_id)
            
            guess_info = {
                'guess_count': len(game_state['guesses']),
                'total_players': len(connected_players),
                'time_remaining': self.game_manager.get_phase_time_remaining(room_id)
            }
            
            self.emit_to_room('guess_submitted', guess_info, room_id)
            logger.debug(f'Broadcasted guess submission to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting guess submission: {e}')
    
    def broadcast_guessing_phase_started(self, room_id: str):
        """Broadcast guessing phase start notification to all players in room."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            # Send personalized responses to each player (excluding their own response)
            for player_id in room_state['players']:
                player = room_state['players'][player_id]
                if not player.get('connected', False):
                    continue
                
                # Use presenter to create personalized guessing phase data
                guessing_info = self.room_state_presenter.create_guessing_phase_data(room_state, room_id, player_id)
                
                self.emit_to_player('guessing_phase_started', guessing_info, player['socket_id'])
            
            logger.debug(f'Broadcasted guessing phase start to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting guessing phase start: {e}')
    
    def broadcast_results_phase_started(self, room_id: str):
        """Broadcast results phase start notification to all players in room."""
        try:
            # Get comprehensive round results
            round_results = self.game_manager.get_round_results(room_id)
            if not round_results:
                return
            
            # Get updated leaderboard
            leaderboard = self.game_manager.get_leaderboard(room_id)
            
            # Get scoring summary
            scoring_summary = self.game_manager.get_scoring_summary(room_id)
            
            config = get_config()
            results_info = {
                'phase': 'results',
                'round_results': round_results,
                'leaderboard': leaderboard,
                'scoring_summary': scoring_summary,
                'phase_duration': config.results_display_time
            }
            
            self.emit_to_room('results_phase_started', results_info, room_id)
            
            # Broadcast updated player list with new scores
            self.broadcast_player_list_update(room_id)
            
            logger.debug(f'Broadcasted results phase start to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting results phase start: {e}')
    
    def broadcast_phase_auto_advanced(self, room_id: str, message: str, new_phase: str, reason: str):
        """Broadcast phase auto-advancement notification."""
        try:
            advance_info = {
                'message': message,
                'new_phase': new_phase,
                'reason': reason
            }
            
            self.emit_to_room('phase_auto_advanced', advance_info, room_id)
            logger.debug(f'Broadcasted phase auto-advance to room {room_id}: {new_phase}')
            
        except Exception as e:
            logger.error(f'Error broadcasting phase auto-advance: {e}')
    
    def broadcast_player_disconnected(self, room_id: str, remaining_count: int, phase: str):
        """Broadcast player disconnection notification."""
        try:
            disconnect_info = {
                'remaining_players': remaining_count,
                'current_phase': phase,
                'message': f'A player has disconnected. {remaining_count} players remaining.'
            }
            
            self.emit_to_room('player_disconnected', disconnect_info, room_id)
            logger.debug(f'Broadcasted player disconnect to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting player disconnect: {e}')
    
    def broadcast_game_paused(self, room_id: str, error_response: Dict[str, Any]):
        """Broadcast game pause notification."""
        try:
            self.emit_to_room('game_paused', error_response, room_id)
            logger.debug(f'Broadcasted game pause to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting game pause: {e}')
    
    def broadcast_countdown_update(self, room_id: str, phase: str, time_remaining: int, duration: int):
        """Broadcast countdown update for active phases."""
        try:
            countdown_data = {
                'phase': phase,
                'time_remaining': time_remaining,
                'phase_duration': duration
            }
            
            self.emit_to_room('countdown_update', countdown_data, room_id)
            
        except Exception as e:
            logger.error(f'Error broadcasting countdown update: {e}')
    
    def broadcast_time_warning(self, room_id: str, message: str, time_remaining: int):
        """Broadcast time warning for active phases."""
        try:
            warning_data = {
                'message': message,
                'time_remaining': time_remaining
            }
            
            self.emit_to_room('time_warning', warning_data, room_id)
            
        except Exception as e:
            logger.error(f'Error broadcasting time warning: {e}')
    
    def broadcast_round_ended(self, room_id: str):
        """Broadcast round end notification."""
        try:
            self.emit_to_room('round_ended', {
                'phase': 'waiting',
                'message': 'Round completed. Ready for next round.'
            }, room_id)
            logger.debug(f'Broadcasted round end to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting round end: {e}')
    
    def broadcast_game_reset(self, room_id: str, message: str):
        """Broadcast game reset notification."""
        try:
            reset_data = {
                'phase': 'waiting',
                'message': message
            }
            
            self.emit_to_room('game_reset', reset_data, room_id)
            logger.debug(f'Broadcasted game reset to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting game reset: {e}')