"""Database table inspection tool."""

import asyncio
import logging
from typing import Any, Dict

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from config import MAX_DATA_ROWS, get_postgres_url
from models.table import Table
from models.connection import Connection
from utils import serialize_response

__all__ = ["inspect"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def inspect(
    ctx: Context,
    table: str = Field(..., description="The database table name to inspect (e.g., 'pitchingstatsgame', 'battingstatsgame')."),
) -> Dict[str, Any]:
    """
    Inspect the structure of a database table.

    Inspection Instructions:
    1. Use this tool to understand table structure like column names, data types, and constraints
    2. Inspecting tables helps understand the structure of the data
    3. Always inspect tables before writing queries to understand their structure and prevent errors
    4. Simply provide the table name as a string (e.g., "pitchingstatsgame", "battingstatsgame")
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    try:
        # Create Table object from string input
        table_obj = Table(table_name=table)
        
        # If no connection provided in the table, use the configured PostgreSQL URL
        if table_obj.connection is None:
            postgres_url = get_postgres_url()
            if not postgres_url:
                raise ConnectionError("No connection provided and PostgreSQL configuration is incomplete. Please provide a connection or configure PostgreSQL settings.")
            table_obj.connection = Connection(url=postgres_url)
            logger.debug("Using configured PostgreSQL connection")
        
        url_map = await _get_context_field("url_map", ctx)
        db = await table_obj.connection.connect(url_map=url_map)
        return serialize_response(await db.inspect_table(table_obj.table_name))
    except Exception as e:
        raise ConnectionError(f"Failed to inspect {table_obj.connection.url if 'table_obj' in locals() else 'unknown'} table {table_obj.table_name if 'table_obj' in locals() else table}: {str(e)}") 