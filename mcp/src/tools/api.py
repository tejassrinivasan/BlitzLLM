"""OpenAPI endpoint discovery and calling tool."""

import asyncio
import logging
import aiohttp
import json
from typing import Any, Dict, Optional

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from config import MAX_DATA_ROWS
from utils import serialize_response

__all__ = ["get_api_docs", "call_api_endpoint"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def get_api_docs(
    ctx: Context,
    openapi_url: str = Field(..., description="OpenAPI specification URL")
) -> dict[str, Any]:
    """
    Discover available endpoints from an OpenAPI specification.
    
    This tool fetches and parses an OpenAPI specification to return information about available endpoints, their methods, parameters, and descriptions.
    
    Discovery Instructions:
    1. Provide the OpenAPI specification URL (usually ends with /openapi.json or /swagger.json)
    2. The tool will parse the specification and return structured information about available endpoints
    3. Use this tool before making API calls to understand what endpoints and methods are available
    4. The response includes endpoint paths, HTTP methods, descriptions, parameters, and response types
    """
    if not openapi_url:
        raise ValueError("openapi_url is required")
    
    try:
        async with aiohttp.ClientSession() as session:
            return await _discover_api(session, openapi_url)
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "openapi_url": openapi_url
        }


async def call_api_endpoint(
    ctx: Context,
    openapi_url: str = Field(..., description="OpenAPI specification URL"),
    endpoint: str = Field(..., description="Specific endpoint to call"),
    method: str = Field(default="GET", description="HTTP method to use (GET, POST, PUT, DELETE, PATCH)"),
    parameters: dict = Field(default_factory=dict, description="Parameters for the API call")
) -> dict[str, Any]:
    """
    Make an API call to a specific endpoint using the OpenAPI specification.
    
    This tool makes actual HTTP requests to API endpoints, using the OpenAPI specification to determine the base URL and server configuration.
    
    API Calling Instructions:
    1. First use get_api_docs to discover available endpoints and their parameters
    2. Provide the same OpenAPI specification URL used for discovery
    3. Specify the endpoint path to call (e.g., "/users" or "/data/{id}")
    4. Choose the appropriate HTTP method (GET, POST, PUT, DELETE, PATCH)
    5. Include parameters as needed (query params for GET, body data for POST/PUT)
    """
    if not openapi_url:
        raise ValueError("openapi_url is required")
    if not endpoint:
        raise ValueError("endpoint is required")
    if not method:
        raise ValueError("method is required")
    
    try:
        async with aiohttp.ClientSession() as session:
            return await _call_api(session, openapi_url, endpoint, method, parameters or {})
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "openapi_url": openapi_url,
            "endpoint": endpoint,
            "method": method
        }


async def _discover_api(session: aiohttp.ClientSession, openapi_url: str) -> Dict[str, Any]:
    """Discover OpenAPI endpoints."""
    async with session.get(openapi_url) as response:
        if response.status != 200:
            return {
                "success": False,
                "error": f"Failed to fetch OpenAPI spec: HTTP {response.status}"
            }
        
        spec = await response.json()
        
        # Extract basic info
        info = spec.get("info", {})
        servers = spec.get("servers", [])
        paths = spec.get("paths", {})
        
        # Extract endpoints
        endpoints = []
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary", ""),
                        "description": details.get("description", ""),
                        "parameters": details.get("parameters", []),
                        "responses": list(details.get("responses", {}).keys())
                    })
        
        return {
            "success": True,
            "api_info": {
                "title": info.get("title", ""),
                "version": info.get("version", ""),
                "description": info.get("description", ""),
                "servers": [server.get("url", "") for server in servers],
                "total_endpoints": len(endpoints)
            },
            "endpoints": endpoints[:20]  # Limit to first 20 for readability
        }


async def _call_api(session: aiohttp.ClientSession, openapi_url: str, endpoint: str, method: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Call an API endpoint."""
    # First get the OpenAPI spec to determine the base URL
    async with session.get(openapi_url) as response:
        if response.status != 200:
            return {
                "success": False,
                "error": f"Failed to fetch OpenAPI spec: HTTP {response.status}"
            }
        
        spec = await response.json()
        servers = spec.get("servers", [])
        
        if not servers:
            return {
                "success": False,
                "error": "No servers defined in OpenAPI spec"
            }
        
        base_url = servers[0].get("url", "")
        full_url = f"{base_url.rstrip('/')}{endpoint}"
        
        # Prepare request parameters
        request_kwargs = {
            "timeout": aiohttp.ClientTimeout(total=30)
        }
        
        if method.upper() in ["POST", "PUT", "PATCH"]:
            request_kwargs["json"] = parameters
        else:
            request_kwargs["params"] = parameters
        
        # Make the API call
        async with session.request(method, full_url, **request_kwargs) as api_response:
            response_text = await api_response.text()
            
            try:
                response_json = json.loads(response_text)
            except json.JSONDecodeError:
                response_json = None
            
            return {
                "success": True,
                "request": {
                    "url": full_url,
                    "method": method.upper(),
                    "parameters": parameters
                },
                "response": {
                    "status": api_response.status,
                    "headers": dict(api_response.headers),
                    "data": response_json if response_json else response_text[:1000]  # Limit response size
                }
            } 