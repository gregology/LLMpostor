"""
Game Phase Enumeration

Defines the game phase states used throughout the application.
"""

from enum import Enum


class GamePhase(Enum):
    """Game phase enumeration."""
    WAITING = "waiting"
    RESPONDING = "responding"
    GUESSING = "guessing"
    RESULTS = "results"