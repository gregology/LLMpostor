"""
Room State Presenter Unit Tests
Tests for the centralized room state transformation service.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.services.room_state_presenter import RoomStatePresenter


class TestRoomStatePresenter:
    """Test RoomStatePresenter functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.mock_game_manager = Mock()
        self.presenter = RoomStatePresenter(self.mock_game_manager)

    def test_initialization(self):
        """Test presenter initialization"""
        assert self.presenter.game_manager == self.mock_game_manager

    def test_create_safe_game_state_waiting_phase(self):
        """Test safe game state creation for waiting phase"""
        mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        room_state = {
            'game_state': {
                'phase': 'waiting',
                'round_number': 0,
                'phase_start_time': mock_datetime,
                'phase_duration': 30,
                'current_prompt': None,
                'responses': [],
                'guesses': {}
            }
        }
        
        result = self.presenter.create_safe_game_state(room_state, 'room123')
        
        assert result['phase'] == 'waiting'
        assert result['round_number'] == 0
        assert result['phase_start_time'] == mock_datetime.isoformat()
        assert result['phase_duration'] == 30
        assert 'current_prompt' not in result  # Should not be included for waiting
        assert 'response_count' not in result
        assert 'responses' not in result

    def test_create_safe_game_state_none_phase_start_time(self):
        """Test safe game state creation with None phase_start_time"""
        room_state = {
            'game_state': {
                'phase': 'waiting',
                'round_number': 0,
                'phase_start_time': None,
                'phase_duration': 30,
                'current_prompt': None,
                'responses': [],
                'guesses': {}
            }
        }
        
        result = self.presenter.create_safe_game_state(room_state, 'room123')
        
        assert result['phase_start_time'] is None

    def test_create_safe_game_state_responding_phase(self):
        """Test safe game state creation for responding phase"""
        mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        room_state = {
            'game_state': {
                'phase': 'responding',
                'round_number': 1,
                'phase_start_time': mock_datetime,
                'phase_duration': 120,
                'current_prompt': {
                    'id': 'prompt1',
                    'prompt': 'Test prompt',
                    'model': 'gpt-4',
                    'ai_response': 'Secret AI response'  # Should be filtered out
                },
                'responses': [{'text': 'Response 1'}, {'text': 'Response 2'}],
                'guesses': {}
            }
        }
        
        self.mock_game_manager.get_phase_time_remaining.return_value = 90
        
        result = self.presenter.create_safe_game_state(room_state, 'room123')
        
        assert result['phase'] == 'responding'
        assert 'current_prompt' in result
        assert result['current_prompt']['prompt'] == 'Test prompt'
        assert 'ai_response' not in result['current_prompt']  # Should be filtered
        assert result['response_count'] == 2
        assert result['time_remaining'] == 90

    def test_create_safe_game_state_guessing_phase(self):
        """Test safe game state creation for guessing phase"""
        mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        room_state = {
            'game_state': {
                'phase': 'guessing',
                'round_number': 1,
                'phase_start_time': mock_datetime,
                'phase_duration': 60,
                'current_prompt': {
                    'id': 'prompt1',
                    'prompt': 'Test prompt',
                    'model': 'gpt-4'
                },
                'responses': [
                    {'text': 'Response 1', 'author_id': 'player1'},
                    {'text': 'Response 2', 'author_id': 'player2'}
                ],
                'guesses': {'player1': 0}
            }
        }
        
        self.mock_game_manager.get_phase_time_remaining.return_value = 45
        
        result = self.presenter.create_safe_game_state(room_state, 'room123')
        
        assert result['phase'] == 'guessing'
        assert 'responses' in result
        assert len(result['responses']) == 2
        assert result['responses'][0]['index'] == 0
        assert result['responses'][0]['text'] == 'Response 1'
        assert 'author_id' not in result['responses'][0]  # Should be filtered
        assert result['guess_count'] == 1
        assert result['time_remaining'] == 45

    def test_create_safe_game_state_results_phase(self):
        """Test safe game state creation for results phase"""
        mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        room_state = {
            'game_state': {
                'phase': 'results',
                'round_number': 1,
                'phase_start_time': mock_datetime,
                'phase_duration': 30,
                'current_prompt': {
                    'id': 'prompt1',
                    'prompt': 'Test prompt',
                    'model': 'gpt-4'
                },
                'responses': [],
                'guesses': {}
            }
        }
        
        result = self.presenter.create_safe_game_state(room_state, 'room123')
        
        assert result['phase'] == 'results'
        assert 'current_prompt' in result
        assert result['current_prompt']['prompt'] == 'Test prompt'

    def test_create_player_list(self):
        """Test player list creation"""
        room_state = {
            'players': {
                'player1': {
                    'player_id': 'player1',
                    'name': 'Alice',
                    'score': 100,
                    'connected': True,
                    'socket_id': 'socket1'  # Should be filtered out
                },
                'player2': {
                    'player_id': 'player2',
                    'name': 'Bob',
                    'score': 50,
                    'connected': False,
                    'socket_id': 'socket2'  # Should be filtered out
                }
            }
        }
        
        result = self.presenter.create_player_list(room_state)
        
        assert len(result) == 2
        assert result[0]['player_id'] == 'player1'
        assert result[0]['name'] == 'Alice'
        assert result[0]['score'] == 100
        assert result[0]['connected'] is True
        assert 'socket_id' not in result[0]  # Should be filtered out
        
        assert result[1]['player_id'] == 'player2'
        assert result[1]['name'] == 'Bob'
        assert result[1]['score'] == 50
        assert result[1]['connected'] is False

    def test_create_player_list_empty(self):
        """Test player list creation with empty players"""
        room_state = {'players': {}}
        
        result = self.presenter.create_player_list(room_state)
        
        assert result == []

    def test_create_responses_for_guessing_no_filter(self):
        """Test response creation for guessing without player filtering"""
        game_state = {
            'responses': [
                {'text': 'Response 1', 'author_id': 'player1'},
                {'text': 'Response 2', 'author_id': 'player2'},
                {'text': 'Response 3', 'author_id': 'player3'}
            ]
        }
        
        result = self.presenter.create_responses_for_guessing(game_state)
        
        assert len(result) == 3
        assert result[0]['index'] == 0
        assert result[0]['text'] == 'Response 1'
        assert 'author_id' not in result[0]
        
        assert result[1]['index'] == 1
        assert result[1]['text'] == 'Response 2'
        
        assert result[2]['index'] == 2
        assert result[2]['text'] == 'Response 3'

    def test_create_responses_for_guessing_with_filter(self):
        """Test response creation for guessing with player filtering"""
        game_state = {
            'responses': [
                {'text': 'Response 1', 'author_id': 'player1'},
                {'text': 'Response 2', 'author_id': 'player2'},
                {'text': 'Response 3', 'author_id': 'player1'}
            ]
        }
        
        result = self.presenter.create_responses_for_guessing(game_state, exclude_player_id='player1')
        
        # Should only include player2's response
        assert len(result) == 1
        assert result[0]['index'] == 1
        assert result[0]['text'] == 'Response 2'

    def test_create_responses_for_guessing_empty(self):
        """Test response creation for guessing with empty responses"""
        game_state = {'responses': []}
        
        result = self.presenter.create_responses_for_guessing(game_state)
        
        assert result == []

    def test_create_room_state_for_player(self):
        """Test complete room state creation for player"""
        mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        room_state = {
            'players': {
                'player1': {
                    'player_id': 'player1',
                    'name': 'Alice',
                    'score': 100,
                    'connected': True
                }
            },
            'game_state': {
                'phase': 'waiting',
                'round_number': 0,
                'phase_start_time': mock_datetime,
                'phase_duration': 30,
                'current_prompt': None,
                'responses': [],
                'guesses': {}
            }
        }
        
        connected_players = ['player1']
        self.mock_game_manager.get_leaderboard.return_value = [{'player_id': 'player1', 'score': 100}]
        
        result = self.presenter.create_room_state_for_player(room_state, 'room123', connected_players)
        
        assert result['room_id'] == 'room123'
        assert len(result['players']) == 1
        assert result['connected_count'] == 1
        assert result['total_count'] == 1
        assert 'game_state' in result
        assert result['game_state']['phase'] == 'waiting'
        assert 'leaderboard' in result

    def test_create_player_list_update(self):
        """Test player list update payload creation"""
        room_state = {
            'players': {
                'player1': {
                    'player_id': 'player1',
                    'name': 'Alice',
                    'score': 100,
                    'connected': True
                },
                'player2': {
                    'player_id': 'player2',
                    'name': 'Bob',
                    'score': 50,
                    'connected': False
                }
            }
        }
        
        connected_players = ['player1']
        
        result = self.presenter.create_player_list_update(room_state, connected_players)
        
        assert len(result['players']) == 2
        assert result['connected_count'] == 1
        assert result['total_count'] == 2

    def test_create_guessing_phase_data_without_player_filter(self):
        """Test guessing phase data creation without player filtering"""
        room_state = {
            'game_state': {
                'phase': 'guessing',
                'round_number': 1,
                'phase_duration': 60,
                'responses': [
                    {'text': 'Response 1', 'author_id': 'player1'},
                    {'text': 'Response 2', 'author_id': 'player2'}
                ]
            }
        }
        
        self.mock_game_manager.get_phase_time_remaining.return_value = 45
        
        result = self.presenter.create_guessing_phase_data(room_state, 'room123')
        
        assert result['phase'] == 'guessing'
        assert len(result['responses']) == 2
        assert result['round_number'] == 1
        assert result['phase_duration'] == 60
        assert result['time_remaining'] == 45

    def test_create_guessing_phase_data_with_player_filter(self):
        """Test guessing phase data creation with player filtering"""
        room_state = {
            'game_state': {
                'phase': 'guessing',
                'round_number': 1,
                'phase_duration': 60,
                'responses': [
                    {'text': 'Response 1', 'author_id': 'player1'},
                    {'text': 'Response 2', 'author_id': 'player2'}
                ]
            }
        }
        
        self.mock_game_manager.get_phase_time_remaining.return_value = 45
        
        result = self.presenter.create_guessing_phase_data(room_state, 'room123', 'player1')
        
        assert result['phase'] == 'guessing'
        assert len(result['responses']) == 1  # player1's response filtered out
        assert result['responses'][0]['text'] == 'Response 2'

    def test_create_safe_prompt_data(self):
        """Test safe prompt data creation filters sensitive fields"""
        prompt = {
            'id': 'prompt1',
            'prompt': 'Test prompt',
            'model': 'gpt-4',
            'ai_response': 'Secret AI response',
            'internal_data': 'Should not be included'
        }
        
        result = self.presenter._create_safe_prompt_data(prompt)
        
        assert result['id'] == 'prompt1'
        assert result['prompt'] == 'Test prompt'
        assert result['model'] == 'gpt-4'
        assert 'ai_response' not in result
        assert 'internal_data' not in result

    def test_create_responding_phase_data(self):
        """Test responding phase specific data creation"""
        game_state = {
            'responses': [{'text': 'Response 1'}, {'text': 'Response 2'}]
        }
        
        self.mock_game_manager.get_phase_time_remaining.return_value = 90
        
        result = self.presenter._create_responding_phase_data(game_state, 'room123')
        
        assert result['response_count'] == 2
        assert result['time_remaining'] == 90

    def test_create_guessing_phase_data_internal(self):
        """Test guessing phase specific data creation"""
        game_state = {
            'responses': [
                {'text': 'Response 1', 'author_id': 'player1'},
                {'text': 'Response 2', 'author_id': 'player2'}
            ],
            'guesses': {'player1': 0, 'player2': 1}
        }
        
        self.mock_game_manager.get_phase_time_remaining.return_value = 45
        
        result = self.presenter._create_guessing_phase_data(game_state, 'room123')
        
        assert len(result['responses']) == 2
        assert result['guess_count'] == 2
        assert result['time_remaining'] == 45


