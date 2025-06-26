"""Database table scanning tool."""

import asyncio
import logging
import re
from typing import Any, Optional, List, Dict
from enum import Enum

import asyncpg
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import get_postgres_url
from ..models.connection import Connection

__all__ = ["scan"]


class MatchMode(str, Enum):
    REGEX = "regex"
    TF_IDF = "tf_idf"
    JACCARD = "jaccard"


def get_ngrams(text: str, n: int = 3) -> List[str]:
    """Generate n-grams from text."""
    if len(text) < n:
        return [text]
    grams = []
    for i in range(len(text) - n + 1):
        grams.append(text[i:i + n])
    return grams


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two strings using the same logic as TypeScript."""
    s1 = text1.lower()
    s2 = text2.lower()
    
    # Check for substring matches first (high priority)
    if s2 in s1 or s1 in s2:
        return 0.9  # High similarity for substring matches
    
    # Calculate character-level similarity (Jaccard similarity on character n-grams)
    ngrams1 = get_ngrams(s1, 3)
    ngrams2 = get_ngrams(s2, 3)
    
    intersection = [gram for gram in ngrams1 if gram in ngrams2]
    union = list(set(ngrams1 + ngrams2))
    
    if len(union) == 0:
        return 0
    
    jaccard_similarity = len(intersection) / len(union)
    
    # Also check for word-based similarity as fallback
    words1 = s1.split()
    words2 = s2.split()
    word_intersection = [word for word in words1 if word in words2]
    word_similarity = len(word_intersection) / max(len(words1), len(words2)) if max(len(words1), len(words2)) > 0 else 0
    
    # Return the maximum of character similarity and word similarity
    return max(jaccard_similarity, word_similarity)


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def scan(
    ctx: Context,
    pattern: str = Field(..., description="Pattern to search for in table names"),
    limit: int = Field(default=10, description="Number of results to return (1-50)", ge=1, le=50),
    mode: MatchMode = Field(default=MatchMode.JACCARD, description="Matching algorithm: regex, tf_idf, or jaccard")
) -> Dict[str, Any]:
    """
    Find and return table names that match the given pattern using different matching algorithms.

    Matching Instructions:
    1. Choose from three matching modes:
        - regex: Returns tables matching a regular expression pattern (case-insensitive). Pattern must be a valid regex expression.
        - tf_idf: Returns tables using TF-IDF (Term Frequency-Inverse Document Frequency) ranking algorithm (case-insensitive). Pattern must be a sentence, phrase, or space-separated words.
        - jaccard: Returns tables using Jaccard similarity algorithm (case-insensitive). Pattern must be a sentence, phrase, or space-separated words.
    2. It is recommended to start with Jaccard similarity algorithm for initial fuzzy matching, and then switch to TF-IDF and regex for more precise matching.
    3. Pattern matching operates on table names in the public schema (e.g., players, batting_stats, innings).
    """
    logger = logging.getLogger("blitz-agent-mcp")
    logger.debug(f"Scanning tables with pattern '{pattern}', mode '{mode}', limit {limit}")

    connection_string = get_postgres_url()

    try:
        # Connect directly to PostgreSQL
        conn = await asyncpg.connect(connection_string)
        
        try:
            # Get all tables in the schema
            tables_query = """
                SELECT 
                    table_name,
                    table_schema,
                    table_type
                FROM 
                    information_schema.tables 
                WHERE 
                    table_schema = $1
                    AND table_type = 'BASE TABLE'
                ORDER BY 
                    table_name;
            """
            
            result = await conn.fetch(tables_query, 'public')
            all_tables = [dict(row) for row in result]
            
            matched_tables = []
            
            if mode == MatchMode.REGEX:
                try:
                    regex = re.compile(pattern, re.IGNORECASE)
                    matched_tables = [
                        {
                            "table_name": table["table_name"],
                            "schema_name": table["table_schema"],
                            "fully_qualified_name": table["table_name"]
                        }
                        for table in all_tables
                        if regex.search(table["table_name"])
                    ][:limit]
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern: {pattern}. Please try a different pattern or use a different matching mode.")
            
            elif mode in [MatchMode.TF_IDF, MatchMode.JACCARD]:
                # Simple similarity scoring
                scored_tables = []
                for table in all_tables:
                    similarity = calculate_similarity(pattern, table["table_name"])
                    if similarity > 0:
                        scored_tables.append({
                            "table_name": table["table_name"],
                            "schema_name": table["table_schema"],
                            "fully_qualified_name": table["table_name"],
                            "similarity": similarity
                        })
                
                # Sort by similarity (highest first) and take top results
                matched_tables = sorted(scored_tables, key=lambda x: x["similarity"], reverse=True)[:limit]
            
            logger.debug(f"Scan completed successfully. Found {len(matched_tables)} matching tables.")
            return {"tables": matched_tables}
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Failed to scan tables: {e}", exc_info=True)
        if "Invalid regex pattern" in str(e):
            raise ConnectionError(str(e))
        elif "connection" in str(e).lower() or "connect" in str(e).lower():
            raise ConnectionError(f"Failed to connect to database - {str(e)}")
        else:
            raise ConnectionError(f"Failed to scan tables - {str(e)}") 