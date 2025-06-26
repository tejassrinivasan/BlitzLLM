"""Connection model for database connections."""

import asyncio
import asyncpg
from dataclasses import dataclass
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from sqlalchemy.engine.url import make_url
from urllib.parse import quote_plus

# Query timeout in seconds (default 60 seconds)
QUERY_TIMEOUT = 60


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
    
    async def scan_tables(self, pattern: str, limit: int = 10, mode: str = "tf_idf") -> list:
        """Scan for tables matching a pattern."""
        conn = await asyncpg.connect(self.connection_string)
        try:
            query = """
                SELECT schemaname || '.' || tablename as full_name
                FROM pg_tables 
                WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                AND (schemaname || '.' || tablename) ILIKE $1
                ORDER BY schemaname, tablename
                LIMIT $2;
            """
            results = await conn.fetch(query, f'%{pattern}%', limit)
            return [row['full_name'] for row in results]
        finally:
            await conn.close() 