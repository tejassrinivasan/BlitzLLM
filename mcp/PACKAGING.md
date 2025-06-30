# Blitz Agent MCP Packaging & Deployment Guide

This guide covers how to package and deploy the Blitz Agent MCP server as a private package using `uvx`.

## Quick Start

1. **Build the package**:
   ```bash
   ./release.sh
   ```

2. **Install with uvx**:
   ```bash
   uvx install ./dist/blitz_agent_mcp-*.whl
   ```

3. **Update your MCP configuration** in `~/.cursor/mcp.json`:
   ```json
   {
     "mcpServers": {
       "blitz-agent-python": {
         "command": "uvx",
         "args": ["run", "blitz-agent-mcp", "--transport", "streamable-http"],
         "env": {
           "POSTGRES_HOST": "your-postgres-host",
           "POSTGRES_PASSWORD": "your-password",
           // ... other env vars
         }
       }
     }
   }
   ```

## Detailed Instructions

### Building the Package

The `release.sh` script will:
- Check for uncommitted changes
- Auto-increment the patch version
- Build the wheel package
- Create a Docker image
- Tag and push to git

```bash
# Build and release locally
./release.sh

# Build and publish to PyPI (requires PYPI_API_TOKEN)
PYPI_API_TOKEN=your-token ./release.sh --pypi
```

### Installation Options

#### Option 1: uvx (Recommended)
```bash
# Install from local wheel
uvx install ./dist/blitz_agent_mcp-*.whl

# Or install from PyPI (if published)
uvx install blitz-agent-mcp
```

#### Option 2: pip
```bash
# Install from local wheel
pip install ./dist/blitz_agent_mcp-*.whl

# Or install from PyPI (if published)
pip install blitz-agent-mcp
```

#### Option 3: Docker
```bash
# Build image
docker build -t blitz-agent-mcp .

# Run container
docker run -p 8000:8000 \
  -e POSTGRES_HOST=your-host \
  -e POSTGRES_PASSWORD=your-password \
  blitz-agent-mcp
```

### MCP Configuration

Update your `~/.cursor/mcp.json` to use the packaged version:

```json
{
  "mcpServers": {
    "blitz-agent-python": {
      "command": "uvx",
      "args": [
        "run", 
        "blitz-agent-mcp", 
        "--transport", "streamable-http"
      ],
      "env": {
        "POSTGRES_HOST": "blitz-instance-1.cdu6kma429k4.us-west-2.rds.amazonaws.com",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DATABASE": "mlb",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "your-password",
        "POSTGRES_SSL": "true",
        "AZURE_OPENAI_API_KEY": "your-azure-key",
        "AZURE_OPENAI_ENDPOINT": "https://blitzgpt.openai.azure.com/",
        "AZURE_SEARCH_ENDPOINT": "https://blitz-ai-search.search.windows.net",
        "AZURE_SEARCH_API_KEY": "your-search-key",
        "COSMOS_DB_ENDPOINT": "https://blitz-queries.documents.azure.com:443/",
        "COSMOS_DB_KEY": "your-cosmos-key"
      }
    }
  }
}
```

### Available Commands

Once installed, you can run:

```bash
# Start with default settings (stdio transport)
blitz-agent-mcp

# Start with streamable-http transport for production
blitz-agent-mcp --transport streamable-http --host 0.0.0.0 --port 8000

# Start with SSE transport
blitz-agent-mcp --transport sse --host 127.0.0.1 --port 8001

# Get help
blitz-agent-mcp --help
```

### Development

For development, install in editable mode:

```bash
cd /path/to/mcp
pip install -e .[dev]
```

Then you can run directly:
```bash
python -m blitz_agent_mcp.main --transport streamable-http
```

### Environment Variables

The server supports these environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `POSTGRES_HOST` | PostgreSQL host | Yes |
| `POSTGRES_PORT` | PostgreSQL port | No (default: 5432) |
| `POSTGRES_DATABASE` | Database name | Yes |
| `POSTGRES_USER` | Database user | Yes |
| `POSTGRES_PASSWORD` | Database password | Yes |
| `POSTGRES_SSL` | Enable SSL | No (default: false) |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | Optional |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint | Optional |
| `COSMOS_DB_ENDPOINT` | Cosmos DB endpoint | Optional |

### Troubleshooting

#### Package not found
```bash
# Check uvx installation
uvx list

# Reinstall the package
uvx uninstall blitz-agent-mcp
uvx install ./dist/blitz_agent_mcp-*.whl
```

#### Import errors
Make sure the package structure is correct:
```
blitz_agent_mcp/
├── __init__.py
├── main.py
├── config.py
├── models/
├── tools/
└── schemas/
```

#### Docker build issues
```bash
# Clean build
docker system prune -f
docker build --no-cache -t blitz-agent-mcp .
```

### Publishing to PyPI

To publish to PyPI:

1. Get a PyPI API token from https://pypi.org/manage/account/token/
2. Set the environment variable:
   ```bash
   export PYPI_API_TOKEN="pypi-your-token-here"
   ```
3. Run the release script with PyPI flag:
   ```bash
   ./release.sh --pypi
   ```

### Version Management

Versions are automatically managed by the release script:
- `./release.sh` - increments patch version (1.0.0 → 1.0.1)
- Manual version bumps can be done by editing `pyproject.toml`

The version follows semantic versioning: `MAJOR.MINOR.PATCH` 