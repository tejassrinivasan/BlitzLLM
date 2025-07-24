"""
Configuration management for BlitzAgent-Agno.

Handles loading and validation of configuration from JSON files and environment variables
using Pydantic for type safety and validation.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

logger = structlog.get_logger(__name__)


class ModelConfig(BaseModel):
    """Model configuration settings."""
    
    provider: str = Field(default="gemini", description="Model provider (gemini, openai, anthropic, azure_openai)")
    name: str = Field(default="gemini-2.5-pro", description="Model name")
    reasoning_model: str = Field(default="gemini-2.5-pro", description="Reasoning model name")
    
    # Reasoning + Response Model Configuration (like Azure OpenAI + Gemini)
    enable_dual_model: bool = Field(default=False, description="Enable separate reasoning and response models")
    reasoning_provider: Optional[str] = Field(default=None, description="Reasoning model provider (azure_openai, gemini)")
    reasoning_model_name: Optional[str] = Field(default=None, description="Specific reasoning model name")
    reasoning_api_key: Optional[str] = Field(default=None, description="API key for reasoning model provider")
    
    # Azure OpenAI reasoning model specific fields
    reasoning_azure_endpoint: Optional[str] = Field(default=None, description="Azure OpenAI reasoning endpoint URL")
    reasoning_azure_deployment: Optional[str] = Field(default=None, description="Azure OpenAI reasoning deployment name")
    
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: int = Field(default=4096, ge=1, le=32768, description="Maximum tokens")
    streaming: bool = Field(default=True, description="Enable streaming responses")
    top_p: float = Field(default=0.95, ge=0.0, le=1.0, description="Top-p (nucleus) sampling")
    top_k: int = Field(default=40, ge=1, le=100, description="Top-k sampling")
    api_key: Optional[str] = Field(default=None, description="API key for the model provider")
    
    # Azure OpenAI specific fields
    azure_endpoint: Optional[str] = Field(default=None, description="Azure OpenAI endpoint URL")
    azure_deployment: Optional[str] = Field(default=None, description="Azure OpenAI deployment name")
    azure_api_version: str = Field(default="2025-03-01-preview", description="Azure OpenAI API version")
    azure_ad_token: Optional[str] = Field(default=None, description="Azure AD token")
    azure_ad_token_provider: Optional[str] = Field(default=None, description="Azure AD token provider")
    
    # Azure OpenAI embedding specific fields
    azure_embedding_deployment: Optional[str] = Field(default=None, description="Azure OpenAI embedding deployment name")
    azure_embedding_model: Optional[str] = Field(default=None, description="Azure OpenAI embedding model name")
    
    @validator('provider')
    def validate_provider(cls, v):
        allowed_providers = ["gemini", "openai", "anthropic", "azure", "azure_openai"]
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of {allowed_providers}")
        return v


class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration."""
    
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    ssl_mode: str = Field(default="prefer", description="SSL mode")
    ssl_cert_path: Optional[str] = Field(default=None, description="SSL certificate path")
    ssl_key_path: Optional[str] = Field(default=None, description="SSL key path")
    ssl_root_cert_path: Optional[str] = Field(default=None, description="SSL root certificate path")
    pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, le=100, description="Max pool overflow")
    pool_timeout: int = Field(default=30, ge=1, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=3600, ge=60, description="Pool recycle time in seconds")
    
    @validator('ssl_mode')
    def validate_ssl_mode(cls, v):
        allowed_modes = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
        if v not in allowed_modes:
            raise ValueError(f"SSL mode must be one of {allowed_modes}")
        return v
    
    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_connection_string(self) -> str:
        """Generate async PostgreSQL connection string."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def get_database_url(self) -> str:
        """Get the database URL for connections."""
        import urllib.parse
        encoded_password = urllib.parse.quote(self.password, safe='')
        return f"postgresql://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.database}"
    
    def get_connection_url(self) -> str:
        """Alias for get_database_url for compatibility."""
        return self.get_database_url()


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) configuration."""
    
    enabled: bool = Field(default=True, description="Enable MCP integration")
    server_url: str = Field(default="ws://localhost:3001", description="MCP server WebSocket URL")
    transport: str = Field(default="websocket", description="Transport type (websocket, stdio)")
    timeout: int = Field(default=30, ge=1, le=300, description="Connection timeout in seconds")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    reconnect_delay: int = Field(default=5, ge=1, le=60, description="Reconnect delay in seconds")
    max_message_size: int = Field(default=1048576, ge=1024, description="Max message size in bytes")
    tools_enabled: List[str] = Field(default_factory=list, description="List of enabled MCP tools")
    
    @validator('server_url')
    def validate_server_url(cls, v):
        if not v.startswith(("ws://", "wss://", "direct://", "stdio://")):
            raise ValueError("MCP server URL must start with ws://, wss://, direct://, or stdio://")
        return v


