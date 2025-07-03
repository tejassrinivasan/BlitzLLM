import asyncio
import logging
import secrets
import uuid
from typing import Any, Dict, List
from azure.cosmos import CosmosClient, exceptions
from datetime import datetime

import httpx
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
    query_description: str = Field(..., description="Description of what the query does"),
    query: str = Field(..., description="SQL query that was executed successfully"),
    assistant_prompt: str = Field(default="", description="Assistant's response or explanation (optional)"),
    league: str = Field(default=None, description="League for the query (e.g., 'mlb', 'nba'). Determines the container to upload to.")
) -> Dict[str, Any]:
    """
    Upload final, successful queries to Cosmos DB for learning purposes.
    
    This tool stores successful query executions in league-specific containers 
    so that you can recall from them in the future.
    
    Uploading Instructions:
    1. Provide a description of what the query does
    2. Include the SQL query that was executed successfully
    3. Optionally include assistant's response or explanation
    4. Specify the league to determine the correct container (mlb-unofficial, nba-unofficial)
    5. A unique UUID will be generated automatically
    6. UserPromptVector and QueryVector will be set to null (embeddings can be generated later)
    
    Container mapping:
    - league="mlb" → "mlb-unofficial" container
    - league="nba" → "nba-unofficial" container
    - league=None → "agent-learning" container (fallback)
    """
    if not query_description:
        raise ValueError("query_description is required")
    if not query:
        raise ValueError("query is required")
    
    logger = logging.getLogger("blitz-agent-mcp")
    
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
        
        # Determine container based on league
        if league:
            league = league.lower()
            if league == "mlb":
                container_name = "mlb-unofficial"
            elif league == "nba":
                container_name = "nba-unofficial"
            else:
                # For unknown leagues, use a generic container
                container_name = f"{league}-unofficial"
        else:
            # Fallback to original container when no league specified
            container_name = "agent-learning"
        
        container = database.get_container_client(container_name)
        
        # Generate unique UUID
        record_id = str(uuid.uuid4())
        
        # Create the query record with the specified fields
        query_record = {
            'id': record_id,
            'UserPrompt': query_description,
            'Query': query,
            'UserPromptVector': None,
            'QueryVector': None
        }
        
        # Upload to Cosmos DB
        response = container.create_item(query_record)
        
        return {
            "success": True,
            "id": record_id,
            "UserPrompt": query_description,
            "Query": query,
            "league": league,
            "container": container_name,
            "embeddings_generated": False,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Successfully uploaded query with ID: {record_id} to container: {container_name}"
        }
        
    except exceptions.CosmosHttpResponseError as e:
        return {
            "success": False,
            "error": f"Cosmos DB error: {e.message}",
            "status_code": e.status_code,
            "league": league,
            "container": container_name if 'container_name' in locals() else "unknown"
        }
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return {
            "success": False,
            "error": f"Upload failed: {str(e)}",
            "league": league,
            "message": "Failed to upload query to Cosmos DB. Please check credentials and try again."
        } 