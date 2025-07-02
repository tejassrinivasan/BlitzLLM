"""
Production FastAPI App for Render deployment.

Enhanced version with insights and conversation endpoints, runtime context support,
memory/session handling, and multi-provider model switching.
"""

import os
import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import structlog

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from agno.models.azure import AzureOpenAI
from agno.models.anthropic import Claude
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.db.postgres import PostgresMemoryDb
from agno.memory.v2.memory import Memory as AgnoMemory

logger = structlog.get_logger(__name__)


# Enums for runtime context
class RuntimeMode(str, Enum):
    """Runtime modes for different use cases."""
    INSIGHT = "insight"
    CONVERSATION = "conversation"


class ToneStyle(str, Enum):
    """Available tone styles for agent responses."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    ANALYTICAL = "analytical"
    CONCISE = "concise"
    DETAILED = "detailed"
    FRIENDLY = "friendly"


class AnalysisLength(str, Enum):
    """Analysis length options for insights."""
    SHORT = "short"
    LONG = "long"


# Pydantic models for the API
class QueryRequest(BaseModel):
    """Basic request model for simple queries."""
    message: str = Field(..., description="Query message")
    user_id: Optional[str] = Field(None, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")


class ConversationRequest(BaseModel):
    """Request model for conversation with runtime context and memory."""
    message: str = Field(..., description="Query message")
    user_id: str = Field(..., description="User identifier (required for memory)")
    session_id: Optional[str] = Field(None, description="Session identifier (will be generated if not provided)")
    tone: ToneStyle = Field(ToneStyle.PROFESSIONAL, description="Response tone style")
    custom_instructions: Optional[str] = Field(None, description="Custom instructions for this query")


class InsightRequest(BaseModel):
    """Request model for insights generation."""
    message: str = Field(..., description="Query message for insights")
    tone: ToneStyle = Field(ToneStyle.ANALYTICAL, description="Response tone style")
    length: AnalysisLength = Field(AnalysisLength.SHORT, description="Length of analysis (short/long)")
    user_id: Optional[str] = Field(None, description="User identifier") 
    session_id: Optional[str] = Field(None, description="Session identifier")


class AgentResponse(BaseModel):
    """Response model for agent queries."""
    response: str
    mode: RuntimeMode
    tone: ToneStyle
    length: Optional[AnalysisLength] = None
    timestamp: str
    model: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    timestamp: str
    model: str
    providers_available: List[str]


def get_temperature():
    """Safely parse temperature from environment variables."""
    temp_str = os.getenv("MODEL__TEMPERATURE", "0.1")
    # Handle malformed temperature like "0.1.1"
    try:
        return float(temp_str)
    except ValueError:
        # Try to fix common issues like "0.1.1" -> "0.1"
        if temp_str.count('.') > 1:
            parts = temp_str.split('.')
            temp_str = f"{parts[0]}.{parts[1]}"
        return float(temp_str)


def create_model_from_env():
    """Create a model based on environment variables."""
    model_provider = os.getenv("MODEL_PROVIDER", "gemini").lower()
    
    # Support both MODEL_PROVIDER and MODEL__PROVIDER formats
    if not model_provider or model_provider == "gemini":
        model_provider = os.getenv("MODEL__PROVIDER", "gemini").lower()
    
    if model_provider == "azure_openai":
        # Azure OpenAI configuration
        api_key = (os.getenv("AZURE_OPENAI_API_KEY") or 
                  os.getenv("MODEL__API_KEY") or
                  os.getenv("OPENAI_API_KEY"))
        endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or 
                   os.getenv("MODEL__AZURE_ENDPOINT"))
        deployment = (os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") or 
                     os.getenv("MODEL__AZURE_DEPLOYMENT") or
                     os.getenv("MODEL__NAME", "gpt-4o"))
        api_version = (os.getenv("AZURE_OPENAI_API_VERSION") or 
                      os.getenv("MODEL__AZURE_API_VERSION", "2024-10-21"))
        
        if not api_key or not endpoint:
            raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables are required for Azure OpenAI")
        
        return AzureOpenAI(
            id=deployment,
            api_key=api_key,
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            api_version=api_version,
            temperature=get_temperature()
        )
    
    elif model_provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required")
        
        return Gemini(
            id="gemini-2.0-flash-exp",
            api_key=api_key,
            temperature=get_temperature()
        )
    
    elif model_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("MODEL__API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        return OpenAIChat(
            id="gpt-4o-mini",
            api_key=api_key,
            temperature=get_temperature()
        )
    
    elif model_provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        return Claude(
            id="claude-3-5-sonnet-20241022",
            api_key=api_key,
            temperature=get_temperature()
        )
    
    else:
        raise ValueError(f"Unsupported model provider: {model_provider}. Supported: azure_openai, gemini, openai, anthropic")


def get_instructions_for_mode(mode: RuntimeMode, tone: ToneStyle, length: Optional[AnalysisLength] = None, custom_instructions: Optional[str] = None) -> str:
    """Generate instructions based on mode, tone, and length."""
    base_instructions = "You are BlitzAgent, an AI assistant specialized in sports analytics. "
    
    # Mode-specific instructions
    if mode == RuntimeMode.INSIGHT:
        if length == AnalysisLength.LONG:
            mode_instructions = (
                "You are generating comprehensive insights for the user based on their query. "
                "Provide detailed analysis with multiple data points, time frames, numbers, "
                "player/team names, matchups, statistics, trends, and contextual information. "
                "Include historical comparisons and future implications. Focus on actionable intelligence."
            )
        else:  # SHORT
            mode_instructions = (
                "You are generating concise insights for the user based on their query. "
                "Provide focused analysis with key data points, numbers, player/team names, "
                "and essential statistics. Keep it brief but impactful."
            )
    else:  # CONVERSATION
        mode_instructions = (
            "You are in a conversation with the user. "
            "Respond with powerful analysis and include any followup questions or clarifications. "
            "Include specific data points, time frames, numbers, player/team names, matchups, and statistics. "
            "Remember previous context in this conversation."
        )
    
    # Tone-specific instructions
    tone_instructions = {
        ToneStyle.PROFESSIONAL: "Maintain a professional, expert tone in your responses.",
        ToneStyle.CASUAL: "Use a casual, friendly tone that's easy to understand.",
        ToneStyle.ANALYTICAL: "Provide analytical, data-driven responses with detailed reasoning.",
        ToneStyle.CONCISE: "Keep responses concise and to the point, focusing on key information.",
        ToneStyle.DETAILED: "Provide comprehensive, detailed explanations with thorough analysis.",
        ToneStyle.FRIENDLY: "Use a warm, approachable tone that makes users feel comfortable."
    }
    
    instructions = f"{base_instructions}{mode_instructions} {tone_instructions.get(tone, tone_instructions[ToneStyle.PROFESSIONAL])}"
    
    if custom_instructions:
        instructions += f" Additional instructions: {custom_instructions}"
    
    return instructions


async def create_storage():
    """Create PostgreSQL storage if database is configured."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            return PostgresStorage(
                connection_string=db_url,
                table_name="agent_sessions"
            )
        except Exception as e:
            logger.warning(f"Failed to create storage: {e}")
    return None


