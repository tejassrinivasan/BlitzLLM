#!/bin/bash

# Pydantic AI Sports Agent Startup Script

echo "🚀 Starting Pydantic AI Sports Agent..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  Warning: ANTHROPIC_API_KEY environment variable is not set."
    echo "   Please set it with: export ANTHROPIC_API_KEY='your_key_here'"
    echo "   Get your API key from: https://console.anthropic.com/"
    echo ""
fi

# Function to find the right pip command
find_pip_command() {
    if command -v pip3 &> /dev/null; then
        echo "pip3"
    elif command -v pip &> /dev/null; then
        echo "pip"
    elif python3 -m pip --version &> /dev/null; then
        echo "python3 -m pip"
    else
        echo ""
    fi
}

# Install dependencies if requirements.txt exists and is newer than last install
if [ -f "requirements.txt" ]; then
    if [ ! -f ".last_install" ] || [ "requirements.txt" -nt ".last_install" ]; then
        echo "📦 Installing/updating dependencies..."
        
        PIP_CMD=$(find_pip_command)
        if [ -z "$PIP_CMD" ]; then
            echo "❌ No pip command found. Please install pip or use a virtual environment."
            echo "   Try: python3 -m ensurepip --default-pip"
            exit 1
        fi
        
        echo "   Using: $PIP_CMD"
        $PIP_CMD install -r requirements.txt
        
        if [ $? -eq 0 ]; then
            touch .last_install
            echo "✅ Dependencies installed successfully"
        else
            echo "❌ Failed to install dependencies"
            exit 1
        fi
    else
        echo "📦 Dependencies are up to date"
    fi
fi

# Set default environment variables if not set
export HOST=${HOST:-"0.0.0.0"}
export PORT=${PORT:-8001}
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}

echo "🔧 Configuration:"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   Log Level: $LOG_LEVEL"
echo ""

echo "🏃 Starting server..."
echo "   API docs will be available at: http://localhost:$PORT/docs"
echo "   Health check: http://localhost:$PORT/health"
echo ""

# Start the agent
python3 main.py 