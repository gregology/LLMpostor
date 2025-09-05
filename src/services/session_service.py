"""
Session Service - Manages player session data and Socket.IO connections.

This service handles:
- Player session creation and cleanup
- Socket ID to player mapping
- Session validation and retrieval
- Connection state management
"""

import logging
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class SessionService:
    """Manages player sessions and Socket.IO connections."""
    
    def __init__(self):
        """Initialize the session service."""
        # Store player sessions (socket_id -> player_info)
        self._player_sessions: Dict[str, Dict[str, str]] = {}
        logger.info("SessionService initialized")
    
    def create_session(self, socket_id: str, room_id: str, player_id: str, player_name: str) -> None:
        """Create or update a player session.
        
        Args:
            socket_id: Socket.IO connection ID
            room_id: Room the player is joining
            player_id: Unique player identifier
            player_name: Player's display name
        """
        try:
            self._player_sessions[socket_id] = {
                'room_id': room_id,
                'player_id': player_id,
                'player_name': player_name
            }
            logger.debug(f"Created session for player {player_name} ({player_id}) in room {room_id}")
            
        except Exception as e:
            logger.error(f"Error creating session for socket {socket_id}: {e}")
    
    def get_session(self, socket_id: str) -> Optional[Dict[str, str]]:
        """Get player session information by socket ID.
        
        Args:
            socket_id: Socket.IO connection ID
            
        Returns:
            Dict with session info or None if not found
        """
        return self._player_sessions.get(socket_id)
    
    def get_session_data(self, socket_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get session data as tuple for convenience.
        
        Args:
            socket_id: Socket.IO connection ID
            
        Returns:
            Tuple of (room_id, player_id, player_name) or (None, None, None)
        """
        session_info = self._player_sessions.get(socket_id)
        if session_info:
            return (
                session_info['room_id'],
                session_info['player_id'], 
                session_info['player_name']
            )
        return None, None, None
    
    def has_session(self, socket_id: str) -> bool:
        """Check if a socket has an active session.
        
        Args:
            socket_id: Socket.IO connection ID
            
        Returns:
            True if session exists
        """
        return socket_id in self._player_sessions
    
    def remove_session(self, socket_id: str) -> Optional[Dict[str, str]]:
        """Remove a player session.
        
        Args:
            socket_id: Socket.IO connection ID
            
        Returns:
            The removed session info or None if not found
        """
        try:
            session_info = self._player_sessions.pop(socket_id, None)
            if session_info:
                logger.debug(f"Removed session for player {session_info['player_name']} ({session_info['player_id']})")
            return session_info
            
        except Exception as e:
            logger.error(f"Error removing session for socket {socket_id}: {e}")
            return None
    
    def get_all_sessions(self) -> Dict[str, Dict[str, str]]:
        """Get all active player sessions.
        
        Returns:
            Dictionary mapping socket_id to session info
        """
        return self._player_sessions.copy()
    
    def get_sessions_count(self) -> int:
        """Get the total number of active sessions.
        
        Returns:
            Number of active sessions
        """
        return len(self._player_sessions)
    
    def get_sessions_by_room(self, room_id: str) -> Dict[str, Dict[str, str]]:
        """Get all sessions for a specific room.
        
        Args:
            room_id: Room identifier
            
        Returns:
            Dictionary mapping socket_id to session info for the room
        """
        room_sessions = {}
        for socket_id, session_info in self._player_sessions.items():
            if session_info['room_id'] == room_id:
                room_sessions[socket_id] = session_info
        return room_sessions
    
    def cleanup_stale_sessions(self, active_socket_ids: set) -> int:
        """Clean up sessions for disconnected sockets.
        
        Args:
            active_socket_ids: Set of currently connected socket IDs
            
        Returns:
            Number of sessions cleaned up
        """
        try:
            stale_sessions = []
            for socket_id in self._player_sessions:
                if socket_id not in active_socket_ids:
                    stale_sessions.append(socket_id)
            
            cleaned_count = 0
            for socket_id in stale_sessions:
                if self.remove_session(socket_id):
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} stale sessions")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up stale sessions: {e}")
            return 0
    
    def validate_session_for_room_action(self, socket_id: str, expected_room_id: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, str]]]:
        """Validate session for room-based actions.
        
        Args:
            socket_id: Socket.IO connection ID
            expected_room_id: Optional room ID to validate against
            
        Returns:
            Tuple of (is_valid, session_info)
        """
        session_info = self.get_session(socket_id)
        if not session_info:
            return False, None
            
        # If expected_room_id provided, validate it matches
        if expected_room_id and session_info['room_id'] != expected_room_id:
            logger.warning(f"Session room mismatch: expected {expected_room_id}, got {session_info['room_id']}")
            return False, session_info
            
        return True, session_info
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information about active sessions.
        
        Returns:
            Dictionary with debug information
        """
        room_counts: Dict[str, int] = {}
        for session_info in self._player_sessions.values():
            room_id = session_info['room_id']
            room_counts[room_id] = room_counts.get(room_id, 0) + 1
        
        return {
            'total_sessions': len(self._player_sessions),
            'sessions_by_room': room_counts,
            'active_rooms': len(room_counts)
        }