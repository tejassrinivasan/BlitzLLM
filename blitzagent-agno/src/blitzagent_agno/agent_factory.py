"""
Agent Factory for BlitzAgent

This module provides factory functions to create different types of agents
that can be reused across the codebase (CLI, playground, server, etc.).
"""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Iterator
from textwrap import dedent
from dataclasses import dataclass
from enum import Enum
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
from agno.workflow import Workflow, RunEvent, RunResponse, WorkflowRunResponseStartedEvent, WorkflowCompletedEvent
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
            "azure_api_version": "2024-10-21",
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
        temperature = 0.1
        max_tokens = 4096
    
    provider = model_config["provider"]
    
    if provider == "azure_openai":
        return AzureOpenAI(
            id=model_config["name"],
            api_key=model_config["api_key"],
            azure_endpoint=model_config["azure_endpoint"],
            azure_deployment=model_config["azure_deployment"],
            api_version=model_config.get("azure_api_version", "2024-10-21"),
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
def blitzAgent_upload_with_confirmation(
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


def create_mcp_tools(config: Config) -> MCPTools:
    """Create MCP tools with proper server configuration."""
    # Get path to MCP server script
    mcp_path = Path(__file__).parent.parent.parent.parent / "mcp"
    mcp_command = f"{mcp_path}/start.sh"
    
    # Log the MCP path for debugging
    logger.info(f"Looking for MCP server at: {mcp_command}")
    
    # Check if the MCP script exists
    if not Path(mcp_command).exists():
        logger.error(f"MCP start script not found at: {mcp_command}")
        # Try alternative path
        alt_mcp_path = Path(__file__).parent.parent.parent.parent / "mcp-ts"
        alt_mcp_command = f"{alt_mcp_path}/start.sh"
        logger.info(f"Trying alternative MCP server at: {alt_mcp_command}")
        mcp_command = alt_mcp_command
    
    # Initialize the MCP server
    server_params = StdioServerParameters(
        command="bash",
        args=[mcp_command],
        read_timeout_seconds=30
    )
    
    try:
        # Set timeout_seconds to match the config.mcp.timeout (default 30 seconds)
        # The default MCPTools timeout is only 5 seconds, which causes webscrape timeouts
        mcp_tools = MCPTools(
            server_params=server_params,
            timeout_seconds=config.mcp.timeout  # Use config timeout instead of default 5s
        )
        logger.info(f"MCP tools created successfully with {config.mcp.timeout}s timeout")
        return mcp_tools
    except Exception as e:
        logger.error(f"Failed to create MCP tools: {e}")
        # Return a placeholder or raise the error
        raise


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
                    You have access to three distinct sources where the tools get their data from:

                    ### 1. HISTORICAL DATABASE (PostgreSQL) - Only contains data until yesterday

                    MANDATORY WORKFLOW SEQUENCE (NO EXCEPTIONS):
                    blitzAgent_get_database_documentation → blitzAgent_recall_similar_db_queries → blitzAgent_search_tables → blitzAgent_inspect → blitzAgent_sample → blitzAgent_query → blitzAgent_validate → blitzAgent_upload

                    MANDATORY RULES FOR DATABASE QUERIES:
                    - **STEP 1: ALWAYS CALL blitzAgent_get_database_documentation FIRST**
                    - **STEP 2: IMMEDIATELY AFTER DOCUMENTATION, ALWAYS CALL blitzAgent_recall_similar_db_queries - NEVER SKIP THIS!**
                    - **STEP 3: THEN PROCEED WITH blitzAgent_search_tables, blitzAgent_inspect, blitzAgent_sample**
                    - **THE blitzAgent_recall_similar_db_queries TOOL IS MANDATORY - DO NOT PROCEED WITHOUT IT**
                    - You MUST use the blitzAgent_validate tool immediately after blitzAgent_query. NEVER return query results as final without validation
                    - If blitzAgent_validate returns that the query is not very accurate or provides recommendations to improve the query, AUTOMATICALLY iterate through the workflow again in a loop until the query is good/accurate.
                    - **CRITICAL: When blitzAgent_validate confirms the query is good/accurate, you MUST IMMEDIATELY use the blitzAgent_upload tool to store the query**
                    - **NEVER complete your response without calling blitzAgent_upload after a successful validation**
                    - **THE UPLOAD STEP IS MANDATORY - DO NOT SKIP IT**
                
                    FOR FOLLOWUP QUESTIONS IN A CONVERSATION:
                    - First check if you still have the database documentation in memory. If not, use the blitzAgent_get_database_documentation tool again to refresh it.
                    - **MANDATORY: ALWAYS use the blitzAgent_recall_similar_db_queries tool again to find relevant past queries that can help answer the current question.**
                    - **DO NOT SKIP blitzAgent_recall_similar_db_queries - IT IS REQUIRED FOR EVERY DATABASE QUERY**
                    - ALWAYS use the blitzAgent_validate tool again after running a query - iterate if needed
                    
                    ---
                    ### 2. API ENDPOINTS
                    - Use this for real-time betting lines, starting lineups, scheduled games, or projections

                    ---
                    ### 3. WEB SCRAPING & SEARCH - Be generous with using this tool to supplement the other data sources
                    - Always cite source URLs
                    - Use to fill gaps not covered by the database or API and supplement the other data sources

                    ---
                    {context.get_response_standards()}
                    """)
    
    # Add custom instructions if provided
    if context.custom_instructions:
        base_instructions += f"\n\n## CUSTOM INSTRUCTIONS\n{context.custom_instructions}"
    
    return base_instructions


def get_query_generator_description(context: Optional[RuntimeContext] = None) -> str:
    """Get specialized description for the Query Generator agent."""
    if context is None:
        context = RuntimeContext(mode=RuntimeMode.INSIGHT, tone=ToneStyle.ANALYTICAL)
    
    description = dedent("""You are a specialized SQL Query Generation Agent for sports analytics databases.

    ## YOUR PRIMARY MISSION: DISCOVER NEW QUERIES THAT CAN BE USED TO ANSWER QUESTIONS IN THE FUTURE
    Generate 5-10 similar/reworded query variations based on a provided description and base query.
    Each variation should attempt to explore different columns, tables, or joins if possible. Start small and build up.
    You should be able to answer the question with the query variations.""")
    
    return description


def get_query_generator_instructions(context: Optional[RuntimeContext] = None) -> str:
    """Get specialized instructions for the Query Generator agent."""
    if context is None:
        context = RuntimeContext(mode=RuntimeMode.INSIGHT, tone=ToneStyle.ANALYTICAL)
    
    instructions = dedent("""
    ## MANDATORY 6-STEP PROCESS (STRICTLY FOLLOW THIS ORDER)

    ### Step 1: Database Documentation
    **ALWAYS START HERE** - Call blitzAgent_get_database_documentation
    - Understand available tables, columns, and relationships
    - Identify relevant data for the query variations

    ### Step 2: Database Analysis (ALWAYS USE THESE TOOLS TO INSPIRE YOU TO CREATE VARIATIONS)
    Call blitzAgent_search_tables, blitzAgent_inspect, and blitzAgent_sample:
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
    **MANDATORY: Call blitzAgent_recall_similar_db_queries**
    - This tool is REQUIRED before writing any queries
    - Search for similar existing queries
    - Learn from past patterns and approaches
    - Identify successful query structures
    - **DO NOT PROCEED to Step 5 without calling this tool**

    ### Step 5: Execute and Validate Each Query
    For EACH variation:
    - Call blitzAgent_query to execute
    - Call blitzAgent_validate to check accuracy
    - If validation fails, refine the query and re-validate
    - Only proceed to upload after successful validation

    ### Step 6: Upload Successful Queries
    - Call blitzAgent_upload for each validated query
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
    model_override: Optional[str] = None
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
    
    # Create tools
    tools = [ReasoningTools(add_instructions=True)]
    
    # Add MCP tools
    mcp_tools = create_mcp_tools(config)
    tools.append(mcp_tools)
    
    # Add confirmation tool if enabled
    if enable_confirmations:
        tools.append(blitzAgent_upload_with_confirmation)
    
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


async def create_cli_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None, model_override: Optional[str] = None) -> Agent:
    """
    Create an Agno Agent specifically configured for CLI use.
    
    Args:
        config: Optional configuration. If None, loads from default config.
        context: Optional runtime context for mode and tone
        model_override: Optional model override (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        
    Returns:
        Configured Agno Agent instance for CLI
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
    mcp_tools = create_mcp_tools(config)
    tools.append(mcp_tools)
    
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
    
    return agent


async def create_server_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None, model_override: Optional[str] = None) -> Agent:
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
    mcp_tools = create_mcp_tools(config)
    tools.append(mcp_tools)
    
    # Create agent
    agent = Agent(
        name="BlitzAgent Server",
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


async def create_query_generator_agent(config: Optional[Config] = None, context: Optional[RuntimeContext] = None, model_override: Optional[str] = None) -> Agent:
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
    mcp_tools = create_mcp_tools(config)
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
# BLITZAGENT WORKFLOW
# =============================================================================

class BlitzAgentWorkflow(Workflow):
    """
    🚀 BlitzAgent Workflow - Deterministic sports analytics workflow
    
    **WORKFLOW LOGIC:**
    1. Main Agent answers user questions using database, API, and web tools
    2. Automatically detects database tool usage 
    3. If database tools used → Query Generator creates 5-10 learning variations
    4. Built-in caching and state management
    5. Full Python control over execution flow
    """
    
    description: str = dedent("""
    Advanced sports analytics workflow that combines database queries, 
    API calls, and web research with automated query learning generation.
    
    This workflow provides deterministic execution, built-in caching, 
    and full control over the agent coordination process.
    """)
    
    # Agent placeholders - these will be created when needed
    main_agent: Agent = None
    query_generator: Agent = None
    _initialized: bool = False
    
    def _initialize_agents_if_needed(self):
        """Initialize agents on first use with proper MCP integration."""
        if self._initialized:
            return
            
        logger.info("🚀 WORKFLOW INITIALIZATION: Starting agent creation...")
        
        # Load config
        config = load_config()
        context = RuntimeContext()
        
        logger.info("🤖 Initializing workflow agents...")
        
        # Create model using the proper config
        if config.model.provider == "azure_openai":
            from agno.models.azure import AzureOpenAI
            model_instance = AzureOpenAI(
                id=config.model.name,
                api_key=config.model.api_key,
                azure_endpoint=config.model.azure_endpoint,
                azure_deployment=config.model.azure_deployment,
                api_version=config.model.azure_api_version,
                temperature=config.model.temperature,
                max_tokens=config.model.max_tokens
            )
            logger.info(f"✅ Azure OpenAI model created: {config.model.name}")
        elif config.model.provider == "openai":
            from agno.models.openai import OpenAIChat
            model_instance = OpenAIChat(
                id=config.model.name,
                api_key=config.model.api_key,
                temperature=config.model.temperature,
                max_tokens=config.model.max_tokens
            )
            logger.info(f"✅ OpenAI model created: {config.model.name}")
        else:
            raise RuntimeError(f"Unsupported model provider: {config.model.provider}")
        
        # Create tools with proper MCP integration
        from agno.tools.reasoning import ReasoningTools
        tools = [ReasoningTools(add_instructions=True)]
        logger.info("✅ Reasoning tools added")
        
        # Add MCP tools using the create_mcp_tools function which handles the connection properly
        try:
            mcp_tools = create_mcp_tools(config)
            tools.append(mcp_tools)
            logger.info("✅ MCP tools successfully added to workflow agents")
        except Exception as e:
            logger.error(f"❌ Failed to add MCP tools: {e}")
            raise RuntimeError(f"MCP tools are required but failed to initialize: {e}")
        
        # Create main agent
        self.main_agent = Agent(
            name="BlitzAgent Main",
            tools=tools,
            description=get_agent_description(AgentType.PLAYGROUND, context),
            instructions=get_agent_instructions(AgentType.PLAYGROUND, context),
            model=model_instance,
            add_history_to_messages=True,
            add_datetime_to_instructions=True,
            markdown=True,
            show_tool_calls=True,  # Enable tool call visibility
            debug_mode=True,       # Enable debug mode
        )
        logger.info("✅ Main agent created with debug mode enabled")
        
        # Create query generator
        self.query_generator = Agent(
            name="BlitzAgent Query Generator",
            tools=tools,
            description=get_agent_description(AgentType.QUERY_GENERATOR, context),
            instructions=get_agent_instructions(AgentType.QUERY_GENERATOR, context),
            model=model_instance,
            add_datetime_to_instructions=True,
            markdown=True,
            show_tool_calls=True,  # Enable tool call visibility
            debug_mode=True,       # Enable debug mode
        )
        logger.info("✅ Query generator created with debug mode enabled")
        
        self._initialized = True
        logger.info("✅ WORKFLOW INITIALIZATION: All agents initialized successfully")

        
    def _detect_database_tools(self, response_content: str, tool_calls: List[Any] = None) -> bool:
        """
        Detect if database tools were used by examining tool calls and content.
        
        Returns True if any database tools were detected.
        """
        database_tool_keywords = [
            "blitzAgent_query",
            "blitzAgent_upload", 
            "blitzAgent_validate",
            "blitzAgent_get_database_documentation",
            "blitzAgent_recall_similar_db_queries",
            "blitzAgent_inspect",
            "blitzAgent_sample",
            "blitzAgent_search_tables"
        ]
        
        logger.info("🔍 TOOL DETECTION: Analyzing response for database tool usage...")
        
        # Check tool calls if available
        if tool_calls:
            for tool_call in tool_calls:
                if hasattr(tool_call, 'tool_name'):
                    if tool_call.tool_name in database_tool_keywords:
                        logger.info(f"✅ DATABASE TOOL DETECTED: {tool_call.tool_name}")
                        return True
                        
        # Check response content for tool mentions
        if response_content:
            for keyword in database_tool_keywords:
                if keyword in response_content:
                    logger.info(f"✅ DATABASE TOOL DETECTED in content: {keyword}")
                    return True
        
        logger.info("❌ NO DATABASE TOOLS DETECTED")
        return False
        
    def _get_cached_main_response(self, user_query: str) -> Optional[str]:
        """Get cached main agent response."""
        cache_key = f"main_response_{hash(user_query)}"
        cached = self.session_state.get(cache_key)
        if cached:
            logger.info(f"📁 CACHE HIT: Found cached main response for query")
        return cached
        
    def _cache_main_response(self, user_query: str, response: str, used_database: bool):
        """Cache main agent response with metadata."""
        cache_key = f"main_response_{hash(user_query)}"
        self.session_state[cache_key] = {
            "response": response,
            "used_database": used_database,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"💾 CACHE STORED: Main response cached (database_used: {used_database})")
        
    def _get_cached_query_variations(self, user_query: str) -> Optional[str]:
        """Get cached query generator response."""
        cache_key = f"query_variations_{hash(user_query)}"
        cached = self.session_state.get(cache_key)
        if cached:
            logger.info(f"📁 CACHE HIT: Found cached query variations")
        return cached
        
    def _cache_query_variations(self, user_query: str, response: str):
        """Cache query generator response."""
        cache_key = f"query_variations_{hash(user_query)}"
        self.session_state[cache_key] = {
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"💾 CACHE STORED: Query variations cached")
        
    def run(self, user_query: str = None, use_cache: bool = True, **kwargs) -> Iterator[RunResponse]:
        """
        🚀 Main workflow execution logic.
        
        **PHASE 1:** Main Agent Analysis
        **PHASE 2:** Database Tool Detection  
        **PHASE 3:** Query Generator (if needed)
        """
        # Handle different call patterns
        if user_query is None and kwargs:
            # Maybe it's coming from kwargs
            user_query = kwargs.get('message') or kwargs.get('input') or kwargs.get('query')
        
        if user_query is None:
            # Default query for testing
            user_query = "Tell me about recent sports news"
            
        logger.info(f"🚀 WORKFLOW START: Query='{user_query}', use_cache={use_cache}")
        
        # Initialize agents if not already done
        self._initialize_agents_if_needed()
        
        # PHASE 1: Check cache first
        if use_cache:
            logger.info("📁 PHASE 1A: Checking cache...")
            cached_main = self._get_cached_main_response(user_query)
            if cached_main and isinstance(cached_main, dict):
                logger.info("📁 CACHE: Using cached main response")
                yield WorkflowRunResponseStartedEvent(
                    run_id=self.run_id,
                    content=cached_main["response"]
                )
                
                # If database was used, check for cached query variations
                if cached_main.get("used_database", False):
                    cached_variations = self._get_cached_query_variations(user_query)
                    if cached_variations and isinstance(cached_variations, dict):
                        logger.info("📁 CACHE: Using cached query variations")
                        yield WorkflowRunResponseStartedEvent(
                            run_id=self.run_id,
                            content=f"\n\n## Learning Variations Generated\n\n{cached_variations['response']}"
                        )
                        logger.info("✅ WORKFLOW COMPLETE: All responses from cache")
                        return
                else:
                    # No database tools used, workflow complete
                    logger.info("✅ WORKFLOW COMPLETE: No database tools used (cached)")
                    yield WorkflowRunResponseStartedEvent(
                        run_id=self.run_id,
                        content=""
                    )
                    return
        
        # PHASE 1: Run Main Agent
        logger.info("🤖 PHASE 1B: Running BlitzAgent Main...")
        yield WorkflowRunResponseStartedEvent(
            run_id=self.run_id,
            content="🤖 **BlitzAgent Main:** Analyzing your question...\n"
        )
        
        try:
            logger.info(f"🔧 MAIN AGENT: Executing query with {len(self.main_agent.tools)} tools available")
            
            # Run main agent synchronously
            main_response = self.main_agent.run(user_query)
            main_content = main_response.content if hasattr(main_response, 'content') else str(main_response)
            tool_calls = getattr(main_response, 'tool_calls', [])
            
            logger.info(f"📊 MAIN AGENT RESPONSE: {len(main_content)} characters, {len(tool_calls)} tool calls")
            
            # Log tool calls for debugging
            if tool_calls:
                logger.info("🔧 TOOL CALLS MADE:")
                for i, tool_call in enumerate(tool_calls):
                    tool_name = getattr(tool_call, 'tool_name', 'unknown')
                    logger.info(f"  {i+1}. {tool_name}")
            else:
                logger.info("🔧 NO TOOL CALLS MADE")
            
            # Yield main agent response
            yield WorkflowRunResponseStartedEvent(
                run_id=self.run_id,
                content=main_content
            )
            
            # PHASE 2: Database Tool Detection
            logger.info("🔍 PHASE 2: Detecting database tool usage...")
            used_database = self._detect_database_tools(main_content, tool_calls)
            
            # Cache main response
            if use_cache:
                self._cache_main_response(user_query, main_content, used_database)
            
            if not used_database:
                logger.info("✅ WORKFLOW COMPLETE: No database tools detected")
                yield WorkflowRunResponseStartedEvent(
                    run_id=self.run_id,
                    content=""
                )
                return
                
            # PHASE 3: Query Generator
            logger.info("🔄 PHASE 3: Running BlitzAgent Query Generator...")
            yield WorkflowRunResponseStartedEvent(
                run_id=self.run_id,
                content="\n\n🔄 **BlitzAgent Query Generator:** Creating learning variations...\n"
            )
            
            # Prepare query generator prompt
            generator_prompt = f"""
            Generate 5-10 query variations based on the database work just completed.
            
            Original user question: {user_query}
            
            Main agent used database tools to answer this question. Create variations that:
            1. Explore different time periods or seasons
            2. Look at different statistical measures  
            3. Use different filtering conditions
            4. Group data differently
            5. Explore related questions
            
            Follow your complete workflow including recall, validation, and upload for each variation.
            """
            
            logger.info(f"🔧 QUERY GENERATOR: Executing with {len(self.query_generator.tools)} tools available")
            
            # Run query generator synchronously
            generator_response = self.query_generator.run(generator_prompt)
            generator_content = generator_response.content if hasattr(generator_response, 'content') else str(generator_response)
            
            logger.info(f"📊 QUERY GENERATOR RESPONSE: {len(generator_content)} characters")
            
            # Cache query variations
            if use_cache:
                self._cache_query_variations(user_query, generator_content)
                
            # Yield generator response
            yield WorkflowRunResponseStartedEvent(
                run_id=self.run_id,
                content=f"\n\n## Learning Variations Generated\n\n{generator_content}"
            )
            
            logger.info("✅ WORKFLOW COMPLETE: All phases executed successfully")
            yield WorkflowRunResponseStartedEvent(
                run_id=self.run_id,
                content=""
            )
            
        except Exception as e:
            logger.error(f"❌ WORKFLOW ERROR: {str(e)}")
            import traceback
            logger.error(f"❌ WORKFLOW TRACEBACK: {traceback.format_exc()}")
            yield WorkflowRunResponseStartedEvent(
                run_id=self.run_id,
                content=f"❌ Workflow error: {str(e)}"
            )


async def create_blitz_workflow(
    config: Optional[Config] = None,
    context: Optional[RuntimeContext] = None, 
    model_override: Optional[str] = None,
    session_id: Optional[str] = None,
    storage = None
) -> BlitzAgentWorkflow:
    """
    Create a BlitzAgent Workflow for deterministic sports analytics.
    
    Args:
        config: Optional configuration
        context: Optional runtime context
        model_override: Optional model override (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        session_id: Optional session ID for caching
        storage: Optional storage backend (Note: storage passed separately to avoid pickling issues)
        
    Returns:
        Configured BlitzAgent Workflow
    """
    if config is None:
        config = load_config()
    if context is None:
        context = RuntimeContext()
        
    # Set up storage if not provided - but don't pass it to workflow constructor
    # to avoid pickling issues
    if storage is None:
        storage = await create_agno_storage(config)
        
    # Create agents
    main_agent = await create_playground_agent(
        config=config,
        enable_confirmations=False,  # No confirmations in workflow
        context=context,
        model_override=model_override
    )
    
    query_generator = await create_query_generator_agent(
        config=config,
        context=RuntimeContext(mode=RuntimeMode.INSIGHT, tone=ToneStyle.ANALYTICAL),
        model_override=model_override
    )
    
    # Create workflow without storage parameter to avoid pickling issues
    workflow = BlitzAgentWorkflow(
        session_id=session_id or f"blitz_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    
    # Assign agents to workflow
    workflow.main_agent = main_agent
    workflow.query_generator = query_generator
    
    # Store the storage reference separately
    workflow._storage = storage
    
    return workflow


# =============================================================================
# FACTORY FUNCTION REGISTRY
# =============================================================================

AGENT_FACTORIES = {
    AgentType.CLI: create_cli_agent,
    AgentType.PLAYGROUND: create_playground_agent,
    AgentType.SERVER: create_server_agent,
    AgentType.BASIC: create_blitz_agent,
    AgentType.QUERY_GENERATOR: create_query_generator_agent,
    "workflow": create_blitz_workflow,  # Deterministic workflow approach
    "hybrid_playground": create_hybrid_playground_agent,
}


async def create_agent(
    agent_type: str, 
    config: Optional[Config] = None, 
    context: Optional[RuntimeContext] = None,
    model_override: Optional[str] = None
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
        
    return await factory_func(config, **kwargs) 