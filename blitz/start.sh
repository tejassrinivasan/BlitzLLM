#!/bin/bash

# Start script for BlitzAgent Agno on Render

set -e  # Exit on any error

echo "🚀 Starting BlitzAgent Agno on Render..."
echo "Environment: $ENVIRONMENT"
echo "Model Provider: $MODEL_PROVIDER"
echo "Port: $PORT"

# Run database migrations if needed (uncomment if using database)
# echo "Running database migrations..."
# python -m alembic upgrade head

# Start the FastAPI server
echo "Starting FastAPI server..."
exec uvicorn blitzagent_agno.production_app:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 1 \
    --log-level info \
    --access-log \
    --no-use-colors 