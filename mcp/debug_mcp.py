#!/usr/bin/env python3
"""Debug script to test MCP server startup"""

import sys
import os
import asyncio
from pathlib import Path

# Add the current directory to the path so we can import the package
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    # Import the MCP server directly
    from blitz_agent_mcp.main import get_mcp
    from mcp.server.fastmcp import FastMCP
    
    print("Testing MCP server creation...")
    
    # Create MCP instance
    mcp = get_mcp(urls=(), api_key=None, host="127.0.0.1", port=8000, quiet=False)
    
    print(f"MCP server created successfully")
    print(f"Number of tools: {len(mcp._tools)}")
    
    # List all tools
    for tool_name in mcp._tools.keys():
        print(f"  - {tool_name}")
    
    print("MCP server test completed successfully!")
    
except Exception as e:
    print(f"Error creating MCP server: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 