class AgentConfig(BaseModel):
    """Agent-specific configuration."""
    
    name: str = Field(default="BlitzAgent", description="Agent name")
    description: str = Field(
        default="AI agent for sports analytics and database insights",
        description="Agent description"
    )
    max_memory_messages: int = Field(default=100, ge=1, le=1000, description="Max messages in memory")
    memory_retention_days: int = Field(default=30, ge=1, le=365, description="Memory retention in days")
    memory_max_conversations: int = Field(default=1000, ge=1, le=10000, description="Max conversations in memory")
    session_timeout_minutes: int = Field(default=30, ge=1, le=1440, description="Session timeout in minutes")
    max_concurrent_sessions: int = Field(default=50, ge=1, le=1000, description="Max concurrent sessions")
    max_iterations: int = Field(default=10, ge=1, le=100, description="Maximum agent iterations")
    enable_reasoning: bool = Field(default=True, description="Enable reasoning mode")
    enable_streaming: bool = Field(default=True, description="Enable streaming responses")
    stream_reasoning: bool = Field(default=True, description="Stream reasoning steps")
    stream_intermediate_steps: bool = Field(default=True, description="Stream intermediate steps")
    show_reasoning_steps: bool = Field(default=True, description="Show reasoning steps")
    monitoring: bool = Field(default=True, description="Enable Agno monitoring")
    debug_mode: bool = Field(default=False, description="Enable debug mode")


class MonitoringConfig(BaseModel):
    """Monitoring and metrics configuration."""
    
    enabled: bool = Field(default=True, description="Enable monitoring")
    agno_monitor: bool = Field(default=True, description="Enable Agno cloud monitoring")
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=8000, ge=1024, le=65535, description="Prometheus metrics port")
    metrics_endpoint: str = Field(default="/metrics", description="Metrics endpoint path")
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json, text)")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    structured_logging: bool = Field(default=True, description="Enable structured logging")
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of {allowed_levels}")
        return v.upper()
    
    @validator('log_format')
    def validate_log_format(cls, v):
        allowed_formats = ["json", "text"]
        if v not in allowed_formats:
            raise ValueError(f"Log format must be one of {allowed_formats}")
        return v


class ServerConfig(BaseModel):
    """Web server configuration."""
    
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1024, le=65535, description="Server port")
    workers: int = Field(default=1, ge=1, le=16, description="Number of workers")
    auto_reload: bool = Field(default=False, description="Enable auto-reload")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080", "*"],
        description="CORS allowed origins"
    )
    cors_credentials: bool = Field(default=True, description="Allow CORS credentials")
    cors_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="CORS allowed methods"
    )
    cors_headers: List[str] = Field(
        default=["*"],
        description="CORS allowed headers"
    )
    max_request_size: int = Field(default=10485760, ge=1024, description="Max request size in bytes")
    timeout: int = Field(default=60, ge=1, le=300, description="Request timeout in seconds")


