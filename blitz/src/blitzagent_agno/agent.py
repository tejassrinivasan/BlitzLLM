"""
BlitzAgent - Advanced AI Agent with Reasoning and Memory

This module implements the main BlitzAgent class using the Agno framework,
featuring Gemini 2.5 Pro reasoning model, PostgreSQL memory, MCP integration,
structured output, and comprehensive metrics collection.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Type, Union, get_type_hints
from contextlib import asynccontextmanager
from pathlib import Path
from dataclasses import dataclass

import structlog
from agno.agent import Agent
from agno.models.google import Gemini
from agno.models.azure import AzureOpenAI
# from agno.models.anthropic import Claude  # Removed - not using anthropic
# from agno.models.groq import Groq  # Removed - not using groq
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.db.postgres import PostgresMemoryDb
from agno.memory.v2.memory import Memory as AgnoMemory
from agno.tools.reasoning import ReasoningTools
from agno.tools.mcp import MCPTools
from pydantic import BaseModel
from pathlib import Path

from .config import Config
from .memory import AgentMemory
from .semantic_memory import SemanticMemory
from .metrics import MetricsCollector
from .tools import ToolRegistry
from .exceptions import BlitzAgentError, ConfigurationError
from .models import SportsAnalysisResponse
from .agent_factory import get_agent_instructions, AgentType, RuntimeContext, RuntimeMode, ToneStyle

# Create AgentError as alias for consistency
AgentError = BlitzAgentError


logger = structlog.get_logger(__name__)


class AgentResponse(BaseModel):
    """Structured response from the agent."""
    
    content: str
    reasoning_steps: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    timestamp: datetime
    duration_ms: int
    token_usage: Dict[str, int] = {}
    
    class Config:
        arbitrary_types_allowed = True


class StreamingResponse:
    """Streaming response handler for real-time agent output."""
    
    def __init__(self, agent_response: Any, show_reasoning: bool = False):
        self.agent_response = agent_response
        self.show_reasoning = show_reasoning
        self.content_chunks: List[str] = []
        self.reasoning_chunks: List[str] = []
        
    async def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        """Async iterator for streaming chunks."""
        try:
            # Check if agent_response is iterable (for streaming)
            if hasattr(self.agent_response, '__iter__') or hasattr(self.agent_response, '__aiter__'):
                if hasattr(self.agent_response, '__aiter__'):
                    # Async iterator
                    async for chunk in self.agent_response:
                        # Extract content from Agno event objects
                        content = self._extract_content_from_chunk(chunk)
                        
                        if content:
                            chunk_data = {
                                "type": "content",
                                "data": content,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            
                            # Handle reasoning steps if enabled
                            reasoning = self._extract_reasoning_from_chunk(chunk)
                            if self.show_reasoning and reasoning:
                                chunk_data["reasoning"] = reasoning
                                self.reasoning_chunks.append(reasoning)
                            
                            self.content_chunks.append(content)
                            yield chunk_data
                else:
                    # Regular iterator
                    for chunk in self.agent_response:
                        # Extract content from Agno event objects
                        content = self._extract_content_from_chunk(chunk)
                        
                        if content:
                            chunk_data = {
                                "type": "content",
                                "data": content,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            
                            # Handle reasoning steps if enabled
                            reasoning = self._extract_reasoning_from_chunk(chunk)
                            if self.show_reasoning and reasoning:
                                chunk_data["reasoning"] = reasoning
                                self.reasoning_chunks.append(reasoning)
                            
                            self.content_chunks.append(content)
                            yield chunk_data
            else:
                # Not iterable, treat as single response
                content = str(self.agent_response.content) if hasattr(self.agent_response, 'content') else str(self.agent_response)
                chunk_data = {
                    "type": "content",
                    "data": content,
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.content_chunks.append(content)
                yield chunk_data
        except Exception as e:
            # Fallback for any iteration issues
            content = str(self.agent_response.content) if hasattr(self.agent_response, 'content') else str(self.agent_response)
            chunk_data = {
                "type": "content",
                "data": content,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
            self.content_chunks.append(content)
            yield chunk_data
    
    def _extract_content_from_chunk(self, chunk) -> Optional[str]:
        """Extract content from Agno event chunk."""
        # Handle different Agno event types
        if hasattr(chunk, 'content') and chunk.content:
            return str(chunk.content)
        elif hasattr(chunk, 'event'):
            # Check for RunResponseContent events
            if chunk.event == 'RunResponseContent' and hasattr(chunk, 'content'):
                return str(chunk.content)
        
        return None
    
    def _extract_reasoning_from_chunk(self, chunk) -> Optional[str]:
        """Extract reasoning from Agno event chunk."""
        if hasattr(chunk, 'reasoning_content') and chunk.reasoning_content:
            return str(chunk.reasoning_content)
        elif hasattr(chunk, 'content') and hasattr(chunk.content, 'reasoning'):
            return str(chunk.content.reasoning)
        
        return None
    
    @property
    def full_content(self) -> str:
        """Get the complete content from all chunks."""
        return "".join(self.content_chunks)
    
    @property
    def reasoning_stream(self) -> List[str]:
        """Get all reasoning steps."""
        return self.reasoning_chunks


class BlitzAgent:
    """
    Advanced AI Agent powered by Agno framework.
    
    Features:
    - Gemini 2.5 Pro reasoning model with streaming
    - PostgreSQL memory integration
    - Python MCP connectivity
    - Structured output with Pydantic
    - Real-time metrics and monitoring
    """
    
    def __init__(self, config: Optional[Config] = None, context: Optional[RuntimeContext] = None):
        """Initialize the BlitzAgent."""
        from .config import load_config
        self.config = config or load_config()
        self.context = context or RuntimeContext(mode=RuntimeMode.CONVERSATION, tone=ToneStyle.PROFESSIONAL)
        self.metrics = MetricsCollector()
        
        # Validate configuration
        errors = self.config.validate_config()
        if errors:
            raise ConfigurationError(f"Configuration errors: {', '.join(errors)}")
        
        # Initialize components
        self._memory: Optional[AgentMemory] = None
        self._semantic_memory: Optional[SemanticMemory] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._agent: Optional[Agent] = None
        
        # MCP command info for agent initialization
        self._mcp_command: Optional[str] = None
        self._mcp_args: Optional[List[str]] = None
        
        # Setup logging
        self.logger = logger.bind(agent_name=self.config.agent.name)
        
        self.logger.info(
            "Initializing BlitzAgent",
            model=self.config.model.name,
            reasoning_model=self.config.model.reasoning_model,
            database=self.config.database.host,
            mcp_url=self.config.mcp.server_url
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
    
    async def initialize(self) -> None:
        """Initialize all agent components."""
        try:
            start_time = time.time()
            
            # Initialize memory first
            await self._initialize_memory()
            
            # Initialize semantic memory
            await self._initialize_semantic_memory()
            
            # Initialize tool registry
            await self._initialize_tools()
            
            # Initialize the main agent
            await self._initialize_agent()
            
            initialization_time = (time.time() - start_time) * 1000
            self.metrics.record_initialization_time(initialization_time)
            
            self.logger.info(
                "BlitzAgent initialized successfully",
                initialization_time_ms=initialization_time
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize BlitzAgent", error=str(e))
            raise BlitzAgentError(f"Initialization failed: {e}") from e
    
    async def _initialize_memory(self) -> None:
        """Initialize PostgreSQL memory."""
        try:
            self._memory = AgentMemory(
                connection_url=self.config.database.get_database_url(),
                retention_days=self.config.agent.memory_retention_days,
                max_conversations=self.config.agent.memory_max_conversations
            )
            await self._memory.initialize()
            
            self.logger.info("Memory initialized", backend="postgresql")
            
        except Exception as e:
            self.logger.error("Failed to initialize memory", error=str(e))
            raise
    
    async def _initialize_semantic_memory(self) -> None:
        """Initialize semantic memory with pgvector."""
        try:
            if self.config.memory and self.config.memory.enabled:
                self._semantic_memory = SemanticMemory(self.config)
                await self._semantic_memory.initialize()
                
                self.logger.info(
                    "Semantic memory initialized",
                    enabled=self.config.memory.enabled,
                    semantic_recall=self.config.memory.semantic_recall.enabled,
                    database=self.config.memory_database.database if self.config.memory_database else self.config.database.database
                )
            else:
                self.logger.info("Semantic memory disabled")
                
        except Exception as e:
            self.logger.error("Failed to initialize semantic memory", error=str(e))
            # Don't raise - allow agent to continue without semantic memory
            self._semantic_memory = None
    
    async def _initialize_tools(self) -> None:
        """Initialize tool registry with MCP tools."""
        try:
            # Initialize tool registry - tools are now handled directly in agent initialization
            self._tool_registry = ToolRegistry(self.config, None)  # No longer need MCP client
            
            # Store MCP command for agent initialization
            self._mcp_command = "uvx"
            self._mcp_args = ["--from", "git+https://github.com/tejassrinivasan/BlitzLLM.git#subdirectory=mcp", "blitz-agent-mcp"]
            
            self.logger.info(
                "Tool registry initialized",
                mcp_command=f"{self._mcp_command} {' '.join(self._mcp_args)}"
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize tools", error=str(e))
            raise
    
    async def _create_agno_storage_table(self, db_url: str) -> None:
        """Create the Agno storage table with correct schema."""
        try:
            import asyncpg
            
            # Parse the database URL
            conn = await asyncpg.connect(db_url)
            
            # Create the sessions table for Agno storage
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS blitz_agent_sessions (
                session_id VARCHAR(255) PRIMARY KEY,
                agent_id VARCHAR(255) NOT NULL,
                user_id VARCHAR(255),
                memory JSONB DEFAULT '{}',
                agent_data JSONB DEFAULT '{}',
                user_data JSONB DEFAULT '{}',
                session_data JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_blitz_agent_sessions_agent_id ON blitz_agent_sessions(agent_id);
            CREATE INDEX IF NOT EXISTS idx_blitz_agent_sessions_user_id ON blitz_agent_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_blitz_agent_sessions_created_at ON blitz_agent_sessions(created_at);
            """
            
            await conn.execute(create_table_sql)
            await conn.close()
            
            self.logger.info("Agno storage table created successfully")
            
        except Exception as e:
            self.logger.error("Failed to create Agno storage table", error=str(e))
            # Don't raise - let Agno try to create it
    
    async def _initialize_agent(self) -> None:
        """Initialize the main Agno agent with tools and configuration."""
        try:
            # MCP command already set in _initialize_tools() - don't overwrite it
            # mcp_path = Path(__file__).parent.parent.parent.parent / "mcp"
            # self._mcp_command = f"{mcp_path}/start.sh"  # DON'T OVERWRITE uvx command!
            
            # Setup model based on provider
            if self.config.model.provider == "gemini":
                from agno.models.gemini import Gemini
                model = Gemini(
                    id=self.config.model.name,
                    api_key=self.config.model.api_key,
                    temperature=self.config.model.temperature,
                    max_tokens=self.config.model.max_tokens,
                    top_p=self.config.model.top_p,
                    top_k=self.config.model.top_k
                )
            elif self.config.model.provider == "azure_openai":
                from agno.models.azure import AzureOpenAI
                model = AzureOpenAI(
                    id=self.config.model.name,
                    api_key=self.config.model.api_key,
                    azure_endpoint=self.config.model.azure_endpoint,
                    azure_deployment=self.config.model.azure_deployment,
                    api_version=self.config.model.azure_api_version,
                    temperature=0.1,
                    max_tokens=self.config.model.max_tokens
                )
            else:
                raise ValueError(f"Unsupported model provider: {self.config.model.provider}")
            
            # Setup reasoning model if dual model is enabled
            reasoning_model = None
            if self.config.model.enable_dual_model and self.config.model.reasoning_provider:
                if self.config.model.reasoning_provider == "azure_openai":
                    reasoning_model = AzureOpenAI(
                        id=self.config.model.reasoning_model_name or "gpt-4o",
                        api_key=self.config.model.reasoning_api_key,
                        azure_endpoint=self.config.model.reasoning_azure_endpoint,
                        azure_deployment=self.config.model.reasoning_azure_deployment,
                        api_version=self.config.model.azure_api_version,
                        temperature=0.1,
                        max_tokens=1024
                    )
                elif self.config.model.reasoning_provider == "gemini":
                    reasoning_model = Gemini(
                        id=self.config.model.reasoning_model_name or "gemini-2.5-pro",
                        api_key=self.config.model.reasoning_api_key,
                        temperature=0.1,
                        top_p=0.95
                    )
                
                self.logger.info(
                    "Dual model configuration enabled",
                    response_model=self.config.model.name,
                    reasoning_model=self.config.model.reasoning_model_name,
                    reasoning_provider=self.config.model.reasoning_provider
                )
            
            # Setup storage for Agno
            storage_db_url = (
                self.config.memory_database.get_connection_url() 
                if self.config.memory_database 
                else self.config.database.get_connection_url()
            )
            
            # Create storage table manually first
            await self._create_agno_storage_table(storage_db_url)
            
            storage = PostgresStorage(
                db_url=storage_db_url,
                table_name="blitz_agent_sessions",
                auto_upgrade_schema=True
            )
            
            # Setup memory for Agno
            memory_db_url = (
                self.config.memory_database.get_connection_url() 
                if self.config.memory_database 
                else self.config.database.get_connection_url()
            )
            
            memory_db = PostgresMemoryDb(
                table_name="agno_memories",
                db_url=memory_db_url
            )
            agno_memory = AgnoMemory(
                db=memory_db
            )
            
            # Prepare tools
            tools = [ReasoningTools(add_instructions=True)]
            
            # Add MCP tools if command is available
            if hasattr(self, '_mcp_command') and self._mcp_command:
                try:
                    # Use Agno's MCPTools with the uvx command and proper timeout
                    from mcp import StdioServerParameters
                    import os
                    
                    # Use current environment and override with database config
                    mcp_env = os.environ.copy()
                    
                    # Set both NBA and MLB database configuration for multi-league support
                    # NBA configuration
                    mcp_env.update({
                        "POSTGRES_NBA_HOST": self.config.database.host,
                        "POSTGRES_NBA_PORT": str(self.config.database.port),
                        "POSTGRES_NBA_DATABASE": "nba",  # NBA database name
                        "POSTGRES_NBA_USER": self.config.database.user,
                        "POSTGRES_NBA_PASSWORD": self.config.database.password,
                        "POSTGRES_NBA_SSL": "true",
                    })
                    
                    # MLB configuration  
                    mcp_env.update({
                        "POSTGRES_MLB_HOST": self.config.database.host,
                        "POSTGRES_MLB_PORT": str(self.config.database.port),
                        "POSTGRES_MLB_DATABASE": "mlb",  # MLB database name
                        "POSTGRES_MLB_USER": self.config.database.user,
                        "POSTGRES_MLB_PASSWORD": self.config.database.password,
                        "POSTGRES_MLB_SSL": "true",
                    })
                    
                    # Set general postgres config for fallback - use NBA as default for now
                    mcp_env.update({
                        "POSTGRES_HOST": self.config.database.host,
                        "POSTGRES_PORT": str(self.config.database.port),
                        "POSTGRES_DATABASE": "nba",  # Default to NBA database
                        "POSTGRES_USER": self.config.database.user,
                        "POSTGRES_PASSWORD": self.config.database.password,
                        "POSTGRES_SSL": self.config.database.ssl_mode,  # Use actual ssl_mode from config
                    })
                    
                    server_params = StdioServerParameters(
                        command=self._mcp_command,
                        args=self._mcp_args,
                        read_timeout_seconds=60,  # Increased timeout for GitHub Actions environment
                        env=mcp_env  # Pass environment variables
                    )
                    
                    # Create MCP tools and initialize properly as context manager
                    try:
                        print(f"🔧 Initializing MCP tools as context manager with timeout {self.config.mcp.timeout}s...")
                        
                        mcp_tools = MCPTools(
                            server_params=server_params,
                            timeout_seconds=self.config.mcp.timeout
                        )
                        
                        # Initialize the session properly
                        await mcp_tools.__aenter__()
                        print("✅ MCP context manager initialized")
                        
                        # Now try to get tools list
                        try:
                            # Try the correct method name for listing tools
                            if hasattr(mcp_tools, 'get_tools'):
                                tools_list = await mcp_tools.get_tools()
                            elif hasattr(mcp_tools, 'list_tools'):
                                tools_list = await mcp_tools.list_tools()
                            else:
                                tools_list = []
                                print("❓ No list_tools or get_tools method found")
                                
                            if tools_list:
                                print(f"✅ MCP tools loaded successfully! Found {len(tools_list)} tools:")
                                for tool in tools_list[:5]:  # Show first 5
                                    name = getattr(tool, 'name', str(tool))
                                    print(f"   - {name}")
                            else:
                                print("❌ No MCP tools found")
                                
                        except Exception as list_error:
                            print(f"❌ Failed to list MCP tools: {list_error}")
                            
                        tools.append(mcp_tools)
                        
                    except Exception as init_error:
                        print(f"❌ MCP context manager initialization failed: {init_error}")
                        # Fallback to regular initialization
                        mcp_tools = MCPTools(
                            server_params=server_params,
                            timeout_seconds=self.config.mcp.timeout
                        )
                        tools.append(mcp_tools)
                        print("🔄 Using fallback MCP initialization")
                    self.logger.info(
                        "MCP tools added to agent", 
                        command=f"{self._mcp_command} {' '.join(self._mcp_args)}", 
                        timeout=self.config.mcp.timeout
                    )
                except Exception as e:
                    self.logger.error("Failed to add MCP tools", error=str(e))
                    # Also print to console for debugging
                    print(f"❌ MCP INITIALIZATION FAILED: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Add any additional tools from registry
            if self._tool_registry:
                additional_tools = self._tool_registry.get_agno_tools()
                if additional_tools:
                    tools.extend(additional_tools)
            
            # Create the agent with optional reasoning model
            agent_params = {
                "model": model,
                "memory": agno_memory,
                "storage": storage,
                "tools": tools,
                "description": self.config.agent.description,
                "monitoring": self.config.agent.monitoring,
                "debug_mode": self.config.agent.debug_mode or self.config.monitoring.debug_mode,
                "show_tool_calls": True,
                "instructions": "You are a helpful assistant.",  # Minimal to avoid context overflow
                "markdown": True,
                "add_history_to_messages": False,  # Disable history to save context
                "num_history_responses": 0        # No history to avoid context overflow
            }
            
            # Add reasoning model if configured
            if reasoning_model:
                agent_params["reasoning_model"] = reasoning_model
            
            self._agent = Agent(**agent_params)
            
            self.logger.info(
                "Agno agent initialized",
                model=self.config.model.reasoning_model,
                tools_count=len(tools),
                memory_enabled=True,
                storage_enabled=True,
                semantic_memory_enabled=bool(self._semantic_memory)
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize Agno agent", error=str(e))
            raise
    
    async def run(
        self,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        stream: bool = None,
        show_reasoning: bool = None,
        **kwargs
    ) -> Union[AgentResponse, StreamingResponse]:
        """
        Run the agent with a message and return response.
        
        Args:
            message: The input message/query
            user_id: Optional user identifier
            session_id: Optional session identifier
            stream: Enable streaming (defaults to config setting)
            show_reasoning: Show reasoning steps (defaults to config setting)
            **kwargs: Additional parameters for the agent
            
        Returns:
            AgentResponse or StreamingResponse depending on streaming setting
        """
        if not self._agent:
            raise AgentError("Agent not initialized. Call initialize() first.")
        
        # Use config defaults if not specified
        stream = stream if stream is not None else self.config.agent.enable_streaming
        show_reasoning = show_reasoning if show_reasoning is not None else self.config.agent.stream_reasoning
        
        start_time = time.time()
        self.metrics.increment_query_count()
        
        try:
            # Store conversation in memory if user_id provided
            if user_id and self._memory:
                await self._memory.store_conversation(
                    user_id=user_id,
                    message=message,
                    session_id=session_id
                )
            
            # Store message in semantic memory and perform semantic recall
            if self._semantic_memory:
                try:
                    # Store the user message
                    await self._semantic_memory.store_message(
                        content=message,
                        role="user",
                        user_id=user_id,
                        session_id=session_id,
                        resource_id=user_id  # Use user_id as resource_id for cross-session recall
                    )
                    
                    # Perform semantic recall to get relevant context
                    semantic_matches = await self._semantic_memory.semantic_recall(
                        query=message,
                        user_id=user_id,
                        session_id=session_id,
                        resource_id=user_id
                    )
                    
                    # Add semantic context to agent parameters if matches found
                    if semantic_matches:
                        semantic_context = self._format_semantic_context(semantic_matches)
                        # Add to agent instructions or context
                        kwargs["semantic_context"] = semantic_context
                        
                        self.logger.info(
                            "Semantic recall completed",
                            matches_found=len(semantic_matches),
                            user_id=user_id
                        )
                        
                except Exception as e:
                    self.logger.warning("Semantic recall failed", error=str(e))
            
            # Prepare agent parameters
            agent_params = {
                "stream": stream,
                "show_full_reasoning": show_reasoning,
                "stream_intermediate_steps": self.config.agent.stream_intermediate_steps,
                **kwargs
            }
            
            self.logger.info(
                "Running agent",
                message_length=len(message),
                user_id=user_id,
                session_id=session_id,
                stream=stream,
                show_reasoning=show_reasoning
            )
            
            # Run the agent
            if stream:
                # Return streaming response
                response = await self._agent.arun(message, **agent_params)
                return StreamingResponse(response, show_reasoning=show_reasoning)
            else:
                # Return complete response
                response = await self._agent.arun(message, **agent_params)
                
                # Create structured response
                duration_ms = int((time.time() - start_time) * 1000)
                
                agent_response = AgentResponse(
                    content=str(response.content) if hasattr(response, 'content') else str(response),
                    reasoning_steps=getattr(response, 'reasoning_steps', []),
                    tool_calls=getattr(response, 'tool_calls', []),
                    metadata={
                        "user_id": user_id,
                        "session_id": session_id,
                        "model": self.config.model.reasoning_model
                    },
                    timestamp=datetime.utcnow(),
                    duration_ms=duration_ms,
                    token_usage=getattr(response, 'usage', {})
                )
                
                # Store response in memory
                if user_id and self._memory:
                    await self._memory.store_conversation(
                        user_id=user_id,
                        message=agent_response.content,
                        session_id=session_id,
                        is_agent_response=True
                    )
                
                # Store assistant response in semantic memory
                if self._semantic_memory and user_id:
                    try:
                        await self._semantic_memory.store_message(
                            content=agent_response.content,
                            role="assistant",
                            user_id=user_id,
                            session_id=session_id,
                            resource_id=user_id,
                            metadata={
                                "duration_ms": duration_ms,
                                "token_usage": agent_response.token_usage,
                                "reasoning_steps": len(agent_response.reasoning_steps),
                                "tool_calls": len(agent_response.tool_calls)
                            }
                        )
                    except Exception as e:
                        self.logger.warning("Failed to store assistant response in semantic memory", error=str(e))
                
                # Record metrics
                self.metrics.record_response_time(duration_ms)
                if agent_response.token_usage:
                    self.metrics.record_token_usage(agent_response.token_usage)
                
                self.logger.info(
                    "Agent response completed",
                    duration_ms=duration_ms,
                    content_length=len(agent_response.content),
                    reasoning_steps=len(agent_response.reasoning_steps),
                    tool_calls=len(agent_response.tool_calls)
                )
                
                return agent_response
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.metrics.increment_error_count()
            self.metrics.record_response_time(duration_ms)
            
            self.logger.error(
                "Agent execution failed",
                error=str(e),
                duration_ms=duration_ms,
                message_length=len(message)
            )
            
            raise AgentError(f"Agent execution failed: {e}") from e
    
    def _format_semantic_context(self, semantic_matches) -> str:
        """Format semantic matches into context for the agent."""
        if not semantic_matches:
            return ""
        
        context_parts = ["## Relevant Context from Previous Conversations:"]
        
        for i, match in enumerate(semantic_matches[:3], 1):  # Limit to top 3 matches
            context_parts.append(f"\n### Context {i} (similarity: {match.similarity:.2f}):")
            context_parts.append(f"**{match.message.role.title()}:** {match.message.content}")
            
            # Add context messages if available
            if match.context_messages:
                context_parts.append("**Context:**")
                for ctx_msg in match.context_messages[-2:]:  # Last 2 context messages
                    context_parts.append(f"- **{ctx_msg.role.title()}:** {ctx_msg.content[:200]}...")
        
        context_parts.append("\n---\n")
        return "\n".join(context_parts)
    
    async def get_conversation_history(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a user."""
        if not self._memory:
            raise AgentError("Memory not initialized")
        
        return await self._memory.get_conversation_history(
            user_id=user_id,
            session_id=session_id,
            limit=limit
        )
    
    async def call_mcp_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call an MCP tool directly via the agent's tool system."""
        if not self._agent:
            raise AgentError("Agent not initialized")
        
        try:
            # MCP tools are now integrated directly into the agent
            # Use the agent's tool system instead of direct MCP client calls
            self.logger.info(
                "MCP tools are integrated into agent - use agent.arun() instead",
                tool_name=tool_name
            )
            raise AgentError("MCP tools are now integrated into the agent. Use agent conversation methods instead of direct tool calls.")
        except Exception as e:
            self.logger.error(
                "MCP tool access failed",
                tool_name=tool_name,
                error=str(e)
            )
            raise AgentError(f"Tool access failed: {e}") from e
    
    async def register_custom_tool(self, tool) -> None:
        """Register a custom tool with the agent."""
        if not self._tool_registry:
            raise AgentError("Tool registry not initialized")
        
        self._tool_registry.register_tool(tool)
        
        # Reinitialize agent with new tools if already initialized
        if self._agent:
            await self._initialize_agent()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current agent metrics."""
        return self.metrics.get_metrics()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all components."""
        health = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check agent
        health["components"]["agent"] = {
            "status": "healthy" if self._agent else "not_initialized"
        }
        
        # Check memory
        if self._memory:
            try:
                await self._memory.health_check()
                health["components"]["memory"] = {"status": "healthy"}
            except Exception as e:
                health["components"]["memory"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"
        else:
            health["components"]["memory"] = {"status": "not_initialized"}
        
        # Check semantic memory
        if self._semantic_memory:
            try:
                semantic_health = await self._semantic_memory.health_check()
                health["components"]["semantic_memory"] = semantic_health
                if semantic_health["status"] != "healthy":
                    health["status"] = "degraded"
            except Exception as e:
                health["components"]["semantic_memory"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"
        else:
            health["components"]["semantic_memory"] = {"status": "not_initialized"}
        
        return health
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        self.logger.info("Cleaning up BlitzAgent resources")
        
        # MCP tools are now handled directly by the agent - no separate cleanup needed
        
        if self._memory:
            await self._memory.cleanup()
        
        if self._semantic_memory:
            await self._semantic_memory.cleanup()
        
        self.logger.info("BlitzAgent cleanup completed")
    


    # Properties for easy access
    @property
    def memory(self) -> Optional[AgentMemory]:
        """Access to agent memory."""
        return self._memory
    
    @property
    def semantic_memory(self) -> Optional[SemanticMemory]:
        """Access to semantic memory."""
        return self._semantic_memory
    
    @property
    def tool_registry(self) -> Optional[ToolRegistry]:
        """Access to tool registry."""
        return self._tool_registry


# Convenience function for quick agent creation
async def create_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None) -> BlitzAgent:
    """Create and initialize a BlitzAgent instance."""
    agent = BlitzAgent(config, context)
    await agent.initialize()
    return agent


# Context manager for automatic cleanup
@asynccontextmanager
async def agent_context(config: Optional[Config] = None, context: Optional[RuntimeContext] = None):
    """Context manager for BlitzAgent with automatic cleanup."""
    agent = BlitzAgent(config, context)
    try:
        await agent.initialize()
        yield agent
    finally:
        await agent.cleanup() 