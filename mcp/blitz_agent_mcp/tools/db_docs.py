"""League-specific database schema information tool."""

import asyncio
import logging
import os
from typing import Any

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import MAX_DATA_ROWS
from ..utils import serialize_response

__all__ = ["get_database_documentation"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def get_database_documentation(
    ctx: Context,
    league: str = Field(..., description="League name (e.g. 'mlb', 'nba')")
) -> dict[str, Any]:
    """
    Get comprehensive database schema information for a specific league. 
    
    This tool provides detailed schema documentation, query requirements/interpretations for supported sports leagues,
    table descriptions, and what you can and cannot answer.

    ALWAYS GET DATABASE DOCUMENTATION BEFORE WRITING QUERIES TO PREVENT ERRORS/WRONG ASSUMPTIONS. NEVER SKIP THIS STEP.
    
    Instructions:
    1. Specify the league name (currently supports 'mlb', 'nba')
    2. Returns comprehensive schema documentation
    3. Use this information to understand available tables
    4. Reference the schema when building queries for that league
    """
    if not league:
        raise ValueError("league is required")
    
    league = league.lower()
    
    if league not in ["mlb", "nba"]:
        return {
            "success": False,
            "error": f"Unsupported league: {league}. Supported leagues: mlb, nba"
        }
    
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        schema_file_path = os.path.join(current_dir, "..", "schemas", f"{league}-schema.md")
        
        with open(schema_file_path, 'r', encoding='utf-8') as file:
            schema_content = file.read()
        
        return {
            "success": True,
            "league": league.upper(),
            "schema_documentation": schema_content,
            "source": "file" if os.path.exists(schema_file_path) else "inline"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "league": league
        }