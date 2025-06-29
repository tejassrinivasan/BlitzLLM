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

from config import MAX_DATA_ROWS
from utils import get_azure_chat_client, serialize_response

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
) -> Dict[str, Any]:
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
    if not query:
        raise ValueError("query is required")
    
    # Handle cases where results or description might be missing due to MCP adapter issues
    if not results or results == "[]" or results == []:
        return {
            "success": False,
            "error": "No results provided for validation",
            "query": query,
            "description": description,
            "message": "Cannot validate query without results data."
        }
    
    # Use fallback description if missing
    if not description or description == "Query validation":
        description = f"SQL query validation for: {query[:100]}..."
    
    try:
        chat_client = get_azure_chat_client()
        
        # Read the schema file for the specified league
        schema_content = _read_schema_file(league)
        schema_section = ""
        if schema_content:
            schema_section = f"""
        DATABASE SCHEMA DOCUMENTATION ({league.upper()}):
        {schema_content}
        
        """
        else:
            logging.warning(f"Could not load schema for league: {league}")
        
        # Just pass the raw results to the AI without parsing, but truncate if too long
        query_results = results
        if len(query_results) > 5000:
            query_results = query_results[:5000] + "... (TRUNCATED)"
        
        analysis_prompt = f"""
        QUERY VALIDATION AND ANALYSIS

        USER'S ORIGINAL QUESTION:
        {user_question or 'Not provided'}

        QUERY DESCRIPTION:
        {description}

        SQL QUERY EXECUTED:
        {query}

        QUERY RESULTS:
        {query_results}

        ADDITIONAL CONTEXT:
        {context or 'None provided'}

        {schema_section}

        ## CRITICAL VALIDATION FRAMEWORK:

        ### 1. COMPLETENESS ANALYSIS:
        - If question asks for "all teams", "each team", or similar comprehensive language, ensure all teams are included
        - If question is about league-wide stats, ensure no arbitrary LIMIT or ORDER BY is preventing complete results
        - Check if the scope of results matches the scope of the question

        ### 2. LOGICAL CONSISTENCY CHECKS:
        - **Home/Away Logic**: For queries involving home vs away performance, verify correct team assignment
        - **Mathematical Integrity**: Verify calculations make sense and aggregations use appropriate grouping
        - **Sports Logic**: Ensure results align with sports reality (realistic stat ranges)

        ### 3. DATA QUALITY ASSESSMENT:
        - Are numbers realistic for the sport and time period?
            - For example, there are 162 games and 30 teams in an MLB season per team, so 2430 total games are played in an MLB season (for MLB we have 2012-2025 so around 30k games)
        - Do aggregate values seem plausible?
        - Are there any suspicious patterns or outliers?
                
        ### 4. QUESTION ALIGNMENT:
        - Does the query structure actually answer what was asked?
        - Are the right metrics being calculated?
        - Is the time period correct?

        ### 5. SCHEMA COMPLIANCE:
        - Does the query follow the database schema rules and interpretation guidelines provided above?
        - Are the correct tables and joins being used based on the schema documentation?
        - Are any schema-specific constraints or limitations being violated?

        Please analyze these query results and provide a comprehensive validation as a JSON object with the following schema:
        {{
            "isValid": boolean,
            "confidenceResultsAreCorrect": number,
            "answersUserQuestion": boolean,
            "issues": string[],
            "insights": string[],
            "recommendations": string[],
            "summary": string,
            "interpretation": string
        }}
        """
        
        system_prompt = f"You are an expert data analyst specializing in sports statistics and SQL query validation. Your job is to analyze query results and determine if they make sense, are complete, and properly answer the user's question. Use the provided database schema documentation to ensure queries follow the correct interpretation rules and data model constraints. Be thorough but concise in your analysis. **TODAY'S DATE:** {datetime.now().strftime('%Y-%m-%d')}. You must respond with only a valid JSON object."

        response = chat_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        
        validation_result = json.loads(response.choices[0].message.content)
        
        return {
            "success": True,
            "validation": validation_result,
            "metadata": {
                "analysis_timestamp": datetime.now().isoformat(),
                "query_analyzed": query,
                "description_analyzed": description,
                "user_question": user_question,
                "league": league,
                "schema_loaded": schema_content is not None
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Validation failed: {str(e)}",
            "query": query,
            "description": description,
            "message": "Unable to validate query results. The query executed but validation analysis failed."
        } 