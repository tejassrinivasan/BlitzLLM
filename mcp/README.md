# 🚀 Blitz Agent MCP Server

A powerful Model Context Protocol (MCP) server for sports database analysis, combining real-time data access, AI-powered insights, and comprehensive validation tools. Built with FastMCP for optimal performance and scalability.

## 🎯 Key Features

- **Multi-League Database Support**: Separate database connections for MLB and NBA data
- **Advanced Query Tools**: SQL execution with league-specific context
- **AI-Powered Validation**: Intelligent query result analysis
- **Historical Query Recall**: Learn from previous successful queries
- **Real-time Data Integration**: Live betting odds and sports data
- **Comprehensive Schema Support**: Detailed documentation for all sports leagues

## 📊 Multi-League Database Configuration

The server supports separate database instances for different sports leagues. This allows you to:

- **Query MLB data**: Use `league="mlb"` parameter
- **Query NBA data**: Use `league="nba"` parameter  
- **Automatic fallback**: Default database when no league is specified

### Configuration Structure

Each league can have its own database configuration in `config.json`:

```json
{
  "services": {
    "postgres": {
      "description": "Default/fallback PostgreSQL database",
      "host": "your-host.com",
      "database": "mlb"
    },
    "postgres_mlb": {
      "description": "MLB-specific database",
      "host": "your-host.com", 
      "database": "mlb"
    },
    "postgres_nba": {
      "description": "NBA-specific database",
      "host": "your-host.com",
      "database": "nba"
    }
  }
}
```

### Environment Variables

You can also configure league-specific databases using environment variables:

```bash
# MLB Database
POSTGRES_MLB_HOST=your-mlb-host.com
POSTGRES_MLB_DATABASE=mlb
POSTGRES_MLB_USER=postgres
POSTGRES_MLB_PASSWORD=your-password

# NBA Database  
POSTGRES_NBA_HOST=your-nba-host.com
POSTGRES_NBA_DATABASE=nba
POSTGRES_NBA_USER=postgres
POSTGRES_NBA_PASSWORD=your-password
```

## 🛠️ Database Tools with League Support

All core database tools now support the `league` parameter:

### `query`
Execute SQL queries against league-specific databases.
```json
{
  "query": "SELECT * FROM games WHERE season = 2024",
  "description": "Get all 2024 games",
  "league": "mlb"
}
```

### `inspect`
Inspect table structure in specific league databases.
```json
{
  "table": "battingstatsgame",
  "league": "mlb"
}
```

### `sample` 
Sample data from league-specific tables.
```json
{
  "table": "playerstatsgame",
  "n": 10,
  "league": "nba"
}
```

### `search_tables`
Search for tables within a specific league database.
```json
{
  "pattern": "player stats",
  "league": "nba",
  "mode": "bm25"
}
```

### `test`
Test database connections for specific leagues.
```json
{
  "league": "mlb"
}
```

### `validate`
Validate query results with league-specific schema context.
```json
{
  "query": "SELECT * FROM standings",
  "results": "[{\"team\": \"Lakers\", \"wins\": 45}]",
  "league": "nba",
  "user_question": "What are the current standings?",
  "description": "Season standings query",
  "context": "Regular season analysis"
}
```

### `upload`
Upload successful queries to league-specific Cosmos DB containers.
```json
{
  "description": "Get team standings for current season",
  "query": "SELECT team, wins, losses FROM standings WHERE season = 2024",
  "league": "nba",
  "results": "[{\"team\": \"Lakers\", \"wins\": 45, \"losses\": 20}]",
  "context": "Season analysis",
  "validation_score": 0.92
}
```

## 📈 Usage Examples

### Querying MLB Data
```python
# Query MLB batting statistics
await query(
    ctx=ctx,
    query="SELECT player_name, avg FROM battingstatsgame WHERE season = 2024",
    description="Get 2024 batting averages",
    league="mlb"
)
```

### Querying NBA Data  
```python
# Query NBA player statistics
await query(
    ctx=ctx, 
    query="SELECT player_name, points FROM playerstatsgame WHERE season = 2024",
    description="Get 2024 scoring stats",
    league="nba"
)
```

### Testing Connections
```python
# Test MLB database connection
await test(ctx=ctx, league="mlb")

# Test NBA database connection  
await test(ctx=ctx, league="nba")

# Test default database connection
await test(ctx=ctx)
```

