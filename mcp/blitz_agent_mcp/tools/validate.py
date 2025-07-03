"""AI-powered validation of query results tool."""

import asyncio
import logging
import json
import os
from typing import Any, Optional, Union, List, Dict
from datetime import datetime
from pathlib import Path

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import MAX_DATA_ROWS
from ..utils import get_azure_chat_client, serialize_response

__all__ = ["validate"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


def _read_schema_file(league: str) -> Optional[str]:
    """
    Read the schema file for the specified league.
    
    Args:
        league: The league name (e.g., 'mlb', 'nba')
        
    Returns:
        The content of the schema file, or None if not found
    """
    if not league:
        return None
        
    # Normalize league name to lowercase
    league = league.lower()
    
    # Map league names to schema file names
    schema_files = {
        'mlb': 'mlb-schema.md',
        'nba': 'nba-schema.md'
    }
    
    if league not in schema_files:
        return None
    
    # Get the path to the schema file
    current_dir = Path(__file__).parent.parent
    schema_path = current_dir / "schemas" / schema_files[league]
    
    try:
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            logging.warning(f"Schema file not found: {schema_path}")
            return None
    except Exception as e:
        logging.error(f"Error reading schema file {schema_path}: {e}")
        return None


async def validate(
    ctx: Context,
    query: str = Field(..., description="SQL query that was executed"),
    results: Any = Field(..., description="The ACTUAL QUERY RESULTS DATA as JSON string (not a summary) - should be the raw data returned from the SQL query"),
    description: str = Field(..., description="Description of what the query was supposed to do"),
    user_question: str = Field(..., description="Original user question"),
    context: str = Field(..., description="Additional context"),
    league: str = Field(..., description="The league being queried (e.g., 'mlb', 'nba') - this will be used to attach the appropriate database schema for better validation")
) -> dict[str, Any]:
    """
    Validate and analyze query results using AI to determine if the results make sense and 
    properly answer the user's question. This tool provides intelligent analysis of whether 
    the query results are correct, relevant, and complete.

    Validation Instructions:
    1. Provide the executed SQL query and its ACTUAL RESULTS DATA (not a summary)
    2. The results parameter must contain the raw JSON data returned from the query
    3. Specify the league (mlb/nba) to include relevant database schema context
    4. Optionally include the original user question for better context
    5. The AI will analyze completeness, logical consistency, and sports realism using league-specific schema knowledge
    6. Returns structured validation with issues, insights, and recommendations

    IMPORTANT: The 'results' parameter should contain the actual data rows returned by the SQL query 
    in JSON format, NOT a summary or description of the results.
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    try:
        # Prepare the validation prompt with schema context
        # Read the schema file for the specified league
        schema_content = _read_schema_file(league)
        
        schema_context = ""
        if schema_content:
            schema_context = f"""
DATABASE SCHEMA DOCUMENTATION ({league.upper()}):
{schema_content}

"""
        else:
            logging.warning(f"Could not load schema for league: {league}")
        
        # Convert results to string if needed
        if not isinstance(results, str):
            results_str = json.dumps(results, indent=2, default=str)
        else:
            results_str = results
        
        validation_prompt = f"""
You are an expert database analyst specializing in sports data validation. Please analyze the following SQL query execution and its results to determine if they properly answer the user's question.

{schema_context}

ORIGINAL USER QUESTION:
{user_question}

SQL QUERY EXECUTED:
{query}

QUERY DESCRIPTION:
{description}

ACTUAL QUERY RESULTS:
{results_str}

ADDITIONAL CONTEXT:
{context}

Please provide a comprehensive validation analysis covering:

1. **Result Correctness**: Do the results make logical sense for the query?
2. **Data Completeness**: Are there missing or unexpected data points?
3. **Query Appropriateness**: Does the SQL query properly address the user's question?
4. **Sports Logic Validation**: Do the results align with expected sports statistics and rules?
5. **Potential Issues**: Any red flags, anomalies, or concerns?
6. **Recommendations**: Suggestions for improvement if needed

Focus particularly on:
- If question is about league-wide stats, ensure no arbitrary LIMIT or ORDER BY is preventing complete results
- Verify date ranges and filters make sense for the sport's calendar
- Check if player/team names are correctly matched
- Validate statistical ranges are realistic for the sport
- Ensure aggregations and calculations are appropriate

Provide your analysis as a structured JSON response with the following format:
{{
    "validation_score": <float between 0.0 and 1.0>,
    "is_correct": <boolean>,
    "confidence": <float between 0.0 and 1.0>,
    "issues_found": [<list of issues>],
    "insights": [<list of insights>],
    "recommendations": [<list of recommendations>],
    "summary": "<brief overall assessment>"
}}
"""
        
        # Make the API call to Azure OpenAI
        azure_client = httpx.AsyncClient()
        try:
            response = await azure_client.post(
                f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/gpt-4o-mini/chat/completions?api-version={AZURE_OPENAI_API_VERSION}",
                headers={
                    "api-key": AZURE_OPENAI_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "messages": [
                        {
                            "role": "user",
                            "content": validation_prompt
                        }
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.1
                },
                timeout=30.0
            )
            response.raise_for_status()
            ai_response = response.json()
            
            # Extract the validation analysis
            validation_text = ai_response["choices"][0]["message"]["content"]
            
            # Try to parse as JSON
            try:
                validation_result = json.loads(validation_text)
            except json.JSONDecodeError:
                # If not valid JSON, create a structured response
                validation_result = {
                    "validation_score": 0.5,
                    "is_correct": None,
                    "confidence": 0.3,
                    "issues_found": ["Unable to parse AI validation response as JSON"],
                    "insights": [],
                    "recommendations": ["Manual review recommended"],
                    "summary": validation_text[:500] + "..." if len(validation_text) > 500 else validation_text
                }
            
            return {
                "success": True,
                "query": query,
                "league": league,
                "validation": validation_result,
                "metadata": {
                    "user_question": user_question,
                    "description": description,
                    "context": context,
                    "results_length": len(results_str),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        finally:
            await azure_client.aclose()
            
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "league": league,
            "timestamp": datetime.now().isoformat()
        } 