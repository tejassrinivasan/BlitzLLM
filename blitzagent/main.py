#!/usr/bin/env python3
"""
Pydantic AI Agent for Sports Analysis
Connects to the Blitz MCP server and uses Claude 4 Sonnet (May 2025) - 
Anthropic's most advanced reasoning model with superior intelligence.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.anthropic import AnthropicModel
from dotenv import load_dotenv
import json
import asyncio
from typing import AsyncGenerator

from config import Config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Request/Response models
class AnalysisRequest(BaseModel):
    query: str = Field(..., description="The sports analysis question or request")
    extra_context: Optional[str] = Field(None, description="Additional context to include in the prompt")
    image: Optional[str] = Field(None, description="Base64 encoded image URL to provide as visual context")

class AnalysisResponse(BaseModel):
    response: str = Field(..., description="The AI agent's analysis response")
    usage: Optional[Dict[str, Any]] = Field(None, description="Token usage information")

class StreamEvent(BaseModel):
    event_type: str = Field(..., description="Type of event (league_detection, tool_call, reasoning, etc.)")
    message: str = Field(..., description="Human-readable message about what's happening")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional event data")
    timestamp: str = Field(..., description="ISO timestamp of the event")

# System prompt template
SYSTEM_PROMPT_TEMPLATE = """
Today's Date: {current_date}

You are an AI sports analytics agent with deep expertise in NBA data.

Your primary responsibility is to **accurately answer the user's question** using available tools. There are three sources of data you can use:
1. The historical database (primary source)
2. Web scraping (secondary source)
3. Live betting data (tertiary source)

## SOURCES OF DATA AND HOW TO USE THEM

## 1. HISTORICAL DATABASE - PRIMARY SOURCE

Use the tools in the following sequence to answer the question with precision:

1. `get_database_documentation` → `recall_similar_db_queries`
2. If sufficient information is available, proceed directly to querying.
3. Otherwise, use `scan`, `inspect`, and `search_tables` to explore the structure of relevant tables and columns.
4. Execute the following:
   - `query`
   - `validate`

**Critical Tool Importance:**

### Query Preprocessing for `recall_similar_db_queries`
Before calling `recall_similar_db_queries`, **preprocess the user's question** to make it more generic and pattern-focused:

**Entity Abstraction Rules:**
- **Player Names**: Replace specific player names with `{player}` or `{PLAYER}`
  - Example: "Stephen Curry's consecutive games" → "{player}'s consecutive games"
- **Team Names**: Replace specific team names with `{team}` or `{TEAM}`
  - Example: "Warriors win rate" → "{team} win rate"
- **Season Years**: Replace specific years with `{year}` or `{SEASON}`
  - Example: "2023 season stats" → "{year} season stats"
- **Stat Values**: Replace specific stat thresholds with `{threshold}` or `{VALUE}`
  - Example: "20+ points" → "{threshold}+ points"
  - Example: "10+ rebounds" → "{threshold}+ rebounds"
- **Time Periods**: Replace specific timeframes with `{period}` or `{TIMEFRAME}`
  - Example: "last 10 games" → "{period} games"

**Pattern Recognition Examples:**
- **Original**: "Stephen Curry's longest consecutive streak scoring 20 points and getting 5 rebounds"
- **Preprocessed**: "{player}'s longest consecutive streak scoring {threshold} points and getting {threshold} rebounds"

- **Original**: "LeBron James average points against Warriors vs Wizards"
- **Preprocessed**: "{player} average points against {team} vs {team}"

- **Original**: "Most recent game-tying buzzer beaters (limit 25)"
- **Preprocessed**: "Most recent game-tying buzzer beaters (limit {threshold})"

**Why This Matters:**
- **Pattern Matching**: The recall tool should find queries with similar statistical patterns, not specific entities or proper nouns
- **Reusability**: Generic patterns can be applied to any player, team, or season
- **Better Results**: More relevant query examples that show the actual SQL structure needed
- **Learning**: Users can see how to adapt patterns for different players/teams

### `recall_similar_db_queries` - Gold Standard Query Reference
This tool provides **gold standard queries** that serve as the foundation for answering user questions effectively:

