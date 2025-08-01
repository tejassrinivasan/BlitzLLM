"""
Tools setup module - defines all MCP tools with proper decorators
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

from ..config import MAX_DATA_ROWS, get_postgres_url
from ..models.table import Table
from ..models.connection import Connection
from ..utils import serialize_response



def setup_tools(mcp: FastMCP):
    """Set up all MCP tools with proper decorators"""
    
    @mcp.tool()
    async def inspect(
        ctx: Context,
        table: str = Field(..., description="The database table name to inspect (e.g., 'pitchingstatsgame', 'battingstatsgame')."),
        league: str = Field(None, description="League to inspect (e.g., 'mlb', 'nba'). If not specified, uses default database."),
    ) -> Dict[str, Any]:
        """
        Inspect the structure of a database table.

        Inspection Instructions:
        1. Use this tool to understand table structure like column names, data types, and constraints
        2. Inspecting tables helps understand the structure of the data
        3. Always inspect tables before writing queries to understand their structure and prevent errors
        4. Simply provide the table name as a string (e.g., "pitchingstatsgame", "battingstatsgame")
        5. Specify the league parameter to inspect tables in the appropriate database (mlb, nba, etc.)
        """
        logger = logging.getLogger("blitz-agent-mcp")
        
        try:
            # Create Table object from string input
            table_obj = Table(table_name=table)
            
            # If no connection provided in the table, use the configured PostgreSQL URL for the specified league
            if table_obj.connection is None:
                postgres_url = get_postgres_url(league)
                if not postgres_url:
                    league_info = f" for league '{league}'" if league else ""
                    raise ConnectionError(f"No connection provided and PostgreSQL configuration{league_info} is incomplete. Please provide a connection or configure PostgreSQL settings.")
                table_obj.connection = Connection(url=postgres_url)
                if league:
                    logger.debug(f"Using configured PostgreSQL connection for league: {league}")
                else:
                    logger.debug("Using configured PostgreSQL connection (default)")
            
            db = await table_obj.connection.connect()
            return serialize_response(await db.inspect_table(table_obj.table_name))
        except Exception as e:
            raise ConnectionError(f"Failed to inspect {table_obj.connection.url if 'table_obj' in locals() else 'unknown'} table {table_obj.table_name if 'table_obj' in locals() else table}: {str(e)}")

    @mcp.tool()
    async def sample(
        ctx: Context,
        table: str = Field(..., description="The database table name to sample (e.g., 'pitchingstatsgame', 'battingstatsgame')."),
        limit: int = Field(MAX_DATA_ROWS, description="Number of rows to sample"),
        league: str = Field(None, description="League to sample from (e.g., 'mlb', 'nba'). If not specified, uses default database."),
    ) -> Dict[str, Any]:
        """
        Sample data from a database table.

        Sampling Instructions:
        1. Use this tool to see actual data from tables
        2. Start with small samples (default limit) to understand data structure
        3. This helps you understand what the actual data looks like before writing complex queries
        4. Specify the league parameter to sample from the appropriate database (mlb, nba, etc.)
        """
        logger = logging.getLogger("blitz-agent-mcp")
        
        try:
            # Create Table object from string input
            table_obj = Table(table_name=table)
            
            # If no connection provided, use the configured PostgreSQL URL for the specified league
            if table_obj.connection is None:
                postgres_url = get_postgres_url(league)
                if not postgres_url:
                    league_info = f" for league '{league}'" if league else ""
                    raise ConnectionError(f"No connection provided and PostgreSQL configuration{league_info} is incomplete. Please provide a connection or configure PostgreSQL settings.")
                table_obj.connection = Connection(url=postgres_url)
                if league:
                    logger.debug(f"Using configured PostgreSQL connection for league: {league}")
                else:
                    logger.debug("Using configured PostgreSQL connection (default)")
            
            db = await table_obj.connection.connect()
            return serialize_response(await db.sample_table(table_obj.table_name, limit))
        except Exception as e:
            raise ConnectionError(f"Failed to sample {table_obj.connection.url if 'table_obj' in locals() else 'unknown'} table {table_obj.table_name if 'table_obj' in locals() else table}: {str(e)}")

    @mcp.tool()
    async def query(
        ctx: Context,
        sql: str = Field(..., description="The SQL query to execute"),
        league: str = Field(None, description="League to query (e.g., 'mlb', 'nba'). If not specified, uses default database."),
    ) -> Dict[str, Any]:
        """
        Execute a SQL query against the database.

        Query Instructions:
        1. Always inspect tables first to understand their structure
        2. Use specific column names instead of SELECT *
        3. Add appropriate WHERE clauses to filter data
        4. Consider using LIMIT to prevent large result sets
        5. Specify the league parameter to query the appropriate database (mlb, nba, etc.)
        """
        logger = logging.getLogger("blitz-agent-mcp")
        
        try:
            # Use the configured PostgreSQL URL for the specified league
            postgres_url = get_postgres_url(league)
            if not postgres_url:
                league_info = f" for league '{league}'" if league else ""
                raise ConnectionError(f"PostgreSQL configuration{league_info} is incomplete. Please configure PostgreSQL settings.")
            
            connection = Connection(url=postgres_url)
            if league:
                logger.debug(f"Using configured PostgreSQL connection for league: {league}")
            else:
                logger.debug("Using configured PostgreSQL connection (default)")
            
            db = await connection.connect()
            return serialize_response(await db.execute_query(sql))
        except Exception as e:
            raise ConnectionError(f"Failed to execute query: {str(e)}")

    @mcp.tool()
    async def search_tables(
        ctx: Context,
        query: str = Field(..., description="Search term or pattern to find relevant tables"),
        league: str = Field(None, description="League to search in (e.g., 'mlb', 'nba'). If not specified, searches default database."),
        max_results: int = Field(10, description="Maximum number of results to return")
    ) -> Dict[str, Any]:
        """
        Search for database tables by name or description.

        Search Instructions:
        1. Use this tool to find relevant tables for your data needs
        2. Search by keywords related to the data you're looking for
        3. This returns table names and descriptions to help you understand what data is available
        4. Specify the league parameter to search in the appropriate database (mlb, nba, etc.)
        """
        from . import search_tables as search_tables_module
        from ..models.connection import Connection
        
        try:
            # Handle database connection based on league
            connection = None
            if league:
                postgres_url = get_postgres_url(league)
                if postgres_url:
                    connection = Connection(url=postgres_url)
            
            # Call the original search_tables function with correct parameters
            # Original function expects: pattern, mode, limit, connection, league
            from .search_tables import SearchMode
            result = await search_tables_module.search_tables(
                ctx=ctx,
                pattern=query,
                mode=SearchMode.BM25,
                limit=max_results,
                connection=connection,
                league=league
            )
            return result
        except Exception as e:
            return {"error": f"Table search failed: {str(e)}", "query": query, "league": league}

    @mcp.tool()
    async def test(
        ctx: Context,
        league: str = Field(None, description="League to test connection for (e.g., 'mlb', 'nba'). If not specified, tests default database."),
    ) -> Dict[str, Any]:
        """
        Test the database connection.

        Test Instructions:
        1. Use this tool to verify that the database connection is working
        2. This is useful for troubleshooting connection issues
        3. Specify the league parameter to test the appropriate database connection (mlb, nba, etc.)
        """
        logger = logging.getLogger("blitz-agent-mcp")
        
        try:
            postgres_url = get_postgres_url(league)
            if not postgres_url:
                league_info = f" for league '{league}'" if league else ""
                raise ConnectionError(f"PostgreSQL configuration{league_info} is incomplete. Please configure PostgreSQL settings.")
            
            connection = Connection(url=postgres_url)
            if league:
                logger.debug(f"Testing configured PostgreSQL connection for league: {league}")
            else:
                logger.debug("Testing configured PostgreSQL connection (default)")
            
            result = await connection.test_connection()
            # Convert ConnectionResult to dictionary
            return {
                "connected": result.connected,
                "message": result.message,
                "league": league,
                "success": result.connected
            }
        except Exception as e:
            raise ConnectionError(f"Connection test failed: {str(e)}")

    # Import and set up other tools
    from . import recall, db_docs, validate, upload, graph, linear_regression, betting

    @mcp.tool()
    async def recall_similar_db_queries(
        ctx: Context,
        query_text: str = Field(..., description="Natural language description of what you want to query"),
        league: str = Field("mlb", description="League to search for similar queries (mlb, nba, etc.)"),
        limit: int = Field(5, description="Maximum number of similar queries to return")
    ) -> Dict[str, Any]:
        """
        Find similar database queries based on natural language description.
        """
        result = await recall.recall_similar_db_queries(ctx, query_text, league, limit)
        return {"queries": result} if isinstance(result, list) else result

    @mcp.tool()
    async def get_database_documentation(
        ctx: Context,
        league: str = Field("mlb", description="League to get documentation for (mlb, nba, etc.)")
    ) -> Dict[str, Any]:
        """
        Get comprehensive database documentation for the specified league.
        """
        result = await db_docs.get_database_documentation(ctx, league)
        return {"documentation": result} if isinstance(result, str) else result

    @mcp.tool()
    async def validate(
        ctx: Context,
        sql: str = Field(..., description="SQL query to validate"),
        league: str = Field("mlb", description="League to validate against (mlb, nba, etc.)")
    ) -> Dict[str, Any]:
        """
        Validate a SQL query without executing it.
        """
        return await validate.validate(ctx, sql, league)

    @mcp.tool()
    async def upload(
        ctx: Context,
        query_text: str = Field(..., description="Natural language description of the query"),
        sql_query: str = Field(..., description="The SQL query"),
        league: str = Field("mlb", description="League this query is for (mlb, nba, etc.)")
    ) -> Dict[str, Any]:
        """
        Upload and store a query for future similarity matching.
        """
        return await upload.upload(ctx, query_text, sql_query, league)

    @mcp.tool()
    async def generate_graph(
        ctx: Context,
        data_source: str = Field(..., description="SQL query or table name to generate graph from"),
        graph_type: str = Field("auto", description="Type of graph to generate (auto, bar, line, scatter, etc.)"),
        league: str = Field("mlb", description="League to query (mlb, nba, etc.)")
    ) -> Dict[str, Any]:
        """
        Generate a graph/chart from query results or table data.
        """
        return await graph.generate_graph(ctx, data_source, graph_type, league)

    @mcp.tool()
    async def run_linear_regression(
        ctx: Context,
        data_source: str = Field(..., description="SQL query to get data for regression"),
        target_column: str = Field(..., description="Name of the target/dependent variable column"),
        feature_columns: List[str] = Field(..., description="List of feature/independent variable column names"),
        league: str = Field("mlb", description="League to query (mlb, nba, etc.)")
    ) -> Dict[str, Any]:
        """
        Run linear regression analysis on query results.
        """
        return await linear_regression.run_linear_regression(ctx, data_source, target_column, feature_columns, league)

    @mcp.tool()
    async def get_betting_events_by_date(
        ctx: Context,
        date: str = Field(..., description="Date in YYYY-MM-DD format"),
        sport: str = Field("basketball", description="Sport to get events for")
    ) -> Dict[str, Any]:
        """
        Get betting events for a specific date and sport.
        """
        return await betting.get_betting_events_by_date(ctx, date, sport)

    @mcp.tool()
    async def get_betting_markets_for_event(
        ctx: Context,
        event_id: str = Field(..., description="Event ID to get markets for")
    ) -> Dict[str, Any]:
        """
        Get betting markets for a specific event.
        """
        return await betting.get_betting_markets_for_event(ctx, event_id) 