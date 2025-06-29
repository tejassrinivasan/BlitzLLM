import asyncio
import logging
import json
from typing import Any, List, Optional

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

# Azure AI Search imports
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

from config import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX
from utils import get_azure_chat_client, serialize_response

logger = logging.getLogger(__name__)

__all__ = ["recall_similar_db_queries"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def rank_search_results(query_text: str, search_results: List[Any], league: str) -> List[Any]:
    """Rank search results using GPT-4o-mini via Azure OpenAI."""
    try:
        # Format the search results for ranking
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                "id": result.get("id", ""),
                "prompt": result.get("UserPrompt", "")
            })

        chat_client = get_azure_chat_client()
        
        system_prompt = f"You are an expert on {league.upper()} and PostgreSQL. Your job is to see which questions from the search results are most similar to the user's question in terms of meaning/intent or the ones you think would be answered with a similar PostgreSQL query. Return a JSON object with a single key 'documentIds' containing a list of the relevant document IDs in order of relevance."
        
        human_prompt = f"""
                        USER QUESTION:
                        {query_text}

                        SEARCH RESULTS:
                        {json.dumps(formatted_results, indent=2)}

                        Return document IDs in order of relevance to the user's message or the ones you think would be answered with a similar PostgreSQL query.
                        Only include documents that are actually relevant - you don't need to return all of them.
                        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt},
        ]

        response = chat_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
        )
        
        try:
            ranking_result = json.loads(response.choices[0].message.content)
            document_ids = ranking_result.get("documentIds", [])
        except (json.JSONDecodeError, AttributeError):
            logger.error("Failed to decode JSON from model response.")
            return search_results[:10]

        # Create a mapping of document ID to full document
        doc_map = {doc.get("id", ""): doc for doc in search_results}

        # Return ranked results in order
        ranked_results = [doc_map[doc_id] for doc_id in document_ids if doc_id in doc_map]

        return ranked_results

    except Exception as error:
        logger.error(f'Error ranking search results: {error}')
        # Return original results if ranking fails
        return search_results[:10]


async def recall_similar_db_queries(
    ctx: Context,
    query: str = Field(..., description="Query to search for"),
    league: str = Field("mlb", description="League to search within"),
    conversation_history: List[str] = Field(default_factory=list, description="Previous conversation context"),
    recall_similar_db_queries_type: str = Field("historical_queries", description="Type of recall_similar_db_queries data to retrieve")
) -> dict[str, Any]:
    """
    Retrieve most relevant historical queries using Azure AI Search hybrid search and GPT-4o-mini reranking.

    ALWAYS RECALL PREVIOUS QUERIES BEFORE WRITING QUERIES TO PREVENT ERRORS/SAVING TIME. NEVER SKIP THIS STEP.

    Instructions:
    1. Uses hybrid search on Azure AI Search index to find similar queries that have been answered in the past and are most relevant to the user's current question
    2. Reranks results using GPT-4o-mini for relevance
    3. Returns the most relevant historical queries for recall_similar_db_queries
    """
    if not query:
        raise ValueError("query is required")
    
    try:
        endpoint = AZURE_SEARCH_ENDPOINT
        api_key = AZURE_SEARCH_KEY
        index_name = AZURE_SEARCH_INDEX or f"blitz-{league.lower()}-index"

        if not endpoint or not api_key:
            logger.warning(f"Azure Search credentials not configured. endpoint: {bool(endpoint)}, api_key: {bool(api_key)}")
            return {
                "success": False,
                "error": "Azure Search credentials not configured. Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY environment variables or configure them in config.json",
                "query": query,
                "league": league,
                "fallback_suggestion": "You can continue without historical context, but recall_similar_db_queries from previous queries will not be available."
            }

        # Combine query with conversation history for better context
        search_text = query
        if conversation_history and len(conversation_history) > 0:
            last_user_messages = conversation_history[-3:]  # Get last 3 messages
            search_text = '\n'.join(last_user_messages + [query])

        # Create SearchClient
        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key)
        )
        
        logger.info(f"Performing hybrid search on index: {index_name}...")
        
        # Perform hybrid search
        results = search_client.search(
            search_text,
            select=["id", "UserPrompt", "Query", "AssistantPrompt"],
            search_mode='any',
            query_type='semantic',
            semantic_configuration_name='my-semantic-config',
            top=20
        )
        
        # Collect results for processing
        collected_results = []
        for result in results:
            collected_results.append(result)
        
        if not collected_results:
            return {
                "success": False,
                "error": "No results found in search index",
                "query": query,
                "league": league
            }
        
        # Rank the results using GPT-4o-mini
        logger.info("Ranking search results with GPT-4o-mini...")
        ranked_results = await rank_search_results(search_text, collected_results, league)
        
        return {
            "success": True,
            "source": "azure_ai_search_hybrid",
            "query": query,
            "league": league,
            "results": [
                {
                    "id": result.get("id"),
                    "user_prompt": result.get("UserPrompt"),
                    "query": result.get("Query"),
                    "assistant_prompt": result.get("AssistantPrompt"),
                    "relevance": "high"
                }
                for result in ranked_results
            ],
            "count": len(ranked_results),
            "message": f"Found {len(ranked_results)} relevant historical queries using hybrid search and GPT-4o-mini ranking"
        }

    except Exception as e:
        logger.error(f"Error in recall_similar_db_queries tool: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to recall_similar_db_queries from history: {str(e)}",
            "query": query,
            "league": league
        } 