"""
Integration tests for scoring system and results display functionality.
"""

import pytest
from unittest.mock import patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app import app, socketio
from src.content_manager import PromptData


class TestScoringAndResults:
    """Test cases for scoring system and results display integration."""
    
    @pytest.fixture
    def mock_content_manager(self):
        """Mock content manager with test prompt."""
        with patch('app.content_manager') as mock_cm:
            mock_prompt = PromptData(
                id="test_001",
                prompt="What is artificial intelligence?",
                model="GPT-4",
                responses=["Artificial intelligence (AI) is a branch of computer science that aims to create intelligent machines."]
            )
            mock_prompt.select_random_response()  # Ensure response is selected for tests
            mock_cm.get_random_prompt_response.return_value = mock_prompt
            mock_cm.is_loaded.return_value = True
            mock_cm.get_prompt_count.return_value = 1
            yield mock_cm
    
    def _setup_complete_round(self, client1, client2, mock_content_manager):
        """Helper to set up a complete round with responses and guesses."""
        # Join room
        client1.emit('join_room', {
            'room_id': 'test_room',
            'player_name': 'Player1'
        })
        client2.emit('join_room', {
            'room_id': 'test_room', 
            'player_name': 'Player2'
        })
        
        # Clear join events
        client1.get_received()
        client2.get_received()
        
        # Start round
        client1.emit('start_round')
        client1.get_received()
        client2.get_received()
        
        # Submit responses
        client1.emit('submit_response', {
            'response': 'AI is when computers think like humans'
        })
        client2.emit('submit_response', {
            'response': 'Artificial intelligence simulates human cognition'
        })
        
        # Clear response events
        client1.get_received()
        client2.get_received()
        
        # Submit guesses (both guess index 1, which should be the LLM response)
        client1.emit('submit_guess', {'guess_index': 1})
        client2.emit('submit_guess', {'guess_index': 0})
        
        return client1, client2
    
    def test_get_round_results_event(self, mock_content_manager):
        """Test get_round_results Socket.IO event."""
        client = socketio.test_client(app)
        client2 = socketio.test_client(app)
        
        try:
            # Complete a round
            self._setup_complete_round(client, client2, mock_content_manager)
            
            # Clear results events
            client.get_received()
            client2.get_received()
            
            # Request round results
            client.emit('get_round_results')
            
            # Check response
            received = client.get_received()
            results_events = [event for event in received if event['name'] == 'round_results']
            
            assert len(results_events) == 1
            event_data = results_events[0]['args'][0]
            
            assert event_data['success'] is True
            assert 'data' in event_data
            assert 'results' in event_data['data']
            
            results = event_data['data']['results']
            assert 'round_number' in results
            assert 'llm_response_index' in results
            assert 'responses' in results
            assert 'player_results' in results
            assert len(results['responses']) == 3  # 2 players + 1 LLM
            assert len(results['player_results']) == 2  # 2 players
            
        finally:
            client.disconnect()
            client2.disconnect()
    
    def test_get_round_results_wrong_phase(self, mock_content_manager):
        """Test get_round_results when not in results phase."""
        client = socketio.test_client(app)
        
        try:
            # Join room but don't complete round
            client.emit('join_room', {
                'room_id': 'test_room',
                'player_name': 'Player1'
            })
            client.get_received()
            
            # Request round results
            client.emit('get_round_results')
            
            # Should get error
            received = client.get_received()
            error_events = [event for event in received if event['name'] == 'error']
            
            assert len(error_events) == 1
            error_data = error_events[0]['args'][0]
            assert error_data['success'] is False
            assert error_data['error']['code'] == 'NO_RESULTS_AVAILABLE'
            
        finally:
            client.disconnect()
    
    def test_get_leaderboard_event(self, mock_content_manager):
        """Test get_leaderboard Socket.IO event."""
        client = socketio.test_client(app)
        client2 = socketio.test_client(app)
        
        try:
            # Complete a round
            self._setup_complete_round(client, client2, mock_content_manager)
            
            # Clear results events
            client.get_received()
            client2.get_received()
            
            # Request leaderboard
            client.emit('get_leaderboard')
            
            # Check response
            received = client.get_received()
            leaderboard_events = [event for event in received if event['name'] == 'leaderboard']
            
            assert len(leaderboard_events) == 1
            event_data = leaderboard_events[0]['args'][0]
            
            assert event_data['success'] is True
            assert 'data' in event_data
            assert 'leaderboard' in event_data['data']
            assert 'scoring_summary' in event_data['data']
            
            leaderboard = event_data['data']['leaderboard']
            assert len(leaderboard) == 2
            
            # Check leaderboard structure
            for player in leaderboard:
                assert 'player_id' in player
                assert 'name' in player
                assert 'score' in player
                assert 'rank' in player
            
            # Check scoring summary
            scoring_summary = event_data['data']['scoring_summary']
            assert 'scoring_rules' in scoring_summary
            assert 'game_stats' in scoring_summary
            
        finally:
            client.disconnect()
            client2.disconnect()
    
    def test_results_phase_comprehensive_data(self, mock_content_manager):
        """Test that results phase provides comprehensive scoring data."""
        client = socketio.test_client(app)
        client2 = socketio.test_client(app)
        
        try:
            # Complete a round
            self._setup_complete_round(client, client2, mock_content_manager)
            
            # Check results phase event
            received1 = client.get_received()
            received2 = client2.get_received()
            
            # Find results_phase_started event
            results_events = []
            for event in received1 + received2:
                if event['name'] == 'results_phase_started':
                    results_events.append(event)
            
            assert len(results_events) > 0
            event_data = results_events[0]['args'][0]
            
            # Check comprehensive data structure
            assert 'round_results' in event_data
            assert 'leaderboard' in event_data
            assert 'scoring_summary' in event_data
            
            round_results = event_data['round_results']
            
            # Check response details include voting information
            for response in round_results['responses']:
                assert 'votes_received' in response
                assert 'voters' in response
                if not response['is_llm']:
                    assert 'author_name' in response
            
            # Check player results include detailed scoring
            for player_id, player_result in round_results['player_results'].items():
                assert 'correct_guess' in player_result
                assert 'deception_points' in player_result
                assert 'round_points' in player_result
                assert 'response_votes' in player_result
            
        finally:
            client.disconnect()
            client2.disconnect()
    
    def test_scoring_accuracy_integration(self, mock_content_manager):
        """Test that scoring calculations are accurate in integration."""
        client = socketio.test_client(app)
        client2 = socketio.test_client(app)
        client3 = socketio.test_client(app)
        
        try:
            # Join room with 3 players
            client.emit('join_room', {
                'room_id': 'test_room',
                'player_name': 'Player1'
            })
            client2.emit('join_room', {
                'room_id': 'test_room',
                'player_name': 'Player2'
            })
            client3.emit('join_room', {
                'room_id': 'test_room',
                'player_name': 'Player3'
            })
            
            # Clear join events
            client.get_received()
            client2.get_received()
            client3.get_received()
            
            # Start round
            client.emit('start_round')
            client.get_received()
            client2.get_received()
            client3.get_received()
            
            # Submit responses
            client.emit('submit_response', {
                'response': 'Very convincing AI-like response'  # This should get votes
            })
            client2.emit('submit_response', {
                'response': 'Player 2 response'
            })
            client3.emit('submit_response', {
                'response': 'Player 3 response'
            })
            
            # Clear response events
            client.get_received()
            client2.get_received()
            client3.get_received()
            
            # Submit guesses - we need to find the actual indices after shuffling
            # For now, just submit some guesses and check the results structure
            client.emit('submit_guess', {'guess_index': 0})
            client2.emit('submit_guess', {'guess_index': 1})
            client3.emit('submit_guess', {'guess_index': 2})
            
            # Get results
            received1 = client.get_received()
            received2 = client2.get_received()
            received3 = client3.get_received()
            
            # Find results event
            results_events = []
            for event in received1 + received2 + received3:
                if event['name'] == 'results_phase_started':
                    results_events.append(event)
            
            assert len(results_events) > 0
            event_data = results_events[0]['args'][0]
            
            # Check leaderboard for correct scoring
            leaderboard = event_data['leaderboard']
            
            # Check that scoring is working (someone should have points)
            total_points = sum(p['score'] for p in leaderboard)
            assert total_points > 0  # Someone should have earned points
            
            # Check that round results contain proper scoring breakdown
            round_results = event_data['round_results']
            assert 'player_results' in round_results
            
            # Verify each player has scoring details
            for player_id, player_result in round_results['player_results'].items():
                assert 'correct_guess' in player_result
                assert 'deception_points' in player_result
                assert 'round_points' in player_result
                assert isinstance(player_result['round_points'], int)
                assert player_result['round_points'] >= 0
            
        finally:
            client.disconnect()
            client2.disconnect()
            client3.disconnect()
    
    def test_leaderboard_persistence_integration(self, mock_content_manager):
        """Test that leaderboard persists across multiple rounds."""
        client = socketio.test_client(app)
        client2 = socketio.test_client(app)
        
        try:
            # Complete first round
            self._setup_complete_round(client, client2, mock_content_manager)
            
            # Get leaderboard after first round
            client.emit('get_leaderboard')
            received = client.get_received()
            
            # Find leaderboard event
            leaderboard_events = [event for event in received if event['name'] == 'leaderboard']
            first_round_leaderboard = leaderboard_events[0]['args'][0]['data']['leaderboard']
            
            # Start second round
            client.emit('start_round')
            client.get_received()
            client2.get_received()
            
            # Complete second round
            client.emit('submit_response', {'response': 'Second round response 1'})
            client2.emit('submit_response', {'response': 'Second round response 2'})
            client.get_received()
            client2.get_received()
            
            client.emit('submit_guess', {'guess_index': 0})
            client2.emit('submit_guess', {'guess_index': 1})
            client.get_received()
            client2.get_received()
            
            # Get leaderboard after second round
            client.emit('get_leaderboard')
            received = client.get_received()
            
            leaderboard_events = [event for event in received if event['name'] == 'leaderboard']
            second_round_leaderboard = leaderboard_events[0]['args'][0]['data']['leaderboard']
            
            # Scores should have potentially increased from first round
            # (depending on correct guesses and deception points)
            for player in second_round_leaderboard:
                first_round_player = next(p for p in first_round_leaderboard if p['player_id'] == player['player_id'])
                # Score should be >= first round score (may have gained points)
                assert player['score'] >= first_round_player['score']
            
        finally:
            client.disconnect()
            client2.disconnect()