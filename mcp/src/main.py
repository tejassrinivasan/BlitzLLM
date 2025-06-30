#!/usr/bin/env python3
"""
Blitz Agent MCP Server

A comprehensive MCP server for sports database analysis, AI-powered insights,
and data validation using FastMCP.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Literal
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass

import click
import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from sqlalchemy.engine.url import make_url

from config import API_KEY_HEADER, BACKEND_URL, get_postgres_url
from models.connection import Connection
from tools import inspect, recall_similar_db_queries, query, sample, search_tables, test, webscrape, validate, upload, get_database_documentation, get_api_docs, call_api_endpoint, generate_graph, run_linear_regression

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("blitz-agent-mcp")


@dataclass
class AppContext:
    """Application context for the MCP server"""
    http_session: httpx.AsyncClient | None = None
    url_map: dict = Field(default_factory=dict)


async def test_connections(urls: tuple[str, ...]) -> None:
    """Test all connections in parallel"""
    if not urls:
        return

    async def _test_connection(url: str) -> None:
        """Test database connection"""
        connection = Connection(url=url)
        result = await connection.test_connection()
        if not result.connected:
            raise RuntimeError(f"Failed to connect to {url}: {result.message}")
        logger.info(f"Connection successful to {url}")

    await asyncio.gather(*(_test_connection(url) for url in urls))


def get_mcp(urls: tuple[str, ...], api_key: str | None = None, host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    # If no URLs provided, try to use the PostgreSQL URL from config
    if not urls:
        postgres_url = get_postgres_url()
        if postgres_url:
            urls = (postgres_url,)
            logger.info(f"Using PostgreSQL URL from configuration: {postgres_url}")
        else:
            logger.warning("No database URLs provided and PostgreSQL configuration incomplete")
    
    cleaned_urls = [url.lstrip("'").rstrip("'") for url in urls]

    # Build URL map for use in the app context
    url_map = {str(url_obj): url_obj for url_obj in map(make_url, cleaned_urls)}

    @asynccontextmanager
    async def app_lifespan(mcp_server: FastMCP) -> AsyncIterator[AppContext]:
        """Manage application lifecycle with type-safe context"""
        # Test connections when the server starts
        await test_connections(cleaned_urls)
        
        if api_key:
            headers = {API_KEY_HEADER: api_key}
            async with httpx.AsyncClient(headers=headers, base_url=BACKEND_URL) as http_client:
                yield AppContext(http_session=http_client, url_map=url_map)
        else:
            yield AppContext(url_map=url_map)

    # Use stateless HTTP for production deployment
    mcp = FastMCP("Blitz Agent MCP Server", lifespan=app_lifespan, host=host, port=port, stateless_http=True)

    # Add tools
    mcp.add_tool(inspect)
    mcp.add_tool(sample)
    mcp.add_tool(query)
    mcp.add_tool(search_tables)
    mcp.add_tool(test)
    mcp.add_tool(recall_similar_db_queries)
    mcp.add_tool(get_database_documentation)
    mcp.add_tool(get_api_docs)
    mcp.add_tool(call_api_endpoint)
    mcp.add_tool(upload)
    mcp.add_tool(validate)
    mcp.add_tool(webscrape)
    mcp.add_tool(generate_graph)
    mcp.add_tool(run_linear_regression)

    return mcp


def run_http_server(mcp_instance: FastMCP, transport: str, host: str = "127.0.0.1", port: int = 8000):
    """Run HTTP server using FastMCP's built-in transport"""
    logger.info(f"Starting {transport} server on {host}:{port}")
    
    # Use FastMCP's built-in transport
    logger.info(f"Using FastMCP built-in {transport} transport")
    mcp_instance.run(transport=transport)


@click.command()
@click.option("--api-key", envvar="BLITZ_API_KEY", help="API key for authentication")
@click.option("--transport", type=click.Choice(["stdio", "sse", "streamable-http"]), default="stdio", help="Transport mode for MCP server (streamable-http recommended for production)")
@click.option("--host", default="127.0.0.1", help="Host to bind the server to (for HTTP transports)")
@click.option("--port", type=int, default=None, help="Port to bind the server to (for HTTP transports)")
@click.argument("urls", nargs=-1)
def main(
    api_key: str | None = None,
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
    host: str = "127.0.0.1",
    port: int | None = None,
    urls: tuple[str, ...] = ()
) -> None:
    """Blitz Agent MCP Server - Run the MCP server"""
    logger.info("Starting MCP server with urls: %s", urls)
    
    # For deployment platforms like Render, use environment variables
    if transport in ("sse", "streamable-http"):
        # Use PORT env var if available (Render, Heroku, etc.)
        if port is None:
            port = int(os.getenv("PORT", "8000"))
        
        # For deployment, bind to all interfaces
        if os.getenv("RENDER") or os.getenv("RAILWAY_PROJECT_ID") or os.getenv("HEROKU_APP_NAME"):
            host = "0.0.0.0"
        
        logger.info(f"{transport} server will bind to {host}:{port}")
    else:
        # For non-HTTP transport, use defaults
        if port is None:
            port = 8000
    
    mcp_instance = get_mcp(urls, api_key, host, port)
    
    # Handle different transport modes
    if transport in ("sse", "streamable-http"):
        run_http_server(mcp_instance, transport, host, port)
    else:
        mcp_instance.run(transport=transport)


if __name__ == "__main__":
    main() 