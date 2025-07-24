"""
Agent Factory for BlitzAgent

This module provides factory functions to create different types of agents
that can be reused across the codebase (CLI, playground, server, etc.).
"""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Iterator, AsyncIterator
from textwrap import dedent
from dataclasses import dataclass
from enum import Enum
from contextlib import asynccontextmanager
import structlog

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Silently ignore if dotenv is not available

from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.db.postgres import PostgresMemoryDb
from agno.memory.v2.memory import Memory as AgnoMemory
from agno.tools.reasoning import ReasoningTools
from agno.tools.mcp import MCPTools
from agno.tools import tool

from mcp import StdioServerParameters
import json

from .config import Config, load_config
from .exceptions import ConfigurationError

logger = structlog.get_logger(__name__)


# =============================================================================
# EASY MODEL SWITCHING
# =============================================================================

def model(model_name: str) -> Dict[str, Any]:
    """
    🚀 EASY MODEL SWITCHING - Just call model("model-name") anywhere!
    
    Examples:
        model("gpt-4o")
        model("claude-sonnet-4-20250514") 
        model("gemini-2.5-pro")
        model("azure:gpt-4o")
    
    Returns a model config that auto-detects provider and sets up credentials.
    """
    model_config = {}
    
    # Handle Azure models (prefix with azure:)
    if model_name.startswith("azure:"):
        actual_model = model_name[6:]  # Remove "azure:" prefix
        model_config.update({
            "provider": "azure_openai",
            "name": actual_model,
            "azure_deployment": actual_model,  # Use model name as deployment name
            "azure_api_version": "2025-03-01-preview",
        })
        # Auto-detect from environment
        import os
        model_config["api_key"] = os.getenv("AZURE_OPENAI_API_KEY")
        model_config["azure_endpoint"] = os.getenv("AZURE_OPENAI_ENDPOINT")
        
    # OpenAI models
    elif model_name in ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"]:
        model_config.update({
            "provider": "openai",
            "name": model_name,
        })
        import os
        model_config["api_key"] = os.getenv("OPENAI_API_KEY")
        
    # Claude models  
    elif "claude" in model_name.lower():
        model_config.update({
            "provider": "anthropic",
            "name": model_name,
        })
        import os
        model_config["api_key"] = os.getenv("ANTHROPIC_API_KEY")
        
    # Gemini models (default)
    elif "gemini" in model_name.lower() or model_name in ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-2.0-flash"]:
        model_config.update({
            "provider": "google",
            "name": model_name,
        })
        import os
        model_config["api_key"] = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY"))
        
    else:
        # Default to Gemini for unknown models
        logger.warning(f"Unknown model {model_name}, defaulting to Gemini provider")
        model_config.update({
            "provider": "google", 
            "name": model_name,
        })
        import os
        model_config["api_key"] = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY"))
    
    return model_config


