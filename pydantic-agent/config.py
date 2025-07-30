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
    
    # Production API Authentication
    API_KEY: Optional[str] = os.getenv("API_KEY")  # Legacy single key (optional)
    PRODUCTION_MODE: bool = os.getenv("PRODUCTION_MODE", "false").lower() == "true"
    
    # Multi-client API keys (JSON string or file path)
    API_KEYS_JSON: Optional[str] = os.getenv("API_KEYS_JSON")  # JSON string of client keys
    API_KEYS_FILE: Optional[str] = os.getenv("API_KEYS_FILE", "api_keys.json")  # File path
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()  # Ensure uppercase for MCP compatibility
    
    # MCP Configuration
    MCP_REPO_URL: str = "git+https://github.com/tejassrinivasan/BlitzLLM.git#subdirectory=mcp"
    MCP_PACKAGE: str = "blitz-agent-mcp"
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Get your API key from https://console.anthropic.com/"
            )
        
        if cls.PRODUCTION_MODE:
            if not cls.API_KEY and not cls.API_KEYS_JSON and not cls.API_KEYS_FILE:
                raise ValueError(
                    "When PRODUCTION_MODE=true, you must provide API keys via one of:\n"
                    "- API_KEY (single key)\n"
                    "- API_KEYS_JSON (JSON string)\n"
                    "- API_KEYS_FILE (JSON file path)"
                ) 