- **Learn from Existing Patterns**: The recalled queries demonstrate proven SQL patterns, table joins, and data filtering techniques that have successfully answered similar questions
- **Understand Context Inclusion**: Study how the recalled queries include relevant context (opponent teams, game outcomes, player performance details) to provide comprehensive answers
- **Follow Output Structure**: Use the recalled queries as templates for your response format, including summary rows and example details
- **Leverage Proven Logic**: The recalled queries contain battle-tested logic for handling edge cases, data filtering, and statistical calculations
- **Maintain Consistency**: Ensure your queries follow the same patterns and output structure as the gold standard examples

**Important Notes:**
- If `validate` provides useful feedback, **iterate automatically** until the query is correct before proceeding to Step 2.
- If the `query` is incorrect on the first try, **continue iterating** using all tools until it's right.
- When forming your query output:
  - Look at the **columns returned** by similar queries.
  - Ensure **column naming and output structure are consistent** with those queries.
  - **Study the recalled queries carefully** - they contain the exact patterns you should follow for similar questions.
  - **Apply the generic patterns** from recalled queries to the specific player/team in the user's question.

### Example Workflow

**User Question**: "How has LeBron James performed against the Warriors this season?"

**Response**:
- Direct answer with specific stats (points, rebounds, assists, shooting percentages)
- Context about matchup history and recent performance trends
- Comparison to season averages and career performance
- Key insights about what makes this matchup interesting


## 2. WEB SCRAPING - SECONDARY SOURCE - Use only if historical database doesn't have the data

**IMPORTANT:** Use webscraping only when historical database doesn't have the data.

**USE ONLY WHEN HISTORICAL DATABASE IS INSUFFICIENT** - For recent news, current injuries, today's games, breaking news, or data not in historical database. 

Available webscraping capabilities:
- Real-time sports news and updates
- Current player injury reports
- Today's game schedules and results
- Breaking trades and signings
- Current standings and playoff scenarios

When to use webscraping:
- Question asks about "today", "current", "recent", "latest", "breaking"
- Historical database doesn't contain the needed information
- User asks about very recent events (last few days)

### Example Workflow:

**User Question**: "What's the latest news on the Warriors?"

**Response**:
- Real-time sports news and updates
- Current player injury reports

## 3. LIVE BETTING DATA (SportsData.io) - TERTIARY SOURCE
- Use this for real-time betting lines and odds for scheduled games
- For questions about upcoming betting lines or odds for specific games

**Specialized Betting Tools:**
You have access to dedicated betting tools that automatically handle API authentication and data formatting:

**Required Two-Step Workflow:**
1. **Get Betting Events by Date:** Use `get_betting_events_by_date(date="2025-06-30")`
   - Returns list of games with BettingEventID for each game
   - Takes a date in YYYY-MM-DD format
2. **Get Betting Markets for Event:** Use `get_betting_markets_for_event(event_id=14219)`
   - Use BettingEventID from step 1
   - Automatically includes available markets only
   - Returns comprehensive odds, spreads, totals, and props

### Example Workflow:

**User Question**: "What are the betting lines for the Warriors vs. Lakers game on June 30th?"

**Response**:
- Real-time betting lines and odds for scheduled games

## Response Standards

- **Accuracy**: Ensure all sports statistics and data are correct and up-to-date
- **Completeness**: Provide enough context for users to understand the sports analysis
- **Clarity**: Use clear, accessible language for sports fans of all levels
- **Relevance**: Keep suggestions closely related to the original sports question
- **Actionability**: Focus on insights that help users make decisions (betting, fantasy, etc.)
- **Professionalism**: Maintain a knowledgeable, analytical tone throughout

## Special Considerations

- **Statistical Questions**: Include relevant context (sample size, timeframes, conditions)
- **Betting Questions**: Provide both statistical analysis and betting implications
- **Player Comparisons**: Use consistent metrics and fair comparisons
- **Team Analysis**: Consider both individual and team-level factors
- **Trend Analysis**: Distinguish between short-term and long-term trends
- **Fantasy Context**: Include fantasy-relevant insights when applicable

