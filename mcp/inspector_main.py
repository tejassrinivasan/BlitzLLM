#!/usr/bin/env python3
"""
Blitz Agent MCP Server - Inspector-compatible version
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

import httpx
import click
from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field
from sqlalchemy.engine.url import make_url

# Add the current directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now we can import our modules
from blitz_agent_mcp.config import API_KEY_HEADER, BACKEND_URL, get_postgres_url
from blitz_agent_mcp.models.connection import Connection

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("blitz-agent-mcp")


@dataclass
class AppContext:
    """Application context for the MCP server"""
    http_session: httpx.AsyncClient | None = None
    url_map: dict = Field(default_factory=dict)


def configure_logging(quiet: bool = False):
    """Configure logging based on mode"""
    if quiet:
        # For CLI usage, suppress most logging except critical errors
        logging.getLogger().setLevel(logging.ERROR)
        # Suppress our own module and all submodules
        logging.getLogger("blitz-agent-mcp").setLevel(logging.ERROR)
        logging.getLogger("blitz_agent_mcp").setLevel(logging.ERROR)
        # Suppress MCP protocol logs
        logging.getLogger("mcp").setLevel(logging.ERROR)
        # Suppress Azure SDK logs
        logging.getLogger("azure").setLevel(logging.ERROR)
        logging.getLogger("azure.core").setLevel(logging.ERROR)
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.ERROR)
        logging.getLogger("azure.search").setLevel(logging.ERROR)
        # Suppress HTTP client logs
        logging.getLogger("httpx").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.ERROR)
        # Suppress other tool logs
        logging.getLogger("toolfront").setLevel(logging.ERROR)
    else:
        # Default verbose logging for direct server usage
        logging.basicConfig(level=logging.INFO)


def get_mcp(urls: tuple[str, ...], api_key: str | None = None, host: str = "127.0.0.1", port: int = 8000, quiet: bool = False) -> FastMCP:
    # Note: Database connections are now handled lazily by individual tools based on league parameter
    # No need to test database connections during startup
    
    @asynccontextmanager
    async def app_lifespan(mcp_server: FastMCP) -> AsyncIterator[AppContext]:
        """Manage application lifecycle with type-safe context"""
        # No database connection testing during startup - connections are handled by tools
        
        if api_key:
            headers = {API_KEY_HEADER: api_key}
            async with httpx.AsyncClient(headers=headers, base_url=BACKEND_URL) as http_client:
                yield AppContext(http_session=http_client, url_map={})
        else:
            yield AppContext(url_map={})

    # Use stateless HTTP for production deployment
    mcp = FastMCP("Blitz Agent MCP Server", lifespan=app_lifespan, host=host, port=port, stateless_http=True)

    # Import tools here so they register themselves with the mcp instance
    from blitz_agent_mcp.tools import tools_setup
    tools_setup.setup_tools(mcp)

    return mcp


def run_http_server(mcp_instance: FastMCP, transport: str, host: str = "127.0.0.1", port: int = 8000, quiet: bool = False):
    """Run HTTP server using FastMCP's built-in transport"""
    if not quiet:
        logger.info(f"Starting {transport} server on {host}:{port}")
        logger.info(f"Using FastMCP built-in {transport} transport")
    
    mcp_instance.run(transport=transport)


# Create the global MCP instance for the Inspector
mcp = get_mcp((), None, "127.0.0.1", 8000, True)  # Use quiet=True for better compatibility


@click.command()
@click.option("--api-key", envvar="BLITZ_API_KEY", help="API key for authentication")
@click.option("--transport", type=click.Choice(["stdio", "sse", "streamable-http"]), default="stdio", help="Transport mode for MCP server (streamable-http recommended for production)")
@click.option("--host", default="127.0.0.1", help="Host to bind the server to (for HTTP transports)")
@click.option("--port", type=int, default=None, help="Port to bind the server to (for HTTP transports)")
@click.option("--quiet", is_flag=True, help="Suppress verbose logging (useful for CLI integration)")
@click.argument("urls", nargs=-1)
def main(
    api_key: str | None = None,
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
    host: str = "127.0.0.1",
    port: int | None = None,
    quiet: bool = False,
    urls: tuple[str, ...] = ()
) -> None:
    """Blitz Agent MCP Server - Run the MCP server"""
    # Configure logging based on quiet mode
    configure_logging(quiet=quiet)
    
    logger.info("Starting MCP server with urls: %s", urls)
    
    # Create MCP instance
    mcp = get_mcp(urls, api_key, host, port or 8000, quiet)
    
    # Run the server
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        run_http_server(mcp, transport, host, port or 8000, quiet)


if __name__ == "__main__":
    main() 