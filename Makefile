.PHONY: dev test test-python test-js install install-python install-js clean help

# Default target
help:
	@echo "LLMposter Development Commands:"
	@echo "  make dev         - Start development server with Gunicorn"
	@echo "  make test        - Run all tests (Python + JavaScript)"
	@echo "  make test-python - Run Python tests only"
	@echo "  make test-js     - Run JavaScript tests only"
	@echo "  make install     - Install all dependencies (Python + JavaScript)"
	@echo "  make install-python - Install Python dependencies only"
	@echo "  make install-js  - Install JavaScript dependencies only"
	@echo "  make clean       - Clean up temporary files"
	@echo "  make help        - Show this help message"

# Start development server
dev:
	@echo "Starting LLMposter development server..."
	uv run python run_dev.py

# Run all tests
test: test-python test-js

# Run Python tests
test-python:
	@echo "Running Python tests..."
	uv run pytest tests/ -v

# Run JavaScript tests
test-js:
	@echo "Running JavaScript tests..."
	@if command -v npm >/dev/null 2>&1; then \
		npm run test:run; \
	else \
		echo "Warning: npm not found. Install Node.js to run JavaScript tests."; \
		echo "Skipping JavaScript tests..."; \
	fi

# Install all dependencies
install: install-python install-js

# Install Python dependencies
install-python:
	@echo "Installing Python dependencies..."
	uv sync

# Install JavaScript dependencies
install-js:
	@echo "Installing JavaScript dependencies..."
	@if command -v npm >/dev/null 2>&1; then \
		npm install; \
	else \
		echo "Warning: npm not found. Install Node.js to install JavaScript dependencies."; \
		echo "You can install Node.js from: https://nodejs.org/"; \
	fi

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	@if [ -d "node_modules" ]; then \
		echo "Removing node_modules..."; \
		rm -rf node_modules/; \
	fi
	@if [ -f "package-lock.json" ]; then \
		echo "Removing package-lock.json..."; \
		rm -f package-lock.json; \
	fi