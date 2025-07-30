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
You are an AI sports analytics agent with deep expertise in both NBA and MLB data.
Your job is to analyze the user's question to determine the appropriate sport/league, then use the correct tools to provide accurate analysis.

**CRITICAL: AUTOMATIC LEAGUE DETECTION**
- Analyze the user's query to determine if it's about basketball (NBA) or baseball (MLB)
- Basketball terms: players like Stephen Curry, LeBron James, teams like Lakers, Warriors, stats like three-pointers, assists, rebounds
- Baseball terms: players like Aaron Judge, Shohei Ohtani, teams like Yankees, Dodgers, stats like home runs, RBIs, ERA, batting average
- Pass the determined league ("nba" or "mlb") to ALL MCP tools automatically
- The user should never need to specify the league - you determine it from context 

---
Today's Date: {current_date}

You have access to three distinct data sources with the following priority order:

### 1. HISTORICAL DATABASE (PostgreSQL) - PREFERRED SOURCE - Only contains data until yesterday

**ALWAYS TRY HISTORICAL DATABASE FIRST** - Most comprehensive and reliable source for player stats, team records, and historical performance.

CRITICAL: DYNAMIC DATABASE SELECTION
- The MCP server automatically connects to the correct database (NBA or MLB) based on your league parameter
- NBA questions → league="nba" → connects to NBA database
- MLB questions → league="mlb" → connects to MLB database
- The system uses the correct credentials from config.json for each database

MANDATORY WORKFLOW SEQUENCE (FOLLOW EXACTLY, NO DEVIATIONS):

**PHASE 1: SETUP (SEQUENTIAL)**
1. get_database_documentation(league="nba" or "mlb") 
2. recall_similar_db_queries(league="nba" or "mlb")

**PHASE 2: EXPLORATION (PARALLEL OK)**  
3. If needed: search_tables, inspect, sample (use sparingly)

**PHASE 3: EXECUTION (INTELLIGENT RETRY ALLOWED)**
4. query(league="nba" or "mlb") - Write comprehensive query
   **CRITICAL SQL REQUIREMENTS:**
   - SINGLE SQL statement ONLY - never multiple semicolon-separated queries
   - PostgreSQL prepared statements do NOT support multiple commands
   - Use JOINs, subqueries, CTEs within ONE statement if needed
   - NO: "SELECT ...; SELECT ...;" or multiple statements
5. validate() - Check the query results
6. **INTELLIGENT RETRY LOGIC:**
   - ✅ IF query FAILS (technical error) → Retry with inspect/sample/different query (MAX 2 retries)
   - ✅ IF validate says "inaccurate/poor results" → Retry with improved query (MAX 2 retries)
   - ✅ IF validate says "good/accurate" → STOP and return analysis
   - ❌ NO retry for minor improvements or "could be better"

**RETRY RULES:**
- **MAX 2 RETRIES** - After 2 failed attempts, work with what you have
- **ONLY RETRY ON FAILURE** - Not for minor improvements or additional data
- **TECHNICAL FAILURES:** Database errors, syntax errors, connection issues
- **VALIDATION FAILURES:** Validate explicitly says results are "inaccurate", "wrong", "poor quality"
- **NO RETRY FOR:** "Could get more data", "different approach might work", "additional analysis"

**WHEN TO STOP:**
- ✅ Validate confirms results are accurate/reasonable
- ✅ After 2 retry attempts (even if not perfect)
- ✅ Any successful query + validation (even if limited data)

---
### 2. WEB SCRAPING - SECONDARY SOURCE - Use only if historical database doesn't have the data

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

---
### 3. LIVE BETTING DATA (SportsData.io) - TERTIARY SOURCE
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

**Complete Workflow Example:**
```
# Step 1: Get betting events for the date
get_betting_events_by_date(date="2025-06-30")

# Step 2: Get betting markets for specific game (use BettingEventID from step 1)
get_betting_markets_for_event(event_id=14219)
```

**Key Benefits:**
- No need to manage API keys or endpoints manually
- Automatic error handling and data validation
- Always returns available betting markets only
- Structured, consistent data format

---
### BETTING ANALYSIS - MANDATORY TWO-PART WORKFLOW

When a user asks for **prop or bet recommendations**, you MUST always perform BOTH analyses below:

## PART 1: EV-BASED ANALYSIS (REQUIRED)
**Step 1:** Get betting data using get_betting_events_by_date/get_betting_markets_for_event
**Step 2:** For each bet, compare odds across ALL available sportsbooks and calculate:
- Convert each odds format to implied probability: 
  * American odds (+150) = 100/(150+100) = 40% implied probability
  * American odds (-150) = 150/(150+100) = 60% implied probability
- **FLAG any props where sportsbooks have >10% difference in implied probability**
- **These are your best EV plays** - recommend the sportsbook with the most favorable odds

