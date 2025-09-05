# Multi-stage build for optimized production image
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Create non-root user for security first
RUN useradd --create-home --shell /bin/bash app

# Set working directory and change ownership
WORKDIR /app
RUN chown app:app /app

# Switch to app user
USER app

# Copy dependency files
COPY --chown=app:app pyproject.toml uv.lock ./

# Install dependencies using uv as app user
RUN uv sync --frozen --no-cache

# Copy application code
COPY --chown=app:app . .

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_ENV=production
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

# Run the application using gunicorn with eventlet workers
CMD ["uv", "run", "gunicorn", "--config", "gunicorn.conf.py", "app:app"]