### Uploading Successful Queries
```python
# Upload MLB query to mlb-unofficial container
await upload(
    ctx=ctx,
    description="Get top 10 home run leaders in 2024",
    query="SELECT player_name, home_runs FROM battingstatsgame WHERE season = 2024 ORDER BY home_runs DESC LIMIT 10",
    league="mlb",
    results="[{\"player_name\": \"Judge\", \"home_runs\": 62}]",
    validation_score=0.95
)

# Upload NBA query to nba-unofficial container
await upload(
    ctx=ctx,
    description="Get top scorers in 2024 season",
    query="SELECT player_name, points FROM playerstatsgame WHERE season = 2024 ORDER BY points DESC LIMIT 10",
    league="nba",
    results="[{\"player_name\": \"Embiid\", \"points\": 33.1}]",
    validation_score=0.88
)
```

## 🔧 Migration Guide

If you're upgrading from a single-database setup:

1. **Update your config.json** to include league-specific database configurations
2. **Add league parameters** to your database tool calls
3. **Test connections** for each league using the `test` tool
4. **Update your queries** to specify the appropriate league

### Backward Compatibility

- Tools without the `league` parameter will use the default database
- Existing queries will continue to work unchanged
- The system gracefully falls back to default settings when league-specific configs are missing

## 🏆 Supported Leagues

- **MLB**: Complete baseball database schema with historical and current data
- **NBA**: Complete basketball database schema with player, team, and game statistics
- **Extensible**: Easily add support for additional leagues

## 🔍 Schema Documentation

Each league has comprehensive schema documentation:

- **MLB Schema**: `/schemas/mlb-schema.md`
- **NBA Schema**: `/schemas/nba-schema.md`

Use the `get_database_documentation` tool to access league-specific schema information:

```json
{
  "league": "mlb"
}
```

## 🚦 Error Handling

The system provides detailed error messages for configuration issues:

- **Missing league config**: Clear indication of what's missing
- **Connection failures**: Specific error details for troubleshooting  
- **Invalid league**: Helpful suggestions for supported leagues

## 🎛️ Configuration Validation

Before using the tools, validate your setup:

```bash
# Test MLB connection
mcp-client test --league mlb

# Test NBA connection  
mcp-client test --league nba

# List available tables
mcp-client search_tables --pattern "stats" --league mlb
```

This multi-league support enables sophisticated cross-sport analysis while maintaining data isolation and optimal performance for each sport's specific requirements.

## Features

### 🏗️ Database Operations
- **Discover**: Explore database schema and structure
- **Inspect**: Examine specific tables with sample data
- **Query**: Execute SQL queries with security controls
- **Sample**: Get filtered sample data from tables
- **Scan**: Search database for patterns and keywords
- **Test**: Validate database connections

### 🤖 AI-Powered Analysis
- **Validate**: AI-powered query result validation
- **recall_similar_db_queries**: Generate insights and pattern analysis
- **Query & Validate**: Combined execution with automatic validation

### 🌐 External Integrations
- **Webscrape**: Extract content using Firecrawl
- **Betting Tools**: Fetch live MLB betting events and markets from SportsData.io
- **Upload**: Store successful queries in Cosmos DB

### 📚 Knowledge Management
- **Get League Info**: Retrieve sport-specific schema documentation

## Installation

### Prerequisites
- Python 3.8+
- pip or uv package manager

### Setup

1. **Clone and navigate to the MCP directory:**
   ```bash
   cd mcp
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   # or using uv
   uv pip install -e .
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run the server:**
   ```bash
   python -m blitz_agent_mcp.server
   # or
   blitz-agent-mcp
   ```

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/database_name

# Azure AI Configuration (for validation and recall_similar_db_queriesing)
AZURE_AI_ENDPOINT=https://your-ai-endpoint.cognitiveservices.azure.com/
AZURE_AI_API_KEY=your_azure_ai_api_key

# Firecrawl Configuration (for web scraping)
FIRECRAWL_API_KEY=your_firecrawl_api_key

# Cosmos DB Configuration (for query recall_similar_db_queriesing)
COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
COSMOS_KEY=your_cosmos_key
COSMOS_DATABASE=blitz-agent
COSMOS_CONTAINER=query-recall_similar_db_queriesing
```

