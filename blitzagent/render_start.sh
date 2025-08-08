#!/bin/bash

# Render deployment startup script for Blitz
echo "🚀 Starting Blitz on Render..."

# Set production defaults
export HOST=${HOST:-"0.0.0.0"}
export PORT=${PORT:-10000}
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}

echo "📡 Host: $HOST"
echo "🔌 Port: $PORT"
echo "📊 Log Level: $LOG_LEVEL"

# Install MCP package in production
echo "📦 Installing MCP package..."
pip install --no-cache-dir --timeout=60 git+https://github.com/tejassrinivasan/BlitzLLM.git#subdirectory=mcp || {
    echo "⚠️  Warning: Failed to install MCP package from git. Continuing without it..."
}

# Verify environment
echo "🔐 Checking environment variables..."
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY is not set"
    exit 1
fi

if [ -z "$API_KEY" ]; then
    echo "❌ API_KEY is not set"
    exit 1
fi

echo "✅ Environment validated"

# Start the server
echo "🎯 Starting Blitz server..."
exec python main.py