async def create_memory():
    """Create memory with semantic recall if database is configured."""
    db_url = os.getenv("DATABASE_URL") 
    if db_url:
        try:
            memory_db = PostgresMemoryDb(
                connection_string=db_url,
                table_name="agent_memory"
            )
            return AgnoMemory(
                db=memory_db,
                enable_semantic_recall=True
            )
        except Exception as e:
            logger.warning(f"Failed to create memory: {e}")
    return None


async def create_blitz_agent(mode: RuntimeMode, tone: ToneStyle, length: Optional[AnalysisLength] = None, custom_instructions: Optional[str] = None, enable_memory: bool = False):
    """Create the BlitzAgent for production with runtime context."""
    try:
        # Import here to avoid circular imports
        from .agent_factory import create_blitz_agent as factory_create_blitz_agent, RuntimeContext
        from .config import Config, ModelConfig, DatabaseConfig, MCPConfig, AgentConfig, MonitoringConfig, ServerConfig, SecurityConfig
        
        # Try to load full config first
        try:
            from .config import load_config
            config = load_config()
        except Exception as config_error:
            logger.warning(f"Failed to load full config, creating minimal config: {config_error}")
            
            # Create minimal config with defaults for production
            model_provider = os.getenv("MODEL_PROVIDER", "azure_openai").lower()
            
            # Create model config from environment
            model_config = ModelConfig(
                provider=model_provider,
                name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
                azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")
            )
            
            # Create minimal database config (even if not used)
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                # Parse DATABASE_URL if available
                import urllib.parse
                parsed = urllib.parse.urlparse(database_url)
                database_config = DatabaseConfig(
                    host=parsed.hostname or "localhost",
                    port=parsed.port or 5432,
                    database=parsed.path.lstrip('/') or "postgres",
                    user=parsed.username or "postgres",
                    password=parsed.password or "",
                    ssl_mode="require" if "sslmode=require" in database_url else "prefer"
                )
            else:
                # Default database config (won't be used if memory disabled)
                database_config = DatabaseConfig(
                    host="localhost",
                    port=5432,
                    database="postgres",  # Required field
                    user="postgres",      # Required field
                    password="",          # Required field (empty string is valid)
                    ssl_mode="prefer"
                )
            
            # Create minimal config
            config = Config(
                model=model_config,
                database=database_config,
                mcp=MCPConfig(),
                agent=AgentConfig(),
                monitoring=MonitoringConfig(enabled=False),
                server=ServerConfig(),
                security=SecurityConfig(),
                environment="production",
                debug=False
            )
        
        # Create runtime context
        context = RuntimeContext(
            mode=mode,
            tone=tone,
            length=length,
            enable_memory=enable_memory and mode == RuntimeMode.CONVERSATION,
            custom_instructions=custom_instructions
        )
        
        # Use the proper BlitzAgent creation function that includes semantic memory
        blitz_agent = await factory_create_blitz_agent(config, context)
        
        logger.info(f"BlitzAgent created successfully with mode: {mode.value}, tone: {tone.value}, memory: {enable_memory}")
        return blitz_agent
        
    except Exception as e:
        logger.error("Failed to create BlitzAgent", error=str(e))
        raise


