"""
Tests for validation utilities module.

This module tests the validation utility functions that provide
common validation patterns across handlers.
"""

import pytest
from unittest.mock import Mock
from typing import Dict, Any

from src.utils.validation_utils import (
    validate_dict_structure,
    validate_session_exists,
    validate_game_phase,
    validate_phase_not_expired,
    validate_join_room_data,
    validate_submit_response_data,
    validate_submit_guess_data
)
from src.core.errors import ErrorCode, ValidationError


class TestValidateDictStructure:
    """Test validate_dict_structure function."""

    def test_valid_dict_with_all_required_fields(self):
        """Test that valid dict with all required fields passes."""
        data = {'room_id': 'test123', 'player_name': 'Alice'}
        required_fields = ['room_id', 'player_name']

        result = validate_dict_structure(data, required_fields)

        assert result == data

    def test_valid_dict_with_extra_fields(self):
        """Test that valid dict with extra fields passes."""
        data = {'room_id': 'test123', 'player_name': 'Alice', 'extra': 'value'}
        required_fields = ['room_id', 'player_name']

        result = validate_dict_structure(data, required_fields)

        assert result == data

    def test_empty_required_fields_passes(self):
        """Test that dict passes when no required fields specified."""
        data = {'anything': 'value'}
        required_fields = []

        result = validate_dict_structure(data, required_fields)

        assert result == data

    def test_invalid_data_type_raises_error(self):
        """Test that non-dict data raises ValidationError."""
        invalid_data = "not a dict"
        required_fields = ['field']

        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(invalid_data, required_fields)

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format - expected dictionary" in exc_info.value.message

    def test_none_data_raises_error(self):
        """Test that None data raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(None, ['field'])

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format - expected dictionary" in exc_info.value.message

    def test_list_data_raises_error(self):
        """Test that list data raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure([1, 2, 3], ['field'])

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format - expected dictionary" in exc_info.value.message

    def test_missing_room_id_specific_error(self):
        """Test specific error for missing room_id field."""
        data = {'player_name': 'Alice'}
        required_fields = ['room_id', 'player_name']

        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(data, required_fields)

        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID
        assert "Room ID is required" in exc_info.value.message

    def test_missing_player_name_specific_error(self):
        """Test specific error for missing player_name field."""
        data = {'room_id': 'test123'}
        required_fields = ['room_id', 'player_name']

        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(data, required_fields)

        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        assert "Player name is required" in exc_info.value.message

    def test_missing_response_specific_error(self):
        """Test specific error for missing response field."""
        data = {}
        required_fields = ['response']

        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(data, required_fields)

        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
        assert "Response is required" in exc_info.value.message

    def test_missing_guess_index_specific_error(self):
        """Test specific error for missing guess_index field."""
        data = {}
        required_fields = ['guess_index']

        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(data, required_fields)

        assert exc_info.value.code == ErrorCode.MISSING_GUESS
        assert "Guess index is required" in exc_info.value.message

    def test_missing_multiple_fields_generic_error(self):
        """Test generic error for multiple missing fields."""
        data = {}
        required_fields = ['room_id', 'player_name']

        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(data, required_fields)

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Missing required fields: room_id, player_name" in exc_info.value.message

    def test_missing_unknown_field_generic_error(self):
        """Test generic error for missing unknown field."""
        data = {}
        required_fields = ['unknown_field']

        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(data, required_fields)

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Missing required fields: unknown_field" in exc_info.value.message

    def test_missing_combination_with_known_field_generic_error(self):
        """Test that multiple fields including known ones use generic error."""
        data = {}
        required_fields = ['room_id', 'unknown_field']

        with pytest.raises(ValidationError) as exc_info:
            validate_dict_structure(data, required_fields)

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Missing required fields: room_id, unknown_field" in exc_info.value.message


