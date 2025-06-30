"""Connection model for database connections."""

import asyncio
import asyncpg
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
from sqlalchemy.engine.url import make_url
from urllib.parse import quote_plus

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

from .database import MatchMode

# Query timeout in seconds (default 60 seconds)
QUERY_TIMEOUT = 60


def tokenize(text: str) -> List[str]:
    """Tokenize text by splitting on common separators and converting to lowercase."""
    import string
    # Replace common separators with spaces
    for char in ['_', '-', '.', ':', ';']:
        text = text.replace(char, ' ')
    # Remove punctuation and split
    text = ''.join(char if char not in string.punctuation else ' ' for char in text)
    return [token.lower() for token in text.split() if token]


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


@dataclass
class ConnectionResult:
    """Result of a connection test."""
    connected: bool
    message: str


class Connection(BaseModel):
    """Enhanced data source with smart path resolution."""
    
    url: str = Field(..., description="URL of the data source with protocol.")
    
    def _encode_password_in_url(self, url: str) -> str:
        """Ensure password in URL is properly encoded."""
        try:
            parsed_url = make_url(url)
            if parsed_url.password:
                # Reconstruct URL with encoded password
                encoded_password = quote_plus(str(parsed_url.password))
                new_url = f"{parsed_url.drivername}://{parsed_url.username}:{encoded_password}@{parsed_url.host}"
                if parsed_url.port:
                    new_url += f":{parsed_url.port}"
                new_url += f"/{parsed_url.database}"
                if parsed_url.query:
                    query_string = "&".join([f"{k}={v}" for k, v in parsed_url.query.items()])
                    new_url += f"?{query_string}"
                return new_url
            return url
        except Exception:
            # If parsing fails, return original URL
            return url
    
    async def connect(self, url_map: Optional[Dict] = None) -> 'DatabaseConnection':
        """Connect to the database and return a connection object."""
        encoded_url = self._encode_password_in_url(self.url)
        return DatabaseConnection(encoded_url)
    
    async def test_connection(self) -> ConnectionResult:
        """Test the database connection."""
        try:
            encoded_url = self._encode_password_in_url(self.url)
            conn = await asyncpg.connect(encoded_url)
            await conn.fetchval("SELECT 1")
            await conn.close()
            return ConnectionResult(connected=True, message="Connection successful")
        except Exception as e:
            return ConnectionResult(connected=False, message=str(e))


