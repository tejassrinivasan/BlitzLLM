import asyncio
import logging
import secrets
from typing import Any, Dict
from azure.cosmos import CosmosClient, exceptions
from datetime import datetime

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import COSMOS_DB_ENDPOINT, COSMOS_DB_KEY
from ..utils import serialize_response

__all__ = ["upload"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def upload(
    ctx: Context,
    description: str = Field(..., description="Description of the query"),
    query: str = Field(..., description="SQL query to upload")
) -> Dict[str, Any]:
    """
    Upload final, successful queries to Cosmos DB for learning purposes.
    
    This tool stores successful query executions with a hex ID, description, and query so that you can recall from them in the future.
    
    Uploading Instructions:
    1. Provide a description of what the query does
    2. Include the SQL query that was executed successfully
    3. A hex string ID will be generated automatically
    """
    if not description:
        raise ValueError("description is required")
    if not query:
        raise ValueError("query is required")
    
    try:
        endpoint = COSMOS_DB_ENDPOINT
        key = COSMOS_DB_KEY
        
        if not endpoint or not key:
            return {
                "success": False,
                "error": "Cosmos DB credentials not configured",
                "message": "COSMOS_DB_ENDPOINT and COSMOS_DB_KEY environment variables must be set"
            }
            
        client = CosmosClient(endpoint, key)
        database = client.get_database_client('sports')
        container = database.get_container_client('agent-learning')
        
        # Generate hex string ID
        hex_id = secrets.token_hex(16)
        
        # Create the simple query record
        query_record = {
            'id': hex_id,
            'description': description,
            'query': query,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Upload to Cosmos DB
        response = container.create_item(query_record)
        
        return {
            "success": True,
            "id": hex_id,
            "description": description,
            "query": query,
            "timestamp": query_record['timestamp'],
            "message": f"Successfully uploaded query with ID: {hex_id}"
        }
        
    except exceptions.CosmosHttpResponseError as e:
        return {
            "success": False,
            "error": f"Cosmos DB error: {e.message}",
            "status_code": e.status_code
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Upload failed: {str(e)}",
            "message": "Failed to upload query to Cosmos DB. Please check credentials and try again."
        } 