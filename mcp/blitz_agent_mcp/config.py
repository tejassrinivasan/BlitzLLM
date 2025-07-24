"""Configuration settings for the Blitz Agent MCP Server."""

import os
import json
from pathlib import Path
from urllib.parse import quote_plus

# Try to load from config.json if available
config_data = {}
try:
    # Try multiple locations in order of preference
    config_locations = [
        # 1. User's home directory (standard location)
        Path.home() / ".config" / "blitz-agent-mcp" / "config.json",
        Path.home() / ".blitz-agent-mcp" / "config.json", 
        # 2. Package directory (bundled config)
        Path(__file__).parent / "config.json",
        # 3. Current working directory
        Path.cwd() / "config.json", 
        # 4. Package installation directory (for git installs)
        Path(__file__).parent.parent / "config.json",
        # 5. Development locations
        Path(__file__).parent.parent.parent / "mcp" / "config.json",
    ]
    
    for config_path in config_locations:
        if config_path.exists():
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            break
except Exception:
    pass

# Database settings
MAX_DATA_ROWS = int(os.getenv("MAX_DATA_ROWS", "1000"))

# API settings
API_KEY_HEADER = "X-API-Key"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Cosmos DB settings
COSMOS_DB_ENDPOINT = os.getenv("COSMOS_DB_ENDPOINT", config_data.get("services", {}).get("cosmosdb", {}).get("endpoint"))
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY", config_data.get("services", {}).get("cosmosdb", {}).get("key"))

# Azure AI Search settings
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", config_data.get("services", {}).get("azure", {}).get("search", {}).get("endpoint"))
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_API_KEY", config_data.get("services", {}).get("azure", {}).get("search", {}).get("apiKey"))
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX_NAME", config_data.get("services", {}).get("azure", {}).get("search", {}).get("indexName"))

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Firecrawl settings
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", config_data.get("services", {}).get("firecrawl", {}).get("apiKey"))

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", config_data.get("services", {}).get("azure", {}).get("openai", {}).get("apiKey"))
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", config_data.get("services", {}).get("azure", {}).get("openai", {}).get("endpoint"))
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", config_data.get("services", {}).get("azure", {}).get("openai", {}).get("apiVersion"))
AZURE_RESOURCE_NAME=os.getenv("AZURE_RESOURCE_NAME", config_data.get("services", {}).get("azure", {}).get("openai", {}).get("resourceName"))

# PostgreSQL settings - fallback to config.json
POSTGRES_HOST=os.getenv("POSTGRES_HOST", config_data.get("services", {}).get("postgres", {}).get("host"))
POSTGRES_PORT=os.getenv("POSTGRES_PORT", str(config_data.get("services", {}).get("postgres", {}).get("port", 5432)))
POSTGRES_DATABASE=os.getenv("POSTGRES_DATABASE", config_data.get("services", {}).get("postgres", {}).get("database"))
POSTGRES_USER=os.getenv("POSTGRES_USER", config_data.get("services", {}).get("postgres", {}).get("user"))
POSTGRES_PASSWORD=os.getenv("POSTGRES_PASSWORD", config_data.get("services", {}).get("postgres", {}).get("password"))
POSTGRES_SSL=os.getenv("POSTGRES_SSL", str(config_data.get("services", {}).get("postgres", {}).get("ssl", "true")).lower())

# League-specific PostgreSQL settings
POSTGRES_MLB_HOST=os.getenv("POSTGRES_MLB_HOST", config_data.get("services", {}).get("postgres_mlb", {}).get("host", POSTGRES_HOST))
POSTGRES_MLB_PORT=os.getenv("POSTGRES_MLB_PORT", str(config_data.get("services", {}).get("postgres_mlb", {}).get("port", POSTGRES_PORT)))
POSTGRES_MLB_DATABASE=os.getenv("POSTGRES_MLB_DATABASE", config_data.get("services", {}).get("postgres_mlb", {}).get("database", POSTGRES_DATABASE))
POSTGRES_MLB_USER=os.getenv("POSTGRES_MLB_USER", config_data.get("services", {}).get("postgres_mlb", {}).get("user", POSTGRES_USER))
POSTGRES_MLB_PASSWORD=os.getenv("POSTGRES_MLB_PASSWORD", config_data.get("services", {}).get("postgres_mlb", {}).get("password", POSTGRES_PASSWORD))
POSTGRES_MLB_SSL=os.getenv("POSTGRES_MLB_SSL", str(config_data.get("services", {}).get("postgres_mlb", {}).get("ssl", POSTGRES_SSL)).lower())

POSTGRES_NBA_HOST=os.getenv("POSTGRES_NBA_HOST", config_data.get("services", {}).get("postgres_nba", {}).get("host", POSTGRES_HOST))
POSTGRES_NBA_PORT=os.getenv("POSTGRES_NBA_PORT", str(config_data.get("services", {}).get("postgres_nba", {}).get("port", POSTGRES_PORT)))
POSTGRES_NBA_DATABASE=os.getenv("POSTGRES_NBA_DATABASE", config_data.get("services", {}).get("postgres_nba", {}).get("database", "nba"))
POSTGRES_NBA_USER=os.getenv("POSTGRES_NBA_USER", config_data.get("services", {}).get("postgres_nba", {}).get("user", POSTGRES_USER))
POSTGRES_NBA_PASSWORD=os.getenv("POSTGRES_NBA_PASSWORD", config_data.get("services", {}).get("postgres_nba", {}).get("password", POSTGRES_PASSWORD))
POSTGRES_NBA_SSL=os.getenv("POSTGRES_NBA_SSL", str(config_data.get("services", {}).get("postgres_nba", {}).get("ssl", POSTGRES_SSL)).lower())

SPORTSDATA_API_KEY=os.getenv("SPORTSDATA_API_KEY", config_data.get("services", {}).get("sportsdata", {}).get("apiKey"))

GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")

def get_postgres_url(league: str = None):
    """Build PostgreSQL connection URL from configuration for specified league."""
    if league:
        league = league.lower()
        if league == "mlb":
            host, port, database, user, password, ssl = (
                POSTGRES_MLB_HOST, POSTGRES_MLB_PORT, POSTGRES_MLB_DATABASE, 
                POSTGRES_MLB_USER, POSTGRES_MLB_PASSWORD, POSTGRES_MLB_SSL
            )
        elif league == "nba":
            host, port, database, user, password, ssl = (
                POSTGRES_NBA_HOST, POSTGRES_NBA_PORT, POSTGRES_NBA_DATABASE,
                POSTGRES_NBA_USER, POSTGRES_NBA_PASSWORD, POSTGRES_NBA_SSL
            )
        else:
            # Fallback to default postgres config for unknown leagues
            host, port, database, user, password, ssl = (
                POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE,
                POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SSL
            )
    else:
        # Default behavior when no league specified
        host, port, database, user, password, ssl = (
            POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE,
            POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SSL
        )
    
    if all([host, port, database, user, password]):
        # URL encode the password to handle special characters
        encoded_password = quote_plus(password)
        # Handle SSL mode properly - use the actual value instead of hardcoding "require"
        if ssl and ssl.lower() not in ["false", "disable", "0", ""]:
            # If SSL mode is specified, use it directly
            if ssl.lower() in ["require", "prefer", "allow", "disable"]:
                ssl_param = f"?sslmode={ssl.lower()}"
            else:
                # For legacy "true" values, default to "prefer" for better compatibility
                ssl_param = "?sslmode=prefer"
        else:
            ssl_param = ""
        return f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}{ssl_param}"
    return None
