#!/bin/bash

# BlitzAgent MCP Server Startup Script

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_DIR="$PROJECT_ROOT/.venv"

# Set PYTHONPATH to include the blitz_agent_mcp directory
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Check if this is being called from CLI (quiet mode)
# Default to quiet mode for cleaner CLI experience
QUIET_MODE="--quiet"

# If BLITZ_MCP_VERBOSE is set, use verbose mode
if [ "$BLITZ_MCP_VERBOSE" = "true" ]; then
    QUIET_MODE=""
    echo "🚀 Starting BlitzAgent MCP Server" >&2
fi

# Activate virtual environment
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "ERROR: Virtual environment not found at $VENV_DIR" >&2
    echo "Please run: python3 -m venv $VENV_DIR && source $VENV_DIR/bin/activate && pip install -e ." >&2
    exit 1
fi

# Check if we can import the main module
python -c "from blitz_agent_mcp.main import main" 2>/dev/null || {
    echo "ERROR: Cannot import main module. Installing dependencies..." >&2
    pip install -e "$PROJECT_ROOT" >&2
}

# Start the MCP server with appropriate flags
exec python -m blitz_agent_mcp.main $QUIET_MODE "$@" 