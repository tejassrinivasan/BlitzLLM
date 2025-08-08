# Multi-stage build for Render deployment
FROM python:3.11-slim as builder

# Set environment variables for pip
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Install git for pip git dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Create wheel directory
WORKDIR /wheels

# Copy requirements and install wheels
COPY requirements.txt .
RUN pip wheel --no-deps --wheel-dir . -r requirements.txt

# Install MCP package as wheel
RUN pip wheel --no-deps --wheel-dir . git+https://github.com/tejassrinivasan/BlitzLLM.git#subdirectory=mcp || echo "Failed to build MCP wheel"

# Final stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=10000

# Create app directory
WORKDIR /app

# Install packages from wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links /wheels /wheels/* && rm -rf /wheels

# Copy application
COPY main.py config.py ./
COPY stream_viewer.html ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PORT}/health')" || exit 1

# Expose port
EXPOSE ${PORT}

# Start application
CMD ["python", "main.py"]