{user_provided_context}
"""

class SportsAnalysisAgent:
    def __init__(self):
        """Initialize the sports analysis agent with Claude 4 Sonnet and MCP tools."""
        # Validate configuration
        Config.validate()
        
        # Initialize Claude 4 Sonnet model with thinking capabilities enabled
        # Note: ANTHROPIC_API_KEY environment variable is used automatically
        from pydantic_ai.models.anthropic import AnthropicModelSettings
        self.model_settings = AnthropicModelSettings(
            anthropic_thinking={'type': 'enabled', 'budget_tokens': 2048},  # Enable reasoning/thinking
        )
        self.model = AnthropicModel("claude-sonnet-4-20250514")
        
        # Initialize MCP server to connect to the Blitz MCP server
        import os
        mcp_env = os.environ.copy()  # Inherit all environment variables
        mcp_env["LOG_LEVEL"] = "INFO"  # FastMCP expects uppercase log level
        mcp_env["FASTMCP_LOG_LEVEL"] = "INFO"  # Alternative env var name
        mcp_env["MCP_LOG_LEVEL"] = "INFO"  # Another possible env var name
        mcp_env["SKIP_MCP_CONNECTION_TEST"] = "true"  # Skip database connection test during startup
        
        # Set correct database credentials explicitly (from config.json)
        correct_password = "_V8fn.eo62B(gZD|OcQcu~0|aP8["
        mcp_env["POSTGRES_PASSWORD"] = correct_password
        mcp_env["POSTGRES_MLB_PASSWORD"] = correct_password
        mcp_env["POSTGRES_NBA_PASSWORD"] = correct_password
        mcp_env["POSTGRES_USER"] = "postgres"
        mcp_env["POSTGRES_HOST"] = "blitz-instance-1.cdu6kma429k4.us-west-2.rds.amazonaws.com"
        mcp_env["POSTGRES_PORT"] = "5432"
        mcp_env["POSTGRES_SSL"] = "true"
        
        # Clear any conflicting variables that might hardcode to MLB
        mcp_env.pop("DATABASE_URL", None)
        mcp_env.pop("POSTGRES_DATABASE", None)  # Don't hardcode database name
        
        try:
            # Try to use installed package command first
            logger.info("Attempting to initialize MCP server from installed package")
            
            # Try different command approaches
            import shutil
            mcp_command = None
            mcp_args = []
            
            # Check if blitz-agent-mcp command exists
            if shutil.which("blitz-agent-mcp"):
                mcp_command = "blitz-agent-mcp"
                mcp_args = []
                logger.info("Found blitz-agent-mcp command")
            elif shutil.which("python"):
                # Fallback: run as Python module
                mcp_command = "python"
                mcp_args = ["-m", "blitz_agent_mcp.main"]
                logger.info("Using Python module execution as fallback")
            else:
                raise Exception("Neither blitz-agent-mcp nor python command found")
            
            # Run the MCP server
            self.mcp_server = MCPServerStdio(
                command=mcp_command,
                args=mcp_args,
                env=mcp_env  # Pass environment with correct credentials
            )
            logger.info("MCP server initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MCP server: {str(e)}")
            logger.error(f"Attempted command: {mcp_command if 'mcp_command' in locals() else Config.MCP_COMMAND}")
            logger.error(f"Environment variables: {list(mcp_env.keys())}")
            
            # Try absolute fallback - run with direct file path if needed
            try:
                import sys
                python_path = sys.executable
                logger.info(f"Attempting fallback with Python executable: {python_path}")
                
                self.mcp_server = MCPServerStdio(
                    command=python_path,
                    args=["-c", "import blitz_agent_mcp.main; blitz_agent_mcp.main.main()"],
                    env=mcp_env
                )
                logger.info("MCP server initialized with Python fallback")
            except Exception as fallback_e:
                logger.error(f"Fallback MCP initialization also failed: {str(fallback_e)}")
                logger.error(f"Full traceback: {str(fallback_e)}")
                # Set to None - we'll handle this gracefully
                self.mcp_server = None
        
        # Create the Pydantic AI agent with structured workflow and thinking enabled
        if self.mcp_server:
            logger.info("Creating agent with MCP tools")
            self.agent = Agent(
                model=self.model,
                model_settings=self.model_settings,  # Enable anthropic thinking
                deps_type=Dict,  # Dependencies will contain extra_context and image
                toolsets=[self.mcp_server],
                retries=5,  # Allow more retries for reliability
                end_strategy='early'  # End as soon as possible
            )
            logger.info("Agent created with MCP tools")
        else:
            # Create agent without MCP tools as fallback
            self.agent = Agent(
                model=self.model,
                model_settings=self.model_settings,  # Enable anthropic thinking
                deps_type=Dict,  # Dependencies will contain extra_context and image
                retries=5,  # Allow more retries for reliability
                end_strategy='early'  # End as soon as possible
            )
            logger.warning("Agent created WITHOUT MCP tools - sports analysis will not work!")
            
        self.mcp_available = self.mcp_server is not None
        
        # Add dynamic system prompt
        @self.agent.system_prompt
        def get_system_prompt(ctx) -> str:
            return self._get_system_prompt(ctx)
        
    def _get_system_prompt(self, ctx) -> str:
        """Generate the system prompt with current context."""
        deps = ctx.deps if ctx.deps else {}
        extra_context = deps.get('extra_context', '')
        image = deps.get('image', '')
        
        # Build user provided context section
        user_context_parts = []
        
        if extra_context:
            user_context_parts.append(f"### This is extra context the user has provided:\n{extra_context}")
        
        if image:
            user_context_parts.append(f"### Here is the base64 image url the user is providing as context:\n{image}")
        
        user_provided_context = "\n\n".join(user_context_parts) if user_context_parts else ""
        
        return SYSTEM_PROMPT_TEMPLATE.format(
            current_date=datetime.now().strftime("%Y-%m-%d"),
            user_provided_context=f"\n\n{user_provided_context}" if user_provided_context else ""
        )
    
    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Perform sports analysis using the agent with retry logic."""
        # Check if MCP is available
        if not self.mcp_available:
            raise HTTPException(
                status_code=503, 
                detail="Sports analysis service unavailable: MCP server failed to initialize. Please contact support."
            )
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                # Set up dependencies (extra context and image - agent will determine league automatically)
                deps = {
                    'extra_context': request.extra_context or '',
                    'image': request.image or ''
                }
                
                # Run the agent - it will analyze the query to determine NBA/MLB automatically
                result = await self.agent.run(
                    request.query,
                    deps=deps
                )
                
                # Safely handle usage data
                usage_data = None
                if result.usage:
                    try:
                        usage_data = result.usage.model_dump() if hasattr(result.usage, 'model_dump') else {"tokens": str(result.usage)}
                    except:
                        usage_data = {"tokens": "unavailable"}
                
                return AnalysisResponse(
                    response=result.output,
                    usage=usage_data
                )
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                last_error = e
                logger.warning(f"Analysis attempt {attempt + 1} failed: {str(e)}")
                logger.warning(f"Full error traceback: {error_details}")
                
                # If it's the last attempt, raise the error
                if attempt == max_attempts - 1:
                    logger.error(f"Analysis failed after {max_attempts} attempts: {str(e)}")
                    logger.error(f"Final error traceback: {error_details}")
                    if not self.mcp_available:
                        raise HTTPException(status_code=503, detail="Sports analysis service unavailable: MCP server connection failed")
                    else:
                        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
                
                # Wait a bit before retrying
                import asyncio
                await asyncio.sleep(1)
    
    async def stream_analyze(self, request: AnalysisRequest) -> AsyncGenerator[StreamEvent, None]:
        """Perform sports analysis with streaming events that capture real agent execution."""
        try:
            # Emit initial event
            yield StreamEvent(
                event_type="analysis_start",
                message=f"Starting analysis of query: '{request.query}'",
                data={"query": request.query, "extra_context": request.extra_context, "image": request.image},
                timestamp=datetime.now().isoformat()
            )
            
            # Set up dependencies
            deps = {
                'extra_context': request.extra_context or '',
                'image': request.image or ''
            }
            
            # Use agent.iter() to capture real execution events
            async with self.agent.iter(request.query, deps=deps) as agent_run:
                async for node in agent_run:
                    
                    # Capture user prompt node (useful)
                    if hasattr(node, 'user_prompt') and node.user_prompt:
                        yield StreamEvent(
                            event_type="user_prompt",
                            message=f"Processing user query: '{node.user_prompt}'",
                            data={"prompt": node.user_prompt},
                            timestamp=datetime.now().isoformat()
                        )
                    
                    # Skip model_request events (not useful for user)
                    
                    # Capture model response and tool calls
                    if hasattr(node, 'model_response') and node.model_response:
                        response = node.model_response
                        
                        # Extract tool calls from the response
                        tool_calls = []
                        text_parts = []
                        
                        for part in response.parts:
                            if hasattr(part, 'tool_name'):  # ToolCallPart
                                tool_calls.append({
                                    "tool_name": part.tool_name,
                                    "tool_call_id": getattr(part, 'tool_call_id', None),
                                    "args": part.args if hasattr(part, 'args') else {}
                                })
                            elif hasattr(part, 'content'):  # TextPart
                                text_parts.append(part.content)
                        
                        # Emit model thinking/reasoning
                        if text_parts:
                            yield StreamEvent(
                                event_type="model_reasoning",
                                message="Claude 4 Sonnet reasoning and analysis",
                                data={
                                    "reasoning": " ".join(text_parts),
                                    "model_name": response.model_name,
                                    "timestamp": response.timestamp.isoformat() if hasattr(response, 'timestamp') else datetime.now().isoformat()
                                },
                                timestamp=datetime.now().isoformat()
                            )
                        
                        # Emit tool calls
                        for tool_call in tool_calls:
                            yield StreamEvent(
                                event_type="tool_call",
                                message=f"Calling MCP tool: {tool_call['tool_name']}",
                                data={
                                    "tool_name": tool_call['tool_name'],
                                    "tool_call_id": tool_call['tool_call_id'],
                                    "arguments": tool_call['args'],
                                    "description": f"Executing {tool_call['tool_name']} with database query"
                                },
                                timestamp=datetime.now().isoformat()
                            )
                        
                        # Emit usage information (useful for monitoring)
                        if hasattr(response, 'usage') and response.usage:
                            try:
                                usage_data = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else {
                                    "tokens": str(response.usage)
                                }
                            except:
                                usage_data = {"tokens": "unavailable"}
                            
                            yield StreamEvent(
                                event_type="usage_update",
                                message="Token usage information",
                                data={
                                    "usage": usage_data,
                                    "model": response.model_name
                                },
                                timestamp=datetime.now().isoformat()
                            )
                    
                    # Capture tool results (useful for debugging MCP tools)
                    if hasattr(node, 'tool_results') and node.tool_results:
                        for tool_result in node.tool_results:
                            # Extract tool result information
                            tool_name = getattr(tool_result, 'tool_name', 'unknown')
                            tool_call_id = getattr(tool_result, 'tool_call_id', None)
                            
                            # Get result content
                            if hasattr(tool_result, 'content'):
                                if isinstance(tool_result.content, str):
                                    content = tool_result.content
                                elif hasattr(tool_result.content, 'text'):
                                    content = tool_result.content.text
                                else:
                                    content = str(tool_result.content)
                            else:
                                content = str(tool_result)
                            
                            # Truncate very long results for readability
                            if len(content) > 1000:
                                content = content[:1000] + "... (truncated)"
                            
                            # Check for errors
                            is_error = hasattr(tool_result, 'is_error') and tool_result.is_error
                            
                            yield StreamEvent(
                                event_type="tool_result",
                                message=f"Result from {tool_name}: {'Error' if is_error else 'Success'}",
                                data={
                                    "tool_name": tool_name,
                                    "tool_call_id": tool_call_id,
                                    "content": content,
                                    "is_error": is_error,
                                    "content_length": len(str(tool_result.content if hasattr(tool_result, 'content') else tool_result))
                                },
                                timestamp=datetime.now().isoformat()
                            )
                
                # Get final result
                if agent_run.result:
                    # Safely handle usage data
                    usage_data = None
                    if agent_run.result.usage:
                        try:
                            usage_data = agent_run.result.usage.model_dump() if hasattr(agent_run.result.usage, 'model_dump') else {"tokens": str(agent_run.result.usage)}
                        except:
                            usage_data = {"tokens": "unavailable"}
                    
                    yield StreamEvent(
                        event_type="analysis_complete",
                        message="Analysis completed successfully!",
                        data={
                            "response_length": len(agent_run.result.output),
                            "usage": usage_data,
                            "message_count": len(agent_run.result.all_messages())
                        },
                        timestamp=datetime.now().isoformat()
                    )
                    
                    yield StreamEvent(
                        event_type="final_result",
                        message="Final analysis result ready",
                        data={"response": agent_run.result.output},
                        timestamp=datetime.now().isoformat()
                    )
                else:
                    yield StreamEvent(
                        event_type="error",
                        message="Agent run completed without result",
                        data={"error": "No result returned from agent"},
                        timestamp=datetime.now().isoformat()
                    )
                    
        except Exception as e:
            logger.error(f"Error during streaming analysis: {str(e)}")
            # Check if it's a retry-related error
            if "exceeded max retries" in str(e).lower():
                yield StreamEvent(
                    event_type="error",
                    message=f"Tool retry limit exceeded. This may be due to database connectivity issues. Please try again.",
                    data={"error": str(e), "suggestion": "Check database connectivity and try again"},
                    timestamp=datetime.now().isoformat()
                )
            else:
                yield StreamEvent(
                    event_type="error",
                    message=f"Analysis failed: {str(e)}",
                    data={"error": str(e), "traceback": str(e)},
                    timestamp=datetime.now().isoformat()
                )

