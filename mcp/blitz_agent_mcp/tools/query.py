"""SQL query execution tool with comprehensive guidelines for historical sports data."""

import asyncio
import logging
from typing import Any, Dict

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from config import MAX_DATA_ROWS, get_postgres_url
from models.query import Query
from models.connection import Connection
from utils import serialize_response

QUERY_ENDPOINT = "query/{dialect}"

__all__ = ["query"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def query(
    ctx: Context,
    query: str = Field(..., description="The read-only SQL query string to execute."),
    description: str = Field(..., description="Description of what the query does."),
) -> Dict[str, Any]:
    """
    This tool allows you to run read-only SQL queries against either a datasource or the filesystem.

    Querying Instructions:
    1. Only query data that has been explicitly discovered, searched for, or referenced in the conversation.
    2. Before writing queries, inspect and/or sample the underlying tables to understand their structure and prevent errors.
    3. When a query fails or returns unexpected results, examine the underlying tables to diagnose the issue and then retry.
    4. Large query results are automatically saved as parquet files for later analysis.
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    try:
        # Create Query object from string parameters
        auto_description = description or f"SQL query execution: {query[:100]}{'...' if len(query) > 100 else ''}"
        query_obj = Query(code=query, description=auto_description)
        
        # If no connection provided in the query, use the configured PostgreSQL URL
        if query_obj.connection is None:
            postgres_url = get_postgres_url()
            if not postgres_url:
                raise ConnectionError("No connection provided and PostgreSQL configuration is incomplete. Please provide a connection or configure PostgreSQL settings.")
            query_obj.connection = Connection(url=postgres_url)
            logger.debug("Using configured PostgreSQL connection")
        
        url_map = await _get_context_field("url_map", ctx)
        db = await query_obj.connection.connect(url_map=url_map)
        result = await db.query(code=query_obj.code)
        return serialize_response(result)
    except Exception as e:
        if isinstance(e, FileNotFoundError | PermissionError):
            raise
        raise RuntimeError(f"Query execution failed: {str(e)}") 