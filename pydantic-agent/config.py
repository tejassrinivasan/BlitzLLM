"""Configuration for the Pydantic AI Sports Agent."""

import os
from typing import Optional

class Config:
    """Configuration settings for the sports agent."""
    
    # Anthropic API configuration
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8001"))
    
    # API Authentication - REQUIRED
    API_KEY: Optional[str] = os.getenv("API_KEY")  # Single key option
    
    # Multi-client API keys (JSON string or file path)
    API_KEYS_JSON: Optional[str] = os.getenv("API_KEYS_JSON")  # JSON string of client keys
    API_KEYS_FILE: Optional[str] = os.getenv("API_KEYS_FILE", "api_keys.json")  # File path
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()  # Ensure uppercase for MCP compatibility
    
    # MCP Configuration (package installed directly in container)
    MCP_COMMAND: str = "blitz-agent-mcp"  # Installed package command
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Get your API key from https://console.anthropic.com/"
            )
        
        # API keys are now always required
        if not cls.API_KEY and not cls.API_KEYS_JSON and not cls.API_KEYS_FILE:
            raise ValueError(
                "API keys are required. Provide via one of:\n"
                "- API_KEY (single key)\n"
                "- API_KEYS_JSON (JSON string)\n"
                "- API_KEYS_FILE (JSON file path)"
            ) 