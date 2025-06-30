"""Configuration settings for the Blitz Agent MCP Server."""

import os
import json
from pathlib import Path
from urllib.parse import quote_plus

# Try to load from config.json if available
config_data = {}
try:
    # First try the mcp-ts directory
    config_path = Path(__file__).parent.parent.parent / "mcp-ts" / "config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            config_data = json.load(f)
    else:
        # Fallback to the original location
        config_path = Path(__file__).parent.parent.parent / "config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config_data = json.load(f)
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

SPORTSDATA_API_KEY=os.getenv("SPORTSDATA_API_KEY", config_data.get("services", {}).get("sportsdata", {}).get("apiKey"))

GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")

def get_postgres_url():
    """Build PostgreSQL connection URL from configuration."""
    if all([POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE, POSTGRES_USER, POSTGRES_PASSWORD]):
        # URL encode the password to handle special characters
        encoded_password = quote_plus(POSTGRES_PASSWORD)
        ssl_param = "?sslmode=require" if POSTGRES_SSL == "true" else ""
        return f"postgresql://{POSTGRES_USER}:{encoded_password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}{ssl_param}"
    return None
