"""Configuration for the Twitter NBA Agent."""

import os
from typing import Optional

class Config:
    """Configuration settings for the Twitter NBA agent."""
    
    # Anthropic API configuration
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8002"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # MCP Configuration (package installed directly in container)
    MCP_COMMAND: str = "blitz-agent-mcp"  # Installed package command
    
    # Twitter API Configuration
    SHARED_CONSUMER_KEY: str = os.getenv("SHARED_CONSUMER_KEY", "IO0UIDgBKTrXby3Sl2zPz0vJO")
    SHARED_CONSUMER_SECRET: str = os.getenv("SHARED_CONSUMER_SECRET", "6hKlyZCwLCpVPZ4dxfCiISC7H4Sg61YJdxYr0nGqHrdBuUt1AF")
    
    # @BlitzAnalytics credentials (for rate-limit-free tweet reading)
    BLITZANALYTICS_BEARER_TOKEN: str = os.getenv("BLITZANALYTICS_BEARER_TOKEN", "AAAAAAAAAAAAAAAAAAAAAL852AEAAAAArcVns1HPuR8uM8MhFdaqncOUcFw%3DTM16qakucHczkcg8MJ4GwamqpuUm0pCKESK2oHsR4i4hJ094LN")
    BLITZANALYTICS_ACCESS_TOKEN: str = os.getenv("BLITZANALYTICS_ACCESS_TOKEN", "1889746223613321216-ASI5OzBr1OJP6E4MbVAq9UKletu2HZ")
    BLITZANALYTICS_ACCESS_SECRET: str = os.getenv("BLITZANALYTICS_ACCESS_SECRET", "aqJrBXgiNoJUhwiZRqOJ0kfWTWtaKWPSiEQVW7VdHLkuO")
    
    # @tejsri01 credentials (for posting questions)
    TEJSRI_BEARER_TOKEN: str = os.getenv("TEJSRI_BEARER_TOKEN", "AAAAAAAAAAAAAAAAAAAAANHQ3AEAAAAA4k9DlSblc8ZgNmgCJWIPvQmlEb8%3DkxTdQkEG97f8v4md0Fzofo9KDnDl0jZuWF8oLVTJ139j5L813d")
    TEJSRI_ACCESS_TOKEN: str = os.getenv("TEJSRI_ACCESS_TOKEN", "1194703284583354370-AL4uu3upXQAkPklgOxTllOz6T3qFz0")
    TEJSRI_ACCESS_SECRET: str = os.getenv("TEJSRI_ACCESS_SECRET", "MIBso7vI5D3tRrVUfCw0gX9Kd8CqyV4ZTXoMHjpcMyq9V")
    
    # @BlitzAIBot credentials (for posting analytics responses - has blue check)
    BLITZAI_BEARER_TOKEN: str = os.getenv("BLITZAI_BEARER_TOKEN", "AAAAAAAAAAAAAAAAAAAAAL852AEAAAAAFDeKS7l%2FbmLY4Aqywrzfj316X9U%3DhMN7FrxP8RVKchRgx08G4vFwEk0XwiY2F1CJ0mk57AMhVFOUlW")
    BLITZAI_ACCESS_TOKEN: str = os.getenv("BLITZAI_ACCESS_TOKEN", "1930145656842399746-N75MTZ1FkOmhM52Ofyrw5XqKsNG1mA")
    BLITZAI_ACCESS_SECRET: str = os.getenv("BLITZAI_ACCESS_SECRET", "zMIrda7t5kEjtVp4drnIlICEh6PyiQH5citssMs0m1tRl")
    
    # Background worker configuration
    WORKER_RUNS_PER_DAY: int = int(os.getenv("WORKER_RUNS_PER_DAY", "6"))
    WORKER_INTERVAL_HOURS: float = 24.0 / WORKER_RUNS_PER_DAY  # 4 hours for 6 runs per day
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Get your API key from https://console.anthropic.com/"
            ) 