class TestRoomStatePresenterEdgeCases:
    """Test edge cases and error scenarios"""

    def setup_method(self):
        """Setup test fixtures for edge case tests"""
        self.mock_game_manager = Mock()
        self.presenter = RoomStatePresenter(self.mock_game_manager)

    def test_create_safe_game_state_missing_prompt(self):
        """Test safe game state creation when current_prompt is None"""
        room_state = {
            'game_state': {
                'phase': 'responding',
                'round_number': 1,
                'phase_start_time': datetime.now(),
                'phase_duration': 120,
                'current_prompt': None,  # None case
                'responses': [],
                'guesses': {}
            }
        }
        
        self.mock_game_manager.get_phase_time_remaining.return_value = 90
        
        result = self.presenter.create_safe_game_state(room_state, 'room123')
        
        assert result['phase'] == 'responding'
        assert 'current_prompt' not in result  # Should not be included when None

    def test_create_responses_for_guessing_all_filtered(self):
        """Test response creation when all responses are filtered out"""
        game_state = {
            'responses': [
                {'text': 'Response 1', 'author_id': 'player1'},
                {'text': 'Response 2', 'author_id': 'player1'}
            ]
        }
        
        result = self.presenter.create_responses_for_guessing(game_state, exclude_player_id='player1')
        
        assert result == []

    def test_create_responses_for_guessing_missing_author_id(self):
        """Test response creation with missing author_id field"""
        game_state = {
            'responses': [
                {'text': 'Response 1'},  # Missing author_id
                {'text': 'Response 2', 'author_id': 'player2'}
            ]
        }
        
        result = self.presenter.create_responses_for_guessing(game_state, exclude_player_id='player1')
        
        # Should include both since first response doesn't have author_id to match
        assert len(result) == 2

    def test_create_player_list_with_missing_fields(self):
        """Test player list creation with missing player fields"""
        room_state = {
            'players': {
                'player1': {
                    'player_id': 'player1',
                    'name': 'Alice'
                    # Missing score and connected fields
                }
            }
        }
        
        # Should handle missing fields gracefully
        result = self.presenter.create_player_list(room_state)
        
        assert len(result) == 1
        assert result[0]['player_id'] == 'player1'
        assert result[0]['name'] == 'Alice'
        # KeyError would be raised if not handled properly