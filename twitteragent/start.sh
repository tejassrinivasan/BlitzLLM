#!/bin/bash
"""
Startup script for Twitter NBA Agent
Handles dependency installation and service startup.
"""

set -e  # Exit on any error

echo "🏀 Starting Twitter NBA Agent Setup"
echo "=================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "Python version: $python_version"

if [[ $(echo "$python_version >= 3.8" | bc -l) -eq 0 ]]; then
    echo "❌ Error: Python 3.8+ required, found $python_version"
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".last_install" ] || [ "requirements.txt" -nt ".last_install" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    touch .last_install
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already up to date"
fi

# Check required environment variables
echo "🔧 Checking configuration..."

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY environment variable is required"
    echo "   Get your API key from https://console.anthropic.com/"
    exit 1
fi

echo "✅ ANTHROPIC_API_KEY configured"

# Check if MCP tools are available
if ! command -v blitz-agent-mcp &> /dev/null; then
    echo "⚠️  Warning: blitz-agent-mcp command not found"
    echo "   MCP tools may not be available for sports analytics"
else
    echo "✅ MCP tools available"
fi

# Configuration summary
echo ""
echo "📋 Configuration Summary:"
echo "   Host: ${HOST:-0.0.0.0}"
echo "   Port: ${PORT:-8002}"
echo "   Log Level: ${LOG_LEVEL:-INFO}"
echo "   Runs per day: ${WORKER_RUNS_PER_DAY:-6}"
echo ""

# Parse command line arguments
MODE=${1:-"worker"}

case $MODE in
    "worker")
        echo "🚀 Starting Background Worker (6x daily NBA automation)"
        echo "   Scheduled times: 6AM, 10AM, 2PM, 6PM, 10PM, 2AM"
        echo "   Use Ctrl+C to stop"
        echo ""
        python worker.py
        ;;
    "api")
        echo "🚀 Starting FastAPI Monitoring Interface"
        echo "   Available at: http://localhost:${PORT:-8002}"
        echo "   Docs at: http://localhost:${PORT:-8002}/docs"
        echo ""
        python main.py
        ;;
    "test")
        echo "🧪 Running Test Workflow (no Twitter posting)"
        python worker.py --test
        ;;
    "once")
        echo "🎯 Running Workflow Once (real Twitter posting)"
        python worker.py --run-once
        ;;
    "status")
        echo "📊 Current Status:"
        python worker.py --status
        ;;
    "stats")
        echo "📈 Execution Statistics:"
        python worker.py --stats
        ;;
    *)
        echo "Usage: $0 [mode]"
        echo ""
        echo "Modes:"
        echo "  worker  - Start background worker (default)"
        echo "  api     - Start FastAPI monitoring interface"
        echo "  test    - Run test workflow"
        echo "  once    - Run workflow once"
        echo "  status  - Show current status"
        echo "  stats   - Show execution statistics"
        echo ""
        echo "Examples:"
        echo "  $0 worker    # Start 6x daily automation"
        echo "  $0 api       # Start monitoring interface"
        echo "  $0 test      # Test without posting to Twitter"
        exit 1
        ;;
esac 