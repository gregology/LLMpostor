"""
Room State Presenter - Centralized room state transformation for broadcasts.

This service provides canonical transformations for room state data that needs
to be sent to clients, ensuring consistent payload shapes and proper data filtering.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class RoomStatePresenter:
    """Centralized service for transforming room state data for client broadcasts."""
    
    def __init__(self, game_manager):
        """Initialize the room state presenter.
        
        Args:
            game_manager: Game state management service for time calculations
        """
        self.game_manager = game_manager
    
    def create_safe_game_state(self, room_state: Dict[str, Any], room_id: str) -> Dict[str, Any]:
        """Create a safe game state object for client consumption.
        
        Args:
            room_state: Full room state from room manager
            room_id: Room identifier for time calculations
            
        Returns:
            Dict containing safe game state data without sensitive information
        """
        game_state = room_state['game_state']
        
        # Base safe state with common fields
        safe_game_state = {
            'phase': game_state['phase'],
            'round_number': game_state['round_number'],
            'phase_start_time': game_state['phase_start_time'].isoformat() if game_state['phase_start_time'] else None,
            'phase_duration': game_state['phase_duration']
        }
        
        # Add prompt information for active phases
        if game_state['phase'] in ['responding', 'guessing', 'results']:
            if game_state['current_prompt']:
                safe_game_state['current_prompt'] = self._create_safe_prompt_data(game_state['current_prompt'])
        
        # Add phase-specific data
        if game_state['phase'] == 'responding':
            safe_game_state.update(self._create_responding_phase_data(game_state, room_id))
        elif game_state['phase'] == 'guessing':
            safe_game_state.update(self._create_guessing_phase_data(game_state, room_id))
        
        return safe_game_state
    
    def create_player_list(self, room_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create a filtered player list for client consumption.
        
        Args:
            room_state: Full room state from room manager
            
        Returns:
            List of player objects with safe data only
        """
        players = room_state['players']
        player_list = []
        
        for player_id, player in players.items():
            player_list.append({
                'player_id': player['player_id'],
                'name': player['name'],
                'score': player.get('score', 0),  # Default to 0 if missing
                'connected': player.get('connected', False)  # Default to False if missing
            })
        
        return player_list
    
    def create_responses_for_guessing(self, game_state: Dict[str, Any], exclude_player_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Create filtered responses list for guessing phase.
        
        Args:
            game_state: Game state containing responses
            exclude_player_id: Optional player ID to exclude from responses (for personalized views)
            
        Returns:
            List of response objects with index and text, optionally filtered
        """
        responses_data = []
        
        for i, response in enumerate(game_state['responses']):
            # Skip this response if it's from the excluded player
            if exclude_player_id and response.get('author_id') == exclude_player_id:
                continue
                
            responses_data.append({
                'index': i,
                'text': response['text']
            })
        
        return responses_data
    
    def create_room_state_for_player(self, room_state: Dict[str, Any], room_id: str, connected_players: List[str]) -> Dict[str, Any]:
        """Create complete room state data for a specific player (join/reconnect).
        
        Args:
            room_state: Full room state from room manager
            room_id: Room identifier
            connected_players: List of connected player IDs
            
        Returns:
            Complete room state object for client consumption
        """
        players = room_state['players']
        player_list = self.create_player_list(room_state)
        safe_game_state = self.create_safe_game_state(room_state, room_id)
        
        # Get leaderboard for room state
        leaderboard = self.game_manager.get_leaderboard(room_id)
        
        return {
            'room_id': room_id,
            'players': player_list,
            'connected_count': len(connected_players),
            'total_count': len(players),
            'game_state': safe_game_state,
            'leaderboard': leaderboard
        }
    
    def create_player_list_update(self, room_state: Dict[str, Any], connected_players: List[str]) -> Dict[str, Any]:
        """Create player list update payload.
        
        Args:
            room_state: Full room state from room manager
            connected_players: List of connected player IDs
            
        Returns:
            Player list update payload
        """
        players = room_state['players']
        player_list = self.create_player_list(room_state)
        
        return {
            'players': player_list,
            'connected_count': len(connected_players),
            'total_count': len(players)
        }
    
    def create_guessing_phase_data(self, room_state: Dict[str, Any], room_id: str, player_id: Optional[str] = None) -> Dict[str, Any]:
        """Create guessing phase start data, optionally personalized for a specific player.
        
        Args:
            room_state: Full room state from room manager
            room_id: Room identifier for time calculations
            player_id: Optional player ID for personalized response filtering
            
        Returns:
            Guessing phase data with responses filtered appropriately
        """
        game_state = room_state['game_state']
        
        # Get filtered responses (exclude player's own response if specified)
        filtered_responses = self.create_responses_for_guessing(game_state, player_id)
        
        return {
            'phase': 'guessing',
            'responses': filtered_responses,
            'round_number': game_state['round_number'],
            'phase_duration': game_state['phase_duration'],
            'time_remaining': self.game_manager.get_phase_time_remaining(room_id)
        }
    
    def _create_safe_prompt_data(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        """Create safe prompt data by filtering out sensitive information.
        
        Args:
            prompt: Full prompt object
            
        Returns:
            Safe prompt data without AI response or other sensitive fields
        """
        return {
            'id': prompt['id'],
            'prompt': prompt['prompt'],
            'model': prompt['model']
        }
    
    def _create_responding_phase_data(self, game_state: Dict[str, Any], room_id: str) -> Dict[str, Any]:
        """Create responding phase specific data.
        
        Args:
            game_state: Game state object
            room_id: Room identifier for time calculations
            
        Returns:
            Dict with responding phase specific fields
        """
        return {
            'response_count': len(game_state['responses']),
            'time_remaining': self.game_manager.get_phase_time_remaining(room_id)
        }
    
    def _create_guessing_phase_data(self, game_state: Dict[str, Any], room_id: str) -> Dict[str, Any]:
        """Create guessing phase specific data.
        
        Args:
            game_state: Game state object
            room_id: Room identifier for time calculations
            
        Returns:
            Dict with guessing phase specific fields
        """
        responses_data = self.create_responses_for_guessing(game_state)
        
        return {
            'responses': responses_data,
            'guess_count': len(game_state['guesses']),
            'time_remaining': self.game_manager.get_phase_time_remaining(room_id)
        }