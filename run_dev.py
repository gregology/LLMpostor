#!/usr/bin/env python3
"""
Development server runner using Gunicorn with eventlet workers.
This provides better Socket.IO support than Flask's development server.
"""

import os
import subprocess
import sys

def main():
    """Run the development server with Gunicorn."""
    
    # Set development environment
    os.environ.setdefault('FLASK_ENV', 'development')
    os.environ.setdefault('PORT', '8000')
    
    # Gunicorn command with eventlet worker
    cmd = [
        'gunicorn',
        '--config', 'gunicorn.conf.py',
        '--reload',  # Auto-reload on code changes
        '--log-level', 'info',
        'wsgi:app'
    ]
    
    print("Starting LLMpostor development server with Gunicorn...")
    print(f"Server will be available at: http://localhost:{os.environ.get('PORT', 8000)}")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nShutting down development server...")
    except subprocess.CalledProcessError as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()