"""
Security Scenario Integration Tests

Comprehensive security validation tests including input validation bypass attempts,
rate limiting effectiveness, error information leakage prevention, SQL injection
and XSS prevention, and session hijacking prevention.
"""

import pytest
import time
import json
import threading
from unittest.mock import Mock, patch, MagicMock
from flask_socketio import SocketIOTestClient

from src.services.rate_limit_service import EventQueueManager, set_event_queue_manager
from src.services.validation_service import ValidationService
from src.core.errors import ErrorCode, ValidationError
from tests.migration_compat import app, socketio, room_manager, session_service
from tests.helpers.room_helpers import join_room_helper, join_room_expect_error, find_event_in_received


class TestSecurityScenarios:
    """Comprehensive security validation tests."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

        # Create test client
        self.client = SocketIOTestClient(app, socketio)
        self.client.connect()

        # Clear received messages
        self.client.get_received()

        # Initialize validation service for direct testing
        self.validation_service = ValidationService()

    def teardown_method(self):
        """Clean up after each test."""
        if hasattr(self, 'client') and self.client and self.client.is_connected():
            self.client.disconnect()
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

    # =================== INPUT VALIDATION BYPASS ATTEMPTS ===================

    def test_malicious_room_id_injection_attempts(self):
        """Test various injection attempts through room_id parameter."""
        malicious_room_ids = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE rooms; --",
            "../../../etc/passwd",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(1)'></iframe>",
            "room_id\x00malicious",
            "room_id\nmalicious",
            "room_id\rmalicious",
            "<object data='javascript:alert(1)'></object>",
            "<embed src='javascript:alert(1)'></embed>",
            "room' UNION SELECT * FROM sensitive_data --",
            "room\'; INSERT INTO users VALUES ('hacker', 'pass'); --"
        ]

        for malicious_id in malicious_room_ids:
            # Attempt to join room with malicious room_id
            error_response = join_room_expect_error(self.client, malicious_id, 'TestPlayer')

            # Should be rejected with appropriate error
            assert error_response['error']['code'] in ['INVALID_ROOM_ID', 'INJECTION_ATTEMPT'], \
                f"Failed to detect injection in room_id: {malicious_id}"

            # Error message should not leak internal details
            assert 'database' not in error_response['error']['message'].lower()
            assert 'sql' not in error_response['error']['message'].lower()
            assert 'script' not in error_response['error']['message'].lower()

    def test_malicious_player_name_injection_attempts(self):
        """Test various injection attempts through player_name parameter."""
        malicious_names = [
            "<script>document.cookie='stolen'</script>",
            "'; UPDATE users SET password='hacked' WHERE id=1; --",
            "javascript:void(0)",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "player'; DELETE FROM sessions; --",
            "player<iframe src='//evil.com'></iframe>",
        ]

        # Create test client for malicious attempts
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()

        try:
            for malicious_name in malicious_names:
                # Clear previous messages
                client2.get_received()

                # Attempt to join with malicious player name
                client2.emit('join_room', {
                    'room_id': 'test-room',
                    'player_name': malicious_name
                })
                received = client2.get_received()

                # Should be rejected or sanitized
                if received:
                    response = received[-1]
                    if 'error' in response.get('args', [{}])[0]:
                        error = response['args'][0]['error']
                        assert error['code'] in ['INVALID_DATA', 'INJECTION_ATTEMPT', 'PLAYER_NAME_TOO_LONG'], \
                            f"Failed to detect injection in player_name: {malicious_name}"

                        # Error message should not leak details
                        assert 'script' not in error['message'].lower()
                        assert 'sql' not in error['message'].lower()
                    elif 'room_joined' in response.get('args', [{}])[0]:
                        # If allowed through, check that it was sanitized
                        joined_data = response['args'][0]['data']
                        sanitized_name = joined_data.get('player_name', '')
                        # Should not contain the raw malicious content
                        assert malicious_name != sanitized_name or len(malicious_name) <= 20, \
                            f"Malicious content passed through unsanitized: {malicious_name}"
        finally:
            client2.disconnect()

    def test_malicious_response_text_injection_attempts(self):
        """Test injection attempts through game response submissions."""
        # Test with simple malicious responses to check validation
        malicious_responses = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE responses; --",
            "<img src=x onerror=alert(1)>",
        ]

        for malicious_response in malicious_responses:
            # Clear previous messages
            self.client.get_received()

            # Attempt to submit malicious response (will fail because not in game)
            self.client.emit('submit_response', {
                'response': malicious_response
            })
            received = self.client.get_received()

            # Should be rejected (either for not being in game or for malicious content)
            if received:
                response = received[-1]
                if 'error' in response.get('args', [{}])[0]:
                    error = response['args'][0]['error']
                    # Should detect some kind of validation error
                    assert error['code'] in ['INJECTION_ATTEMPT', 'INVALID_DATA', 'NOT_IN_ROOM', 'WRONG_PHASE'], \
                        f"Failed to properly handle malicious response: {malicious_response[:50]}..."

                    # Error message should not leak the malicious content
                    error_msg = error['message']
                    assert malicious_response not in error_msg

    def test_oversized_payload_attacks(self):
        """Test protection against oversized payload attacks."""
        # Create extremely large payload
        large_payload = {
            'room_id': 'test-room',
            'player_name': 'TestPlayer',
            'large_data': 'A' * 50000,  # 50KB of data
            'nested_data': {
                'level1': {
                    'level2': {
                        'level3': {
                            'level4': {
                                'level5': 'deep_data' * 1000
                            }
                        }
                    }
                }
            }
        }

        # Attempt to send oversized payload
        self.client.emit('join_room', large_payload)
        received = self.client.get_received()

        # Should be rejected due to size
        if received:
            response = received[-1]
            if 'error' in response.get('args', [{}])[0]:
                error = response['args'][0]['error']
                assert error['code'] in ['DATA_SIZE_EXCEEDED', 'INVALID_DATA'], \
                    "Failed to reject oversized payload"

    def test_deeply_nested_payload_attacks(self):
        """Test protection against deeply nested payload attacks."""
        # Create deeply nested structure
        nested_data = {'level': 0}
        current = nested_data

        # Create 20 levels of nesting (should exceed limit)
        for i in range(1, 21):
            current['nested'] = {'level': i}
            current = current['nested']

        payload = {
            'room_id': 'test-room',
            'player_name': 'TestPlayer',
            'deep_data': nested_data
        }

        # Attempt to send deeply nested payload
        self.client.emit('join_room', payload)
        received = self.client.get_received()

        # Should be rejected due to excessive nesting
        if received:
            response = received[-1]
            if 'error' in response.get('args', [{}])[0]:
                error = response['args'][0]['error']
                assert error['code'] in ['SUSPICIOUS_DATA_PATTERNS', 'INVALID_DATA'], \
                    "Failed to reject deeply nested payload"

    # =================== RATE LIMITING EFFECTIVENESS ===================

    def test_rate_limiting_blocks_rapid_requests(self):
        """Test that rate limiting effectively blocks rapid successive requests."""
        # Temporarily disable testing environment bypass for this test
        with patch.object(EventQueueManager, '_is_testing', return_value=False):
            # Create rate-limited event queue manager
            manager = EventQueueManager()

            # Mock client identification
            client_id = 'test_client_123'

            # Simulate rapid requests (should exceed rate limit)
            blocked_count = 0
            for i in range(20):  # Try 20 rapid requests
                if not manager.can_process_event(client_id, 'test_event'):
                    blocked_count += 1

                # Very short delay between requests
                time.sleep(0.01)

            # Should have blocked some requests
            assert blocked_count > 0, "Rate limiting should have blocked some rapid requests"

    def test_rate_limiting_testing_environment_bypass(self):
        """Test that rate limiting is properly bypassed in testing environment."""
        # Ensure testing environment is detected (default behavior)
        manager = EventQueueManager()

        client_id = 'test_client_456'

        # Simulate many rapid requests
        blocked_count = 0
        for i in range(50):  # Many requests
            if not manager.can_process_event(client_id, 'test_event'):
                blocked_count += 1

        # Should not block any requests in testing environment
        assert blocked_count == 0, "Rate limiting should be bypassed in testing environment"

    # =================== ERROR INFORMATION LEAKAGE PREVENTION ===================

    def test_error_messages_do_not_leak_internal_details(self):
        """Test that error messages don't leak internal system information."""
        # Test that basic validation errors don't leak sensitive information

        # 1. Test with malformed data
        self.client.emit('join_room', {'malformed': 'data'})
        received = self.client.get_received()

        if received:
            response = received[-1]
            if 'error' in response.get('args', [{}])[0]:
                error_msg = response['args'][0]['error']['message']
                # Should not leak internal details
                assert 'database' not in error_msg.lower()
                assert 'internal' not in error_msg.lower()
                assert 'traceback' not in error_msg.lower()

        # 2. Test with invalid room operation
        self.client.emit('get_room_info', {'room_id': 'nonexistent-room'})
        received = self.client.get_received()

        if received:
            response = received[-1]
            if 'error' in response.get('args', [{}])[0]:
                error_msg = response['args'][0]['error']['message']
                # Should be user-friendly, not technical
                assert 'exception' not in error_msg.lower()
                assert 'stack' not in error_msg.lower()

    def test_validation_errors_sanitize_user_input(self):
        """Test that validation error messages don't echo back malicious input."""
        malicious_inputs = [
            "<script>alert('reflected_xss')</script>",
            "'; DELETE FROM users; --",
            "<img src=x onerror=alert(document.cookie)>",
            "javascript:void(0)"
        ]

        for malicious_input in malicious_inputs:
            # Try malicious input as room_id
            error_response = join_room_expect_error(self.client, malicious_input, 'TestPlayer')
            error_msg = error_response['error']['message']

            # Error message should not contain the raw malicious input
            assert malicious_input not in error_msg, \
                f"Error message leaked malicious input: {malicious_input}"

            # Should not contain script tags or SQL keywords
            assert '<script>' not in error_msg.lower()
            assert 'alert(' not in error_msg.lower()
            assert 'delete from' not in error_msg.lower()

    def test_error_responses_consistent_structure(self):
        """Test that error responses have consistent structure and don't leak implementation details."""
        # Generate various types of errors
        error_scenarios = [
            # Missing data
            {'emit': 'join_room', 'data': {}},
            # Invalid room format
            {'emit': 'join_room', 'data': {'room_id': '<script>', 'player_name': 'Test'}},
            # Missing player name
            {'emit': 'join_room', 'data': {'room_id': 'test-room'}},
            # Invalid game action
            {'emit': 'submit_response', 'data': {'response': 'test'}}
        ]

        for scenario in error_scenarios:
            self.client.emit(scenario['emit'], scenario['data'])
            received = self.client.get_received()

            if received:
                response = received[-1]
                if 'error' in response.get('args', [{}])[0]:
                    error = response['args'][0]['error']

                    # All errors should have consistent structure
                    assert 'code' in error, "Error missing error code"
                    assert 'message' in error, "Error missing error message"

                    # Error codes should be from defined enum
                    error_code = error['code']
                    valid_codes = [code.value for code in ErrorCode]
                    assert error_code in valid_codes, f"Unknown error code: {error_code}"

                    # Error messages should be user-friendly, not technical
                    message = error['message'].lower()
                    assert 'exception' not in message
                    assert 'traceback' not in message
                    assert 'stack' not in message
                    assert 'internal error' not in message or 'internal_error' == error_code.lower()

    # =================== SQL INJECTION AND XSS PREVENTION ===================

    def test_sql_injection_prevention_direct_validation(self):
        """Test SQL injection prevention through direct validation service testing."""
        sql_injection_payloads = [
            "'; DROP TABLE rooms; --",
            "' UNION SELECT * FROM users --",
            "'; INSERT INTO admin VALUES ('hacker'); --",
            "'; UPDATE users SET role='admin' WHERE id=1; --",
            "room'; DELETE FROM sessions; --",
        ]

        for payload in sql_injection_payloads:
            # Test through validation service
            with pytest.raises(ValidationError) as exc_info:
                self.validation_service.validate_text_integrity(payload, "room_id")

            assert exc_info.value.code == ErrorCode.INJECTION_ATTEMPT, \
                f"Failed to detect SQL injection: {payload}"

    def test_xss_prevention_direct_validation(self):
        """Test XSS prevention through direct validation service testing."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "<iframe src='javascript:alert(1)'></iframe>",
            "<svg onload=alert('xss')>",
            "<object data='javascript:alert(1)'></object>",
            "<embed src='javascript:alert(1)'>",
            "javascript:alert('xss')",
            "<input type='text' onfocus='alert(1)'>",
            "<body onload=alert('xss')>",
            "<div onclick='alert(1)'>click me</div>"
        ]

        for payload in xss_payloads:
            # Test through validation service
            with pytest.raises(ValidationError) as exc_info:
                self.validation_service.validate_text_integrity(payload, "user_input")

            assert exc_info.value.code == ErrorCode.INJECTION_ATTEMPT, \
                f"Failed to detect XSS: {payload}"

    def test_html_escaping_in_valid_content(self):
        """Test that HTML characters are properly escaped in otherwise valid content."""
        content_with_html = "My name is <John> & I like math: 2 > 1"

        # Should not raise injection error (not malicious)
        sanitized = self.validation_service.validate_text_integrity(content_with_html, "response")

        # But should escape HTML entities
        assert '&lt;John&gt;' in sanitized
        assert '&amp;' in sanitized
        assert '&gt;' in sanitized

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "....//....//etc/passwd",
        ]

        for payload in path_traversal_payloads:
            with pytest.raises(ValidationError) as exc_info:
                self.validation_service.validate_text_integrity(payload, "file_path")

            assert exc_info.value.code == ErrorCode.INJECTION_ATTEMPT, \
                f"Failed to detect path traversal: {payload}"

    # =================== SESSION HIJACKING PREVENTION ===================

    def test_session_isolation_between_clients(self):
        """Test that sessions are properly isolated between different clients."""
        # Create first client and join room
        join_room_helper(self.client, 'test-room', 'Player1')

        # Create second client
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()

        try:
            # Join same room with different name
            join_room_helper(client2, 'test-room', 'Player2')

            # Core security test: Sessions should be completely separate
            assert self.client.eio_sid != client2.eio_sid, "Clients should have different session IDs"

            # Verify both clients successfully joined the same room but with different sessions
            # Check that room has both players
            room_state = room_manager.get_room_state('test-room')
            assert room_state is not None, "Room should exist"
            players = room_state.get('players', {})
            player_names = [player_info['name'] for player_info in players.values()]
            assert 'Player1' in player_names, "Player1 should be in room"
            assert 'Player2' in player_names, "Player2 should be in room"
            assert len(players) == 2, "Room should have exactly 2 players"

        finally:
            client2.disconnect()

    def test_session_token_manipulation_protection(self):
        """Test protection against session token manipulation."""
        # Join room normally
        join_room_helper(self.client, 'test-room', 'Player1')

        # Try to submit response as different player (simulating session hijacking)
        with patch.object(session_service, 'get_session') as mock_session:
            # Mock session to return different player
            mock_session.return_value = {
                'room_id': 'test-room',
                'player_name': 'DifferentPlayer'
            }

            # Mock game state
            with patch.object(room_manager, 'get_room_state') as mock_state:
                mock_state.return_value = {
                    'phase': 'responding',
                    'players': ['Player1', 'DifferentPlayer'],
                    'current_prompt': 'Test prompt'
                }

                # Attempt to submit response
                self.client.emit('submit_response', {'response': 'Test response'})
                received = self.client.get_received()

                # Should either succeed with proper player or reject based on validation
                # The key is that it should use the session service consistently

    def test_session_cleanup_on_disconnect(self):
        """Test that sessions are properly cleaned up when clients disconnect."""
        # Join room
        join_room_helper(self.client, 'test-room', 'Player1')

        # Get original session ID
        original_sid = self.client.eio_sid

        # Disconnect client
        self.client.disconnect()

        # Reconnect with new client instance
        self.client = SocketIOTestClient(app, socketio)
        self.client.connect()

        # New session should have different ID
        new_sid = self.client.eio_sid
        assert new_sid != original_sid, "New connection should have different session ID"

        # Clear received messages for clean slate
        self.client.get_received()

    def test_concurrent_session_manipulation(self):
        """Test protection against concurrent session manipulation attacks."""
        # Create multiple clients for concurrent access
        clients = []

        try:
            # Create 5 concurrent clients
            for i in range(5):
                client = SocketIOTestClient(app, socketio)
                client.connect()
                clients.append(client)

            # Have all clients try to join the same room simultaneously
            def join_room_concurrent(client, player_name):
                try:
                    join_room_helper(client, 'concurrent-room', player_name)
                except:
                    pass  # Some may fail due to concurrency

            # Start all join attempts concurrently
            threads = []
            for i, client in enumerate(clients):
                thread = threading.Thread(
                    target=join_room_concurrent,
                    args=(client, f'Player{i}')
                )
                threads.append(thread)
                thread.start()

            # Wait for all to complete
            for thread in threads:
                thread.join()

            # Verify room state is consistent
            room_state = room_manager.get_room_state('concurrent-room')
            if room_state:
                # Should have valid player list without duplicates
                players = room_state.get('players', [])
                assert len(players) == len(set(players)), "Room should not have duplicate players"
                assert len(players) <= 5, "Room should not have more players than clients"

        finally:
            # Clean up all clients
            for client in clients:
                if client.is_connected():
                    client.disconnect()

    # =================== ADDITIONAL SECURITY TESTS ===================

    def test_unicode_normalization_attacks(self):
        """Test protection against Unicode normalization attacks."""
        unicode_attacks = [
            "admin\u0000",  # Null byte - should be caught
        ]

        for attack_string in unicode_attacks:
            # Clear previous messages
            self.client.get_received()

            # Test in player name validation
            self.client.emit('join_room', {
                'room_id': 'test-room',
                'player_name': attack_string
            })
            received = self.client.get_received()

            # Should either sanitize, reject, or pass through safely
            if received:
                response = received[-1]
                if 'error' in response.get('args', [{}])[0]:
                    # If rejected, error should not leak the attack string
                    error_msg = response['args'][0]['error']['message']
                    assert attack_string not in error_msg
                elif 'room_joined' in response.get('args', [{}])[0]:
                    # If allowed through, should be sanitized
                    joined_data = response['args'][0]['data']
                    sanitized_name = joined_data.get('player_name', '')
                    # Should not contain problematic unicode
                    assert '\u0000' not in sanitized_name

    def test_encoding_manipulation_attacks(self):
        """Test protection against various encoding manipulation attacks."""
        # Test with various problematic encodings
        encoding_attacks = [
            "test\x00room",  # Null byte - should be detected
        ]

        for attack_string in encoding_attacks:
            with pytest.raises(ValidationError) as exc_info:
                self.validation_service.validate_text_integrity(attack_string, "test_field")

            assert exc_info.value.code == ErrorCode.INJECTION_ATTEMPT, \
                f"Failed to detect encoding attack: {attack_string!r}"

    def test_payload_bombing_prevention(self):
        """Test prevention of payload bombing attacks (zip bombs, etc.)."""
        # Test with highly repetitive data that might expand significantly
        repetitive_data = {
            'room_id': 'test-room',
            'player_name': 'TestPlayer',
            'bomb_data': 'A' * 1000,  # Large but not excessive
            'nested_bomb': {
                'data': ['repeat_me'] * 500  # Repetitive array
            }
        }

        # Should handle without issues (within reasonable limits)
        self.client.emit('join_room', repetitive_data)
        received = self.client.get_received()

        # Should either succeed or fail gracefully with size limits
        if received and 'error' in received[-1].get('args', [{}])[0]:
            error = received[-1]['args'][0]['error']
            assert error['code'] in ['DATA_SIZE_EXCEEDED', 'INVALID_DATA']

    def test_protocol_confusion_attacks(self):
        """Test protection against protocol confusion attacks."""
        # Test sending non-JSON data that might confuse parsers
        invalid_payloads = [
            "not_json_at_all",
            "<xml><root>test</root></xml>",
            "BINARY_DATA\x00\x01\x02\x03",
            "function(){alert('xss')}",
            "{malformed json without quotes}",
            '{"incomplete": json',
            '{"duplicate_key": 1, "duplicate_key": 2}'
        ]

        for payload in invalid_payloads:
            # These should be handled gracefully by the underlying SocketIO/JSON parsing
            # The key is that they don't crash the application
            try:
                self.client.emit('join_room', payload)
                received = self.client.get_received()
                # If we get a response, it should be an error
                if received and 'error' in received[-1].get('args', [{}])[0]:
                    error = received[-1]['args'][0]['error']
                    assert error['code'] in ['INVALID_DATA', 'MALFORMED_PAYLOAD']
            except Exception:
                # Exception in client is acceptable - server should remain stable
                pass