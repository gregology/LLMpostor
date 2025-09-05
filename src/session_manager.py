"""
Session manager for LLMposter.
"""

class SessionManager:
    def __init__(self):
        self.player_sessions = {}

    def get_session(self, sid):
        return self.player_sessions.get(sid)

    def create_session(self, sid, room_id, player_id, player_name):
        self.player_sessions[sid] = {
            'room_id': room_id,
            'player_id': player_id,
            'player_name': player_name
        }

    def delete_session(self, sid):
        if sid in self.player_sessions:
            del self.player_sessions[sid]
