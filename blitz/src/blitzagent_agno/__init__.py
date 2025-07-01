"""
BlitzAgent-Agno

A powerful AI agent built with the Agno framework for sports analytics and database insights.
Features Gemini 2.5 Pro reasoning model with streaming capabilities, PostgreSQL memory integration,
Python MCP connectivity, structured outputs, and comprehensive metrics.
"""

__version__ = "0.1.0"
__author__ = "BlitzAgent Team"
__email__ = "team@blitzagent.com"
__description__ = "BlitzAgent built with Agno framework - Single agent with Gemini 2.5 Pro reasoning, PostgreSQL memory, Python MCP integration, structured output, and metrics"

# Core imports
from .agent import BlitzAgent, create_agent, agent_context
from .config import Config
from .memory import AgentMemory
from .metrics import MetricsCollector
from .mcp_client import MCPClient
from .tools import ToolRegistry
from .exceptions import (
    BlitzAgentError,
    ConfigurationError,
    MemoryError,
    MCPError,
    ModelError,
    MetricsError,
)

# Version info
version_info = tuple(map(int, __version__.split(".")))

__all__ = [
    # Core classes
    "BlitzAgent",
    "create_agent",
    "agent_context",
    "AgentMemory",
    "MetricsCollector",
    "MCPClient",
    "ToolRegistry",
    
    # Configuration
    "Config",
    
    # Exceptions
    "BlitzAgentError",
    "ConfigurationError",
    "MemoryError",
    "MCPError",
    "ModelError",
    "MetricsError",
    
    # Metadata
    "__version__",
    "version_info",
]

# Package-level constants
DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 4096
DEFAULT_STREAM = True

# Logging setup
import logging
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Get package logger
logger = structlog.get_logger(__name__)

# Package initialization
logger.info(
    "BlitzAgent-Agno initialized",
    version=__version__,
    default_model=DEFAULT_MODEL,
    components=[
        "BlitzAgent",
        "AgentMemory", 
        "MCPClient",
        "MetricsCollector",
        "ToolRegistry"
    ]
) 