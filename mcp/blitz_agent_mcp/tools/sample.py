"""Database table sampling tool."""

import asyncio
import logging
from typing import Any

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import MAX_DATA_ROWS, get_postgres_url
from ..models.table import Table
from ..models.connection import Connection
from ..utils import serialize_response

__all__ = ["sample"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def sample(
    ctx: Context,
    table: str = Field(..., description="The database table name to sample (e.g., 'pitchingstatsgame', 'battingstatsgame')."),
    n: int = Field(5, description="Number of rows to sample", ge=1, le=MAX_DATA_ROWS),
    league: str = Field(default=None, description="League to sample (e.g., 'mlb', 'nba'). If not specified, uses default database."),
) -> dict[str, Any]:
    """
    Get a sample of data from a database table.

    Sampling Instructions:
    1. Use this tool to preview actual data values and content.
    2. Sampling tables helps validate your assumptions about the data.
    3. Always sample tables before writing queries to understand their structure and prevent errors.
    4. Simply provide the table name as a string (e.g., "pitchingstatsgame", "battingstatsgame").
    5. Specify the league parameter to sample tables in the appropriate database (mlb, nba, etc.)
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    try:
        # Create Table object and use configured PostgreSQL URL for the specified league
        postgres_url = get_postgres_url(league)
        if not postgres_url:
            league_info = f" for league '{league}'" if league else ""
            raise ConnectionError(f"PostgreSQL configuration{league_info} is incomplete. Please configure PostgreSQL settings.")
        
        table_obj = Table(table_name=table, connection=Connection(url=postgres_url))
        if league:
            logger.debug(f"Using configured PostgreSQL connection for league: {league}")
        else:
            logger.debug("Using configured PostgreSQL connection (default)")
        
        url_map = await _get_context_field("url_map", ctx)
        db = await table_obj.connection.connect(url_map=url_map)
        return serialize_response(await db.sample_table(table_obj.table_name, n=n))
    except Exception as e:
        raise ConnectionError(f"Failed to sample table {table}: {str(e)}") 