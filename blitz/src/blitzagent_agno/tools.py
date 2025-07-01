"""
Tool management and registry for BlitzAgent.

This module provides a comprehensive tool registry that integrates with MCP
and manages tool discovery, validation, and execution.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass
from functools import wraps
import inspect

from agno.tools import Function
from pydantic import BaseModel, Field

from .config import Config
from .mcp_client import MCPClient
from .exceptions import ToolError, ToolExecutionError, ToolRegistrationError
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Information about a registered tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    source: str  # 'mcp', 'local', 'agno'
    category: str
    enabled: bool = True
    rate_limit: Optional[int] = None
    timeout: Optional[float] = None


class ToolSchema(BaseModel):
    """Schema for tool definition."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: Dict[str, Any] = Field(..., description="Tool parameters schema")
    required: List[str] = Field(default_factory=list, description="Required parameters")
    category: str = Field(default="general", description="Tool category")


class ToolResult(BaseModel):
    """Result from tool execution."""
    success: bool = Field(..., description="Whether execution was successful")
    result: Any = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time: float = Field(..., description="Execution time in seconds")
    tool_name: str = Field(..., description="Name of executed tool")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


def tool_with_metrics(func: Callable) -> Callable:
    """Decorator to add metrics tracking to tool functions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        tool_name = func.__name__
        start_time = asyncio.get_event_loop().time()
        
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            # Track successful execution
            if hasattr(MetricsCollector, '_instance') and MetricsCollector._instance:
                MetricsCollector._instance.tool_executions.labels(
                    tool_name=tool_name, 
                    status="success"
                ).inc()
                MetricsCollector._instance.tool_execution_duration.labels(
                    tool_name=tool_name
                ).observe(execution_time)
            
            return ToolResult(
                success=True,
                result=result,
                execution_time=execution_time,
                tool_name=tool_name
            )
            
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            
            # Track failed execution
            if hasattr(MetricsCollector, '_instance') and MetricsCollector._instance:
                MetricsCollector._instance.tool_executions.labels(
                    tool_name=tool_name, 
                    status="error"
                ).inc()
                MetricsCollector._instance.tool_execution_duration.labels(
                    tool_name=tool_name
                ).observe(execution_time)
            
            logger.error(f"Tool {tool_name} execution failed: {str(e)}")
            
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
                tool_name=tool_name
            )
    
    return wrapper


class ToolRegistry:
    """Central registry for managing tools."""
    
    def __init__(self, config: Config, mcp_client: Optional[MCPClient] = None):
        self.config = config
        self.mcp_client = mcp_client
        self._tools: Dict[str, ToolInfo] = {}
        self._tool_functions: Dict[str, Callable] = {}
        self._categories: Dict[str, List[str]] = {}
        self._initialized = False
        
        logger.info("Initializing ToolRegistry")
    
    async def initialize(self) -> None:
        """Initialize the tool registry."""
        if self._initialized:
            return
        
        try:
            # Load local tools
            await self._load_local_tools()
            
            # Load MCP tools if client is available
            if self.mcp_client:
                await self._load_mcp_tools()
            
            # Load Agno built-in tools
            await self._load_agno_tools()
            
            self._initialized = True
            logger.info(f"ToolRegistry initialized with {len(self._tools)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize ToolRegistry: {str(e)}")
            raise ToolRegistrationError(f"Tool registry initialization failed: {str(e)}")
    
    async def _load_local_tools(self) -> None:
        """Load local tool implementations."""
        # Database tools
        await self._register_tool(
            name="query_database",
            description="Execute SQL queries on the sports database",
            parameters={
                "query": {"type": "string", "description": "SQL query to execute"},
                "limit": {"type": "integer", "description": "Maximum rows to return", "default": 100}
            },
            function=self._query_database,
            category="database",
            source="local"
        )
        
        # Analysis tools
        await self._register_tool(
            name="analyze_player_stats",
            description="Analyze player statistics and performance",
            parameters={
                "player_name": {"type": "string", "description": "Player name"},
                "season": {"type": "string", "description": "Season year"},
                "metrics": {"type": "array", "description": "Metrics to analyze"}
            },
            function=self._analyze_player_stats,
            category="analysis",
            source="local"
        )
        
        # Search tools
        await self._register_tool(
            name="search_games",
            description="Search for games by criteria",
            parameters={
                "team": {"type": "string", "description": "Team name"},
                "date_range": {"type": "object", "description": "Date range"},
                "league": {"type": "string", "description": "League (MLB, NBA, etc.)"}
            },
            function=self._search_games,
            category="search",
            source="local"
        )
    
    async def _load_mcp_tools(self) -> None:
        """Load tools from MCP server."""
        if not self.mcp_client or not self.mcp_client.connected:
            logger.warning("MCP client not available or not connected")
            return
        
        try:
            # Get available tools from MCP
            tools_info = await self.mcp_client.list_tools()
            
            for tool_info in tools_info:
                await self._register_mcp_tool(tool_info)
                
            logger.info(f"Loaded {len(tools_info)} tools from MCP")
            
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {str(e)}")
    
    async def _load_agno_tools(self) -> None:
        """Load Agno built-in tools."""
        # This would integrate with Agno's tool system
        # For now, we'll register some common tools
        
        await self._register_tool(
            name="web_search",
            description="Search the web for information",
            parameters={
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Number of results", "default": 5}
            },
            function=self._web_search,
            category="web",
            source="agno"
        )
    
    async def _register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        function: Callable,
        category: str = "general",
        source: str = "local",
        rate_limit: Optional[int] = None,
        timeout: Optional[float] = None
    ) -> None:
        """Register a tool in the registry."""
        if name in self._tools:
            logger.warning(f"Tool {name} already registered, overwriting")
        
        tool_info = ToolInfo(
            name=name,
            description=description,
            parameters=parameters,
            source=source,
            category=category,
            rate_limit=rate_limit,
            timeout=timeout
        )
        
        self._tools[name] = tool_info
        self._tool_functions[name] = tool_with_metrics(function)
        
        # Update categories
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(name)
        
        logger.debug(f"Registered tool: {name} (category: {category}, source: {source})")
    
    async def _register_mcp_tool(self, tool_info: Dict[str, Any]) -> None:
        """Register a tool from MCP server."""
        name = tool_info.get("name")
        if not name:
            logger.warning("MCP tool missing name, skipping")
            return
        
        async def mcp_tool_wrapper(**kwargs):
            """Wrapper for MCP tool execution."""
            return await self.mcp_client.call_tool(name, kwargs)
        
        await self._register_tool(
            name=name,
            description=tool_info.get("description", "MCP tool"),
            parameters=tool_info.get("inputSchema", {}).get("properties", {}),
            function=mcp_tool_wrapper,
            category="mcp",
            source="mcp"
        )
    
    async def execute_tool(
        self,
        name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute a tool by name."""
        if not self._initialized:
            await self.initialize()
        
        if name not in self._tools:
            raise ToolError(f"Tool '{name}' not found")
        
        tool_info = self._tools[name]
        if not tool_info.enabled:
            raise ToolError(f"Tool '{name}' is disabled")
        
        parameters = parameters or {}
        
        try:
            # Validate parameters
            await self._validate_parameters(name, parameters)
            
            # Execute tool
            tool_func = self._tool_functions[name]
            result = await tool_func(**parameters)
            
            logger.debug(f"Tool {name} executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {str(e)}")
            raise ToolExecutionError(f"Tool '{name}' execution failed: {str(e)}")
    
    async def _validate_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> None:
        """Validate tool parameters."""
        tool_info = self._tools[tool_name]
        tool_params = tool_info.parameters
        
        # Check required parameters
        required = [k for k, v in tool_params.items() if v.get("required", False)]
        missing = [k for k in required if k not in parameters]
        
        if missing:
            raise ToolError(f"Missing required parameters for {tool_name}: {missing}")
        
        # Validate parameter types (basic validation)
        for param, value in parameters.items():
            if param in tool_params:
                expected_type = tool_params[param].get("type")
                if expected_type and not self._validate_type(value, expected_type):
                    raise ToolError(f"Invalid type for parameter {param} in {tool_name}")
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate parameter type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected = type_mapping.get(expected_type)
        if expected:
            return isinstance(value, expected)
        return True
    
    def get_tool_info(self, name: str) -> Optional[ToolInfo]:
        """Get information about a tool."""
        return self._tools.get(name)
    
    def list_tools(
        self,
        category: Optional[str] = None,
        source: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[ToolInfo]:
        """List available tools."""
        tools = list(self._tools.values())
        
        if category:
            tools = [t for t in tools if t.category == category]
        
        if source:
            tools = [t for t in tools if t.source == source]
        
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        
        return tools
    
    def get_categories(self) -> List[str]:
        """Get all tool categories."""
        return list(self._categories.keys())
    
    def get_enabled_tools(self) -> List[ToolInfo]:
        """Get all enabled tools."""
        return [tool for tool in self._tools.values() if tool.enabled]
    
    async def enable_tool(self, name: str) -> None:
        """Enable a tool."""
        if name in self._tools:
            self._tools[name].enabled = True
            logger.info(f"Enabled tool: {name}")
        else:
            raise ToolError(f"Tool '{name}' not found")
    
    async def disable_tool(self, name: str) -> None:
        """Disable a tool."""
        if name in self._tools:
            self._tools[name].enabled = False
            logger.info(f"Disabled tool: {name}")
        else:
            raise ToolError(f"Tool '{name}' not found")
    
    # Tool implementations
    async def _query_database(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Query the sports database."""
        # This would integrate with the actual database
        logger.info(f"Executing database query: {query[:100]}...")
        
        # Placeholder implementation
        return {
            "query": query,
            "rows_affected": 0,
            "results": [],
            "execution_time": 0.1
        }
    
    async def _analyze_player_stats(
        self,
        player_name: str,
        season: str,
        metrics: List[str]
    ) -> Dict[str, Any]:
        """Analyze player statistics."""
        logger.info(f"Analyzing stats for {player_name} in {season}")
        
        # Placeholder implementation
        return {
            "player": player_name,
            "season": season,
            "metrics": metrics,
            "analysis": {},
            "insights": []
        }
    
    async def _search_games(
        self,
        team: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
        league: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for games."""
        logger.info(f"Searching games for team: {team}, league: {league}")
        
        # Placeholder implementation
        return {
            "team": team,
            "league": league,
            "date_range": date_range,
            "games": [],
            "total_found": 0
        }
    
    async def _web_search(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """Search the web."""
        logger.info(f"Web search: {query}")
        
        # Placeholder implementation
        return {
            "query": query,
            "num_results": num_results,
            "results": [],
            "search_time": 0.2
        }
    
    def to_agno_tools(self) -> List[Function]:
        """Convert registered tools to Agno Function objects."""
        agno_functions = []
        
        for name, tool_info in self._tools.items():
            if not tool_info.enabled:
                continue
            
            # Create Agno Function
            function = Function(
                name=name,
                description=tool_info.description,
                func=self._tool_functions[name]
            )
            agno_functions.append(function)
        
        return agno_functions
    
    def get_agno_tools(self) -> List[Function]:
        """Get tools formatted for Agno agent."""
        return self.to_agno_tools()


# Global tool registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry(
    config: Optional[Config] = None,
    mcp_client: Optional[MCPClient] = None
) -> ToolRegistry:
    """Get or create the global tool registry."""
    global _tool_registry
    
    if _tool_registry is None:
        if config is None:
            raise ValueError("Config required for first-time registry creation")
        _tool_registry = ToolRegistry(config, mcp_client)
    
    return _tool_registry


async def initialize_tools(
    config: Config,
    mcp_client: Optional[MCPClient] = None
) -> ToolRegistry:
    """Initialize the global tool registry."""
    registry = get_tool_registry(config, mcp_client)
    await registry.initialize()
    return registry 