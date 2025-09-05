"""
Broadcast manager for LLMposter.
"""

import logging
from flask_socketio import SocketIO
from src.game_manager import GameManager
from src.room_manager import RoomManager
from src.error_handler import ErrorHandler, ErrorCode

logger = logging.getLogger(__name__)

class BroadcastManager:
    def __init__(self, socketio: SocketIO, room_manager: RoomManager, game_manager: GameManager):
        self.socketio = socketio
        self.room_manager = room_manager
        self.game_manager = game_manager

    

    def _broadcast_player_list_update(self, room_id: str):
        """Broadcast updated player list to all players in room."""
        try:
            players = self.room_manager.get_room_players(room_id)
            connected_players = self.room_manager.get_connected_players(room_id)
            
            # Prepare player list data (without sensitive info)
            player_list = []
            for player in players:
                player_list.append({
                    'player_id': player['player_id'],
                    'name': player['name'],
                    'score': player['score'],
                    'connected': player['connected']
                })
            
            self.socketio.emit('player_list_updated', {
                'players': player_list,
                'connected_count': len(connected_players),
                'total_count': len(players)
            }, room=room_id)
            
            logger.debug(f'Broadcasted player list update to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting player list update: {e}')

    def _broadcast_room_state_update(self, room_id: str):
        """Broadcast current room state to all players in room."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            game_state = room_state['game_state']
            
            # Prepare safe game state data (hide sensitive info during certain phases)
            safe_game_state = {
                'phase': game_state['phase'],
                'round_number': game_state['round_number'],
                'phase_start_time': game_state['phase_start_time'].isoformat() if game_state['phase_start_time'] else None,
                'phase_duration': game_state['phase_duration']
            }
            
            # Add phase-specific data
            if game_state['phase'] in ['responding', 'guessing', 'results']:
                if game_state['current_prompt']:
                    safe_game_state['current_prompt'] = {
                        'id': game_state['current_prompt']['id'],
                        'prompt': game_state['current_prompt']['prompt'],
                        'model': game_state['current_prompt']['model']
                    }
            
            if game_state['phase'] == 'responding':
                # Show response count and time remaining during responding phase
                safe_game_state['response_count'] = len(game_state['responses'])
                safe_game_state['time_remaining'] = self.game_manager.get_phase_time_remaining(room_id)
            
            if game_state['phase'] == 'results':
                # Show responses (with authorship revealed in results phase)
                safe_game_state['responses'] = []
                for i, response in enumerate(game_state['responses']):
                    response_data = {
                        'index': i,
                        'text': response['text'],
                        'is_llm': response['is_llm']
                    }
                    if not response['is_llm']:
                        # Find player name for human responses
                        author_id = response['author_id']
                        players = room_state['players']
                        if author_id in players:
                            response_data['author_name'] = players[author_id]['name']
                    
                    safe_game_state['responses'].append(response_data)
            
            if game_state['phase'] == 'guessing':
                # Show guess count and time remaining during guessing phase
                safe_game_state['guess_count'] = len(game_state['guesses'])
                safe_game_state['time_remaining'] = self.game_manager.get_phase_time_remaining(room_id)
            
            if game_state['phase'] == 'results':
                # Show guessing results and detailed round results
                safe_game_state['guesses'] = {}
                players = room_state['players']
                for player_id, guess_index in game_state['guesses'].items():
                    if player_id in players:
                        player_name = players[player_id]['name']
                        safe_game_state['guesses'][player_name] = guess_index
                
                # Include detailed round results
                round_results = self.game_manager.get_round_results(room_id)
                if round_results:
                    safe_game_state['round_results'] = round_results
            
            # During guessing phase, send personalized room states (excluding own responses)
            if game_state['phase'] == 'guessing':
                for player_id in room_state['players']:
                    player = room_state['players'][player_id]
                    if not player.get('connected', False):
                        continue
                    
                    # Create personalized game state for this player
                    personalized_game_state = safe_game_state.copy()
                    personalized_game_state['responses'] = []
                    
                    # Filter out this player's own response
                    for i, response in enumerate(game_state['responses']):
                        if response['author_id'] != player_id:
                            personalized_game_state['responses'].append({
                                'index': i,
                                'text': response['text']
                            })
                    
                    self.socketio.emit('room_state_updated', personalized_game_state, room=player['socket_id'])
            else:
                # For all other phases, broadcast normally
                self.socketio.emit('room_state_updated', safe_game_state, room=room_id)
            
            logger.debug(f'Broadcasted room state update to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting room state update: {e}')

    def _send_room_state_to_player(self, room_id: str, socket_id: str):
        """Send current room state to a specific player."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                self.socketio.emit('error', {
                    'code': 'ROOM_NOT_FOUND',
                    'message': 'Room not found'
                }, room=socket_id)
                return
            
            # Get player list
            players = self.room_manager.get_room_players(room_id)
            connected_players = self.room_manager.get_connected_players(room_id)
            
            player_list = []
            for player in players:
                player_list.append({
                    'player_id': player['player_id'],
                    'name': player['name'],
                    'score': player['score'],
                    'connected': player['connected']
                })
            
            # Get game state
            game_state = room_state['game_state']
            safe_game_state = {
                'phase': game_state['phase'],
                'round_number': game_state['round_number'],
                'phase_start_time': game_state['phase_start_time'].isoformat() if game_state['phase_start_time'] else None,
                'phase_duration': game_state['phase_duration']
            }
            
            # Add phase-specific data
            if game_state['phase'] in ['responding', 'guessing', 'results']:
                if game_state['current_prompt']:
                    safe_game_state['current_prompt'] = {
                        'id': game_state['current_prompt']['id'],
                        'prompt': game_state['current_prompt']['prompt'],
                        'model': game_state['current_prompt']['model']
                    }
            
            if game_state['phase'] in ['responding']:
                # Show response count without revealing content
                safe_game_state['response_count'] = len(game_state['responses'])
                safe_game_state['time_remaining'] = self.game_manager.get_phase_time_remaining(room_id)
            
            # Get leaderboard for room state
            leaderboard = self.game_manager.get_leaderboard(room_id)
            
            # Send comprehensive room state
            self.socketio.emit('room_state', {
                'room_id': room_id,
                'players': player_list,
                'connected_count': len(connected_players),
                'total_count': len(players),
                'game_state': safe_game_state,
                'leaderboard': leaderboard
            }, room=socket_id)
            
            logger.debug(f'Sent room state to player {socket_id} in room {room_id}')
            
        except Exception as e:
            logger.error(f'Error sending room state to player: {e}')

    def _broadcast_round_started(self, room_id: str):
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
                
                self.socketio.emit('round_started', prompt_info, room=room_id)
                logger.debug(f'Broadcasted round start to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting round start: {e}')

    def _broadcast_response_submitted(self, room_id: str):
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
            
            self.socketio.emit('response_submitted', response_info, room=room_id)
            logger.debug(f'Broadcasted response submission to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting response submission: {e}')

    def _broadcast_guess_submitted(self, room_id: str):
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
            
            self.socketio.emit('guess_submitted', guess_info, room=room_id)
            logger.debug(f'Broadcasted guess submission to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting guess submission: {e}')

    def _broadcast_guessing_phase_started(self, room_id: str):
        """Broadcast guessing phase start notification to all players in room."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            game_state = room_state['game_state']
            
            # Send personalized responses to each player (excluding their own response)
            for player_id in room_state['players']:
                player = room_state['players'][player_id]
                if not player.get('connected', False):
                    continue
                    
                # Filter out this player's own response
                filtered_responses = []
                for i, response in enumerate(game_state['responses']):
                    if response['author_id'] != player_id:
                        filtered_responses.append({
                            'index': i,
                            'text': response['text']
                        })
                
                guessing_info = {
                    'phase': 'guessing',
                    'responses': filtered_responses,
                    'round_number': game_state['round_number'],
                    'phase_duration': game_state['phase_duration'],
                    'time_remaining': self.game_manager.get_phase_time_remaining(room_id)
                }
                
                self.socketio.emit('guessing_phase_started', guessing_info, room=player['socket_id'])
            
            logger.debug(f'Broadcasted guessing phase start to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting guessing phase start: {e}')

    def _broadcast_results_phase_started(self, room_id: str):
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
            
            results_info = {
                'phase': 'results',
                'round_results': round_results,
                'leaderboard': leaderboard,
                'scoring_summary': scoring_summary,
                'phase_duration': 30  # Results phase duration
            }
            
            self.socketio.emit('results_phase_started', results_info, room=room_id)
            
            # Broadcast updated player list with new scores
            self._broadcast_player_list_update(room_id)
            
            logger.debug(f'Broadcasted results phase start to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting results phase start: {e}')

    def _broadcast_round_ended(self, room_id: str):
        """Broadcast round end notification."""
        try:
            self.socketio.emit('round_ended', {
                'phase': 'waiting',
                'message': 'Round completed. Ready for next round.'
            }, room=room_id)
            logger.debug(f'Broadcasted round end to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting round end: {e}')