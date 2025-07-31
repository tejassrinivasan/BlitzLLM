# Pydantic AI Sports Agent

A powerful AI-powered sports analysis agent built with [Pydantic AI](https://ai.pydantic.dev/agents/) that connects to the Blitz MCP server and uses Claude 4 Sonnet for advanced reasoning and analysis.

## Features

- 🤖 **Claude 4 Sonnet Integration**: Uses Anthropic's most advanced reasoning model (May 2025) with superior intelligence and capabilities
- 🔌 **MCP Server Connection**: Connects to the Blitz MCP server for comprehensive sports data access
- 🏈 **Multi-League Support**: Supports both NBA and MLB data analysis
- 📊 **Comprehensive Analysis**: Historical database queries, web scraping, and live betting data
- 🌐 **REST API**: FastAPI-based server for easy integration
- ⚙️ **Configurable Context**: Optional extra context parameters for customized analysis

## Quick Start

### Prerequisites

- Python 3.9+
- Anthropic API key ([Get one here](https://console.anthropic.com/))
- Access to the Blitz MCP server

### Installation

1. Clone the repository and navigate to the pydantic-agent folder:
```bash
cd pydantic-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

> **Note**: This installs `pydantic-ai-slim[mcp]` which includes MCP (Model Context Protocol) support for connecting to external tools and servers.

3. Set up your environment:
```bash
# Copy the example environment file
cp example.env .env

# Edit .env and add your Anthropic API key
# Get your API key from: https://console.anthropic.com/
```

Or set the environment variable directly:
```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

### Running the Agent

#### Option 1: As a Server (Recommended)
```bash
python main.py
```

The server will start on `http://localhost:8001` by default.

#### Option 2: Test Script
```bash
python test_agent.py
```

## API Usage

### Analyze Sports Query

**POST** `/analyze`

```json
{
  "query": "What are Stephen Curry's shooting stats this season?",
  "league": "nba",
  "extra_context": "Focus on three-point shooting performance"
}
```

**Response:**
```json
{
  "response": "Detailed analysis of Stephen Curry's shooting statistics...",
  "usage": {
    "requests": 1,
    "request_tokens": 150,
    "response_tokens": 800,
    "total_tokens": 950
  }
}
```

### Parameters

- **query** (required): The sports analysis question or request
- **league** (optional): League to focus on - "mlb" (default) or "nba"
- **extra_context** (optional): Additional context to include in the analysis

### Health Check

**GET** `/health`

Returns server health status.

## 🚀 Model Information

The agent uses **Claude 4 Sonnet** (May 2025) - Anthropic's most advanced reasoning model with superior intelligence across coding, agentic search, and AI agent capabilities.

### Claude 4 Sonnet Features:
- **Superior Reasoning**: Best-in-class performance on complex reasoning tasks
- **Advanced Coding**: State-of-the-art coding capabilities with 10% improvement over previous generation
- **200K Context Window**: Massive context for analyzing large documents and datasets
- **Hybrid Reasoning**: Can switch between fast responses and deep thinking

### Alternative Models:
If you need to use a different model, update `main.py`:
```python
# Current (recommended):
self.model = AnthropicModel("claude-4-sonnet")  

# Alternative options:
self.model = AnthropicModel("claude-3-7-sonnet-20250219")  # Older but still powerful
self.model = AnthropicModel("claude-opus-4")  # Even more powerful (if available)
```

> **Note**: Model availability may vary by region. Check [Anthropic's documentation](https://docs.anthropic.com/en/docs/welcome) for the latest model identifiers.

## Example API Calls

### Using curl

```bash
# NBA query
curl -X POST "http://localhost:8001/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How has LeBron James performed in clutch situations this season?",
    "league": "nba",
    "extra_context": "Focus on games in the last 5 minutes with score within 5 points"
  }'

# MLB query
curl -X POST "http://localhost:8001/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the best pitching matchups for today?",
    "league": "mlb"
  }'
```

### Using Python

```python
import httpx
import asyncio

async def analyze_sports():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/analyze",
            json={
                "query": "Which NBA teams have the best three-point defense?",
                "league": "nba",
                "extra_context": "Include data from the last 20 games"
            }
        )
        result = response.json()
        print(result["response"])

asyncio.run(analyze_sports())
```

## Configuration

The agent can be configured using environment variables:

- `ANTHROPIC_API_KEY`: Your Anthropic API key (required)
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: 8001)
- `LOG_LEVEL`: Logging level (default: "INFO") - supports DEBUG, INFO, WARNING, ERROR, CRITICAL

## Data Sources

The agent has access to three data sources in priority order:

1. **Historical Database (PostgreSQL)** - Comprehensive player stats, team records, and historical performance
2. **Web Scraping** - Real-time sports news, injuries, and current events
3. **Live Betting Data** - Real-time betting lines and odds

## Capabilities

### Database Analysis
- Player statistics and performance metrics
- Team records and historical data
- Advanced analytics and comparisons
- Multi-season trend analysis

### Real-time Data
- Current injury reports
- Today's game schedules and results
- Breaking trades and signings
- Live betting odds and markets

### Betting Analysis
- Expected value (EV) calculations
- Historical trend analysis
- Prop bet recommendations
- Sportsbook comparison

## Interactive Documentation

Once the server is running, visit `http://localhost:8001/docs` for interactive API documentation powered by Swagger UI.

## Error Handling

The agent includes comprehensive error handling:

- Configuration validation on startup
- Graceful handling of MCP server connection issues
- Detailed error messages for debugging
- Automatic retry logic for transient failures

## Development

### Running Tests
```bash
python test_agent.py
```

### Debugging
Set the log level to debug for more detailed logging:
```bash
export LOG_LEVEL=DEBUG
python main.py
```

## Architecture

The agent follows Pydantic AI's best practices:

- **Agent-centric design**: Single agent with comprehensive sports analysis capabilities
- **Type safety**: Full Pydantic validation for requests and responses
- **Tool integration**: Seamless MCP server connection for data access
- **Structured outputs**: Consistent response format with usage tracking

## Support

For issues or questions:
1. Check the logs for detailed error messages
2. Verify your Anthropic API key is valid
3. Ensure the MCP server is accessible
4. Review the interactive documentation at `/docs` 