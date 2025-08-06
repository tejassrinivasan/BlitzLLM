#!/usr/bin/env python3
"""
MCP Server for Inspector - Simplified version
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inspector-mcp")

def create_mcp() -> FastMCP:
    """Create MCP server for inspector"""
    
    mcp = FastMCP("Blitz Agent MCP Server")
    
    @mcp.tool()
    async def test_tool(
        ctx: Context,
        message: str = Field(..., description="A test message")
    ) -> Dict[str, Any]:
        """A simple test tool"""
        logger.info(f"Test tool called with message: {message}")
        return {
            "success": True,
            "message": f"Received: {message}",
            "tools_available": ["test_tool", "count_tools", "echo", "inspect", "sample", "query"]
        }
    
    @mcp.tool()
    async def count_tools(
        ctx: Context
    ) -> Dict[str, Any]:
        """Count the number of available tools"""
        logger.info("Count tools called")
        return {
            "tool_count": 6,
            "tools": ["test_tool", "count_tools", "echo", "inspect", "sample", "query"]
        }
    
    @mcp.tool()
    async def echo(
        ctx: Context,
        text: str = Field(..., description="Text to echo back")
    ) -> Dict[str, Any]:
        """Echo back the input text"""
        logger.info(f"Echo called with: {text}")
        return {
            "echoed": text,
            "length": len(text)
        }
    
    @mcp.tool()
    async def inspect(
        ctx: Context,
        table: str = Field(..., description="The database table name to inspect"),
        league: str = Field(None, description="League to inspect (e.g., 'mlb', 'nba')")
    ) -> Dict[str, Any]:
        """Inspect the structure of a database table"""
        logger.info(f"Inspect called for table: {table}, league: {league}")
        return {
            "table": table,
            "league": league,
            "message": "This is a mock inspect response - real implementation would connect to database"
        }
    
    @mcp.tool()
    async def sample(
        ctx: Context,
        table: str = Field(..., description="The database table name to sample"),
        limit: int = Field(10, description="Number of rows to sample"),
        league: str = Field(None, description="League to sample from")
    ) -> Dict[str, Any]:
        """Sample data from a database table"""
        logger.info(f"Sample called for table: {table}, limit: {limit}, league: {league}")
        return {
            "table": table,
            "limit": limit,
            "league": league,
            "message": "This is a mock sample response - real implementation would query database"
        }
    
    @mcp.tool()
    async def query(
        ctx: Context,
        sql: str = Field(..., description="The SQL query to execute"),
        league: str = Field(None, description="League to query")
    ) -> Dict[str, Any]:
        """Execute a SQL query against the database"""
        logger.info(f"Query called with SQL: {sql}, league: {league}")
        return {
            "sql": sql,
            "league": league,
            "message": "This is a mock query response - real implementation would execute SQL"
        }
    
    return mcp

# Create the MCP instance
mcp = create_mcp()

# This is what the MCP Inspector expects
if __name__ == "__main__":
    mcp.run(transport="stdio") 