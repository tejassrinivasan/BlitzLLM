# BlitzAgent-Agno

A powerful AI agent built with the [Agno framework](https://agno.com) for sports analytics and database insights. Features Gemini 2.5 Pro with optional reasoning models, PostgreSQL memory integration, Python MCP connectivity, and comprehensive metrics.

## 🚀 Features

- **🧠 Advanced Reasoning**: Gemini 2.5 Pro model with optional reasoning model configuration
- **💾 PostgreSQL Memory**: Persistent conversation history and user sessions
- **🔌 Python MCP Integration**: Connect to existing MCP server tools
- **📈 Comprehensive Metrics**: Prometheus metrics for monitoring and observability
- **⚡ High Performance**: Built on Agno's lightning-fast agent framework
- **🌐 Web Interface**: FastAPI server with WebSocket support
- **🎛️ CLI Tools**: Interactive chat and single-query interfaces

## 📋 Requirements

- Python 3.10+
- PostgreSQL database
- Google Gemini API key
- Optional: Azure OpenAI API key (for reasoning + response model)
- Running Python MCP server (optional)
- Node.js 18+ (for Agent UI)

## 🛠️ Installation

### Quick Setup (Recommended)

For the fastest setup experience with Agent UI:

```bash
git clone <your-repo-url>
cd blitzagent-agno
python setup_playground.py
```

This script will:
- ✅ Install BlitzAgent dependencies
- 🎨 Set up the Agent UI
- 📝 Create configuration files
- 🔑 Help you configure API keys

### Manual Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd blitzagent-agno
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -e .
```

### 4. Set up configuration

Copy the example configuration and environment files:

```bash
cp config/config.example.json config/config.json
cp .env.example .env
```

### 5. Configure environment variables

Edit `.env` with your settings:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=blitzagent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Optional: For reasoning + response model setup
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Optional MCP Integration
MCP_SERVER_URL=ws://localhost:3001
MCP_ENABLED=true

# Optional Monitoring
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=8000

# Security
JWT_SECRET_KEY=your_secret_key_here
API_RATE_LIMIT=100
```

### 6. Set up PostgreSQL database

```bash
# Create database
createdb blitzagent

# Initialize tables (handled automatically on first run)
```

## 🎯 CLI Commands

### Core Commands

#### Interactive Chat
Start an interactive chat session with the agent:

```bash
blitzagent-agno chat
```

**Options:**
- `--user, -u TEXT`: User ID for session tracking
- `--session, -s TEXT`: Session ID for conversation grouping
- `--stream/--no-stream`: Enable/disable streaming responses (default: enabled)
- `--reasoning/--no-reasoning`: Show/hide reasoning steps (default: enabled)
- `--config, -c PATH`: Custom configuration file path

**Examples:**
```bash
# Basic chat
blitzagent-agno chat

# Chat with user tracking
blitzagent-agno chat --user john_doe --session analysis_2024

# Chat without streaming
blitzagent-agno chat --no-stream

# Chat without reasoning display
blitzagent-agno chat --no-reasoning
```

#### Single Query
Send a single query and get a response:

```bash
blitzagent-agno query "Your question here"
```

**Options:**
- `--user, -u TEXT`: User ID for session tracking
- `--session, -s TEXT`: Session ID for conversation grouping
- `--stream/--no-stream`: Enable/disable streaming responses (default: enabled)
- `--reasoning/--no-reasoning`: Show/hide reasoning steps (default: enabled)
- `--format, -f [text|json]`: Output format (default: text)
- `--config, -c PATH`: Custom configuration file path

**Examples:**
```bash
# Basic query
blitzagent-agno query "What are the Lakers' stats this season?"

# Query with JSON output
blitzagent-agno query "Analyze the Warriors performance" --format json

# Query without streaming for clean output
blitzagent-agno query "Compare NBA teams" --no-stream --format json

# Query with user tracking
blitzagent-agno query "Who won last night?" --user analyst --session daily_report
```

#### Conversation History
View conversation history for a specific user:

```bash
blitzagent-agno history USER_ID
```

**Options:**
- `--session, -s TEXT`: Filter by specific session ID
- `--limit, -l INTEGER`: Number of entries to retrieve (default: 10, max: 100)
- `--config, -c PATH`: Custom configuration file path

**Examples:**
```bash
# Get last 10 conversations for user
blitzagent-agno history john_doe

# Get last 25 conversations
blitzagent-agno history john_doe --limit 25

# Get conversations from specific session
blitzagent-agno history john_doe --session analysis_2024
```

### System Commands

#### Health Check
Check the agent's health status:

```bash
blitzagent-agno health
```

Shows status of:
- Agent initialization
- Database connectivity
- MCP server connection
- Memory system

#### Metrics
Display current agent metrics:

```bash
blitzagent-agno metrics
```

Shows:
- Total queries processed
- Success rate
- Average response time
- Token usage statistics
- Active sessions
- Uptime
- Top used tools

#### Configuration
Display current configuration:

```bash
blitzagent-agno config
```

Shows:
- Model configuration
- Database settings
- MCP server settings
- Agent settings

### Web Server

#### Start Web Server
Start the FastAPI web server:

```bash
blitzagent-server
```

**Alternative:**
```bash
uvicorn blitzagent_agno.server:app --host 0.0.0.0 --port 8000
```

**Available endpoints:**
- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health
- **Metrics**: http://localhost:8000/api/metrics
- **WebSocket Chat**: ws://localhost:8000/ws/chat

### 🎨 Agent UI Playground

BlitzAgent includes a beautiful Agent UI for interactive conversations:

#### Start Playground Server

```bash
blitzagent-playground
```

The playground server will start at **http://localhost:7777**

#### Set Up Agent UI

```bash
# Install the Agent UI
npx create-agent-ui@latest

# Start the UI
cd agent-ui && npm run dev
```

The Agent UI will be available at **http://localhost:3000**

#### Usage
1. **Start the playground server**: `blitzagent-playground`
2. **Start the Agent UI**: `npm run dev` in the agent-ui directory  
3. **Open**: http://localhost:3000
4. **Connect**: Select `localhost:7777` endpoint
5. **Chat**: Start interacting with your BlitzAgent!

**Features:**
- 🎨 Beautiful, modern interface
- 💬 Real-time chat with your agent
- 📝 Conversation history
- 🧠 Reasoning step visualization (if dual model enabled)
- 📊 Agent metrics and status
- 🎛️ No data sent to external services - all local

### Interactive Chat Commands

When in interactive chat mode (`blitzagent-agno chat`), you can use these special commands:

- **`help`**: Show available commands and tips
- **`clear`**: Clear the screen
- **`metrics`**: Show quick metrics summary
- **`quit`, `exit`, `bye`**: Exit the chat session

## 🏗️ Architecture

### Core Components

1. **BlitzAgent**: Main agent class with Gemini 2.5 Pro model
2. **Memory System**: PostgreSQL-based conversation storage
3. **MCP Client**: WebSocket client for Python MCP server
4. **Metrics**: Prometheus metrics collection
5. **Tools Registry**: Integration with MCP tools
6. **Web Server**: FastAPI with WebSocket support

### Project Structure

```
blitzagent-agno/
├── src/blitzagent_agno/
│   ├── __init__.py           # Package initialization
│   ├── agent.py              # Main BlitzAgent class
│   ├── config.py             # Configuration management
│   ├── memory.py             # PostgreSQL memory system
│   ├── metrics.py            # Prometheus metrics
│   ├── mcp_client.py         # MCP WebSocket client
│   ├── tools.py              # Tool registry
│   ├── cli.py                # CLI interface
│   ├── server.py             # FastAPI web server
│   └── exceptions.py         # Custom exceptions
├── config/
│   └── config.example.json   # Configuration template
├── examples/
│   ├── basic_usage.py        # Basic usage examples
│   └── sports_analysis.py    # Sports analytics examples
├── tests/                    # Test suite
├── .env.example              # Environment template
├── pyproject.toml            # Project configuration
└── README.md                 # This file
```

## ⚙️ Configuration

The agent uses a JSON configuration file and environment variables:

### config/config.json

```json
{
  "model": {
    "provider": "gemini",
    "name": "gemini-2.5-pro",
    "reasoning_model": "gemini-2.5-pro",
    "temperature": 0.1,
    "max_tokens": 4096,
    "streaming": true
  },
  "database": {
    "host": "localhost",
    "port": 5432,
    "database": "blitzagent",
    "user": "postgres",
    "ssl_mode": "prefer",
    "pool_size": 10,
    "max_overflow": 20
  },
  "mcp": {
    "enabled": true,
    "server_url": "ws://localhost:3001",
    "timeout": 30,
    "retry_attempts": 3
  },
  "agent": {
    "name": "BlitzAgent",
    "description": "AI agent for sports analytics and insights",
    "max_memory_messages": 100,
    "enable_reasoning": true
  }
}
```

## 🧠 Reasoning + Response Model Setup

You can configure the agent to use separate reasoning and response models, similar to the DeepSeek R1 + Claude Sonnet pattern. This allows you to leverage powerful reasoning models while maintaining natural conversational responses.

### Example: Azure OpenAI + Gemini

Update your `config/config.json`:

```json
{
  "model": {
    "provider": "gemini",
    "name": "gemini-2.5-pro",
    "enable_dual_model": true,
    "reasoning_provider": "azure_openai", 
    "reasoning_model_name": "gpt-4o",
    "reasoning_azure_endpoint": "https://your-resource.openai.azure.com/",
    "reasoning_azure_deployment": "gpt-4o",
    "api_key": "your_gemini_key_here",
    "reasoning_api_key": "your_azure_openai_key_here",
    "temperature": 0.1,
    "max_tokens": 4096
  }
}
```

### Example: Gemini + Azure OpenAI (Reversed)

```json
{
  "model": {
    "provider": "azure_openai",
    "name": "gpt-4o",
    "azure_endpoint": "https://your-resource.openai.azure.com/",
    "azure_deployment": "gpt-4o", 
    "enable_dual_model": true,
    "reasoning_provider": "gemini",
    "reasoning_model_name": "gemini-2.5-pro",
    "api_key": "your_azure_openai_key_here",
    "reasoning_api_key": "your_gemini_key_here",
    "temperature": 0.1,
    "max_tokens": 4096
  }
}
```

### Single Model (Default)

```json
{
  "model": {
    "provider": "gemini",
    "name": "gemini-2.5-pro",
    "api_key": "your_gemini_key_here",
    "enable_dual_model": false,
    "temperature": 0.1,
    "max_tokens": 4096
  }
}
```

## 🔧 Usage Examples

### Sports Analytics

```python
from blitzagent_agno import BlitzAgent

agent = BlitzAgent()

# Team performance analysis
response = await agent.arun(
    "Compare the Lakers and Warriors performance this season, "
    "including wins, losses, key player stats, and recent trends"
)

# Player statistics
response = await agent.arun(
    "Get detailed statistics for LeBron James this season "
    "and compare with his career averages"
)

# Market analysis
response = await agent.arun(
    "What are the latest NBA trades and how might they "
    "affect team standings and playoff predictions?"
)
```

# Structured outputs are temporarily disabled

### Memory and Context

```python
# The agent automatically maintains conversation context
await agent.arun("Who won the last Lakers game?")
await agent.arun("What was the final score?")  # Remembers previous context
await agent.arun("How did LeBron perform in that game?")  # Continues context
```

## 📊 Monitoring and Metrics

The agent includes comprehensive monitoring:

### Prometheus Metrics

- `blitzagent_requests_total`: Total number of requests
- `blitzagent_request_duration_seconds`: Request processing time
- `blitzagent_tokens_used_total`: Total tokens consumed
- `blitzagent_errors_total`: Total number of errors
- `blitzagent_memory_operations_total`: Memory system operations
- `blitzagent_mcp_calls_total`: MCP tool calls

### Health Checks

```bash
curl http://localhost:8000/health
```

### Logs

Structured logging with different levels:

```python
import structlog

logger = structlog.get_logger()
logger.info("Agent started", session_id="123", user_id="user1")
```

## 🧪 Testing

Run the test suite:

```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest

# Run with coverage
pytest --cov=src/blitzagent_agno --cov-report=html

# Run specific test
pytest tests/test_agent.py::test_basic_query
```

## 🚀 Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["uvicorn", "blitzagent_agno.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

```bash
# Production settings
ENVIRONMENT=production
LOG_LEVEL=info
WORKERS=4
MAX_CONNECTIONS=100

# Database
POSTGRES_HOST=prod-db-host
POSTGRES_SSL_MODE=require

# Security
JWT_SECRET_KEY=production-secret-key
CORS_ORIGINS=https://yourdomain.com

# Monitoring
PROMETHEUS_ENABLED=true
METRICS_PORT=9090
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- 📧 Email: support@blitzagent.com
- 💬 Discord: [BlitzAgent Community](https://discord.gg/blitzagent)
- 📖 Documentation: [docs.blitzagent.com](https://docs.blitzagent.com)
- 🐛 Issues: [GitHub Issues](https://github.com/blitzagent/blitzagent-agno/issues)

## 🙏 Acknowledgments

- [Agno Framework](https://agno.com) - The lightweight AI agent framework
- [Google Gemini](https://ai.google.dev) - Advanced reasoning model
- [PostgreSQL](https://postgresql.org) - Reliable database system
- [FastAPI](https://fastapi.tiangolo.com) - Modern web framework
- [Prometheus](https://prometheus.io) - Monitoring and alerting 

## 🧠 Semantic Memory & Recall

BlitzAgent features an advanced semantic memory system that enables contextual conversation recall:

### Features
- **Vector Embeddings**: Uses OpenAI embeddings (text-embedding-ada-002) to create semantic representations
- **pgvector Integration**: Leverages PostgreSQL's pgvector extension for efficient similarity search
- **Cross-Session Recall**: Finds relevant conversations across different sessions
- **Contextual Retrieval**: Automatically includes surrounding conversation context

### Configuration
```json
{
  "memory": {
    "enabled": true,
    "semantic_recall": {
      "enabled": true,
      "top_k": 5,
      "message_range": 3,
      "scope": "resource",
      "embedding_model": "text-embedding-ada-002",
      "similarity_threshold": 0.7
    },
    "vector_store": {
      "provider": "pgvector",
      "table_name": "message_embeddings",
      "dimension": 1536
    }
  }
}
```

### Setup
1. **Enable semantic recall** in your config.json
2. **Run setup script**:
   ```bash
   python setup_semantic_memory.py
   ```
3. **Verify vector operations** are working properly

### How It Works
1. **Message Storage**: Every conversation is converted to embeddings and stored
2. **Semantic Search**: When you ask a question, the system finds similar past conversations
3. **Context Integration**: Relevant context is automatically added to the agent's prompt
4. **Personalized Responses**: The agent uses past insights to provide better answers

### Vector Type Handling
The system properly handles PostgreSQL's `public.vector` type:
- Embeddings are stored as `public.vector(1536)` 
- Similarity search uses cosine distance operators (`<=>`)
- Proper type casting ensures compatibility with pgvector

## 🏃‍♂️ Quick Start

1. **Clone and setup**:
   ```bash
   git clone <repository>
   cd blitzagent-agno
   python setup_dev.py
   ```

2. **Configure database and API keys** in `config.json`

3. **Setup semantic memory**:
   ```bash
   python setup_semantic_memory.py
   ```

4. **Run playground**:
   ```bash
   python -m blitzagent_agno.playground
   ``` 