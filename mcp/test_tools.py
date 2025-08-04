#!/usr/bin/env python3
"""Test script to check MCP tool registration"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'blitz_agent_mcp'))

from mcp.server.fastmcp import FastMCP
from blitz_agent_mcp.tools.tools_setup import setup_tools

def test_tool_registration():
    """Test if tools are being registered correctly"""
    try:
        # Create MCP instance
        mcp = FastMCP("Test Blitz Agent MCP Server")
        
        # Set up tools
        setup_tools(mcp)
        
        # Check if tools were registered
        print(f"Number of tools registered: {len(mcp._tools)}")
        
        # List all registered tools
        for tool_name, tool_func in mcp._tools.items():
            print(f"Tool: {tool_name}")
            
        return True
    except Exception as e:
        print(f"Error setting up tools: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tool_registration()
    sys.exit(0 if success else 1) 