"""
Concurrency tests for RoomManager class.

Tests concurrent access patterns to ensure thread safety with the simplified locking strategy.
This file focuses exclusively on multi-threaded scenarios and race condition detection.
Basic functionality tests are covered in test_room_manager_comprehensive.py.
"""

import pytest
import threading
import time
from datetime import datetime
from src.room_manager import RoomManager


class TestRoomManagerConcurrency:
    """
    Test cases for RoomManager concurrency behavior.

    These tests specifically target thread safety and race conditions.
    They use multiple threads to stress-test the locking mechanisms
    and ensure data consistency under concurrent access.
    """
    
    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.results = []
        self.errors = []
    
    def test_concurrent_room_creation(self):
        """Test that concurrent room creation works correctly."""
        room_ids = [f"room_{i}" for i in range(10)]
        threads = []
        
        def create_room_worker(room_id):
            try:
                result = self.room_manager.create_room(room_id)
                self.results.append(('create', room_id, True, result['room_id']))
            except ValueError as e:
                # Expected for duplicate rooms
                self.results.append(('create', room_id, False, str(e)))
            except Exception as e:
                self.errors.append(('create', room_id, str(e)))
        
        # Start all threads
        for room_id in room_ids:
            thread = threading.Thread(target=create_room_worker, args=(room_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "Thread did not complete in time"
        
        # Check results
        assert len(self.errors) == 0, f"Unexpected errors: {self.errors}"
        assert len(self.results) == 10, "Should have 10 results"
        
        # All rooms should have been created successfully
        successful_creates = [r for r in self.results if r[2] is True]
        assert len(successful_creates) == 10
        
        # Verify room creation results consistency
        created_rooms = self.room_manager.get_all_rooms()
        assert len(created_rooms) == 10
    
    def test_concurrent_player_addition(self):
        """Test concurrent player addition to the same room."""
        room_id = "concurrent_test_room"
        self.room_manager.create_room(room_id)
        
        player_names = [f"Player_{i}" for i in range(5)]
        threads = []
        
        def add_player_worker(player_name):
            try:
                result = self.room_manager.add_player_to_room(
                    room_id, player_name, f"socket_{player_name}"
                )
                self.results.append(('add', player_name, True, result['player_id']))
            except ValueError as e:
                # Expected for duplicate names
                self.results.append(('add', player_name, False, str(e)))
            except Exception as e:
                self.errors.append(('add', player_name, str(e)))
        
        # Start all threads
        for player_name in player_names:
            thread = threading.Thread(target=add_player_worker, args=(player_name,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "Thread did not complete in time"
        
        # Check results
        assert len(self.errors) == 0, f"Unexpected errors: {self.errors}"
        assert len(self.results) == 5, "Should have 5 results"
        
        # All players should have been added successfully
        successful_adds = [r for r in self.results if r[2] is True]
        assert len(successful_adds) == 5
        
        # Verify room has all players
        players = self.room_manager.get_room_players(room_id)
        assert len(players) == 5
        
        player_names_in_room = {p['name'] for p in players}
        assert player_names_in_room == set(player_names)
    
    def test_concurrent_add_remove_players(self):
        """Test concurrent addition and removal of players."""
        room_id = "add_remove_test_room"
        self.room_manager.create_room(room_id)
        
        # Add some initial players
        initial_players = []
        for i in range(3):
            player = self.room_manager.add_player_to_room(
                room_id, f"Initial_{i}", f"socket_initial_{i}"
            )
            initial_players.append(player)
        
        threads = []
        
        def add_player_worker():
            for i in range(2):
                try:
                    result = self.room_manager.add_player_to_room(
                        room_id, f"New_{threading.current_thread().ident}_{i}", 
                        f"socket_new_{threading.current_thread().ident}_{i}"
                    )
                    self.results.append(('add', result['name'], True, result['player_id']))
                except Exception as e:
                    self.errors.append(('add', f"thread_{threading.current_thread().ident}", str(e)))
        
        def remove_player_worker():
            # Remove initial players
            for player in initial_players:
                try:
                    result = self.room_manager.remove_player_from_room(
                        room_id, player['player_id']
                    )
                    self.results.append(('remove', player['name'], result, player['player_id']))
                except Exception as e:
                    self.errors.append(('remove', player['name'], str(e)))
        
        # Start threads
        for _ in range(2):  # 2 add worker threads
            thread = threading.Thread(target=add_player_worker)
            threads.append(thread)
            thread.start()
        
        thread = threading.Thread(target=remove_player_worker)
        threads.append(thread)
        thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "Thread did not complete in time"
        
        # Check for errors
        assert len(self.errors) == 0, f"Unexpected errors: {self.errors}"
        
        # Verify final state is consistent
        if self.room_manager.room_exists(room_id):
            players = self.room_manager.get_room_players(room_id)
            # Should have 4 new players (2 from each add worker)
            assert len(players) == 4
    
    def test_concurrent_room_creation_and_deletion(self):
        """Test concurrent room creation and deletion."""
        room_ids = [f"room_{i}" for i in range(3)]
        threads = []
        
        def create_delete_worker(room_id):
            try:
                # Create room
                self.room_manager.create_room(room_id)
                self.results.append(('create', room_id, True, None))
                
                # Add a small delay to increase chance of race conditions
                time.sleep(0.001)
                
                # Delete room
                result = self.room_manager.delete_room(room_id)
                self.results.append(('delete', room_id, result, None))
                
            except Exception as e:
                self.errors.append((room_id, str(e)))
        
        # Start all threads
        for room_id in room_ids:
            thread = threading.Thread(target=create_delete_worker, args=(room_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "Thread did not complete in time"
        
        # Check results
        assert len(self.errors) == 0, f"Unexpected errors: {self.errors}"
        
        # Should have 6 results (3 creates + 3 deletes)
        assert len(self.results) == 6
        
        # All creates should succeed
        creates = [r for r in self.results if r[0] == 'create']
        assert len(creates) == 3
        assert all(r[2] is True for r in creates)
        
        # All deletes should succeed
        deletes = [r for r in self.results if r[0] == 'delete']
        assert len(deletes) == 3
        assert all(r[2] is True for r in deletes)
        
        # No rooms should exist after deletion
        for room_id in room_ids:
            assert not self.room_manager.room_exists(room_id)
    
    def test_concurrent_game_state_updates(self):
        """Test concurrent game state updates on the same room."""
        room_id = "game_state_test_room"
        self.room_manager.create_room(room_id)
        
        threads = []
        phase_sequence = ["responding", "guessing", "results", "waiting"]
        
        def update_game_state_worker(phase):
            try:
                game_state = {
                    "phase": phase,
                    "current_prompt": f"Test prompt for {phase}",
                    "responses": [],
                    "guesses": {},
                    "round_number": 1,
                    "phase_start_time": None,
                    "phase_duration": 0
                }
                result = self.room_manager.update_game_state(room_id, game_state)
                self.results.append(('update', phase, result, None))
            except Exception as e:
                self.errors.append(('update', phase, str(e)))
        
        # Start threads for each phase
        for phase in phase_sequence:
            thread = threading.Thread(target=update_game_state_worker, args=(phase,))
            threads.append(thread)
            thread.start()
            # Small delay to encourage race conditions but maintain some ordering
            time.sleep(0.001)
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "Thread did not complete in time"
        
        # Check results
        assert len(self.errors) == 0, f"Unexpected errors: {self.errors}"
        assert len(self.results) == len(phase_sequence)
        
        # At least some updates should succeed (some may fail due to invalid transitions)
        successful_updates = [r for r in self.results if r[2] is True]
        assert len(successful_updates) >= 1
        
        # Final state should be consistent
        room_state = self.room_manager.get_room_state(room_id)
        assert room_state is not None
        assert "phase" in room_state["game_state"]
    
    def test_concurrent_player_operations_multiple_rooms(self):
        """Test concurrent operations across multiple rooms."""
        room_ids = [f"multi_room_{i}" for i in range(3)]
        
        # Create rooms
        for room_id in room_ids:
            self.room_manager.create_room(room_id)
        
        threads = []
        
        def multi_room_worker(worker_id):
            try:
                # Add player to each room
                for room_id in room_ids:
                    player = self.room_manager.add_player_to_room(
                        room_id, f"Worker_{worker_id}", f"socket_{worker_id}_{room_id}"
                    )
                    self.results.append(('add', room_id, worker_id, player['player_id']))
                
                # Update connections
                for room_id in room_ids:
                    players = self.room_manager.get_room_players(room_id)
                    for player in players:
                        if player['name'] == f"Worker_{worker_id}":
                            self.room_manager.disconnect_player_from_room(
                                room_id, player['player_id']
                            )
                            self.results.append(('disconnect', room_id, worker_id, player['player_id']))
                            break
                
            except Exception as e:
                self.errors.append((worker_id, str(e)))
        
        # Start worker threads
        for worker_id in range(2):
            thread = threading.Thread(target=multi_room_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "Thread did not complete in time"
        
        # Check results
        assert len(self.errors) == 0, f"Unexpected errors: {self.errors}"
        
        # Should have results for all operations
        adds = [r for r in self.results if r[0] == 'add']
        disconnects = [r for r in self.results if r[0] == 'disconnect']
        
        assert len(adds) == 6  # 2 workers * 3 rooms
        assert len(disconnects) == 6  # 2 workers * 3 rooms
        
        # Verify final state
        for room_id in room_ids:
            players = self.room_manager.get_room_players(room_id)
            assert len(players) == 2  # 2 workers per room
            
            # All players should be disconnected
            connected_players = self.room_manager.get_connected_players(room_id)
            assert len(connected_players) == 0
    
    def test_stress_concurrent_operations(self):
        """Stress test with many concurrent operations (respecting room capacity)."""
        room_id = "stress_test_room"
        self.room_manager.create_room(room_id)
        
        threads = []
        num_threads = 8  # Limit to room capacity
        operations_per_thread = 1  # One player per thread to avoid capacity issues
        
        def stress_worker(worker_id):
            try:
                for i in range(operations_per_thread):
                    # Add player
                    player_name = f"Stress_{worker_id}_{i}"
                    try:
                        player = self.room_manager.add_player_to_room(
                            room_id, player_name, f"socket_{worker_id}_{i}"
                        )
                        
                        # Update activity
                        self.room_manager.update_room_activity(room_id)
                        
                        # Update player connection status
                        if i % 2 == 0:
                            # Reconnect player
                            # Note: reconnection is handled via add_player_to_room with existing name
                            pass
                        else:
                            # Disconnect player
                            self.room_manager.disconnect_player_from_room(
                                room_id, player['player_id']
                            )
                        
                        # Update score
                        self.room_manager.update_player_score(
                            room_id, player['player_id'], i * 10
                        )
                        
                        self.results.append((worker_id, i, 'completed'))
                        
                    except ValueError as e:
                        if "is full" in str(e):
                            # Room capacity reached - this is expected behavior
                            self.results.append((worker_id, i, 'room_full'))
                        else:
                            self.errors.append((worker_id, str(e)))
                    
            except Exception as e:
                self.errors.append((worker_id, str(e)))
        
        # Start all threads
        for worker_id in range(num_threads):
            thread = threading.Thread(target=stress_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10.0)  # Longer timeout for stress test
            assert not thread.is_alive(), "Thread did not complete in time"
        
        # Check results - no unexpected errors
        assert len(self.errors) == 0, f"Unexpected errors: {self.errors}"
        assert len(self.results) == num_threads * operations_per_thread
        
        # Count successful vs room-full results
        completed = [r for r in self.results if r[2] == 'completed']
        room_full = [r for r in self.results if r[2] == 'room_full']
        
        # Should have exactly 8 completed (room capacity) and 0 room_full in this case
        assert len(completed) == 8
        assert len(room_full) == 0
        
        # Verify final room state is consistent
        room_state = self.room_manager.get_room_state(room_id)
        assert room_state is not None
        
        players = self.room_manager.get_room_players(room_id)
        assert len(players) == 8  # Room capacity
        
        # All players should have valid data
        for player in players:
            assert 'player_id' in player
            assert 'name' in player
            assert 'score' in player
            assert isinstance(player['score'], int)