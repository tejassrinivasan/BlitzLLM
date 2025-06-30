#!/bin/bash

# Render-specific startup script for Blitz Agent MCP Server
echo "🚀 Starting BlitzAgent MCP Server for Render deployment" >&2

# Set environment for production
export RENDER=true

# Start the MCP server with streamable-http transport (recommended for production)
exec python -m blitz_agent_mcp.main --transport streamable-http --host 0.0.0.0 --port $PORT 