class TestValidateSessionExists:
    """Test validate_session_exists function."""

    def test_valid_session_info_passes(self):
        """Test that valid session info passes validation."""
        session_info = {'player_id': 'player1', 'room_id': 'room123'}

        result = validate_session_exists(session_info)

        assert result == session_info

    def test_empty_dict_session_raises_error(self):
        """Test that empty dict session raises ValidationError (empty dict is falsy)."""
        session_info = {}

        with pytest.raises(ValidationError) as exc_info:
            validate_session_exists(session_info)

        assert exc_info.value.code == ErrorCode.NOT_IN_ROOM
        assert "You are not currently in a room" in exc_info.value.message

    def test_none_session_raises_error(self):
        """Test that None session raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_session_exists(None)

        assert exc_info.value.code == ErrorCode.NOT_IN_ROOM
        assert "You are not currently in a room" in exc_info.value.message

    def test_falsy_session_raises_error(self):
        """Test that falsy session values raise ValidationError."""
        for falsy_value in [False, 0, "", []]:
            with pytest.raises(ValidationError) as exc_info:
                validate_session_exists(falsy_value)

            assert exc_info.value.code == ErrorCode.NOT_IN_ROOM
            assert "You are not currently in a room" in exc_info.value.message


class TestValidateGamePhase:
    """Test validate_game_phase function."""

    def test_valid_game_state_and_phase_passes(self):
        """Test that valid game state with correct phase passes."""
        game_state = {'phase': 'responding', 'round': 1}
        expected_phase = 'responding'

        result = validate_game_phase(game_state, expected_phase)

        assert result == game_state

    def test_none_game_state_raises_error(self):
        """Test that None game state raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase(None, 'responding')

        assert exc_info.value.code == ErrorCode.ROOM_NOT_FOUND
        assert "Room not found or game not started" in exc_info.value.message

    def test_empty_game_state_raises_error(self):
        """Test that empty game state raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase({}, 'responding')

        assert exc_info.value.code == ErrorCode.ROOM_NOT_FOUND
        assert "Room not found or game not started" in exc_info.value.message

    def test_falsy_game_state_raises_error(self):
        """Test that falsy game state values raise ValidationError."""
        for falsy_value in [False, 0, "", []]:
            with pytest.raises(ValidationError) as exc_info:
                validate_game_phase(falsy_value, 'responding')

            assert exc_info.value.code == ErrorCode.ROOM_NOT_FOUND
            assert "Room not found or game not started" in exc_info.value.message

    def test_wrong_phase_responding_specific_message(self):
        """Test specific error message for wrong responding phase."""
        game_state = {'phase': 'guessing'}

        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase(game_state, 'responding')

        assert exc_info.value.code == ErrorCode.WRONG_PHASE
        assert "Responses can only be submitted during the responding phase" in exc_info.value.message

    def test_wrong_phase_guessing_specific_message(self):
        """Test specific error message for wrong guessing phase."""
        game_state = {'phase': 'responding'}

        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase(game_state, 'guessing')

        assert exc_info.value.code == ErrorCode.WRONG_PHASE
        assert "Guesses can only be submitted during the guessing phase" in exc_info.value.message

    def test_wrong_phase_results_specific_message(self):
        """Test specific error message for wrong results phase."""
        game_state = {'phase': 'responding'}

        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase(game_state, 'results')

        assert exc_info.value.code == ErrorCode.WRONG_PHASE
        assert "Results are only available during the results phase" in exc_info.value.message

    def test_wrong_phase_waiting_specific_message(self):
        """Test specific error message for wrong waiting phase."""
        game_state = {'phase': 'responding'}

        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase(game_state, 'waiting')

        assert exc_info.value.code == ErrorCode.WRONG_PHASE
        assert "This action can only be performed while waiting for players" in exc_info.value.message

    def test_wrong_phase_unknown_generic_message(self):
        """Test generic error message for unknown phase."""
        game_state = {'phase': 'responding'}

        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase(game_state, 'unknown_phase')

        assert exc_info.value.code == ErrorCode.WRONG_PHASE
        assert "Game must be in unknown_phase phase" in exc_info.value.message

    def test_missing_phase_field_wrong_phase_error(self):
        """Test that missing phase field is treated as wrong phase."""
        game_state = {'round': 1}

        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase(game_state, 'responding')

        assert exc_info.value.code == ErrorCode.WRONG_PHASE
        assert "Responses can only be submitted during the responding phase" in exc_info.value.message

    def test_none_phase_field_wrong_phase_error(self):
        """Test that None phase field is treated as wrong phase."""
        game_state = {'phase': None}

        with pytest.raises(ValidationError) as exc_info:
            validate_game_phase(game_state, 'responding')

        assert exc_info.value.code == ErrorCode.WRONG_PHASE
        assert "Responses can only be submitted during the responding phase" in exc_info.value.message


class TestValidatePhaseNotExpired:
    """Test validate_phase_not_expired function."""

    def test_phase_not_expired_passes(self):
        """Test that non-expired phase passes validation."""
        mock_game_manager = Mock()
        mock_game_manager.is_phase_expired.return_value = False
        room_id = 'room123'

        # Should not raise any exception
        validate_phase_not_expired(mock_game_manager, room_id)

        mock_game_manager.is_phase_expired.assert_called_once_with(room_id)

    def test_phase_expired_raises_error(self):
        """Test that expired phase raises ValidationError."""
        mock_game_manager = Mock()
        mock_game_manager.is_phase_expired.return_value = True
        room_id = 'room123'

        with pytest.raises(ValidationError) as exc_info:
            validate_phase_not_expired(mock_game_manager, room_id)

        assert exc_info.value.code == ErrorCode.PHASE_EXPIRED
        assert "The current phase has expired" in exc_info.value.message
        mock_game_manager.is_phase_expired.assert_called_once_with(room_id)

    def test_game_manager_exception_propagates(self):
        """Test that exceptions from game manager propagate."""
        mock_game_manager = Mock()
        mock_game_manager.is_phase_expired.side_effect = Exception("Manager error")
        room_id = 'room123'

        with pytest.raises(Exception, match="Manager error"):
            validate_phase_not_expired(mock_game_manager, room_id)


class TestValidateJoinRoomData:
    """Test validate_join_room_data function."""

    def test_valid_join_room_data_passes(self):
        """Test that valid join room data passes validation."""
        data = {'room_id': 'room123', 'player_name': 'Alice'}

        result = validate_join_room_data(data)

        expected = {'room_id': 'room123', 'player_name': 'Alice'}
        assert result == expected

    def test_valid_join_room_data_with_extras_filters(self):
        """Test that extra fields are filtered out."""
        data = {'room_id': 'room123', 'player_name': 'Alice', 'extra': 'value'}

        result = validate_join_room_data(data)

        expected = {'room_id': 'room123', 'player_name': 'Alice'}
        assert result == expected
        assert 'extra' not in result

    def test_missing_room_id_raises_error(self):
        """Test that missing room_id raises ValidationError."""
        data = {'player_name': 'Alice'}

        with pytest.raises(ValidationError) as exc_info:
            validate_join_room_data(data)

        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID
        assert "Room ID is required" in exc_info.value.message

    def test_missing_player_name_raises_error(self):
        """Test that missing player_name raises ValidationError."""
        data = {'room_id': 'room123'}

        with pytest.raises(ValidationError) as exc_info:
            validate_join_room_data(data)

        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        assert "Player name is required" in exc_info.value.message

    def test_invalid_data_type_raises_error(self):
        """Test that invalid data type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_join_room_data("not a dict")

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format - expected dictionary" in exc_info.value.message