class SecurityConfig(BaseModel):
    """Security configuration."""
    
    jwt_secret_key: Optional[str] = Field(default=None, description="JWT secret key (optional)")
    api_key: Optional[str] = Field(default=None, description="API key for authentication (optional)")
    jwt_expiration_hours: int = Field(default=24, ge=1, le=8760, description="JWT expiration in hours")
    api_rate_limit: int = Field(default=100, ge=1, le=10000, description="API rate limit per minute")
    rate_limit_window_minutes: int = Field(default=1, ge=1, le=60, description="Rate limit window in minutes")
    force_https: bool = Field(default=False, description="Force HTTPS in production")
    
    @validator('jwt_secret_key')
    def validate_jwt_secret_key(cls, v):
        if v is not None and len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        return v


class SemanticRecallConfig(BaseModel):
    """Semantic recall configuration."""
    
    enabled: bool = Field(default=True, description="Enable semantic recall")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of similar messages to retrieve")
    message_range: int = Field(default=3, ge=0, le=10, description="Context messages around each match")
    scope: str = Field(default="resource", description="Search scope (thread, resource)")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model name")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    
    @validator('scope')
    def validate_scope(cls, v):
        allowed_scopes = ["thread", "resource"]
        if v not in allowed_scopes:
            raise ValueError(f"Scope must be one of {allowed_scopes}")
        return v


class VectorStoreConfig(BaseModel):
    """Vector store configuration."""
    
    provider: str = Field(default="pgvector", description="Vector store provider")
    table_name: str = Field(default="message_embeddings", description="Vector table name")
    dimension: int = Field(default=1536, ge=128, le=3072, description="Embedding dimension")
    
    @validator('provider')
    def validate_provider(cls, v):
        allowed_providers = ["pgvector", "chroma", "pinecone", "weaviate"]
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of {allowed_providers}")
        return v


class MemoryStorageConfig(BaseModel):
    """Memory storage configuration."""
    
    table_name: str = Field(default="agent_messages", description="Messages table name")
    cleanup_interval_hours: int = Field(default=24, ge=1, le=168, description="Cleanup interval in hours")
    max_message_age_days: int = Field(default=90, ge=1, le=365, description="Max message age in days")


