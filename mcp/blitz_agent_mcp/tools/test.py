"""Database connection testing tool."""

import asyncio
import logging
from typing import Any, Dict

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from config import MAX_DATA_ROWS, get_postgres_url
from models.connection import Connection
from utils import serialize_response

__all__ = ["test"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def test(
    ctx: Context
) -> Dict[str, Any]:
    """
    Test whether a data source is connected.

    Instructions:
    1. Only use this tool if you suspect the connection to a data source is not working, and want to troubleshoot it.
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    connection = Connection(url=get_postgres_url())
    
    url_map = await _get_context_field("url_map", ctx)
    db = await connection.connect(url_map=url_map)
    result = await db.test_connection()
    return {"connected": result.connected, "message": result.message} 