# Global agent instance
# Sports agent is now initialized in the startup event and stored in app.state

# Authentication setup
import json
from typing import Dict, Optional
from datetime import datetime
import hashlib

class ClientAuth:
    """Manages multiple client API keys and authentication."""
    
    def __init__(self):
        self.clients: Dict[str, Dict] = {}
        self.load_clients()
    
    def load_clients(self):
        """Load client API keys from environment or file."""
        # Try to load from JSON string first
        if Config.API_KEYS_JSON:
            try:
                self.clients = json.loads(Config.API_KEYS_JSON)
                logger.info(f"Loaded {len(self.clients)} clients from API_KEYS_JSON")
                return
            except json.JSONDecodeError as e:
                logger.error(f"Invalid API_KEYS_JSON format: {e}")
        
        # Try to load from file
        if Config.API_KEYS_FILE:
            try:
                import os
                if os.path.exists(Config.API_KEYS_FILE):
                    with open(Config.API_KEYS_FILE, 'r') as f:
                        self.clients = json.load(f)
                    logger.info(f"Loaded {len(self.clients)} clients from {Config.API_KEYS_FILE}")
                    return
            except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
                logger.error(f"Error loading API keys file: {e}")
        
        # Fallback to single API key
        if Config.API_KEY:
            self.clients = {
                "default": {
                    "name": "Default Client",
                    "api_key": Config.API_KEY,
                    "created_at": datetime.now().isoformat(),
                    "rate_limit": 100,  # requests per hour
                    "enabled": True
                }
            }
            logger.info("Using single API key for default client")
        else:
            logger.warning("No API keys configured!")
    
    def authenticate(self, api_key: str) -> Optional[Dict]:
        """Authenticate API key and return client info."""
        for client_id, client_data in self.clients.items():
            if client_data.get("api_key") == api_key and client_data.get("enabled", True):
                return {
                    "client_id": client_id,
                    "name": client_data.get("name", client_id),
                    "rate_limit": client_data.get("rate_limit", 100),
                    "metadata": client_data.get("metadata", {})
                }
        return None

