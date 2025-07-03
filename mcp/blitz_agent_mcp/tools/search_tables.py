"""Database table scanning tool."""

import asyncio
import logging
import re
import math
from typing import Any, Optional, List, Dict
from enum import Enum
from collections import Counter

import asyncpg
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import get_postgres_url
from ..models.connection import Connection

__all__ = ["search_tables"]

MAX_DATA_ROWS = 50


class SearchMode(str, Enum):
    JACCARD = "jaccard"
    JARO_WINKLER = "jaro_winkler"
    BM25 = "bm25"
    REGEX = "regex"


def get_ngrams(text: str, n: int = 3) -> List[str]:
    """Generate n-grams from text."""
    if len(text) < n:
        return [text]
    grams = []
    for i in range(len(text) - n + 1):
        grams.append(text[i:i + n])
    return grams


def jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between two strings using character n-grams."""
    s1 = text1.lower()
    s2 = text2.lower()
    
    # Check for substring matches first (high priority)
    if s2 in s1 or s1 in s2:
        return 0.9  # High similarity for substring matches
    
    # Calculate character-level similarity (Jaccard similarity on character n-grams)
    ngrams1 = set(get_ngrams(s1, 3))
    ngrams2 = set(get_ngrams(s2, 3))
    
    intersection = ngrams1.intersection(ngrams2)
    union = ngrams1.union(ngrams2)
    
    if len(union) == 0:
        return 0
    
    jaccard_sim = len(intersection) / len(union)
    
    # Also check for word-based similarity as fallback
    words1 = set(s1.split())
    words2 = set(s2.split())
    word_intersection = words1.intersection(words2)
    word_similarity = len(word_intersection) / max(len(words1), len(words2)) if max(len(words1), len(words2)) > 0 else 0
    
    # Return the maximum of character similarity and word similarity
    return max(jaccard_sim, word_similarity)


def jaro_winkler_similarity(s1: str, s2: str) -> float:
    """Calculate Jaro-Winkler similarity between two strings."""
    s1 = s1.lower()
    s2 = s2.lower()
    
    if s1 == s2:
        return 1.0
    
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0
    
    # Calculate the match window
    match_window = max(len1, len2) // 2 - 1
    if match_window < 0:
        match_window = 0
    
    # Initialize arrays to track matches
    s1_matches = [False] * len1
    s2_matches = [False] * len2
    
    matches = 0
    transpositions = 0
    
    # Find matches
    for i in range(len1):
        start = max(0, i - match_window)
        end = min(i + match_window + 1, len2)
        
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break
    
    if matches == 0:
        return 0.0
    
    # Count transpositions
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        
        while not s2_matches[k]:
            k += 1
        
        if s1[i] != s2[k]:
            transpositions += 1
        
        k += 1
    
    # Calculate Jaro similarity
    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3
    
    # Calculate Jaro-Winkler similarity
    prefix = 0
    for i in range(min(len1, len2, 4)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    
    return jaro + (0.1 * prefix * (1 - jaro))


def bm25_similarity(query: str, document: str) -> float:
    """Calculate BM25 similarity score between query and document."""
    # BM25 parameters
    k1 = 1.2
    b = 0.75
    
    query_terms = query.lower().split()
    doc_terms = document.lower().split()
    
    if not query_terms or not doc_terms:
        return 0.0
    
    # Calculate term frequencies
    doc_tf = Counter(doc_terms)
    doc_length = len(doc_terms)
    
    # For simplicity, assume average document length is 3 (typical table names are short)
    avg_doc_length = 3
    
    score = 0.0
    for term in query_terms:
        if term in doc_tf:
            tf = doc_tf[term]
            # For table name searching, assume each term appears in roughly 10% of documents (idf ≈ 2.3)
            idf = 2.3
            
            # BM25 formula
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avg_doc_length)))
    
    return min(score / len(query_terms), 1.0)  # Normalize to [0, 1]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def search_tables(
    ctx: Context,
    pattern: str = Field(..., description="Pattern to search for. "),
    mode: SearchMode = Field(SearchMode.BM25, description="The search mode to use."),
    limit: int = Field(10, description="Number of results to return.", ge=1, le=50),
    connection: Optional[Connection] = Field(default=None, description="The data source to search. If not provided, uses the configured PostgreSQL database."),
    league: str = Field(default=None, description="League to search (e.g., 'mlb', 'nba'). If not specified, uses default database."),
) -> Dict[str, Any]:
    """
    Find and return fully qualified table names that match the given pattern.

    Search Instructions:
    1. Determine the best search mode to use:
        - regex:
            * Returns tables matching a regular expression pattern
            * Pattern must be a valid regex expression
            * Case-sensitive
            * Use when you need precise table name matching
        - bm25:
            * Returns tables using BM25 (Best Match 25) ranking algorithm
            * Pattern must be a sentence, phrase, or space-separated words
            * Case-insensitive
            * Use when searching tables names with descriptive keywords
        - jaro_winkler:
            * Returns tables using Jaro-Winkler similarity algorithm
            * Pattern must be an existing table name.
            * Case-insensitive
            * Use to search for similar table names.
        - jaccard:
            * Returns tables using Jaccard similarity algorithm (n-gram based)
            * Pattern must be a sentence, phrase, or space-separated words
            * Case-insensitive
            * Use for fuzzy matching based on character overlap
    2. Search operates on fully-qualified table names (e.g., schema.table_name or database.schema.table_name).
    3. When search returns unexpected results, examine the returned tables and retry with a different pattern and/or search mode.
    4. Specify the league parameter to search tables in the appropriate database (mlb, nba, etc.)
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    try:
        # If no connection provided, use the configured PostgreSQL URL for the specified league
        if connection is None:
            postgres_url = get_postgres_url(league)
            if not postgres_url:
                league_info = f" for league '{league}'" if league else ""
                raise ConnectionError(f"No connection provided and PostgreSQL configuration{league_info} is incomplete. Please provide a connection or configure PostgreSQL settings.")
            connection = Connection(url=postgres_url)
            if league:
                logger.debug(f"Using configured PostgreSQL connection for league: {league}")
            else:
                logger.debug("Using configured PostgreSQL connection (default)")
        
        url_map = await _get_context_field("url_map", ctx)
        db = await connection.connect(url_map=url_map)
        result = await db.search_tables(pattern=pattern, limit=limit, mode=mode)
        return {
            "pattern": pattern,
            "mode": mode.value,
            "limit": limit,
            "league": league,
            "tables": result
        }
    except Exception as e:
        raise RuntimeError(f"Table search failed: {str(e)}") 