class DatabaseConnection:
    """Database connection wrapper for query operations."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    async def test_connection(self) -> ConnectionResult:
        """Test the database connection."""
        try:
            conn = await asyncpg.connect(self.connection_string)
            await conn.fetchval("SELECT 1")
            await conn.close()
            return ConnectionResult(connected=True, message="Connection successful")
        except Exception as e:
            return ConnectionResult(connected=False, message=str(e))
    
    async def query(self, code: str) -> Dict[str, Any]:
        """Execute a SQL query with timeout."""
        conn = await asyncpg.connect(self.connection_string)
        try:
            # Execute query with timeout
            results = await asyncio.wait_for(
                conn.fetch(code), 
                timeout=QUERY_TIMEOUT
            )
            rows = []
            for row in results:
                row_dict = {}
                for key, value in row.items():
                    if isinstance(value, (int, float, str, bool, type(None))):
                        row_dict[key] = value
                    else:
                        row_dict[key] = str(value)
                rows.append(row_dict)
            
            return {
                "data": rows,
                "row_count": len(rows),
                "columns": list(rows[0].keys()) if rows else []
            }
        except asyncio.TimeoutError:
            raise RuntimeError(f"Query timed out after {QUERY_TIMEOUT} seconds. Please simplify your query or add more specific WHERE conditions to reduce the data being processed.")
        finally:
            await conn.close()
    
    async def inspect_table(self, table_path: str) -> Dict[str, Any]:
        """Inspect table structure."""
        conn = await asyncpg.connect(self.connection_string)
        try:
            # Remove schema prefix if present - just use table name, assume public schema
            if '.' in table_path:
                table_name = table_path.split('.', 1)[1]
            else:
                table_name = table_path
            
            # Get column information from public schema
            columns_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position;
            """
            columns = await conn.fetch(columns_query, table_name)
            
            return {
                "table": table_name,
                "columns": [
                    {
                        "name": col['column_name'],
                        "type": col['data_type'],
                        "nullable": col['is_nullable'] == 'YES',
                        "default": col['column_default'],
                        "max_length": col['character_maximum_length']
                    }
                    for col in columns
                ]
            }
        finally:
            await conn.close()
    
    async def sample_table(self, table_path: str, n: int = 5) -> Dict[str, Any]:
        """Sample data from a table."""
        conn = await asyncpg.connect(self.connection_string)
        try:
            # Remove schema prefix if present - just use table name
            if '.' in table_path:
                table_name = table_path.split('.', 1)[1]
            else:
                table_name = table_path
                
            query = f'SELECT * FROM "{table_name}" LIMIT {n}'
            results = await conn.fetch(query)
            
            rows = []
            for row in results:
                row_dict = {}
                for key, value in row.items():
                    if isinstance(value, (int, float, str, bool, type(None))):
                        row_dict[key] = value
                    else:
                        row_dict[key] = str(value)
                rows.append(row_dict)
            
            return {
                "table": table_name,
                "sample_size": len(rows),
                "data": rows,
                "columns": list(rows[0].keys()) if rows else []
            }
        finally:
            await conn.close()
    
    async def search_tables(self, pattern: str, limit: int = 10, mode: MatchMode = MatchMode.BM25) -> list:
        """Search for tables matching a pattern using various algorithms."""
        conn = await asyncpg.connect(self.connection_string)
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
                    table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                ORDER BY 
                    table_name;
            """
            
            result = await conn.fetch(tables_query)
            all_tables = [dict(row) for row in result]
            table_names = [table["table_name"] for table in all_tables]
            
            # Use the appropriate search method
            if mode == MatchMode.REGEX:
                matched_names = self._search_tables_regex(table_names, pattern, limit)
            elif mode == MatchMode.JARO_WINKLER:
                matched_names = self._search_tables_jaro_winkler(table_names, pattern, limit)
            elif mode == MatchMode.BM25:
                matched_names = self._search_tables_bm25(table_names, pattern, limit)
            elif mode == MatchMode.JACCARD:
                matched_names = self._search_tables_jaccard(table_names, pattern, limit)
            else:
                matched_names = []
            
            # Convert back to the expected format
            matched_tables = []
            for name in matched_names:
                # Find the original table info
                table_info = next((t for t in all_tables if t["table_name"] == name), None)
                if table_info:
                    matched_tables.append({
                        "table_name": table_info["table_name"],
                        "schema_name": table_info["table_schema"],
                        "fully_qualified_name": f"{table_info['table_schema']}.{table_info['table_name']}"
                    })
            
            return matched_tables
            
        finally:
            await conn.close()
    
    def _search_tables_regex(self, table_names: List[str], pattern: str, limit: int) -> List[str]:
        """Search tables using regex pattern."""
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            return [name for name in table_names if regex.search(name)][:limit]
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {pattern}. Please try a different pattern or use a different search mode.")

    def _search_tables_jaro_winkler(self, table_names: List[str], pattern: str, limit: int) -> List[str]:
        """Search tables using Jaro-Winkler similarity."""
        tokenized_pattern = " ".join(tokenize(pattern))
        similarities = [
            (name, jaro_winkler_similarity(" ".join(tokenize(name)), tokenized_pattern)) for name in table_names
        ]
        return [name for name, _ in sorted(similarities, key=lambda x: x[1], reverse=True)][:limit]

    def _search_tables_bm25(self, table_names: List[str], pattern: str, limit: int) -> List[str]:
        """Search tables using BM25 ranking algorithm."""
        if BM25Okapi is None:
            # Fallback to simple token matching if BM25 is not available
            return self._search_tables_simple_token_match(table_names, pattern, limit)
            
        query_tokens = tokenize(pattern)
        if not query_tokens:
            return []

        valid_tables = [(name, tokenize(name)) for name in table_names]
        valid_tables = [(name, tokens) for name, tokens in valid_tables if tokens]
        if not valid_tables:
            return []

        # Create corpus of tokenized table names
        corpus = [tokens for _, tokens in valid_tables]

        # Initialize BM25 with the corpus
        bm25 = BM25Okapi(corpus)

        # Get BM25 scores for the query
        scores = bm25.get_scores(query_tokens)

        return [
            name
            for name, _ in sorted(
                zip([n for n, _ in valid_tables], scores, strict=False), key=lambda x: x[1], reverse=True
            )
        ][:limit]

    def _search_tables_jaccard(self, table_names: List[str], pattern: str, limit: int) -> List[str]:
        """Search tables using Jaccard similarity."""
        similarities = []
        for name in table_names:
            similarity = self._jaccard_similarity(pattern, name)
            if similarity > 0:
                similarities.append((name, similarity))
        
        return [name for name, _ in sorted(similarities, key=lambda x: x[1], reverse=True)][:limit]

    def _search_tables_simple_token_match(self, table_names: List[str], pattern: str, limit: int) -> List[str]:
        """Fallback simple token matching when BM25 is not available."""
        query_tokens = set(tokenize(pattern))
        if not query_tokens:
            return []
        
        scores = []
        for name in table_names:
            name_tokens = set(tokenize(name))
            if name_tokens:
                # Simple overlap score
                overlap = len(query_tokens.intersection(name_tokens))
                if overlap > 0:
                    score = overlap / len(query_tokens.union(name_tokens))
                    scores.append((name, score))
        
        return [name for name, _ in sorted(scores, key=lambda x: x[1], reverse=True)][:limit]

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two strings using character n-grams."""
        s1 = text1.lower()
        s2 = text2.lower()
        
        # Check for substring matches first (high priority)
        if s2 in s1 or s1 in s2:
            return 0.9  # High similarity for substring matches
        
        # Calculate character-level similarity (Jaccard similarity on character n-grams)
        ngrams1 = set(self._get_ngrams(s1, 3))
        ngrams2 = set(self._get_ngrams(s2, 3))
        
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

    def _get_ngrams(self, text: str, n: int = 3) -> List[str]:
        """Generate n-grams from text."""
        if len(text) < n:
            return [text]
        grams = []
        for i in range(len(text) - n + 1):
            grams.append(text[i:i + n])
        return grams 