**Example:** If DraftKings has "Player A Over 0.5 Singles" at +150 (40% implied) but FanDuel has it at +120 (45.5% implied), DraftKings offers better value.

## PART 2: TREND-BASED ANALYSIS (REQUIRED AND MUST BE DONE, NO EXCEPTIONS)  
**Step 1:** Use get_database_documentation
**Step 2:** Check how often the upcoming bet lines have hit in the last 10 games by querying the games, battingstatsgame, and pitchingstatsgame tables
- Calculate hit rate. For example, "Player X has hit Over 0.5 Singles in 8 of last 10 games (80%)"
- Compare hit rate to implied probability from odds

**Step 3:** Flag props where historical performance significantly differs from bookmaker odds:
- If player hits prop 80% historically but odds imply 40%, that's a STRONG BUY
- If player hits prop 30% historically but odds imply 60%, that's a STRONG FADE

---
## RESPONSE STANDARDS
- After successful validation, provide comprehensive analysis IMMEDIATELY
- Include specific data points, time frames, numbers, player/team names, matchups, and statistics to support insights
- Focus on actionable intelligence and trends
- Cite all sources used (URLs for web scraping, API endpoints)  
- Do NOT reference any tool names, methods, table names, database names, or ANY other proprietary information
- Handle edge cases gracefully (e.g., no data, tool failure)
- **RETRY ONLY ON GENUINE FAILURES** - Not for "could be better" or "more complete"
- **END YOUR RESPONSE AFTER ANALYSIS** - Do not suggest additional queries or investigations

## RETRY DECISION CRITERIA
**RETRY IF:**
- Query fails with database/syntax error
- Validate response contains: "inaccurate", "wrong", "poor quality", "unreliable", "incorrect"
- No data returned when data should exist

**DO NOT RETRY IF:**  
- Validate says "good", "accurate", "reasonable", "limited but correct"
- Results are incomplete but accurate for available data
- You want "more comprehensive" or "additional" analysis