### Claude Desktop Integration

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "blitz-agent": {
      "command": "python",
      "args": ["-m", "blitz_agent_mcp.server"],
      "env": {
        "DATABASE_URL": "your_database_url",
        "AZURE_AI_ENDPOINT": "your_azure_endpoint",
        "AZURE_AI_API_KEY": "your_azure_key"
      }
    }
  }
}
```

### Cursor MCP Integrations 
Run what's in GIT:
{
  "mcpServers": {
    "blitz-mcp": {
      "command": "uvx",
      "args": ["--from", "git+file:///Users/devonsinha/workspace/BlitzLLM#subdirectory=mcp", "blitz-agent-mcp", "--transport", "stdio", "--quiet"],
      "cwd": "/Users/devonsinha/workspace/BlitzLLM/mcp"
    }
  }
}



### Local Debug 
run 'uv run mcp dev inspector_main.py' from the mcp dir

## Tools Reference

### Database Tools

#### `discover`
Explore database schema and structure.
```json
{
  "connection_string": "postgresql://user:pass@host:port/db"
}
```

#### `inspect`
Examine specific tables with sample data.
```json
{
  "connection_string": "postgresql://user:pass@host:port/db",
  "table_name": "games",
  "limit": 5
}
```

#### `query`
Execute SQL queries (SELECT only for security).
```json
{
  "connection_string": "postgresql://user:pass@host:port/db",
  "sql": "SELECT * FROM games WHERE season = 2024",
  "limit": 100
}
```

#### `sample`
Get filtered sample data from tables.
```json
{
  "connection_string": "postgresql://user:pass@host:port/db",
  "table_name": "players",
  "limit": 10,
  "where_clause": "position = 'QB'"
}
```

#### `search_tables`
Search database for patterns or keywords.
```json
{
  "connection_string": "postgresql://user:pass@host:port/db",
  "search_term": "touchdown",
  "search_type": "column_names"
}
```

#### `test`
Test database connection and performance.
```json
{
  "connection_string": "postgresql://user:pass@host:port/db"
}
```

### AI Tools

#### `validate`
AI-powered validation of query results.
```json
{
  "data": "[{\"team\": \"Lakers\", \"wins\": 45}]",
  "query": "SELECT team, wins FROM standings",
  "context": "Season standings validation"
}
```

#### `recall_similar_db_queries`
Generate insights and pattern analysis.
```json
{
  "data": "[{\"player\": \"LeBron\", \"points\": 25.2}]",
  "recall_similar_db_queriesing_type": "pattern_analysis",
  "context": "Player performance analysis"
}
```

#### `query_and_validate`
Combined query execution with automatic validation.
```json
{
  "connection_string": "postgresql://user:pass@host:port/db",
  "sql": "SELECT * FROM player_stats WHERE season = 2024",
  "context": "Season performance analysis"
}
```

### Integration Tools

#### `webscrape`
Extract content using Firecrawl.
```json
{
  "url": "https://example.com/sports-news",
  "formats": ["markdown", "html"]
}
```

#### `get_betting_events_by_date`
Fetch all MLB betting events for a specific date.
```json
{
  "date": "2025-06-30"
}
```

#### `get_betting_markets_for_event`
Get detailed betting markets and odds for a specific event.
```json
{
  "event_id": 14219
}
```

#### `upload`
Store successful queries in league-specific Cosmos DB containers.
```json
{
  "description": "Get 2024 season games",
  "query": "SELECT * FROM games WHERE season = 2024",
  "league": "mlb",
  "results": "[{\"game_id\": 1, \"score\": \"10-7\"}]",
  "context": "Game results query",
  "validation_score": 0.95
}
```

**Container Mapping:**
- `league="mlb"` → `mlb-unofficial` container
- `league="nba"` → `nba-unofficial` container  
- `league=None` → `agent-learning` container (fallback)

### Knowledge Tools

#### `get_league_info`
Retrieve sport-specific schema documentation.
```json
{
  "league": "mlb"
}
```

## Security Features

- **Read-only queries**: Only SELECT statements are allowed
- **SQL injection protection**: Parameterized queries
- **Connection validation**: Automatic connection testing
- **Rate limiting**: Built-in request throttling
- **Error handling**: Comprehensive error reporting

## Development

### Running in Development Mode

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run with hot reload
python -m blitz_agent_mcp.server

# Run tests
pytest

# Format code
black src/
ruff check src/
```

### Adding New Tools

1. Create a new tool file in `src/blitz_agent_mcp/tools/`
2. Implement the `handle_<tool_name>` async function
3. Add the tool to `src/blitz_agent_mcp/tools/__init__.py`
4. Register the tool in `src/blitz_agent_mcp/server.py`

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
- Open a GitHub issue
- Check the MCP documentation: https://modelcontextprotocol.io
- Review the Python SDK docs: https://github.com/modelcontextprotocol/python-sdk 