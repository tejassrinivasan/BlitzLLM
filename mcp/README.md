# Blitz Agent MCP Server (Python)

A comprehensive Model Context Protocol (MCP) server for sports database analysis, AI-powered insights, and data validation using the official Python MCP SDK.

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
- **API**: Discover and call OpenAPI endpoints
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

#### `api`
Discover and call OpenAPI endpoints.
```json
{
  "action": "discover",
  "openapi_url": "https://api.example.com/openapi.json"
}
```

#### `upload`
Store successful queries in Cosmos DB.
```json
{
  "query": "SELECT * FROM games",
  "results": "[{\"game_id\": 1, \"score\": \"10-7\"}]",
  "context": "Game results query",
  "validation_score": 0.95
}
```

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

## Supported Leagues

- **MLB**: Complete baseball database schema
- **NBA**: Complete basketball database schema
- **More leagues**: Easily extensible

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