class TestValidateSubmitResponseData:
    """Test validate_submit_response_data function."""

    def test_valid_response_data_passes(self):
        """Test that valid response data passes validation."""
        data = {'response': 'My funny response'}

        result = validate_submit_response_data(data)

        expected = {'response': 'My funny response'}
        assert result == expected

    def test_valid_response_data_with_extras_filters(self):
        """Test that extra fields are filtered out."""
        data = {'response': 'My funny response', 'extra': 'value'}

        result = validate_submit_response_data(data)

        expected = {'response': 'My funny response'}
        assert result == expected
        assert 'extra' not in result

    def test_missing_response_raises_error(self):
        """Test that missing response raises ValidationError."""
        data = {}

        with pytest.raises(ValidationError) as exc_info:
            validate_submit_response_data(data)

        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
        assert "Response is required" in exc_info.value.message

    def test_invalid_data_type_raises_error(self):
        """Test that invalid data type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_submit_response_data("not a dict")

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format - expected dictionary" in exc_info.value.message


class TestValidateSubmitGuessData:
    """Test validate_submit_guess_data function."""

    def test_valid_guess_data_passes(self):
        """Test that valid guess data passes validation."""
        data = {'guess_index': 2}

        result = validate_submit_guess_data(data)

        expected = {'guess_index': 2}
        assert result == expected

    def test_valid_guess_data_with_extras_filters(self):
        """Test that extra fields are filtered out."""
        data = {'guess_index': 1, 'extra': 'value'}

        result = validate_submit_guess_data(data)

        expected = {'guess_index': 1}
        assert result == expected
        assert 'extra' not in result

    def test_missing_guess_index_raises_error(self):
        """Test that missing guess_index raises ValidationError."""
        data = {}

        with pytest.raises(ValidationError) as exc_info:
            validate_submit_guess_data(data)

        assert exc_info.value.code == ErrorCode.MISSING_GUESS
        assert "Guess index is required" in exc_info.value.message

    def test_invalid_data_type_raises_error(self):
        """Test that invalid data type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_submit_guess_data("not a dict")

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format - expected dictionary" in exc_info.value.message


class TestValidationUtilsEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_values_preserved(self):
        """Test that empty string values are preserved (not treated as missing)."""
        data = {'room_id': '', 'player_name': ''}

        result = validate_join_room_data(data)

        expected = {'room_id': '', 'player_name': ''}
        assert result == expected

    def test_zero_values_preserved(self):
        """Test that zero values are preserved (not treated as missing)."""
        data = {'guess_index': 0}

        result = validate_submit_guess_data(data)

        expected = {'guess_index': 0}
        assert result == expected

    def test_false_values_preserved(self):
        """Test that False values are preserved (not treated as missing)."""
        data = {'response': False}

        result = validate_submit_response_data(data)

        expected = {'response': False}
        assert result == expected

    def test_none_values_preserved(self):
        """Test that None values are preserved (not treated as missing)."""
        data = {'response': None}

        result = validate_submit_response_data(data)

        expected = {'response': None}
        assert result == expected

    def test_complex_data_types_preserved(self):
        """Test that complex data types are preserved."""
        data = {'response': {'nested': 'object'}}

        result = validate_submit_response_data(data)

        expected = {'response': {'nested': 'object'}}
        assert result == expected

    def test_list_values_preserved(self):
        """Test that list values are preserved."""
        data = {'response': [1, 2, 3]}

        result = validate_submit_response_data(data)

        expected = {'response': [1, 2, 3]}
        assert result == expected


class TestValidationUtilsIntegration:
    """Test integration scenarios with multiple validation functions."""

    def test_session_and_phase_validation_chain(self):
        """Test chaining session and phase validation."""
        session_info = {'player_id': 'player1', 'room_id': 'room123'}
        game_state = {'phase': 'responding', 'round': 1}

        # Both validations should pass
        validated_session = validate_session_exists(session_info)
        validated_game_state = validate_game_phase(game_state, 'responding')

        assert validated_session == session_info
        assert validated_game_state == game_state

    def test_data_structure_then_specific_validation_chain(self):
        """Test chaining structure validation with specific validation."""
        raw_data = {'room_id': 'room123', 'player_name': 'Alice', 'extra': 'ignored'}

        # First validate structure, then apply specific validation
        validated_structure = validate_dict_structure(raw_data, ['room_id', 'player_name'])
        validated_join_data = validate_join_room_data(raw_data)

        assert validated_structure == raw_data
        assert validated_join_data == {'room_id': 'room123', 'player_name': 'Alice'}
        assert 'extra' not in validated_join_data

    def test_all_error_codes_covered(self):
        """Test that all relevant error codes are properly used."""
        error_codes_used = set()

        # Test each validation function's error codes
        try:
            validate_dict_structure("not dict", ['field'])
        except ValidationError as e:
            error_codes_used.add(e.code)

        try:
            validate_session_exists(None)
        except ValidationError as e:
            error_codes_used.add(e.code)

        try:
            validate_game_phase(None, 'responding')
        except ValidationError as e:
            error_codes_used.add(e.code)

        mock_game_manager = Mock()
        mock_game_manager.is_phase_expired.return_value = True
        try:
            validate_phase_not_expired(mock_game_manager, 'room123')
        except ValidationError as e:
            error_codes_used.add(e.code)

        try:
            validate_game_phase({'phase': 'wrong'}, 'responding')
        except ValidationError as e:
            error_codes_used.add(e.code)

        try:
            validate_dict_structure({}, ['room_id'])
        except ValidationError as e:
            error_codes_used.add(e.code)

        try:
            validate_dict_structure({}, ['player_name'])
        except ValidationError as e:
            error_codes_used.add(e.code)

        try:
            validate_dict_structure({}, ['response'])
        except ValidationError as e:
            error_codes_used.add(e.code)

        try:
            validate_dict_structure({}, ['guess_index'])
        except ValidationError as e:
            error_codes_used.add(e.code)

        # Verify expected error codes are used
        expected_codes = {
            ErrorCode.INVALID_DATA,
            ErrorCode.NOT_IN_ROOM,
            ErrorCode.ROOM_NOT_FOUND,
            ErrorCode.PHASE_EXPIRED,
            ErrorCode.WRONG_PHASE,
            ErrorCode.MISSING_ROOM_ID,
            ErrorCode.MISSING_PLAYER_NAME,
            ErrorCode.EMPTY_RESPONSE,
            ErrorCode.MISSING_GUESS
        }

        assert error_codes_used == expected_codes