def get_available_providers() -> List[str]:
    """Check which model providers are available based on environment variables."""
    providers = []
    
    if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
        providers.append("azure_openai")
    
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        providers.append("gemini")
    
    if os.getenv("OPENAI_API_KEY"):
        providers.append("openai")
    
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    
    return providers


def generate_session_id() -> str:
    """Generate a new session ID."""
    return str(uuid.uuid4())


def create_production_app() -> FastAPI:
    """Create the production FastAPI app."""
    try:
        # Create base app
        app = FastAPI(
            title="BlitzAgent API",
            description="BlitzAgent - AI Assistant for Sports Analytics with Memory & Multi-Provider Support",
            version="2.1.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure based on your needs
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Store app state
        model_provider = os.getenv("MODEL_PROVIDER") or os.getenv("MODEL__PROVIDER", "azure_openai")
        app.state.model_info = model_provider.lower()
        app.state.available_providers = get_available_providers()
        app.state.memory_enabled = bool(os.getenv("DATABASE_URL"))
        
        @app.on_event("startup")
        async def startup_event():
            """Initialize on startup."""
            try:
                logger.info(f"BlitzAgent API starting up with {app.state.model_info} provider")
                logger.info(f"Available providers: {app.state.available_providers}")
                logger.info(f"Memory/Database enabled: {app.state.memory_enabled}")
            except Exception as e:
                logger.error("Failed during startup", error=str(e))
        
        @app.get("/", response_model=Dict[str, Any])
        async def root():
            """Root endpoint."""
            return {
                "service": "BlitzAgent API",
                "status": "running",
                "version": "2.1.0",
                "description": "AI Assistant for Sports Analytics with Memory & Multi-Provider Support",
                "endpoints": {
                    "basic_query": "POST /api/query",
                    "insights": "POST /api/insights", 
                    "conversation": "POST /api/conversation",
                    "health": "GET /health",
                    "docs": "GET /docs"
                },
                "current_model": app.state.model_info,
                "available_providers": app.state.available_providers,
                "memory_enabled": app.state.memory_enabled,
                "supported_tones": [tone.value for tone in ToneStyle],
                "analysis_lengths": [length.value for length in AnalysisLength],
                "timestamp": datetime.utcnow().isoformat()
            }
        
        @app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint."""
            return HealthResponse(
                status="healthy",
                service="BlitzAgent API",
                version="2.1.0",
                timestamp=datetime.utcnow().isoformat(),
                model=app.state.model_info,
                providers_available=app.state.available_providers
            )
        
        @app.post("/api/query", response_model=AgentResponse)
        async def query_agent(request: QueryRequest):
            """Basic query endpoint - simple conversation mode."""
            agent = None
            try:
                agent = await create_blitz_agent(
                    mode=RuntimeMode.CONVERSATION,
                    tone=ToneStyle.PROFESSIONAL,
                    enable_memory=False
                )
                
                response = await agent.run(
                    message=request.message,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    stream=False
                )
                
                return AgentResponse(
                    response=response.content,
                    mode=RuntimeMode.CONVERSATION,
                    tone=ToneStyle.PROFESSIONAL,
                    timestamp=datetime.utcnow().isoformat(),
                    model=app.state.model_info,
                    user_id=request.user_id,
                    session_id=request.session_id
                )
                
            except Exception as e:
                logger.error("Error during basic query", error=str(e))
                raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
            finally:
                if agent:
                    try:
                        await agent.cleanup()
                    except Exception as cleanup_error:
                        logger.warning("Error cleaning up agent", error=str(cleanup_error))
        
        @app.post("/api/insights", response_model=AgentResponse)
        async def get_insights(request: InsightRequest):
            """Insights endpoint - focused on analytical insights with length control."""
            agent = None
            try:
                agent = await create_blitz_agent(
                    mode=RuntimeMode.INSIGHT,
                    tone=request.tone,
                    length=request.length,
                    enable_memory=False  # Insights don't need memory
                )
                
                response = await agent.run(
                    message=request.message,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    stream=False
                )
                
                return AgentResponse(
                    response=response.content,
                    mode=RuntimeMode.INSIGHT,
                    tone=request.tone,
                    length=request.length,
                    timestamp=datetime.utcnow().isoformat(),
                    model=app.state.model_info,
                    user_id=request.user_id,
                    session_id=request.session_id
                )
                
            except Exception as e:
                logger.error("Error during insights generation", error=str(e))
                raise HTTPException(status_code=500, detail=f"Insights failed: {str(e)}")
            finally:
                if agent:
                    try:
                        await agent.cleanup()
                    except Exception as cleanup_error:
                        logger.warning("Error cleaning up agent", error=str(cleanup_error))
        
        @app.post("/api/conversation", response_model=AgentResponse)
        async def conversation(request: ConversationRequest):
            """Conversation endpoint - interactive chat with memory and session handling."""
            agent = None
            try:
                # Generate session_id if not provided
                session_id = request.session_id or generate_session_id()
                
                agent = await create_blitz_agent(
                    mode=RuntimeMode.CONVERSATION,
                    tone=request.tone,
                    custom_instructions=request.custom_instructions,
                    enable_memory=app.state.memory_enabled  # Enable memory if database is available
                )
                
                response = await agent.run(
                    message=request.message,
                    user_id=request.user_id,
                    session_id=session_id,
                    stream=False
                )
                
                return AgentResponse(
                    response=response.content,
                    mode=RuntimeMode.CONVERSATION,
                    tone=request.tone,
                    timestamp=datetime.utcnow().isoformat(),
                    model=app.state.model_info,
                    user_id=request.user_id,
                    session_id=session_id  # Always return session_id
                )
                
            except Exception as e:
                logger.error("Error during conversation", error=str(e))
                raise HTTPException(status_code=500, detail=f"Conversation failed: {str(e)}")
            finally:
                # Clean up agent resources to prevent memory leaks
                if agent:
                    try:
                        await agent.cleanup()
                    except Exception as cleanup_error:
                        logger.warning("Error cleaning up agent", error=str(cleanup_error))
        
        @app.get("/api/info")
        async def info():
            """Get detailed API information."""
            return {
                "service": "BlitzAgent API",
                "version": "2.1.0",
                "current_model": app.state.model_info,
                "available_providers": app.state.available_providers,
                "memory_enabled": app.state.memory_enabled,
                "runtime_modes": [mode.value for mode in RuntimeMode],
                "tone_styles": [tone.value for tone in ToneStyle],
                "analysis_lengths": [length.value for length in AnalysisLength],
                "timestamp": datetime.utcnow().isoformat(),
                "endpoints": {
                    "GET /": "API root and service info",
                    "GET /health": "Health check",
                    "POST /api/query": "Basic query (conversation mode, professional tone, no memory)",
                    "POST /api/insights": "Generate insights (insight mode, customizable tone & length)", 
                    "POST /api/conversation": "Interactive conversation (conversation mode, memory enabled, returns session_id)",
                    "GET /api/info": "This endpoint",
                    "GET /docs": "Interactive API documentation",
                    "GET /redoc": "Alternative API documentation"
                },
                "model_switching": {
                    "instruction": "Change MODEL_PROVIDER environment variable to switch models",
                    "supported_providers": ["azure_openai", "gemini", "openai", "anthropic"],
                    "current_provider": app.state.model_info
                },
                "memory_features": {
                    "enabled": app.state.memory_enabled,
                    "semantic_recall": app.state.memory_enabled,
                    "session_management": "Automatic session_id generation and return",
                    "database_required": "Set DATABASE_URL environment variable to enable memory"
                }
            }
        
        logger.info("Production FastAPI app created successfully")
        return app
        
    except Exception as e:
        logger.error("Failed to create production app", error=str(e))
        raise


# Create the app instance for deployment
app = create_production_app()


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting BlitzAgent production server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    ) 