# Initialize client authentication
client_auth = ClientAuth()
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key and return client info."""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    client_info = client_auth.authenticate(credentials.credentials)
    if not client_info:
        # Log the failed attempt for security monitoring
        hashed_key = hashlib.sha256(credentials.credentials.encode()).hexdigest()[:8]
        logger.warning(f"Authentication failed for key hash: {hashed_key}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"Authenticated client: {client_info['name']} ({client_info['client_id']})")
    return client_info

# FastAPI app setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting Pydantic AI Sports Agent")
    yield
    logger.info("Shutting down Pydantic AI Sports Agent")

app = FastAPI(
    title="Pydantic AI Sports Agent",
    description="AI-powered sports analysis agent using Claude 4 Sonnet (May 2025) and MCP tools for superior reasoning and analysis",
    version="1.0.0",
    lifespan=lifespan
)

async def event_stream(request: AnalysisRequest) -> AsyncGenerator[str, None]:
    """Convert analysis events to Server-Sent Events format."""
    # Get the agent from app state
    if not hasattr(app.state, 'agent') or not app.state.agent:
        error_event = {
            "event_type": "error",
            "message": "Sports analysis service is not initialized",
            "timestamp": datetime.now().isoformat()
        }
        yield f"data: {json.dumps(error_event)}\n\n"
        return
    
    async for event in app.state.agent.stream_analyze(request):
        # Format as SSE
        event_data = json.dumps(event.model_dump())
        yield f"data: {event_data}\n\n"

@app.on_event("startup")
async def startup_event():
    """Initialize the sports agent on startup."""
    import time
    app.state.start_time = time.time()
    
    logger.info("Starting Pydantic AI Sports Agent")
    try:
        app.state.agent = SportsAnalysisAgent()
        logger.info("Sports agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize sports agent: {e}")
        app.state.agent = None

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down Pydantic AI Sports Agent")

@app.get("/health")
async def health_check():
    """Health check endpoint to verify system status."""
    import time
    from datetime import datetime
    
    # Check if agent is available
    agent_status = "up" if hasattr(app.state, 'agent') and app.state.agent else "down"
    
    # Check MCP server status
    mcp_status = "connected" if hasattr(app.state, 'agent') and app.state.agent and app.state.agent.mcp_available else "disconnected"
    
    # Check Anthropic API (basic check)
    anthropic_status = "available" if Config.ANTHROPIC_API_KEY else "unavailable"
    
    # Determine overall status
    if agent_status == "up" and mcp_status == "connected" and anthropic_status == "available":
        overall_status = "healthy"
    elif agent_status == "up" and anthropic_status == "available":
        overall_status = "degraded"  # MCP might be down but basic functionality works
    else:
        overall_status = "unhealthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": {
            "api": {
                "status": agent_status,
                "uptime": int(time.time() - app.state.start_time) if hasattr(app.state, 'start_time') else 0
            },
            "mcp_server": {
                "status": mcp_status,
                "last_check": datetime.utcnow().isoformat() + "Z",
                "tools_available": 12 if mcp_status == "connected" else 0
            },
            "anthropic": {
                "status": anthropic_status,
                "model": "claude-sonnet-4-20250514" if anthropic_status == "available" else None
            }
        },
        "version": "1.0.0"
    }

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_sports_query(
    request: AnalysisRequest,
    client_info: Dict = Depends(verify_api_key)
) -> AnalysisResponse:
    """
    Analyze a sports query using AI and return insights.
    The agent automatically determines whether the query is about NBA or MLB.
    
    Requires API key authentication via Bearer token.
    
    - **query**: The sports question or analysis request
    - **extra_context**: Optional additional context to include in the analysis
    - **image**: Optional base64 encoded image URL to provide as visual context
    """
    logger.info(f"Analysis request from {client_info['name']} ({client_info['client_id']}): {request.query[:100]}...")
    
    # Get the agent from app state
    if not hasattr(app.state, 'agent') or not app.state.agent:
        raise HTTPException(status_code=503, detail="Sports analysis service is not initialized")
    
    return await app.state.agent.analyze(request)

@app.post("/analyze/stream")
async def stream_sports_analysis(
    request: AnalysisRequest,
    client_info: Dict = Depends(verify_api_key)
) -> StreamingResponse:
    """
    Stream the analysis process in real-time using Server-Sent Events.
    Shows league detection, reasoning, tool calls, and database queries as they happen.
    
    Requires API key authentication via Bearer token.
    
    - **query**: The sports question or analysis request
    - **extra_context**: Optional additional context to include in the analysis
    - **image**: Optional base64 encoded image URL to provide as visual context
    
    Returns a stream of events showing the agent's reasoning process.
    """
    logger.info(f"Streaming analysis request from {client_info['name']} ({client_info['client_id']}): {request.query[:100]}...")
    
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=Config.HOST, 
        port=Config.PORT, 
        log_level=Config.LOG_LEVEL.lower()  # uvicorn expects lowercase
    ) 