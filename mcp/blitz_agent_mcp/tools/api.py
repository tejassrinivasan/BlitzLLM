"""OpenAPI endpoint discovery and calling tool."""

import asyncio
import logging
import aiohttp
import json
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import MAX_DATA_ROWS
from ..utils import serialize_response

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
    6. For APIs requiring authentication, include the API key in parameters (e.g., {"key": "your_api_key"})
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


def _detect_api_type_and_base_url(openapi_url: str, spec: Dict[str, Any]) -> tuple[str, str]:
    """
    Detect API type and determine the correct base URL.
    
    Some APIs have incorrect or outdated OpenAPI specs, so we need to detect
    common patterns and override with known working base URLs.
    """
    # Check if this is a SportsData.io API
    if "sportsdata.io" in openapi_url.lower():
        # Extract API info from the swagger URL pattern
        # Expected pattern: https://sportsdata.io/downloads/swagger/{sport}-v3-{category}.json
        url_parts = openapi_url.lower().split('/')
        if 'swagger' in url_parts:
            swagger_filename = url_parts[-1]  # e.g., "mlb-v3-odds.json"
            if swagger_filename.endswith('.json'):
                swagger_parts = swagger_filename[:-5].split('-')  # Remove .json, split by -
                if len(swagger_parts) >= 3:
                    sport = swagger_parts[0]  # e.g., "mlb"
                    version = swagger_parts[1]  # e.g., "v3"
                    category = swagger_parts[2]  # e.g., "odds"
                    
                    # Construct the correct base URL for SportsData.io
                    base_url = f"https://api.sportsdata.io/{version}/{sport}/{category}"
                    return "sportsdata", base_url
    
    # Fallback to OpenAPI spec servers
    servers = spec.get("servers", [])
    if servers:
        return "openapi", servers[0].get("url", "")
    
    return "unknown", ""


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
        
        # Detect API type and get correct base URL
        api_type, detected_base_url = _detect_api_type_and_base_url(openapi_url, spec)
        
        # Extract endpoints
        endpoints = []
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    endpoint_info = {
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary", ""),
                        "description": details.get("description", ""),
                        "parameters": details.get("parameters", []),
                        "responses": list(details.get("responses", {}).keys())
                    }
                    
                    # For SportsData.io, add API key requirement info
                    if api_type == "sportsdata":
                        endpoint_info["requires_api_key"] = True
                        endpoint_info["api_key_param"] = "key"
                    
                    endpoints.append(endpoint_info)
        
        return {
            "success": True,
            "api_info": {
                "title": info.get("title", ""),
                "version": info.get("version", ""),
                "description": info.get("description", ""),
                "servers": [server.get("url", "") for server in servers],
                "detected_base_url": detected_base_url,
                "api_type": api_type,
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
        
        # Detect API type and get correct base URL
        api_type, base_url = _detect_api_type_and_base_url(openapi_url, spec)
        
        if not base_url:
            return {
                "success": False,
                "error": "No valid base URL found in OpenAPI spec or detected patterns"
            }
        
        # For SportsData.io APIs, ensure endpoint has correct format
        if api_type == "sportsdata":
            # Ensure endpoint starts with /json for SportsData.io
            if not endpoint.startswith('/json'):
                if endpoint.startswith('/JSON'):
                    endpoint = endpoint.replace('/JSON', '/json', 1)
                elif not endpoint.startswith('/'):
                    endpoint = f"/json/{endpoint}"
                else:
                    endpoint = f"/json{endpoint}"
            
            # Ensure API key is provided for SportsData.io
            if 'key' not in parameters:
                return {
                    "success": False,
                    "error": "API key is required for SportsData.io. Please include 'key' in parameters."
                }
        
        # Construct full URL
        full_url = f"{base_url.rstrip('/')}{endpoint}"
        
        # Prepare request parameters
        request_kwargs = {
            "timeout": aiohttp.ClientTimeout(total=30)
        }
        
        # For all requests, pass parameters as query params (including API keys)
        # This ensures API keys are always included in the URL
        if method.upper() in ["POST", "PUT", "PATCH"]:
            # For POST/PUT/PATCH, separate query params from body data
            query_params = {}
            body_data = {}
            
            for key, value in parameters.items():
                # API keys and common query params go in URL
                if key.lower() in ['key', 'api_key', 'apikey', 'token', 'include', 'exclude', 'format']:
                    query_params[key] = value
                else:
                    body_data[key] = value
            
            if query_params:
                request_kwargs["params"] = query_params
            if body_data:
                request_kwargs["json"] = body_data
        else:
            # For GET requests, all parameters go as query params
            request_kwargs["params"] = parameters
        
        # Make the API call
        try:
            async with session.request(method, full_url, **request_kwargs) as api_response:
                response_text = await api_response.text()
                
                try:
                    response_json = json.loads(response_text)
                except json.JSONDecodeError:
                    response_json = None
                
                # Limit response data size for readability
                response_data = response_json if response_json else response_text
                if isinstance(response_data, str) and len(response_data) > 2000:
                    response_data = response_data[:2000] + "... (truncated)"
                elif isinstance(response_data, list) and len(response_data) > 10:
                    response_data = response_data[:10] + [{"...": f"and {len(response_data) - 10} more items"}]
                
                return {
                    "success": api_response.status < 400,
                    "request": {
                        "url": full_url,
                        "method": method.upper(),
                        "parameters": parameters,
                        "detected_api_type": api_type,
                        "base_url": base_url
                    },
                    "response": {
                        "status": api_response.status,
                        "headers": dict(api_response.headers),
                        "data": response_data
                    }
                }
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"HTTP request failed: {str(e)}",
                "request": {
                    "url": full_url,
                    "method": method.upper(),
                    "parameters": parameters
                }
            } 