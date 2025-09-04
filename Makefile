.PHONY: dev test install clean help

# Default target
help:
	@echo "LLMposter Development Commands:"
	@echo "  make dev     - Start development server with Gunicorn"
	@echo "  make test    - Run all tests"
	@echo "  make install - Install dependencies"
	@echo "  make clean   - Clean up temporary files"
	@echo "  make help    - Show this help message"

# Start development server
dev:
	@echo "Starting LLMposter development server..."
	uv run python run_dev.py

# Run tests
test:
	@echo "Running tests..."
	uv run pytest tests/ -v

# Install dependencies
install:
	@echo "Installing dependencies..."
	uv sync

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/