class MemoryConfig(BaseModel):
    """Memory configuration."""
    
    enabled: bool = Field(default=True, description="Enable memory")
    semantic_recall: SemanticRecallConfig = Field(default_factory=SemanticRecallConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    storage: MemoryStorageConfig = Field(default_factory=MemoryStorageConfig)


class Config(BaseModel):
    """Main configuration class."""
    
    # Core configuration sections
    model: ModelConfig = Field(default_factory=ModelConfig)
    database: DatabaseConfig
    memory_database: Optional[DatabaseConfig] = Field(default=None, description="Separate database for memory storage")
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    memory: Optional[MemoryConfig] = Field(default=None, description="Memory configuration")
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    # Environment settings
    environment: str = Field(default="development", description="Environment (development, production, testing)")
    debug: bool = Field(default=True, description="Enable debug mode")
    
    @validator('environment')
    def validate_environment(cls, v):
        allowed_envs = ["development", "production", "testing"]
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of {allowed_envs}")
        return v
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Check for required API keys based on model provider
        if self.model.provider == "gemini" and not self.model.api_key:
            errors.append("Google API key is required for Gemini model")
        elif self.model.provider == "openai" and not self.model.api_key:
            errors.append("OpenAI API key is required for OpenAI model")
        elif self.model.provider == "anthropic" and not self.model.api_key:
            errors.append("Anthropic API key is required for Anthropic model")
        
        # Check database connection parameters
        if not self.database.host:
            errors.append("Database host is required")
        if not self.database.database:
            errors.append("Database name is required")
        if not self.database.user:
            errors.append("Database user is required")
        if not self.database.password:
            errors.append("Database password is required")
        
        # Check security configuration (if enabled)
        if self.security and self.security.jwt_secret_key and len(self.security.jwt_secret_key) < 32:
            errors.append("JWT secret key must be at least 32 characters long")
        
        return errors
    
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == "testing"


def load_config_from_file(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    
    if config_path is None:
        # Try default locations
        possible_paths = [
            Path("config/config.json"),
            Path("config.json"),
            Path("../config/config.json"),
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
        else:
            logger.warning("No configuration file found, using environment variables only")
            return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        logger.info("Configuration loaded from file", file_path=str(config_path))
        return config_data
    
    except FileNotFoundError:
        logger.warning("Configuration file not found", file_path=str(config_path))
        return {}
    
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in configuration file", file_path=str(config_path), error=str(e))
        raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    except Exception as e:
        logger.error("Error loading configuration file", file_path=str(config_path), error=str(e))
        raise


def merge_config_with_env(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge configuration data with environment variables."""
    
    # Environment variable mappings
    env_mappings = {
        # Model configuration (both formats supported)
        "GEMINI_API_KEY": "model.api_key",
        "MODEL__PROVIDER": "model.provider",
        "MODEL__NAME": "model.name",
        "MODEL__REASONING_MODEL": "model.reasoning_model",
        "MODEL__API_KEY": "model.api_key",
        "MODEL__AZURE_ENDPOINT": "model.azure_endpoint",
        "MODEL__AZURE_DEPLOYMENT": "model.azure_deployment",
        "MODEL__AZURE_API_VERSION": "model.azure_api_version",
        "MODEL__TEMPERATURE": "model.temperature",
        "MODEL__MAX_TOKENS": "model.max_tokens",
        "MODEL__STREAMING": "model.streaming",
        "MODEL__TOP_P": "model.top_p",
        "MODEL__TOP_K": "model.top_k",
        
        # Legacy model configuration
        "MODEL_PROVIDER": "model.provider",
        "MODEL_NAME": "model.name",
        "MODEL_TEMPERATURE": "model.temperature",
        "MODEL_MAX_TOKENS": "model.max_tokens",
        "MODEL_STREAMING": "model.streaming",
        
        # Database configuration (both formats supported)
        "DATABASE__HOST": "database.host",
        "DATABASE__PORT": "database.port",
        "DATABASE__DATABASE": "database.database",
        "DATABASE__USER": "database.user",
        "DATABASE__PASSWORD": "database.password",
        "DATABASE__SSL_MODE": "database.ssl_mode",
        "DATABASE__POOL_SIZE": "database.pool_size",
        "DATABASE__MAX_OVERFLOW": "database.max_overflow",
        "DATABASE__CONNECTION_TIMEOUT": "database.pool_timeout",
        
        # Legacy database configuration
        "POSTGRES_HOST": "database.host",
        "POSTGRES_PORT": "database.port",
        "POSTGRES_DATABASE": "database.database",
        "POSTGRES_USER": "database.user",
        "POSTGRES_PASSWORD": "database.password",
        "POSTGRES_SSL_MODE": "database.ssl_mode",
        "POSTGRES_POOL_SIZE": "database.pool_size",
        "POSTGRES_MAX_OVERFLOW": "database.max_overflow",
        
        # MCP configuration (both formats supported)
        "MCP__ENABLED": "mcp.enabled",
        "MCP__SERVER_URL": "mcp.server_url",
        "MCP__TRANSPORT": "mcp.transport",
        "MCP__TIMEOUT": "mcp.timeout",
        "MCP__RETRY_ATTEMPTS": "mcp.retry_attempts",
        
        # Legacy MCP configuration
        "MCP_ENABLED": "mcp.enabled",
        "MCP_SERVER_URL": "mcp.server_url",
        "MCP_TIMEOUT": "mcp.timeout",
        "MCP_RETRY_ATTEMPTS": "mcp.retry_attempts",
        
        # Agent configuration (both formats supported)
        "AGENT__NAME": "agent.name",
        "AGENT__DESCRIPTION": "agent.description",
        "AGENT__MAX_MEMORY_MESSAGES": "agent.max_memory_messages",
        "AGENT__ENABLE_REASONING": "agent.enable_reasoning",
        "AGENT__ENABLE_STREAMING": "agent.enable_streaming",
        "AGENT__STREAM_REASONING": "agent.stream_reasoning",
        "AGENT__MAX_CONVERSATION_LENGTH": "agent.max_memory_messages",
        "AGENT__MEMORY_RETENTION_DAYS": "agent.memory_retention_days",
        
        # Legacy agent configuration
        "AGENT_NAME": "agent.name",
        "AGENT_DESCRIPTION": "agent.description",
        "MAX_MEMORY_MESSAGES": "agent.max_memory_messages",
        "ENABLE_REASONING": "agent.enable_reasoning",
        
        # Monitoring configuration
        "PROMETHEUS_ENABLED": "monitoring.prometheus_enabled",
        "PROMETHEUS_PORT": "monitoring.prometheus_port",
        "LOG_LEVEL": "monitoring.log_level",
        
        # Server configuration
        "API_HOST": "server.host",
        "API_PORT": "server.port",
        "API_WORKERS": "server.workers",
        
        # Security configuration (both formats supported)
        "SECURITY__JWT_SECRET_KEY": "security.jwt_secret_key",
        "SECURITY__JWT_EXPIRATION_HOURS": "security.jwt_expiration_hours",
        "SECURITY__API_RATE_LIMIT": "security.api_rate_limit",
        "SECURITY__RATE_LIMIT_ENABLED": "security.api_rate_limit",
        "SECURITY__MAX_REQUESTS_PER_MINUTE": "security.api_rate_limit",
        
        # Legacy security configuration
        "JWT_SECRET_KEY": "security.jwt_secret_key",
        "JWT_EXPIRATION_HOURS": "security.jwt_expiration_hours",
        "API_RATE_LIMIT": "security.api_rate_limit",
        
        # Environment
        "ENVIRONMENT": "environment",
        "DEBUG": "debug",
    }
    
    # Apply environment variables
    for env_var, config_path in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value is not None:
            # Parse the value based on type
            try:
                # Try to parse as JSON first (handles booleans, numbers, etc.)
                parsed_value = json.loads(env_value.lower() if env_value.lower() in ['true', 'false'] else env_value)
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, use as string
                parsed_value = env_value
            
            # Set the value in config_data using dot notation
            keys = config_path.split('.')
            current = config_data
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = parsed_value
    
    return config_data


def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """
    Load and validate configuration from file and environment variables.
    
    Args:
        config_path: Path to configuration file. If None, searches for config.json
        
    Returns:
        Validated Config object
        
    Raises:
        ValueError: If configuration is invalid
        FileNotFoundError: If required configuration file is not found
    """
    
    logger.info("Loading BlitzAgent configuration")
    
    # Load from file
    config_data = load_config_from_file(config_path)
    
    # Merge with environment variables
    config_data = merge_config_with_env(config_data)
    
    try:
        # Create and validate config
        config = Config(**config_data)
        
        # Log configuration summary
        logger.info(
            "Configuration loaded successfully",
            environment=config.environment,
            model_provider=config.model.provider,
            model_name=config.model.name,
            database_host=config.database.host,
            mcp_enabled=config.mcp.enabled,
            prometheus_enabled=config.monitoring.prometheus_enabled,
        )
        
        return config
    
    except Exception as e:
        logger.error("Configuration validation failed", error=str(e))
        raise ValueError(f"Configuration validation failed: {e}")


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config


def reload_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """Reload configuration from file and environment variables."""
    global _config
    _config = load_config(config_path)
    return _config 