"""
BlitzAgent Playground integration with Agno.

This module provides integration with the Agno Playground for interactive
agent usage with a web interface.
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
import structlog
import nest_asyncio

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded from .env file")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables only")
    print("   Install with: pip install python-dotenv")

from agno.playground import Playground
from rich.console import Console
from rich.prompt import Prompt

from .config import load_config
from .agent_factory import create_hybrid_playground_agent, AgentType, RuntimeContext, RuntimeMode, ToneStyle, model

# Allow nested event loops
nest_asyncio.apply()

logger = structlog.get_logger(__name__)

# Console for HITL interactions
console = Console()


# =============================================================================
# 🎯 EASY MODEL SWITCHING - CHANGE THIS TO SWITCH MODELS!
# =============================================================================

# Just change this line to switch models for the playground:
PLAYGROUND_MODEL = "azure:gpt-4o"  # Uses Azure OpenAI for gpt-4o, or set to: "gpt-4o", "claude-sonnet-4-20250514", etc.

# Examples you can set:
# PLAYGROUND_MODEL = "gpt-4o"  # Regular OpenAI
# PLAYGROUND_MODEL = "azure:gpt-4o"  # Azure OpenAI (current setting)
# PLAYGROUND_MODEL = "claude-sonnet-4-20250514" 
# PLAYGROUND_MODEL = "gemini-2.5-pro"


async def run_server() -> None:
    """Run the BlitzAgent playground server with MCP integration and semantic memory."""
    
    # Load configuration
    config = load_config()
    
    print("🚀 Starting BlitzAgent Playground with MCP Integration and Semantic Memory...")
    print(f"📊 Agent: {config.agent.name}")
    
    # Show model info
    if PLAYGROUND_MODEL:
        print(f"🤖 Model: {PLAYGROUND_MODEL} (override)")
        model_config = model(PLAYGROUND_MODEL)
        print(f"🔧 Provider: {model_config['provider']}")
        
        # Debug Azure configuration
        if model_config['provider'] == 'azure_openai':
            import os
            azure_endpoint = model_config.get('azure_endpoint') or os.getenv('AZURE_OPENAI_ENDPOINT')
            azure_key = model_config.get('api_key') or os.getenv('AZURE_OPENAI_API_KEY')
            print(f"🔗 Azure Endpoint: {azure_endpoint[:50] + '...' if azure_endpoint else 'NOT SET'}")
            print(f"🔑 Azure API Key: {'SET' if azure_key else 'NOT SET'}")
    else:
        print(f"🤖 Model: {config.model.name} (from config)")
        print(f"🔧 Provider: {config.model.provider}")
    
    print(f"🧠 Memory: {'Enabled' if config.memory.enabled else 'Disabled'}")
    print(f"🔍 Semantic Recall: {'Enabled' if config.memory.semantic_recall.enabled else 'Disabled'}")
    print("🤝 Human-in-the-loop: Enabled for upload operations")
    
    # Show model switching tip
    if not PLAYGROUND_MODEL:
        print()
        print("💡 Easy Model Switching:")
        print("   Edit PLAYGROUND_MODEL in playground.py to switch models!")
        print("   Examples: 'gpt-4o', 'claude-sonnet-4-20250514', 'gemini-2.5-pro'")
    
    # Create runtime context for playground (conversation mode by default)
    context = RuntimeContext(
        mode=RuntimeMode.CONVERSATION,
        tone=ToneStyle.PROFESSIONAL
    )
    
    # Create MCP tools with proper async context management
    from .agent_factory import create_mcp_tools
    from agno.tools.reasoning import ReasoningTools
    from agno.agent import Agent
    from .agent_factory import create_agno_model, create_agno_storage, create_agno_memory, get_agent_instructions, blitzAgent_upload_with_confirmation, create_model_from_config
    
    async with create_mcp_tools(config) as mcp_tools:
        print("✅ MCP Server connected successfully with all tools loaded")
        
        # Create agent components with model override if specified
        if PLAYGROUND_MODEL:
            model_config = model(PLAYGROUND_MODEL)
            model_instance = await create_model_from_config(model_config, config)
        else:
            model_instance = await create_agno_model(config)
            
        storage = await create_agno_storage(config)
        memory = await create_agno_memory(config) if context.should_enable_memory() else None
        
        # Create tools list with MCP tools properly included
        tools = [ReasoningTools(add_instructions=True), mcp_tools, blitzAgent_upload_with_confirmation]
        
        # Create single agent
        single_agent = Agent(
            name="BlitzAgent",
            agent_id="blitz_single",
            tools=tools,
            instructions=get_agent_instructions("playground", context),
            model=model_instance,
            storage=storage,
            memory=memory,
            enable_user_memories=context.should_enable_memory(),
            enable_session_summaries=context.should_enable_memory(),
            add_history_to_messages=True,
            num_history_responses=5 if context.should_enable_memory() else 1,
            add_datetime_to_instructions=True,
            markdown=True,
        )
        
        print("✅ BlitzAgent initialized")
        print(f"🔧 Tools loaded: {len(tools)} tool groups")
        
        # Create playground with single agent only
        playground = Playground(
            agents=[single_agent],
            app_id="blitzagent-playground",
            name="BlitzAgent Playground",
            description="BlitzAgent for sports analytics with MCP integration and semantic memory"
        )
        app = playground.get_app()
        
        print("🌟 Playground ready with BlitzAgent!")
        print("📊 BlitzAgent - Single agent for comprehensive sports analytics")
        print("🧠 Conversations will be remembered and provide personalized context!")
        print("🤝 Upload operations will require your confirmation before proceeding!")

        # Serve the app while keeping MCP context alive
        playground.serve(app)


if __name__ == "__main__":
    asyncio.run(run_server())


def main():
    """Main entry point for the blitzagent-playground CLI command."""
    asyncio.run(run_server()) 