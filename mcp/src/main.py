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


def get_mcp(urls: tuple[str, ...], api_key: str | None = None) -> FastMCP:
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

    mcp = FastMCP("Blitz Agent MCP Server", lifespan=app_lifespan)

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


def run_sse_server(mcp_instance: FastMCP, host: str = "127.0.0.1", port: int = 8000):
    """Run SSE server with custom configuration for deployment platforms"""
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    # Get or create the FastAPI app from FastMCP
    if hasattr(mcp_instance, 'app'):
        app = mcp_instance.app
    elif hasattr(mcp_instance, '_app'):
        app = mcp_instance._app
    else:
        # If we can't access the app directly, create our own wrapper
        app = FastAPI(title="Blitz Agent MCP Server")
        
        @app.get("/")
        @app.head("/")
        async def health_check():
            """Health check endpoint for deployment platforms"""
            return JSONResponse({
                "status": "ok", 
                "service": "Blitz Agent MCP Server", 
                "version": "1.0.0"
            })
        
        @app.get("/health")
        @app.head("/health")
        async def health():
            """Alternative health check endpoint"""
            return JSONResponse({
                "status": "healthy", 
                "timestamp": asyncio.get_event_loop().time()
            })
        
        # Try to mount the MCP routes if possible
        try:
            if hasattr(mcp_instance, 'router'):
                app.include_router(mcp_instance.router)
        except Exception as e:
            logger.warning(f"Could not mount MCP routes: {e}")
    
    # Add health check endpoints if they don't exist
    if not any(route.path == "/" for route in app.routes):
        @app.get("/")
        @app.head("/")
        async def health_check():
            """Health check endpoint for deployment platforms"""
            return JSONResponse({
                "status": "ok", 
                "service": "Blitz Agent MCP Server", 
                "version": "1.0.0"
            })
    
    if not any(route.path == "/health" for route in app.routes):
        @app.get("/health")
        @app.head("/health")
        async def health():
            """Alternative health check endpoint"""
            return JSONResponse({
                "status": "healthy", 
                "timestamp": asyncio.get_event_loop().time()
            })
    
    logger.info(f"Starting SSE server on {host}:{port}")
    
    # Configure uvicorn for deployment
    config = {
        "host": host,
        "port": port,
        "log_level": "info",
        "access_log": True,
    }
    
    # Try to use FastMCP's built-in server first
    try:
        # Check if FastMCP supports host/port parameters
        mcp_instance.run(transport="sse", host=host, port=port)
    except TypeError:
        # Fallback: run with uvicorn directly
        logger.info("Using fallback uvicorn server")
        uvicorn.run(app, **config)
    except Exception as e:
        logger.error(f"Error running server: {e}")
        # Last resort: run with basic uvicorn
        uvicorn.run(app, **config)


@click.command()
@click.option("--api-key", envvar="BLITZ_API_KEY", help="API key for authentication")
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="Transport mode for MCP server")
@click.option("--host", default="127.0.0.1", help="Host to bind the server to (for SSE transport)")
@click.option("--port", type=int, default=None, help="Port to bind the server to (for SSE transport)")
@click.argument("urls", nargs=-1)
def main(
    api_key: str | None = None,
    transport: Literal["stdio", "sse"] = "stdio",
    host: str = "127.0.0.1",
    port: int | None = None,
    urls: tuple[str, ...] = ()
) -> None:
    """Blitz Agent MCP Server - Run the MCP server"""
    logger.info("Starting MCP server with urls: %s", urls)
    
    # For deployment platforms like Render, use environment variables
    if transport == "sse":
        # Use PORT env var if available (Render, Heroku, etc.)
        if port is None:
            port = int(os.getenv("PORT", "8000"))
        
        # For deployment, bind to all interfaces
        if os.getenv("RENDER") or os.getenv("RAILWAY_PROJECT_ID") or os.getenv("HEROKU_APP_NAME"):
            host = "0.0.0.0"
        
        logger.info(f"SSE server will bind to {host}:{port}")
    
    mcp_instance = get_mcp(urls, api_key)
    
    # Handle different transport modes
    if transport == "sse":
        run_sse_server(mcp_instance, host, port)
    else:
        mcp_instance.run(transport=transport)


if __name__ == "__main__":
    main() 