async def create_model_from_config(model_config: Dict[str, Any], base_config: Optional[Config] = None):
    """Create an Agno model from a model config dictionary."""
    if base_config:
        # Use temperature and other settings from base config
        temperature = base_config.model.temperature
        max_tokens = base_config.model.max_tokens
    else:
        temperature=0.1
        max_tokens = 4096
    
    provider = model_config["provider"]
    
    if provider == "azure_openai":
        return AzureOpenAI(
            id=model_config["name"],
            api_key=model_config["api_key"],
            azure_endpoint=model_config["azure_endpoint"],
            azure_deployment=model_config["azure_deployment"],
            api_version=model_config.get("azure_api_version", "2025-03-01-preview"),
            temperature=temperature,
            max_tokens=max_tokens
        )
    elif provider == "openai":
        return OpenAIChat(
            id=model_config["name"],
            api_key=model_config["api_key"],
            temperature=temperature,
            max_tokens=max_tokens
        )
    elif provider == "anthropic":
        return Claude(
            id=model_config["name"],
            api_key=model_config["api_key"],
            temperature=temperature,
            max_tokens=max_tokens
        )
    elif provider == "google":
        return Gemini(
            id=model_config["name"],
            api_key=model_config["api_key"],
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        raise ConfigurationError(f"Unsupported model provider: {provider}")


# =============================================================================
# RUNTIME CONFIGURATION
# =============================================================================

class RuntimeMode(Enum):
    """Runtime modes for different use cases."""
    INSIGHT = "insight"
    CONVERSATION = "conversation"


class ToneStyle(Enum):
    """Available tone styles for agent responses."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    ANALYTICAL = "analytical"
    CONCISE = "concise"
    DETAILED = "detailed"
    FRIENDLY = "friendly"


@dataclass
class RuntimeContext:
    """Runtime context configuration for agents."""
    mode: RuntimeMode = RuntimeMode.CONVERSATION
    tone: ToneStyle = ToneStyle.PROFESSIONAL
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    custom_instructions: Optional[str] = None
    
    def get_mode_description(self) -> str:
        """Get the mode description for instructions."""
        if self.mode == RuntimeMode.INSIGHT:
            return "You are generating insights for the user based on their query."
        else:
            return "You are in a conversation with the user."
    
    def get_tone_description(self) -> str:
        """Get the tone description for instructions."""
        tone_descriptions = {
            ToneStyle.PROFESSIONAL: "Maintain a professional, expert tone in your responses.",
            ToneStyle.CASUAL: "Use a casual, friendly tone that's easy to understand.",
            ToneStyle.ANALYTICAL: "Provide analytical, data-driven responses with detailed reasoning.",
            ToneStyle.CONCISE: "Keep responses concise and to the point, focusing on key information.",
            ToneStyle.DETAILED: "Provide comprehensive, detailed explanations with thorough analysis.",
            ToneStyle.FRIENDLY: "Use a warm, approachable tone that makes users feel comfortable."
        }
        return tone_descriptions.get(self.tone, tone_descriptions[ToneStyle.PROFESSIONAL])
    
    def get_response_standards(self) -> str:
        """Get response standards based on mode."""
        if self.mode == RuntimeMode.INSIGHT:
            return dedent("""
            ## RESPONSE STANDARDS (INSIGHT MODE)
            - Provide a comprehensive analysis with 1-2 sentences
            - Include specific data points, time frames, numbers, player/team names, matchups, and statistics to support insights
            - Focus on actionable intelligence and trends
            - Cite all sources used (URLs for web scraping, API endpoints)
            - Do NOT reference any tool names, methods, table names, database names, or ANY other proprietary information
            - Handle edge cases gracefully (e.g., no data, tool failure)
            """).strip()
        else:
            return dedent("""
            ## RESPONSE STANDARDS (CONVERSATION MODE)
            - Respond with a 1-2 sentence powerful analysis with any followup questions or clarifications the user may have
            - Include specific data points, time frames, numbers, player/team names, matchups, and statistics to support insights
            - Include any specific URLs used for web scraping or APIs
            - Do NOT reference any tool names, methods, table names, database names, or ANY other proprietary information
            - Handle edge cases gracefully (e.g., no data, tool failure, or unclear query)
            """).strip()
    
    def should_enable_memory(self) -> bool:
        """Determine if memory should be enabled based on mode."""
        return self.mode == RuntimeMode.CONVERSATION


# =============================================================================
# TOOL CONFIGURATION  
# =============================================================================

@tool(requires_confirmation=True)
def upload_with_confirmation(
    description: str,
    query: str
) -> str:
    """
    Upload final, successful queries to the learning database with user confirmation.
    
    This tool stores successful query executions with a description and query for future recall.
    User will be prompted for confirmation before uploading.
    
    Args:
        description: Description of what the query does
        query: SQL query that was executed successfully
        
    Returns:
        str: Success message or error details
    """
    try:
        # Note: This is a placeholder - the actual implementation would
        # call the real MCP upload tool through the agent's MCP client
        return f"Successfully uploaded query with description: '{description}' and query: '{query[:100]}...'"
    except Exception as e:
        return f"Upload failed: {str(e)}"





# =============================================================================
# AGENT TYPES
# =============================================================================

class AgentType:
    """Constants for different agent types."""
    CLI = "cli"
    PLAYGROUND = "playground"
    SERVER = "server"
    BASIC = "basic"
    QUERY_GENERATOR = "query_generator"


# =============================================================================
# CORE AGENT CREATION FUNCTIONS
# =============================================================================

async def create_blitz_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None):
    """
    Create a core BlitzAgent instance.
    
    Args:
        config: Optional configuration. If None, loads from default config.
        context: Optional runtime context for mode and tone
        
    Returns:
        Initialized BlitzAgent instance
    """
    # Import here to avoid circular import
    from .agent import BlitzAgent
    
    if config is None:
        config = load_config()
    
    agent = BlitzAgent(config, context)
    await agent.initialize()
    return agent


async def create_agno_model(config: Config):
    """Create an Agno model based on configuration."""
    if config.model.provider == "azure_openai":
        return AzureOpenAI(
            id=config.model.name,
            api_key=config.model.api_key,
            azure_endpoint=config.model.azure_endpoint,
            azure_deployment=config.model.azure_deployment,
            api_version=config.model.azure_api_version,
            temperature=config.model.temperature,
            max_tokens=config.model.max_tokens
        )
    elif config.model.provider == "openai":
        return OpenAIChat(
            id=config.model.name,
            api_key=config.model.api_key,
            temperature=config.model.temperature,
            max_tokens=config.model.max_tokens
        )
    elif config.model.provider == "anthropic":
        return Claude(
            id=config.model.name,
            api_key=config.model.api_key,
            temperature=config.model.temperature,
            max_tokens=config.model.max_tokens
        )
    elif config.model.provider == "google":
        return Gemini(
            id=config.model.name,
            api_key=config.model.api_key,
            temperature=config.model.temperature,
            max_tokens=config.model.max_tokens
        )
    else:
        raise ConfigurationError(f"Unsupported model provider: {config.model.provider}")


def create_mcp_tools(config: Config, league: str = "mlb") -> MCPTools:
    """Create MCP tools with proper server configuration (sync version)."""
    # Use the uvx command directly as configured in mcp.json
    mcp_command = "uvx"
    mcp_args = ["--from", "git+https://github.com/tejassrinivasan/BlitzLLM.git#subdirectory=mcp", "blitz-agent-mcp"]
    
    # Log the MCP command for debugging
    logger.info(f"Creating MCP tools with command: {mcp_command} {' '.join(mcp_args)} for league: {league}")
    
    # Use current environment and override with database config
    import os
    mcp_env = os.environ.copy()
    
    # Set both NBA and MLB database configuration for multi-league support
    # NBA configuration
    mcp_env.update({
        "POSTGRES_NBA_HOST": config.database.host,
        "POSTGRES_NBA_PORT": str(config.database.port),
        "POSTGRES_NBA_DATABASE": "nba",  # NBA database name
        "POSTGRES_NBA_USER": config.database.user,
        "POSTGRES_NBA_PASSWORD": config.database.password,
        "POSTGRES_NBA_SSL": "true",
    })
    
    # MLB configuration  
    mcp_env.update({
        "POSTGRES_MLB_HOST": config.database.host,
        "POSTGRES_MLB_PORT": str(config.database.port),
        "POSTGRES_MLB_DATABASE": "mlb",  # MLB database name
        "POSTGRES_MLB_USER": config.database.user,
        "POSTGRES_MLB_PASSWORD": config.database.password,
        "POSTGRES_MLB_SSL": "true",
    })
    
    logger.info(f"Configured MCP tools for multi-league support (primary: {league})")
    
    # Set general postgres config to match the primary league
    primary_database = "nba" if league.lower() == "nba" else "mlb"
    mcp_env.update({
        "POSTGRES_HOST": config.database.host,
        "POSTGRES_PORT": str(config.database.port),
        "POSTGRES_DATABASE": primary_database,  # Set to match the primary league
        "POSTGRES_USER": config.database.user,
        "POSTGRES_PASSWORD": config.database.password,
        "POSTGRES_SSL": config.database.ssl_mode,  # Use actual ssl_mode from config
    })
    
    # Initialize the MCP server with uvx command and proper timeouts
    server_params = StdioServerParameters(
        command=mcp_command,
        args=mcp_args,
        read_timeout_seconds=60,  # Increased timeout for GitHub Actions environment
        env=mcp_env  # Pass environment variables
    )
    
    try:
        # Use reasonable timeout for MCP tools initialization
        mcp_tools = MCPTools(
            server_params=server_params,
            timeout_seconds=90  # Increased timeout for GitHub Actions environment
        )
        logger.info(f"MCP tools created successfully with uvx command")
        return mcp_tools
    except Exception as e:
        logger.error(f"Failed to create MCP tools: {e}")
        # Instead of raising, return None or create a fallback
        # This prevents the CLI from hanging if MCP tools fail
        raise RuntimeError(f"MCP tools initialization failed: {e}. The agent will not have database/API access.")


@asynccontextmanager
async def create_mcp_tools_async(config: Config, league: str = "mlb") -> AsyncIterator[MCPTools]:
    """Create MCP tools as an async context manager for proper connection handling."""
    # Use the uvx command directly as configured in mcp.json
    mcp_command = "uvx"
    mcp_args = ["--from", "git+https://github.com/tejassrinivasan/BlitzLLM.git#subdirectory=mcp", "blitz-agent-mcp"]
    
    # Log the MCP command for debugging
    logger.info(f"Creating async MCP tools with command: {mcp_command} {' '.join(mcp_args)} for league: {league}")
    
    # Use current environment and override with database config
    import os
    mcp_env = os.environ.copy()
    
    # Set both NBA and MLB database configuration for multi-league support
    # NBA configuration
    mcp_env.update({
        "POSTGRES_NBA_HOST": config.database.host,
        "POSTGRES_NBA_PORT": str(config.database.port),
        "POSTGRES_NBA_DATABASE": "nba",  # NBA database name
        "POSTGRES_NBA_USER": config.database.user,
        "POSTGRES_NBA_PASSWORD": config.database.password,
        "POSTGRES_NBA_SSL": config.database.ssl_mode,  # Use actual ssl_mode from config
    })
    
    # MLB configuration  
    mcp_env.update({
        "POSTGRES_MLB_HOST": config.database.host,
        "POSTGRES_MLB_PORT": str(config.database.port),
        "POSTGRES_MLB_DATABASE": "mlb",  # MLB database name
        "POSTGRES_MLB_USER": config.database.user,
        "POSTGRES_MLB_PASSWORD": config.database.password,
        "POSTGRES_MLB_SSL": config.database.ssl_mode,  # Use actual ssl_mode from config
    })
    
    logger.info(f"Configured async MCP tools for multi-league support (primary: {league})")
    
    # Set general postgres config to match the primary league
    primary_database = "nba" if league.lower() == "nba" else "mlb"
    mcp_env.update({
        "POSTGRES_HOST": config.database.host,
        "POSTGRES_PORT": str(config.database.port),
        "POSTGRES_DATABASE": primary_database,  # Set to match the primary league
        "POSTGRES_USER": config.database.user,
        "POSTGRES_PASSWORD": config.database.password,
        "POSTGRES_SSL": config.database.ssl_mode,  # Use actual ssl_mode from config
    })
    
    # Initialize the MCP server with uvx command and proper timeouts
    server_params = StdioServerParameters(
        command=mcp_command,
        args=mcp_args,
        read_timeout_seconds=60,  # Increased timeout for GitHub Actions environment
        env=mcp_env  # Pass environment variables
    )
    
    # Use MCPTools directly as an async context manager
    async with MCPTools(
        server_params=server_params,
        timeout_seconds=90  # Increased timeout for GitHub Actions environment
    ) as mcp_tools:
        logger.info(f"MCP tools connected successfully with uvx command")
        yield mcp_tools


async def create_agno_storage(config: Config) -> PostgresStorage:
    """Create Agno storage for sessions."""
    storage_db_url = (
        config.memory_database.get_connection_url() 
        if config.memory_database 
        else config.database.get_connection_url()
    )
    
    return PostgresStorage(
        table_name="blitz_agent_sessions",
        db_url=storage_db_url,
        auto_upgrade_schema=True,
    )


async def create_agno_memory(config: Config) -> AgnoMemory:
    """Create Agno memory for conversation memory."""
    storage_db_url = (
        config.memory_database.get_connection_url() 
        if config.memory_database 
        else config.database.get_connection_url()
    )
    
    memory_db = PostgresMemoryDb(
        table_name="agno_memories",
        db_url=storage_db_url
    )
    
    return AgnoMemory(db=memory_db)





# =============================================================================
# INSTRUCTION GENERATION
# =============================================================================

def get_agent_description(agent_type: str = AgentType.BASIC, context: Optional[RuntimeContext] = None) -> str:
    """Get agent description based on agent type and runtime context."""
    if context is None:
        context = RuntimeContext()
    
    # Query Generator has completely separate description
    if agent_type == AgentType.QUERY_GENERATOR:
        return get_query_generator_description(context)
    
    # Base description for all other agent types
    base_description = dedent(f"""You are an AI sports analytics agent with deep expertise in MLB and NBA data.
                    Your job is to use the tools available to you to answer the user's question. 

                    {context.get_mode_description()}
                    {context.get_tone_description()}""")
    
    return base_description


def get_agent_instructions(agent_type: str = AgentType.BASIC, context: Optional[RuntimeContext] = None) -> str:
    """Get instructions based on agent type and runtime context."""
    if context is None:
        context = RuntimeContext()
    
    # Query Generator has completely separate instructions
    if agent_type == AgentType.QUERY_GENERATOR:
        return get_query_generator_instructions(context)
    
    # Base instructions for all other agent types
    base_instructions = dedent(f"""
                    You are an AI sports analytics agent with deep expertise in both NBA and MLB data.
                    Your job is to use the tools available to you to answer the user's question. 

                    ---
                    Today's Date: {datetime.now().strftime("%Y-%m-%d")}

                    You have access to three distinct data sources with the following priority order:

                    ### 1. HISTORICAL DATABASE (PostgreSQL) - PREFERRED SOURCE - Only contains data until yesterday

                    **ALWAYS TRY HISTORICAL DATABASE FIRST** - Most comprehensive and reliable source for player stats, team records, and historical performance.

                    MANDATORY WORKFLOW SEQUENCE (NO EXCEPTIONS):
                    get_database_documentation → recall_similar_db_queries → search_tables → inspect → sample → query → validate → upload

                    MANDATORY RULES FOR DATABASE QUERIES:
                    - **CRITICAL: CHOOSE THE CORRECT LEAGUE DATABASE**
                    - **For NBA questions (Stephen Curry, Klay Thompson, Lakers, Warriors, basketball): Use league="nba"**
                    - **For MLB questions (baseball players, teams, pitching, batting): Use league="mlb"**
                    - **STEP 1: ALWAYS CALL get_database_documentation(league="nba" or "mlb") FIRST**
                    - **STEP 2: IMMEDIATELY AFTER DOCUMENTATION, ALWAYS CALL recall_similar_db_queries(league="nba" or "mlb") - NEVER SKIP THIS!**
                    - **STEP 3: THEN PROCEED WITH search_tables(league="nba" or "mlb"), inspect(league="nba" or "mlb"), sample(league="nba" or "mlb") if needed**
                    - **THE recall_similar_db_queries TOOL IS MANDATORY - DO NOT PROCEED WITHOUT IT**
                    - You MUST use the validate tool immediately after query. NEVER return query results as final without validation
                    - If validate returns that the query is not very accurate or provides recommendations to improve the query, AUTOMATICALLY iterate through the workflow again in a loop until the query is good/accurate.

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
                    - Provide a comprehensive analysis
                    - Include specific data points, time frames, numbers, player/team names, matchups, and statistics to support insights
                    - Focus on actionable intelligence and trends
                    - Cite all sources used (URLs for web scraping, API endpoints)
                    - Do NOT reference any tool names, methods, table names, database names, or ANY other proprietary information
                    - Handle edge cases gracefully (e.g., no data, tool failure)
                    """)
    
    # Add custom instructions if provided
    if context.custom_instructions:
        base_instructions += f"\n\n## CUSTOM INSTRUCTIONS\n{context.custom_instructions}"
    
    return base_instructions


def get_query_generator_description(context: Optional[RuntimeContext] = None) -> str:
    """Get specialized description for the Query Generator agent."""
    if context is None:
        context = RuntimeContext(mode=RuntimeMode.INSIGHT, tone=ToneStyle.ANALYTICAL)
    
    description = dedent(f"""
    
    Today's Date: {datetime.now().strftime("%Y-%m-%d")}

    You are a specialized SQL Query Generation Agent for sports analytics databases.

    ## YOUR PRIMARY MISSION: DISCOVER NEW QUERIES THAT CAN BE USED TO ANSWER QUESTIONS IN THE FUTURE
    Generate 5-10 similar/reworded query variations based on a provided description and base query.
    Each variation should attempt to explore different columns, tables, or joins if possible. Start small and build up.
    You should be able to answer the question with the query variations.""")
    
    return description


def get_query_generator_instructions(context: Optional[RuntimeContext] = None) -> str:
    """Get specialized instructions for the Query Generator agent."""
    if context is None:
        context = RuntimeContext(mode=RuntimeMode.INSIGHT, tone=ToneStyle.ANALYTICAL)
    
    instructions = dedent(f"""
    Today's Date: {datetime.now().strftime("%Y-%m-%d")}

    ## MANDATORY 6-STEP PROCESS (STRICTLY FOLLOW THIS ORDER)

    ### Step 1: Database Documentation
    **ALWAYS START HERE** - Call get_database_documentation
    - Understand available tables, columns, and relationships
    - Identify relevant data for the query variations

    ### Step 2: Database Analysis (ALWAYS USE THESE TOOLS TO INSPIRE YOU TO CREATE VARIATIONS)
    Call search_tables, inspect, and sample:
    - Explore table structures and data types
    - Understand data ranges and available values
    - Identify key columns for variations

    ### Step 3: Generate Query Variations
    Create 5-10 variations that explore different dimensions:
    
    **Time Variations:**
    - Different seasons, date ranges, recent vs historical, etc.
    - Game situations (playoffs, regular season, clutch time, etc.)
    
    **Metric Variations:**
    - Different statistics
    - Rate stats vs counting stats
    - Advanced metrics vs basic metrics
    
    **Filter Variations:**
    - Different player positions or team contexts
    - Home vs away games
    - Performance thresholds and conditions
    
    **Aggregation Variations:**
    - Different grouping (by team, player, season, etc.)
    - Various statistical functions (avg, sum, max, percentiles, etc.)

    ### Step 4: Query Recall (MOST IMPORTANT STEP - NEVER SKIP)
    **MANDATORY: Call recall_similar_db_queries**
    - This tool is REQUIRED before writing any queries
    - Search for similar existing queries
    - Learn from past patterns and approaches
    - Identify successful query structures
    - **DO NOT PROCEED to Step 5 without calling this tool**

    ### Step 5: Execute and Validate Each Query
    For EACH variation:
    - Call query to execute
    - Call validate to check accuracy
    - If validation fails, refine the query and re-validate
    - Only proceed to upload after successful validation

    ### Step 6: Upload Successful Queries
    - Call upload for each validated query
    - Provide clear descriptions of what each variation explores
    - Build the learning database for future use

    ## VARIATION QUALITY STANDARDS

    **Good Variations Should:**
    - Maintain the core intent of the original query
    - Explore meaningfully different aspects of the data
    - Use appropriate statistical measures
    - Include relevant filters and conditions
    - Be executable and return useful results

    **Avoid:**
    - Trivial changes (just changing team names, etc.)
    - Variations that fundamentally change the logic of the query
    - Overly complex queries that are hard to understand
    - Duplicate or near-duplicate logic (same query but different parameters)

    ## RESPONSE FORMAT
    Structure your response as:
    ### Database Analysis Summary
    - Key tables and columns identified
    - Relevant data ranges and constraints

    ### Query Variations Generated
    For each variation:
    1. **Variation [N]: [Clear Description]**
       - Purpose: What unique aspect this explores
       - Key Changes: How it differs from the base query
       - Validation Status: Pass/Fail with details

    ### Results Summary
    - Total variations created: X
    - Successfully validated: Y
    - Uploaded to learning database: Z

    ## EXECUTION REQUIREMENTS
    - NEVER skip any of the 6 steps
    - ALWAYS validate before uploading
    - Generate meaningful, not trivial variations
    - Focus on query diversity and learning value
    - Maintain analytical rigor throughout the process
    """)
    
    # Add custom instructions if provided
    if context.custom_instructions:
        instructions += f"\n\n## ADDITIONAL INSTRUCTIONS\n{context.custom_instructions}"
    
    return instructions


# =============================================================================
# INDIVIDUAL AGENT FACTORIES
# =============================================================================

async def create_playground_agent(
    config: Optional[Config] = None,
    enable_confirmations: bool = True,
    context: Optional[RuntimeContext] = None,
    model_override: Optional[str] = None,
    league: str = "mlb"
) -> Agent:
    """
    Create an Agno Agent specifically configured for playground use.
    
    Args:
        config: Optional configuration. If None, loads from default config.
        enable_confirmations: Whether to enable confirmation prompts for certain tools
        context: Optional runtime context for mode and tone
        model_override: Optional model override (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        
    Returns:
        Configured Agno Agent instance for playground
    """
    if config is None:
        config = load_config()
    if context is None:
        context = RuntimeContext()
    
    # Handle model override
    if model_override:
        model_config = model(model_override)
        model_instance = await create_model_from_config(model_config, config)
    else:
        model_instance = await create_agno_model(config)
    
    # Create required components
    storage = await create_agno_storage(config)
    
    # Create memory only if enabled by context
    memory = None
    if context.should_enable_memory():
        memory = await create_agno_memory(config)
    
    # Create tools (same as playground)
    tools = [ReasoningTools(add_instructions=True)]
    
    # Add MCP tools
    mcp_tools = create_mcp_tools(config, league)
    tools.append(mcp_tools)
    
    # Add confirmation tool if enabled
    if enable_confirmations:
        tools.append(upload_with_confirmation)
    
    # Create agent
    agent = Agent(
        name="BlitzAgent",
        tools=tools,
        description=get_agent_description(AgentType.PLAYGROUND, context),
        instructions=get_agent_instructions(AgentType.PLAYGROUND, context),
        model=model_instance,
        storage=storage,
        memory=memory,
        # Enable Agno memory features only if memory is enabled
        enable_user_memories=context.should_enable_memory(),
        enable_session_summaries=context.should_enable_memory(),
        add_history_to_messages=True,
        num_history_responses=5 if context.should_enable_memory() else 1,
        add_datetime_to_instructions=True,
        monitoring=True,
        markdown=True,
    )
    
    return agent


@asynccontextmanager 
async def create_cli_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None, model_override: Optional[str] = None, league: str = "mlb") -> AsyncIterator[Agent]:
    """
    Create a CLI agent with properly managed MCP tools in an async context manager.
    This mirrors the playground approach and ensures MCP tools are properly connected.
    
    Args:
        config: Optional configuration. If None, loads from default config.
        context: Optional runtime context for mode and tone
        model_override: Optional model override (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        
    Yields:
        Configured Agno Agent instance for CLI with connected MCP tools
    """
    if config is None:
        config = load_config()
    if context is None:
        context = RuntimeContext()
    
    # Handle model override
    if model_override:
        model_config = model(model_override)
        model_instance = await create_model_from_config(model_config, config)
    else:
        model_instance = await create_agno_model(config)
    
    # Create required components
    storage = await create_agno_storage(config)
    
    # Create memory only if enabled by context
    memory = None
    if context.should_enable_memory():
        memory = await create_agno_memory(config)
    
    # Create MCP tools using async context manager (mirrors playground approach)
    async with create_mcp_tools_async(config, league) as mcp_tools:
        # Create tools with properly connected MCP tools
        tools = [ReasoningTools(add_instructions=True), mcp_tools, upload_with_confirmation]
        
        # Create agent
        agent = Agent(
            name="BlitzAgent CLI",
            tools=tools,
            description=get_agent_description(AgentType.CLI, context),
            instructions=get_agent_instructions(AgentType.CLI, context),
            model=model_instance,
            storage=storage,
            memory=memory,
            # CLI specific settings
            add_history_to_messages=True,
            num_history_responses=3 if context.should_enable_memory() else 1,
            add_datetime_to_instructions=True,
            monitoring=True,
            markdown=False,  # Plain text for CLI
        )
        
        yield agent


async def create_server_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None, model_override: Optional[str] = None, league: str = "mlb") -> Agent:
    """
    Create an Agno Agent specifically configured for server/API use.
    
    Args:
        config: Optional configuration. If None, loads from default config.
        context: Optional runtime context for mode and tone
        model_override: Optional model override (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        
    Returns:
        Configured Agno Agent instance for server
    """
    if config is None:
        config = load_config()
    if context is None:
        context = RuntimeContext()
    
    # Handle model override
    if model_override:
        model_config = model(model_override)
        model_instance = await create_model_from_config(model_config, config)
    else:
        model_instance = await create_agno_model(config)
    
    # Create required components
    storage = await create_agno_storage(config)
    
    # Create memory only if enabled by context
    memory = None
    if context.should_enable_memory():
        memory = await create_agno_memory(config)
    
    # Create tools
    tools = [ReasoningTools(add_instructions=True)]
    
    # Add MCP tools
    mcp_tools = create_mcp_tools(config, league)
    tools.append(mcp_tools)
    
    # Create agent
    agent = Agent(
        name="BlitzAgent Server",
        agent_id="blitzagent-server",  # Explicit agent ID for API access
        tools=tools,
        description=get_agent_description(AgentType.SERVER, context),
        instructions=get_agent_instructions(AgentType.SERVER, context),
        model=model_instance,
        storage=storage,
        memory=memory,
        # Server specific settings
        add_history_to_messages=True,
        num_history_responses=5 if context.should_enable_memory() else 1,
        add_datetime_to_instructions=True,
        monitoring=True,
        markdown=True,
    )
    
    return agent


async def create_query_generator_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None, model_override: Optional[str] = None, league: str = "mlb") -> Agent:
    """
    Create an Agno Agent specifically for generating multiple query variations.
    
    This agent takes a description and base query, then generates 5-10 similar variations
    following the full workflow for each.
    
    Args:
        config: Optional configuration. If None, loads from default config.
        context: Optional runtime context (memory disabled for this agent type)
        model_override: Optional model override (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        
    Returns:
        Configured Agno Agent instance for query generation
    """
    if config is None:
        config = load_config()
    if context is None:
        context = RuntimeContext(mode=RuntimeMode.INSIGHT, tone=ToneStyle.ANALYTICAL)
    
    # Force insight mode for query generator (no memory needed)
    context.mode = RuntimeMode.INSIGHT
    
    # Handle model override
    if model_override:
        model_config = model(model_override)
        model_instance = await create_model_from_config(model_config, config)
    else:
        model_instance = await create_agno_model(config)
    
    # Create required components
    storage = await create_agno_storage(config)
    # No memory for query generator
    
    # Create tools
    tools = [ReasoningTools(add_instructions=True)]
    
    # Add MCP tools
    mcp_tools = create_mcp_tools(config, league)
    tools.append(mcp_tools)
    
    # Note: MCP tools already includes blitzAgent_upload (no confirmation needed)
    
    # Create agent with specific instructions
    agent = Agent(
        name="BlitzAgent Query Generator",
        tools=tools,
        description=get_agent_description(AgentType.QUERY_GENERATOR, context),
        instructions=get_agent_instructions(AgentType.QUERY_GENERATOR, context),
        model=model_instance,
        storage=storage,
        memory=None,  # No memory for query generation
        # Query generator specific settings
        enable_user_memories=False,
        enable_session_summaries=False,
        add_history_to_messages=False,
        add_datetime_to_instructions=True,
        monitoring=True,
        markdown=True,
    )
    
    return agent


# =============================================================================
# PLAYGROUND WRAPPER FOR COMPATIBILITY
# =============================================================================

class PlaygroundAgentWrapper:
    """Wrapper to integrate BlitzAgent with Agno Playground while preserving all functionality."""
    
    def __init__(self, blitz_agent, agno_agent: Agent, context: Optional[RuntimeContext] = None):
        self.blitz_agent = blitz_agent
        self.agno_agent = agno_agent
        self.context = context or RuntimeContext()
        
    async def arun(self, message: str, **kwargs):
        """Run the agent with BlitzAgent semantic memory integration."""
        try:
            # Extract user info from kwargs if available
            user_id = kwargs.pop('user_id', self.context.user_id or 'playground_user')
            session_id = kwargs.pop('session_id', self.context.session_id)
            
            # Only use semantic memory if in conversation mode
            should_store_memory = (
                self.context.should_enable_memory() and 
                self.blitz_agent.semantic_memory and 
                self.blitz_agent.semantic_memory.recall_config.enabled
            )
            
            if should_store_memory:
                # Store the user message in semantic memory first
                await self.blitz_agent.semantic_memory.store_message(
                    content=message,
                    role="user",
                    user_id=user_id,
                    session_id=session_id,
                    resource_id=f"{user_id}_{session_id}" if session_id else user_id
                )
            
            # Use the Agno agent for proper playground streaming support
            response = await self.agno_agent.arun(message, **kwargs)
            
            # If memory is enabled and this is a streaming response, wrap it to capture content
            if should_store_memory and hasattr(response, '__aiter__'):
                # Return a streaming response wrapper that captures content for memory
                return self._wrap_streaming_response(response, user_id, session_id)
            elif should_store_memory and hasattr(response, 'content'):
                # For non-streaming responses, store immediately
                await self.blitz_agent.semantic_memory.store_message(
                    content=response.content,
                    role="assistant",
                    user_id=user_id,
                    session_id=session_id,
                    resource_id=f"{user_id}_{session_id}" if session_id else user_id
                )
            
            return response
            
        except Exception as e:
            logger.error("Hybrid agent execution failed in playground", error=str(e))
            # Fallback to pure Agno agent
            return await self.agno_agent.arun(message, **kwargs)
    
    async def _wrap_streaming_response(self, response, user_id: str, session_id: str):
        """Wrap a streaming response to capture content for memory storage."""
        collected_content = ""
        
        async for chunk in response:
            # Capture content based on event type - only collect actual response content
            if hasattr(chunk, 'event') and hasattr(chunk, 'content'):
                # Only collect content from RunResponseContent events (the actual message content)
                if chunk.event == "RunResponseContent" and isinstance(chunk.content, str):
                    collected_content += chunk.content
            elif hasattr(chunk, 'content') and isinstance(chunk.content, str):
                # Fallback for non-event chunks with string content
                collected_content += chunk.content
            
            # Yield the chunk to the playground unchanged
            yield chunk
        
        # Store the complete response in memory after streaming is done
        if collected_content and self.blitz_agent.semantic_memory:
            try:
                await self.blitz_agent.semantic_memory.store_message(
                    content=collected_content,
                    role="assistant",
                    user_id=user_id,
                    session_id=session_id,
                    resource_id=f"{user_id}_{session_id}" if session_id else user_id
                )
            except Exception as e:
                logger.error("Failed to store streaming response in memory", error=str(e))
            
    def __getattr__(self, name):
        """Delegate other attributes to Agno agent."""
        return getattr(self.agno_agent, name)


async def create_hybrid_playground_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None, model_override: Optional[str] = None) -> PlaygroundAgentWrapper:
    """
    Create a hybrid agent that uses BlitzAgent core with Agno Playground compatibility.
    
    Args:
        config: Optional configuration. If None, loads from default config.
        context: Optional runtime context for mode and tone
        model_override: Optional model override (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        
    Returns:
        PlaygroundAgentWrapper that combines both agent types
    """
    if config is None:
        config = load_config()
    if context is None:
        context = RuntimeContext()
    
    # Create BlitzAgent for semantic memory and core functionality
    blitz_agent = await create_blitz_agent(config, context)
    
    # Create Agno agent for playground compatibility
    agno_agent = await create_playground_agent(config, True, context, model_override)
    
    # Return wrapped combination
    return PlaygroundAgentWrapper(blitz_agent, agno_agent, context)





# =============================================================================
# FACTORY FUNCTION REGISTRY
# =============================================================================

AGENT_FACTORIES = {
    AgentType.CLI: create_cli_agent,
    AgentType.PLAYGROUND: create_playground_agent,
    AgentType.SERVER: create_server_agent,
    AgentType.BASIC: create_blitz_agent,
    AgentType.QUERY_GENERATOR: create_query_generator_agent,
    "hybrid_playground": create_hybrid_playground_agent,
}


async def create_agent(
    agent_type: str, 
    config: Optional[Config] = None, 
    context: Optional[RuntimeContext] = None,
    model_override: Optional[str] = None,
    league: str = "mlb"
):
    """
    Factory function to create different types of agents.
    
    Args:
        agent_type: Type of agent to create (see AgentType constants)
        config: Optional configuration. If None, loads from default config.
        context: Optional runtime context for mode, tone, and memory settings
        model_override: Optional model override (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        
    Returns:
        Configured agent instance
        
    Raises:
        ValueError: If agent_type is not supported
    """
    if agent_type not in AGENT_FACTORIES:
        available_types = list(AGENT_FACTORIES.keys())
        raise ValueError(f"Unsupported agent type: {agent_type}. Available types: {available_types}")
    
    factory_func = AGENT_FACTORIES[agent_type]
    
    # Check if factory function accepts model_override parameter
    import inspect
    sig = inspect.signature(factory_func)
    kwargs = {}
    
    if 'context' in sig.parameters:
        kwargs['context'] = context
    if 'model_override' in sig.parameters:
        kwargs['model_override'] = model_override
    if 'league' in sig.parameters:
        kwargs['league'] = league
        
    return await factory_func(config, **kwargs) 