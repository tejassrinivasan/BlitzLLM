"""Database connection testing tool."""

import asyncio
import logging
from typing import Any, Dict

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import MAX_DATA_ROWS, get_postgres_url
from ..models.connection import Connection
from ..utils import serialize_response

__all__ = ["test"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def test(
    ctx: Context,
    league: str = Field(default=None, description="League to test (e.g., 'mlb', 'nba'). If not specified, tests default database connection."),
) -> Dict[str, Any]:
    """
    Test whether a data source is connected.

    Instructions:
    1. Only use this tool if you suspect the connection to a data source is not working, and want to troubleshoot it.
    2. Specify the league parameter to test the appropriate database connection (mlb, nba, etc.)
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    try:
        # Test the configured PostgreSQL connection for the specified league
        postgres_url = get_postgres_url(league)
        if not postgres_url:
            league_info = f" for league '{league}'" if league else ""
            return {
                "success": False,
                "message": f"PostgreSQL configuration{league_info} is incomplete",
                "league": league,
                "error": "Missing database configuration"
            }
        
        connection = Connection(url=postgres_url)
        result = await connection.test_connection()
        
        if league:
            logger.info(f"Database connection test for league '{league}': {'SUCCESS' if result.connected else 'FAILED'}")
        else:
            logger.info(f"Default database connection test: {'SUCCESS' if result.connected else 'FAILED'}")
        
        return {
            "success": result.connected,
            "message": result.message,
            "league": league,
            "connection_url": f"{postgres_url.split('@')[0]}@***" if postgres_url else None  # Hide credentials
        }
        
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return {
            "success": False,
            "message": str(e),
            "league": league,
            "error": "Connection test exception"
        } 