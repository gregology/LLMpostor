"""
Configuration settings for LLMposter application.
"""

import os

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    PROMPTS_FILE = os.environ.get('PROMPTS_FILE') or 'prompts.yaml'
    MAX_PLAYERS_PER_ROOM = int(os.environ.get('MAX_PLAYERS_PER_ROOM', 8))
    RESPONSE_TIME_LIMIT = int(os.environ.get('RESPONSE_TIME_LIMIT', 180))  # 3 minutes
    GUESSING_TIME_LIMIT = int(os.environ.get('GUESSING_TIME_LIMIT', 120))  # 2 minutes
    RESULTS_DISPLAY_TIME = int(os.environ.get('RESULTS_DISPLAY_TIME', 30))  # 30 seconds

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    FLASK_ENV = 'production'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}