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
    query: str = Field(..., description="SQL query to upload"),
    league: str = Field(default=None, description="League for the query (e.g., 'mlb', 'nba'). Determines the container to upload to."),
    results: str = Field(default=None, description="Query results (optional)"),
    context: str = Field(default=None, description="Additional context (optional)"),
    validation_score: float = Field(default=0.0, description="Validation score (optional)", ge=0.0, le=1.0)
) -> Dict[str, Any]:
    """
    Upload final, successful queries to Cosmos DB for learning purposes.
    
    This tool stores successful query executions in league-specific containers so that you can recall from them in the future.
    
    Uploading Instructions:
    1. Provide a description of what the query does
    2. Include the SQL query that was executed successfully
    3. Specify the league to determine the correct container (mlb-unofficial, nba-unofficial)
    4. Optionally include results, context, and validation score
    5. A hex string ID will be generated automatically
    
    Container mapping:
    - league="mlb" → "mlb-unofficial" container
    - league="nba" → "nba-unofficial" container
    - league=None → "agent-learning" container (fallback)
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
        
        # Generate hex string ID
        hex_id = secrets.token_hex(16)
        
        # Create the query record with enhanced fields
        query_record = {
            'id': hex_id,
            'description': description,
            'query': query,
            'league': league,
            'results': results,
            'context': context,
            'validation_score': validation_score,
            'timestamp': datetime.utcnow().isoformat(),
            'container': container_name
        }
        
        # Upload to Cosmos DB
        response = container.create_item(query_record)
        
        return {
            "success": True,
            "id": hex_id,
            "description": description,
            "query": query,
            "league": league,
            "container": container_name,
            "validation_score": validation_score,
            "timestamp": query_record['timestamp'],
            "message": f"Successfully uploaded query with ID: {hex_id} to container: {container_name}"
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
        return {
            "success": False,
            "error": f"Upload failed: {str(e)}",
            "league": league,
            "message": "Failed to upload query to Cosmos DB. Please check credentials and try again."
        } 