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

from ..config import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY
from ..utils import get_azure_chat_client, serialize_response

logger = logging.getLogger(__name__)

__all__ = ["recall_similar_db_queries"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def rank_search_results(query_text: str, search_results: List[Any], league: str) -> List[Any]:
    """Rank search results using GPT-4o-mini via Azure OpenAI."""
    try:
        # If no results to rank, return empty list
        if not search_results:
            return []
            
        # Format the search results for ranking
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                "id": result.get("id", ""),
                "prompt": result.get("UserPrompt", "")
            })

        logger.info(f"Ranking {len(formatted_results)} search results for query: {query_text}")

        chat_client = get_azure_chat_client()
        
        # Updated prompt to be less restrictive and more inclusive
        system_prompt = f"""You are an expert on {league.upper()} and PostgreSQL. Your job is to identify which questions from the search results are similar to the user's question in terms of meaning, intent, or would require similar data/analysis.

Be inclusive - if a question involves similar players, statistics, timeframes, or analytical approaches, it's likely relevant. For sports queries, questions about the same players or similar statistical analysis should generally be considered relevant.

Return a JSON object with a single key 'documentIds' containing a list of the relevant document IDs in order of relevance (most relevant first)."""
        
        human_prompt = f"""USER QUESTION:
{query_text}

SEARCH RESULTS:
{json.dumps(formatted_results, indent=2)}

Return document IDs for questions that are similar or would help answer the user's question. Be generous in your relevance assessment - if there's any connection in terms of players, statistics, or analytical approach, include it."""

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
            logger.info(f"GPT-4o-mini ranked results: {len(document_ids)} documents selected")
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to decode JSON from model response: {e}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            # Fallback to returning top search results
            return search_results[:10]

        # Create a mapping of document ID to full document
        doc_map = {doc.get("id", ""): doc for doc in search_results}

        # Return ranked results in order
        ranked_results = [doc_map[doc_id] for doc_id in document_ids if doc_id in doc_map]
        
        logger.info(f"Final ranked results: {len(ranked_results)} documents")
        return ranked_results

    except Exception as error:
        logger.error(f'Error ranking search results: {error}')
        # Return original results if ranking fails
        return search_results[:10]


async def recall_similar_db_queries(
    ctx: Context,
    query_description: str = Field(..., description="Description of what the query does"),
    league: str = Field("mlb", description="League to search within"),
) -> dict[str, Any]:
    """
    Retrieve most relevant historical queries using Azure AI Search hybrid search and GPT-4o-mini reranking.

    ALWAYS RECALL PREVIOUS QUERIES BEFORE WRITING QUERIES TO PREVENT ERRORS/SAVING TIME. NEVER SKIP THIS STEP.

    Instructions:
    1. Uses hybrid search on Azure AI Search index to find similar queries that have been answered in the past and are most relevant to the user's current question
    2. Reranks results using GPT-4o-mini for relevance
    3. Returns the most relevant historical queries for recall_similar_db_queries
    """
    if not query_description:
        raise ValueError("query_description is required")
    
    try:
        endpoint = AZURE_SEARCH_ENDPOINT
        api_key = AZURE_SEARCH_KEY
        
        index_name = f"blitz-{league.lower()}-index"
        
        logger.info(f"Using search index: {index_name} for league: {league}")

        if not endpoint or not api_key:
            logger.warning(f"Azure Search credentials not configured. endpoint: {bool(endpoint)}, api_key: {bool(api_key)}")
            return {
                "success": False,
                "error": "Azure Search credentials not configured. Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY environment variables or configure them in config.json",
                "query": query_description,
                "league": league,
                "fallback_suggestion": "You can continue without historical context, but recall_similar_db_queries from previous queries will not be available."
            }

        # Create SearchClient
        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key)
        )
        
        logger.info(f"Performing hybrid search on index: {index_name}...")
        
        # Perform hybrid search
        results = search_client.search(
            query_description,
            select=["id", "UserPrompt", "Query"],
            search_mode='any',
            query_type='semantic',
            semantic_configuration_name='my-semantic-config',
            top=20
        )
        
        # Collect results for processing
        collected_results = []
        for result in results:
            collected_results.append(result)
        
        logger.info(f"Azure Search returned {len(collected_results)} results")
        
        if not collected_results:
            return {
                "success": False,
                "error": "No results found in search index",
                "query": query_description,
                "league": league
            }
        
        # Log some details about the search results for debugging
        for i, result in enumerate(collected_results[:3]):  # Log first 3 results
            logger.info(f"Search result {i+1}: ID={result.get('id', 'N/A')}, Score={getattr(result, '@search.score', 'N/A')}")
        
        # Rank the results using GPT-4o-mini
        logger.info("Ranking search results with GPT-4o-mini...")
        ranked_results = await rank_search_results(query_description, collected_results, league)
        
        logger.info(f"Returning {len(ranked_results)} final results to user")

        return {
            "success": True,
            "source": "azure_ai_search_hybrid",
            "query": query_description,
            "league": league,
            "results": [
                {
                    "id": result.get("id"),
                    "user_prompt": result.get("UserPrompt"),
                    "query": result.get("Query"),
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
            "query": query_description,
            "league": league
        } 