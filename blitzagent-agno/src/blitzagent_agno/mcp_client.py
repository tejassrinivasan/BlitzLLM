"""
MCP (Model Context Protocol) client for BlitzAgent.

This module provides connectivity to the Python MCP server,
enabling access to database tools, web scraping, and other capabilities.
"""

import asyncio
import json
import time
import subprocess
import os
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import structlog
import websockets
import asyncpg
from websockets.exceptions import ConnectionClosed, WebSocketException

from .exceptions import MCPError, MCPConnectionError, MCPTimeoutError


logger = structlog.get_logger(__name__)


class MCPClient:
    """
    Client for communicating with MCP servers.
    
    Supports WebSocket and stdio transports for connecting to
    Model Context Protocol servers. Also provides direct database
    tool integration when MCP server is not available.
    """
    
    def __init__(
        self,
        server_url: str,
        transport: str = "websocket",
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        database_config=None
    ):
        """Initialize MCP client."""
        self.server_url = server_url
        self.transport = transport.lower()
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.database_config = database_config
        
        # Connection state
        self.websocket = None
        self.process = None
        self.connected = False
        self.available_tools = {}
        self.db_connection = None
        
        # Request tracking
        self._request_id = 0
        self._pending_requests = {}
        
        self.logger = logger.bind(
            component="mcp_client",
            server_url=server_url,
            transport=transport
        )
    
    async def connect(self) -> None:
        """Connect to the MCP server."""
        if self.transport == "websocket":
            await self._connect_websocket()
        elif self.transport == "stdio":
            await self._connect_stdio()
        elif self.server_url.startswith("direct://"):
            await self._connect_direct()
        else:
            # Fall back to direct database connection
            await self._connect_direct()
        
        # Initialize session (only for non-direct connections)
        if self.connected and not self.server_url.startswith("direct://"):
            await self._initialize_session()
            await self._list_tools()
        
        self.logger.info(
            "MCP client connected",
            available_tools=len(self.available_tools)
        )
    
    async def _connect_stdio(self) -> None:
        """Connect via stdio transport."""
        try:
            # For stdio transport, we'll use direct database integration
            await self._connect_direct()
            self.logger.info("Using direct database integration (stdio fallback)")
            
        except Exception as e:
            self.logger.error("Failed to connect via stdio", error=str(e))
            raise MCPConnectionError(f"Stdio connection failed: {e}")
    
    async def _connect_direct(self) -> None:
        """Connect directly to database tools."""
        try:
            # Get database connection from config or environment
            if self.database_config:
                db_host = self.database_config.host
                db_port = str(self.database_config.port)
                db_name = self.database_config.database
                db_user = self.database_config.user
                db_password = self.database_config.password
            else:
                db_host = os.getenv("DATABASE_HOST")
                db_port = os.getenv("DATABASE_PORT", "5432")
                db_name = os.getenv("DATABASE_NAME")
                db_user = os.getenv("DATABASE_USER")
                db_password = os.getenv("DATABASE_PASSWORD")
            
            if not all([db_host, db_name, db_user, db_password]):
                raise MCPConnectionError("Database configuration incomplete")
            
            # URL encode password for special characters
            import urllib.parse
            encoded_password = urllib.parse.quote(db_password, safe='')
            
            conn_str = f'postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}'
            
            self.db_connection = await asyncpg.connect(conn_str, ssl='require')
            self.connected = True
            
            # Register built-in database tools
            self.available_tools = {
                "query_database": {
                    "description": "Execute SQL queries on the database",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "SQL query to execute"},
                            "limit": {"type": "integer", "description": "Maximum number of rows to return", "default": 100}
                        },
                        "required": ["query"]
                    }
                },
                "inspect_tables": {
                    "description": "List all tables and their schemas",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "schema": {"type": "string", "description": "Schema name", "default": "public"}
                        }
                    }
                },
                "sample_data": {
                    "description": "Get sample data from a table",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "table_name": {"type": "string", "description": "Name of the table"},
                            "limit": {"type": "integer", "description": "Number of rows to sample", "default": 10}
                        },
                        "required": ["table_name"]
                    }
                }
            }
            
            self.logger.info("Direct database connection established")
            
        except Exception as e:
            self.logger.error("Failed to connect directly to database", error=str(e))
            raise MCPConnectionError(f"Direct connection failed: {e}")
    
    async def _connect_websocket(self) -> None:
        """Connect via WebSocket."""
        for attempt in range(self.retry_attempts):
            try:
                self.websocket = await websockets.connect(
                    self.server_url,
                    timeout=self.timeout,
                    ping_interval=20,
                    ping_timeout=10
                )
                self.connected = True
                self.logger.info("WebSocket connection established")
                return
                
            except Exception as e:
                self.logger.warning(
                    "WebSocket connection attempt failed",
                    attempt=attempt + 1,
                    error=str(e)
                )
                
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    raise MCPConnectionError(f"Failed to connect after {self.retry_attempts} attempts: {e}")
    
    async def _initialize_session(self) -> None:
        """Initialize MCP session."""
        try:
            response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                }
            })
            
            self.logger.debug("MCP session initialized", response=response)
            
        except Exception as e:
            self.logger.error("Failed to initialize MCP session", error=str(e))
            raise MCPError(f"Session initialization failed: {e}")
    
    async def _list_tools(self) -> None:
        """List available tools from the MCP server."""
        try:
            response = await self._send_request("tools/list", {})
            
            if "tools" in response:
                self.available_tools = {
                    tool["name"]: {
                        "description": tool.get("description", ""),
                        "inputSchema": tool.get("inputSchema", {})
                    }
                    for tool in response["tools"]
                }
            
            self.logger.debug(
                "Available tools retrieved",
                tool_count=len(self.available_tools),
                tools=list(self.available_tools.keys())
            )
            
        except Exception as e:
            self.logger.error("Failed to list tools", error=str(e))
            # Don't raise here - continue without tools
            self.available_tools = {}
    
    async def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on the MCP server or execute directly."""
        if not self.connected:
            raise MCPError("Not connected to MCP server")
        
        if tool_name not in self.available_tools:
            raise MCPError(f"Tool '{tool_name}' not available. Available tools: {list(self.available_tools.keys())}")
        
        start_time = time.time()
        
        try:
            # Handle direct database tools
            if self.db_connection and tool_name in ["query_database", "inspect_tables", "sample_data"]:
                response = await self._call_direct_tool(tool_name, parameters)
            else:
                # Use regular MCP protocol
                response = await self._send_request("tools/call", {
                    "name": tool_name,
                    "arguments": parameters
                })
            
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                "Tool called successfully",
                tool_name=tool_name,
                duration_ms=duration_ms,
                has_result="content" in response
            )
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(
                "Tool call failed",
                tool_name=tool_name,
                duration_ms=duration_ms,
                error=str(e)
            )
            raise MCPError(f"Tool call failed: {e}")
    
    async def _call_direct_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools directly against the database."""
        try:
            if tool_name == "query_database":
                query = parameters["query"]
                limit = parameters.get("limit", 100)
                
                # Add LIMIT if not already present
                if "LIMIT" not in query.upper() and limit:
                    query = f"{query.rstrip(';')} LIMIT {limit}"
                
                rows = await self.db_connection.fetch(query)
                
                # Convert rows to dictionaries
                result_data = [dict(row) for row in rows]
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Query executed successfully. Returned {len(result_data)} rows."
                        }
                    ],
                    "result": result_data,
                    "isError": False
                }
                
            elif tool_name == "inspect_tables":
                schema = parameters.get("schema", "public")
                
                query = """
                    SELECT 
                        table_name,
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns 
                    WHERE table_schema = $1
                    ORDER BY table_name, ordinal_position
                """
                
                rows = await self.db_connection.fetch(query, schema)
                
                # Group by table
                tables = {}
                for row in rows:
                    table_name = row['table_name']
                    if table_name not in tables:
                        tables[table_name] = []
                    
                    tables[table_name].append({
                        'column': row['column_name'],
                        'type': row['data_type'],
                        'nullable': row['is_nullable'] == 'YES',
                        'default': row['column_default']
                    })
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Found {len(tables)} tables in schema '{schema}'"
                        }
                    ],
                    "result": tables,
                    "isError": False
                }
                
            elif tool_name == "sample_data":
                table_name = parameters["table_name"]
                limit = parameters.get("limit", 10)
                
                # Safely quote table name
                query = f"SELECT * FROM {table_name} LIMIT $1"
                rows = await self.db_connection.fetch(query, limit)
                
                result_data = [dict(row) for row in rows]
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Sample data from {table_name}: {len(result_data)} rows"
                        }
                    ],
                    "result": result_data,
                    "isError": False
                }
            
            else:
                raise MCPError(f"Unknown direct tool: {tool_name}")
                
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing {tool_name}: {str(e)}"
                    }
                ],
                "result": None,
                "isError": True
            }
    
    async def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get the list of available tools."""
        return self.available_tools.copy()
    
    async def get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        """Get the input schema for a specific tool."""
        if tool_name not in self.available_tools:
            raise MCPError(f"Tool '{tool_name}' not available")
        
        return self.available_tools[tool_name].get("inputSchema", {})
    
    async def _send_request(
        self,
        method: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a request to the MCP server."""
        if not self.connected or not self.websocket:
            raise MCPError("Not connected to MCP server")
        
        request_id = self._get_next_request_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        try:
            # Send request
            await self.websocket.send(json.dumps(request))
            
            # Wait for response
            response = await asyncio.wait_for(
                self._wait_for_response(request_id),
                timeout=self.timeout
            )
            
            if "error" in response:
                error = response["error"]
                raise MCPError(f"MCP server error: {error.get('message', 'Unknown error')}")
            
            return response.get("result", {})
            
        except asyncio.TimeoutError:
            raise MCPTimeoutError(f"Request timed out after {self.timeout} seconds")
        except ConnectionClosed:
            self.connected = False
            raise MCPConnectionError("Connection to MCP server lost")
        except WebSocketException as e:
            raise MCPConnectionError(f"WebSocket error: {e}")
        except Exception as e:
            raise MCPError(f"Request failed: {e}")
    
    async def _wait_for_response(self, request_id: int) -> Dict[str, Any]:
        """Wait for a specific response from the server."""
        while True:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                if data.get("id") == request_id:
                    return data
                else:
                    # Handle notifications or other responses
                    self.logger.debug("Received unmatched message", data=data)
                    
            except json.JSONDecodeError as e:
                self.logger.warning("Received invalid JSON", error=str(e))
                continue
    
    def _get_next_request_id(self) -> int:
        """Get the next request ID."""
        self._request_id += 1
        return self._request_id
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on MCP connection."""
        try:
            if not self.connected:
                return {
                    "status": "disconnected",
                    "error": "Not connected to MCP server"
                }
            
            # Try to list tools as a health check
            tools = await self.list_tools()
            
            return {
                "status": "healthy",
                "server_url": self.server_url,
                "transport": self.transport,
                "available_tools": len(tools),
                "tools": list(tools.keys())
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        try:
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            
            if self.process:
                self.process.terminate()
                await asyncio.sleep(0.1)
                if self.process.poll() is None:
                    self.process.kill()
                self.process = None
            
            if self.db_connection:
                await self.db_connection.close()
                self.db_connection = None
            
            self.connected = False
            self.available_tools = {}
            
            self.logger.info("MCP client disconnected")
            
        except Exception as e:
            self.logger.error("Error during disconnect", error=str(e))
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Utility functions for MCP tool integration
class MCPToolWrapper:
    """Wrapper for MCP tools to integrate with Agno."""
    
    def __init__(
        self,
        name: str,
        mcp_client: MCPClient,
        description: str = "",
        schema: Optional[Dict[str, Any]] = None
    ):
        """Initialize MCP tool wrapper."""
        self.name = name
        self.mcp_client = mcp_client
        self.description = description
        self.schema = schema or {}
    
    async def __call__(self, **kwargs) -> Dict[str, Any]:
        """Execute the MCP tool."""
        return await self.mcp_client.call_tool(self.name, kwargs)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return self.schema


async def create_mcp_client(
    server_url: str,
    transport: str = "websocket",
    timeout: int = 30,
    retry_attempts: int = 3
) -> MCPClient:
    """Create and connect an MCP client."""
    client = MCPClient(
        server_url=server_url,
        transport=transport,
        timeout=timeout,
        retry_attempts=retry_attempts
    )
    await client.connect()
    return client


def parse_mcp_url(url: str) -> Dict[str, str]:
    """Parse MCP URL and extract components."""
    parsed = urlparse(url)
    
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port) if parsed.port else "8080",
        "path": parsed.path or "/mcp"
    } 