{extra_context}
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
            # MCP package is now installed directly in container - run it directly
            logger.info("Initializing MCP server from installed package (no downloads needed)")
            
            # Run the installed blitz-agent-mcp directly instead of using uvx
            self.mcp_server = MCPServerStdio(
                command=Config.MCP_COMMAND,  # Use installed package directly
                args=["--quiet"],  # Just quiet flag, no --from needed
                env=mcp_env  # Pass environment with correct credentials and no hardcoded database
            )
            logger.info("MCP server initialized successfully from installed package")
        except Exception as e:
            logger.error(f"Failed to initialize MCP server: {str(e)}")
            logger.error(f"Command: {Config.MCP_COMMAND} --quiet")
            logger.error(f"Environment variables: {list(mcp_env.keys())}")
            logger.error(f"Full traceback: {str(e)}")
            # For now, set to None and we'll handle this in the agent creation
            self.mcp_server = None
        
        # Create the Pydantic AI agent with structured workflow and thinking enabled
        if self.mcp_server:
            self.agent = Agent(
                model=self.model,
                model_settings=self.model_settings,  # Enable anthropic thinking
                deps_type=str,  # Dependencies will be the league
                toolsets=[self.mcp_server],
                retries=5,  # Allow more retries for reliability
                end_strategy='early',  # End as soon as possible
                tool_retries=0  # Disable tool-level retries, let agent handle retries
            )
            logger.info("Agent created with MCP tools (tool retries disabled)")
        else:
            # Create agent without MCP tools as fallback
            self.agent = Agent(
                model=self.model,
                model_settings=self.model_settings,  # Enable anthropic thinking
                deps_type=str,  # Dependencies will be the league
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
        extra_context = ctx.deps if ctx.deps else ""
        
        return SYSTEM_PROMPT_TEMPLATE.format(
            current_date=datetime.now().strftime("%Y-%m-%d"),
            extra_context=f"\n\n### Additional Context:\n{extra_context}" if extra_context else ""
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
                # Set up dependencies (just extra context - agent will determine league automatically)
                deps = request.extra_context or ""
                
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
                data={"query": request.query, "extra_context": request.extra_context},
                timestamp=datetime.now().isoformat()
            )
            
            # Set up dependencies
            deps = request.extra_context or ""
            
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
                    
                    # Skip tool_results events (not useful for user)
                
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
sports_agent = SportsAnalysisAgent()

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
    async for event in sports_agent.stream_analyze(request):
        # Format as SSE
        event_data = json.dumps(event.model_dump())
        yield f"data: {event_data}\n\n"

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_sports_query(request: AnalysisRequest) -> AnalysisResponse:
    """
    Analyze a sports query using AI and return insights.
    The agent automatically determines whether the query is about NBA or MLB.
    
    - **query**: The sports question or analysis request
    - **extra_context**: Optional additional context to include in the analysis
    """
    return await sports_agent.analyze(request)

@app.post("/analyze/stream")
@app.options("/analyze/stream")  # Handle preflight requests
async def stream_sports_analysis(request: AnalysisRequest = None) -> StreamingResponse:
    """
    Stream the analysis process in real-time using Server-Sent Events.
    Shows league detection, reasoning, tool calls, and database queries as they happen.
    
    - **query**: The sports question or analysis request
    - **extra_context**: Optional additional context to include in the analysis
    
    Returns a stream of events showing the agent's reasoning process.
    """
    # Handle OPTIONS preflight request
    if request is None:
        from fastapi.responses import Response
        return Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
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

@app.get("/analyze/stream")
async def analyze_stream_get():
    """Handle GET requests to streaming endpoint - provide usage info."""
    return {
        "error": "This endpoint requires POST method",
        "message": "Use POST /analyze/stream with JSON body containing 'query' and optional 'extra_context'",
        "example": {
            "query": "Stephen Curry shooting stats this season",
            "extra_context": "Focus on three-point shooting"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/stream")
async def stream_viewer():
    """Serve the streaming analysis web interface."""
    from fastapi.responses import HTMLResponse
    import os
    
    html_path = os.path.join(os.path.dirname(__file__), "stream_viewer.html")
    try:
        with open(html_path, 'r') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Stream Viewer Not Found</h1><p>stream_viewer.html file not found</p>",
            status_code=404
        )

# Multi-client API key management
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
        if not Config.PRODUCTION_MODE:
            return
        
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
    
    def get_client_by_key(self, api_key: str) -> Optional[str]:
        """Get client ID by API key."""
        client = self.authenticate(api_key)
        return client["client_id"] if client else None

# Initialize client authentication
client_auth = ClientAuth()
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for production endpoints and return client info."""
    if not Config.PRODUCTION_MODE:
        return {"client_id": "development", "name": "Development Mode"}
    
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

# Production endpoint - Simple streaming with only final results
@app.post("/api/v1/analyze")
async def production_analyze(
    request: AnalysisRequest,
    client_info: Dict = Depends(verify_api_key)
) -> StreamingResponse:
    """
    Production API endpoint for sports analysis.
    Requires API key authentication and streams only the final answer.
    
    Headers: Authorization: Bearer YOUR_API_KEY
    """
    async def production_stream():
        try:
            # Log the request with client info
            logger.info(f"Analysis request from {client_info['name']} ({client_info['client_id']}): {request.query[:100]}...")
            
            # Get the full analysis result
            result = await sports_agent.analyze(request)
            
            # Stream only the final answer as a simple text stream
            lines = result.response.split('\n')
            for i, line in enumerate(lines):
                if line.strip():
                    yield f"data: {json.dumps({'content': line, 'done': i == len(lines) - 1})}\n\n"
                    await asyncio.sleep(0.1)  # Small delay for smooth streaming
            
            # Final completion marker
            yield f"data: {json.dumps({'content': '', 'done': True, 'client_id': client_info['client_id']})}\n\n"
            
            logger.info(f"Analysis completed for {client_info['name']}")
            
        except Exception as e:
            logger.error(f"Production API error for {client_info['name']}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e), 'done': True, 'client_id': client_info['client_id']})}\n\n"
    
    return StreamingResponse(
        production_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

@app.get("/api/v1/health")
async def production_health(client_info: Dict = Depends(verify_api_key)):
    """Production health check endpoint."""
    return {
        "status": "healthy" if sports_agent.mcp_available else "degraded",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "anthropic_thinking": "enabled",
        "mcp_server": "available" if sports_agent.mcp_available else "unavailable",
        "sports_analysis": "available" if sports_agent.mcp_available else "unavailable",
        "client_id": client_info["client_id"],
        "client_name": client_info["name"]
    }

@app.get("/api/v1/clients")
async def list_clients(client_info: Dict = Depends(verify_api_key)):
    """List all clients (admin endpoint)."""
    # Only allow certain clients to view all clients
    if client_info["client_id"] not in ["admin", "default"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    clients_info = []
    for client_id, client_data in client_auth.clients.items():
        clients_info.append({
            "client_id": client_id,
            "name": client_data.get("name", client_id),
            "enabled": client_data.get("enabled", True),
            "rate_limit": client_data.get("rate_limit", 100),
            "created_at": client_data.get("created_at", "unknown"),
            "api_key_hash": hashlib.sha256(client_data["api_key"].encode()).hexdigest()[:8]
        })
    
    return {
        "total_clients": len(clients_info),
        "clients": clients_info
    }

@app.get("/api/v1/whoami")
async def whoami(client_info: Dict = Depends(verify_api_key)):
    """Get current client information."""
    return {
        "client_id": client_info["client_id"],
        "name": client_info["name"],
        "rate_limit": client_info["rate_limit"],
        "metadata": client_info.get("metadata", {}),
        "authenticated_at": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=Config.HOST, 
        port=Config.PORT, 
        log_level=Config.LOG_LEVEL.lower()  # uvicorn expects lowercase
    ) 