"""
WSGI entry point for LLMposter application.
Used for production deployment with Gunicorn.
"""

from app import app, socketio

if __name__ == "__main__":
    # For development with Gunicorn
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)
else:
    # For production WSGI servers
    application = app