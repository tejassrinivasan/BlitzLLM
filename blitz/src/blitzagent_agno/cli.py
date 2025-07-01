"""
Command-line interface for BlitzAgent Agno.

This module provides CLI commands for interacting with the agent,
including chat mode, single queries, and system management.
"""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.status import Status

from .agent_factory import create_hybrid_playground_agent, AgentType, RuntimeContext, RuntimeMode, ToneStyle
from .config import load_config
from .exceptions import BlitzAgentError


app = typer.Typer(
    name="blitzagent",
    help="BlitzAgent Agno - Advanced AI agent with reasoning and memory",
    add_completion=False
)
console = Console()


@app.command()
def chat(
    user_id: Optional[str] = typer.Option(None, "--user", "-u", help="User ID for session tracking"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming responses"),
    reasoning: bool = typer.Option(True, "--reasoning/--no-reasoning", help="Show reasoning steps"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Configuration file path"),
):
    """Start interactive chat with the agent."""
    asyncio.run(_chat_mode(user_id, session_id, stream, reasoning, config_file))


@app.command()
def insights(
    message: str = typer.Argument(..., help="Question to get insights about"),
    user_id: Optional[str] = typer.Option(None, "--user", "-u", help="User ID for session tracking"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming responses"),
    reasoning: bool = typer.Option(True, "--reasoning/--no-reasoning", help="Show reasoning steps"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format (text|json)"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Configuration file path"),
):
    """Get AI insights about your question."""
    asyncio.run(_single_query(message, user_id, session_id, stream, reasoning, output_format, config_file))


@app.command()
def query(
    message: str = typer.Argument(..., help="Query message to send to the agent"),
    user_id: Optional[str] = typer.Option(None, "--user", "-u", help="User ID for session tracking"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming responses"),
    reasoning: bool = typer.Option(True, "--reasoning/--no-reasoning", help="Show reasoning steps"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format (text|json)"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Configuration file path"),
):
    """Send a single query to the agent."""
    asyncio.run(_single_query(message, user_id, session_id, stream, reasoning, output_format, config_file))


@app.command()
def history(
    user_id: str = typer.Argument(..., help="User ID to get history for"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of entries to retrieve"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Configuration file path"),
):
    """Get conversation history for a user."""
    asyncio.run(_get_history(user_id, session_id, limit, config_file))


@app.command()
def health():
    """Check agent health status."""
    asyncio.run(_health_check())


@app.command()
def metrics():
    """Display current agent metrics."""
    asyncio.run(_show_metrics())


@app.command()
def config():
    """Display current configuration."""
    _show_config()


async def _chat_mode(
    user_id: Optional[str],
    session_id: Optional[str], 
    stream: bool,
    reasoning: bool,
    config_file: Optional[str]
):
    """Interactive chat mode."""
    try:
        console.print(Panel.fit(
            "[bold blue]BlitzAgent Agno[/bold blue]\n"
            "Advanced AI Agent with Reasoning and Memory\n\n"
            "Type 'quit', 'exit', or 'bye' to exit\n"
            "Type 'help' for available commands",
            title="Welcome"
        ))
        
        # Load configuration
        config = load_config()
        
        # Create runtime context for conversation mode
        context = RuntimeContext(
            mode=RuntimeMode.CONVERSATION,
            tone=ToneStyle.PROFESSIONAL,
            user_id=user_id,
            session_id=session_id
        )
        
        # Use the exact working playground pattern - agent created INSIDE MCP context
        from .agent_factory import create_mcp_tools_async, create_agno_model, create_agno_storage, create_agno_memory, get_agent_instructions, upload_with_confirmation
        from agno.tools.reasoning import ReasoningTools
        from agno.agent import Agent
        
        async with create_mcp_tools_async(config) as mcp_tools:
            # Create agent components (exact same as playground)
            model_instance = await create_agno_model(config)
            storage = await create_agno_storage(config)
            memory = await create_agno_memory(config) if context.should_enable_memory() else None
            
            # Create tools list with MCP tools properly included (exact same as playground)
            tools = [ReasoningTools(add_instructions=True), mcp_tools, upload_with_confirmation]
            
            # Create agent (exact same pattern as playground)
            agent = Agent(
                name="BlitzAgent CLI",
                agent_id="blitz_cli",
                tools=tools,
                instructions=get_agent_instructions("cli", context),
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
            
            console.print("[green]✓[/green] Agent initialized successfully with MCP tools\n")
            
            # Show user info
            if user_id:
                console.print(f"[dim]User ID: {user_id}[/dim]")
            if session_id:
                console.print(f"[dim]Session ID: {session_id}[/dim]")
            console.print()
            
            try:
                while True:
                    try:
                        # Get user input
                        message = console.input("[bold cyan]You:[/bold cyan] ")
                        
                        if message.lower() in ["quit", "exit", "bye"]:
                            console.print("\n[yellow]Goodbye![/yellow]")
                            break
                        
                        if message.lower() == "help":
                            _show_chat_help()
                            continue
                        
                        if message.lower() == "clear":
                            console.clear()
                            continue
                        
                        if message.lower() == "metrics":
                            console.print(f"\n[dim]Agent active and ready[/dim]\n")
                            continue
                        
                        if not message.strip():
                            continue
                        
                        # Send message to agent
                        if stream:
                            await _stream_response_with_agno_agent(agent, message, user_id, session_id, reasoning)
                        else:
                            with console.status("[bold blue]🤖 Thinking...", spinner="dots"):
                                response = await agent.arun(
                                    message,
                                    user_id=user_id,
                                    session_id=session_id,
                                    stream=False
                                )
                            
                            console.print("\n[bold green]Agent:[/bold green]")
                            console.print(Markdown(response.content))
                        
                        console.print()  # Add spacing between responses
                        
                    except KeyboardInterrupt:
                        console.print("\n[yellow]Interrupted by user[/yellow]")
                        break
                    except Exception as e:
                        console.print(f"\n[red]Error: {e}[/red]\n")
                        
            finally:
                # Clean up agent resources if needed
                if hasattr(agent, 'cleanup'):
                    await agent.cleanup()
                
    except Exception as e:
        console.print(f"[red]Failed to initialize agent: {e}[/red]")
        sys.exit(1)


async def _single_query(
    message: str,
    user_id: Optional[str],
    session_id: Optional[str],
    stream: bool,
    reasoning: bool,
    output_format: str,
    config_file: Optional[str]
):
    """Execute a single query."""
    try:
        # Load configuration
        config = load_config()
        
        # Create runtime context for single query mode
        context = RuntimeContext(
            mode=RuntimeMode.INSIGHT,
            tone=ToneStyle.PROFESSIONAL,
            user_id=user_id,
            session_id=session_id
        )
        
        # Use the exact working playground pattern - agent created INSIDE MCP context
        from .agent_factory import create_mcp_tools_async, create_agno_model, create_agno_storage, create_agno_memory, get_agent_instructions, upload_with_confirmation
        from agno.tools.reasoning import ReasoningTools
        from agno.agent import Agent
        
        async with create_mcp_tools_async(config) as mcp_tools:            
            # Create agent components (exact same as playground)
            model_instance = await create_agno_model(config)
            storage = await create_agno_storage(config)
            memory = await create_agno_memory(config) if context.should_enable_memory() else None
            
            # Create tools list with MCP tools properly included (exact same as playground)
            tools = [ReasoningTools(add_instructions=True), mcp_tools, upload_with_confirmation]
            
            # Create agent (exact same pattern as playground)
            agent = Agent(
                name="BlitzAgent CLI",
                agent_id="blitz_cli_query",
                tools=tools,
                instructions=get_agent_instructions("cli", context),
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
            
            # Start thinking indicator immediately
            with console.status("[bold blue]🤖 Thinking...", spinner="dots") as status:
                try:
                    # Standard query
                    if stream:
                        await _stream_response_with_agno_agent(agent, message, user_id, session_id, reasoning, status)
                    else:
                        response = await agent.arun(
                            message,
                            user_id=user_id,
                            session_id=session_id,
                            stream=False
                        )
                        
                        # Stop thinking indicator before showing response
                        status.stop()
                        
                        if output_format == "json":
                            import json
                            output = {
                                "content": response.content,
                                "metadata": getattr(response, 'metadata', {}),
                                "timestamp": response.created_at.isoformat() if hasattr(response, 'created_at') else None
                            }
                            console.print(json.dumps(output, indent=2))
                        else:
                            console.print(Markdown(response.content))
                finally:
                    # Clean up agent resources if needed
                    if hasattr(agent, 'cleanup'):
                        await agent.cleanup()
                    
    except Exception as e:
        console.print(f"[red]Query failed: {e}[/red]")
        sys.exit(1)


async def _stream_response_with_agno_agent(
    agent,
    message: str,
    user_id: Optional[str],
    session_id: Optional[str],
    show_reasoning: bool,
    status=None
):
    """Stream agent response using Agno agent."""
    # Run the agent with streaming
    try:
        if hasattr(agent, 'arun'):
            streaming_response = await agent.arun(
                message,
                user_id=user_id,
                session_id=session_id,
                stream=True
            )
        else:
            streaming_response = await agent.run(
                message,
                user_id=user_id,
                session_id=session_id,
                stream=True
            )
    except Exception as e:
        # If streaming fails, try non-streaming
        console.print(f"\n[yellow]Streaming failed, falling back to non-streaming: {e}[/yellow]")
        if hasattr(agent, 'arun'):
            response = await agent.arun(
                message,
                user_id=user_id,
                session_id=session_id,
                stream=False
            )
        else:
            response = await agent.run(
                message,
                user_id=user_id,
                session_id=session_id,
                stream=False
            )
        
        # Stop thinking indicator before showing response
        if status:
            status.stop()
        console.print("\n[bold green]Agent:[/bold green]")
        
        if hasattr(response, 'content'):
            console.print(response.content)
        else:
            console.print(str(response))
        return
    
    # Once we have the streaming response, stop the thinking indicator
    if status:
        status.stop()
    console.print("\n[bold green]Agent:[/bold green] ", end="")
    
    content_parts = []
    
    # Check if this is actually a streaming response
    if hasattr(streaming_response, '__aiter__'):
        # This is an async iterator - stream it
        async for chunk in streaming_response:
            await _process_chunk(chunk, content_parts, show_reasoning)
    elif hasattr(streaming_response, '__iter__') and not hasattr(streaming_response, 'content'):
        # This is a regular iterator (but not a response object) - stream it
        for chunk in streaming_response:
            await _process_chunk(chunk, content_parts, show_reasoning)
    else:
        # This is not a streaming response, just print the content
        if hasattr(streaming_response, 'content'):
            console.print(streaming_response.content)
        else:
            console.print(str(streaming_response))


async def _process_chunk(chunk, content_parts, show_reasoning):
    """Process a single chunk from the streaming response."""
    # Handle different chunk types from Agno
    if hasattr(chunk, 'content') and chunk.content:
        content = chunk.content
        content_parts.append(str(content))
        console.print(str(content), end="")
    elif isinstance(chunk, dict):
        if chunk.get("type") == "content":
            content = chunk.get("data", "")
            content_parts.append(str(content))
            console.print(str(content), end="")
        elif show_reasoning and "reasoning" in chunk:
            console.print(f"\n[dim]💭 {chunk['reasoning']}[/dim]")
    elif hasattr(chunk, 'delta') and chunk.delta:
        # Handle delta-style streaming
        content = chunk.delta
        content_parts.append(str(content))
        console.print(str(content), end="")


async def _get_history(
    user_id: str,
    session_id: Optional[str],
    limit: int,
    config_file: Optional[str]
):
    """Get conversation history for a user."""
    try:
        # Load configuration
        config = load_config()
        
        # Create runtime context for history retrieval
        context = RuntimeContext(
            mode=RuntimeMode.CONVERSATION,
            tone=ToneStyle.PROFESSIONAL
        )
        
        # Create agent with properly initialized MCP tools
        from .agent_factory import create_hybrid_playground_agent
        agent = await create_hybrid_playground_agent(config, context)
        try:
            # Try to get conversation history if the agent supports it
            if hasattr(agent, 'get_conversation_history'):
                history = await agent.get_conversation_history(
                    user_id=user_id,
                    session_id=session_id,
                    limit=limit
                )
                
                if history:
                    console.print(f"\n[bold]Conversation History for {user_id}[/bold]")
                    if session_id:
                        console.print(f"[dim]Session: {session_id}[/dim]")
                    console.print()
                    
                    for entry in history:
                        timestamp = entry.get('timestamp', 'Unknown time')
                        role = entry.get('role', 'unknown').title()
                        content = entry.get('content', '')[:200] + '...' if len(entry.get('content', '')) > 200 else entry.get('content', '')
                        console.print(f"[blue]{timestamp}[/blue] - [bold]{role}:[/bold] {content}\n")
                else:
                    console.print(f"[yellow]No conversation history found for user {user_id}[/yellow]")
            else:
                console.print(f"[yellow]History not available for this agent configuration[/yellow]")
        finally:
            # Clean up agent resources if needed
            if hasattr(agent, 'cleanup'):
                await agent.cleanup()
                
    except Exception as e:
        console.print(f"[red]Failed to retrieve history: {e}[/red]")
        sys.exit(1)


async def _health_check():
    """Check agent health status."""
    try:
        # Load configuration
        config = load_config()
        
        # Create runtime context for health check
        context = RuntimeContext(
            mode=RuntimeMode.CONVERSATION,
            tone=ToneStyle.PROFESSIONAL
        )
        
        # Use the same agent creation approach as playground
        agent = await create_hybrid_playground_agent(config, context)
        try:
            console.print("[green]✓[/green] Agent health check: OK")
            console.print(f"[green]✓[/green] Configuration loaded successfully")
            console.print(f"[green]✓[/green] Database connection: Ready")
            console.print(f"[green]✓[/green] MCP tools: Available")
        finally:
            # Clean up agent resources if needed
            if hasattr(agent, 'cleanup'):
                await agent.cleanup()
            
    except Exception as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        sys.exit(1)


async def _show_metrics():
    """Display current agent metrics."""
    try:
        # Load configuration
        config = load_config()
        
        # Create runtime context for metrics
        context = RuntimeContext(
            mode=RuntimeMode.CONVERSATION,
            tone=ToneStyle.PROFESSIONAL
        )
        
        # Use the same agent creation approach as playground
        agent = await create_hybrid_playground_agent(config, context)
        try:
            console.print(f"[bold]Agent Metrics[/bold]")
            console.print(f"[green]✓[/green] Agent Status: Active")
            console.print(f"[green]✓[/green] Model: {config.model.name}")
            console.print(f"[green]✓[/green] Provider: {config.model.provider}")
            console.print(f"[green]✓[/green] Memory: {'Enabled' if config.memory.enabled else 'Disabled'}")
        finally:
            # Clean up agent resources if needed
            if hasattr(agent, 'cleanup'):
                await agent.cleanup()
            
    except Exception as e:
        console.print(f"[red]Failed to get metrics: {e}[/red]")
        sys.exit(1)


def _show_config():
    """Display current configuration."""
    try:
        config = load_config()
        
        console.print(Panel.fit(
            f"[bold]Model:[/bold] {config.model.name}\n"
            f"[bold]Provider:[/bold] {config.model.provider}\n"
            f"[bold]Temperature:[/bold] {config.model.temperature}\n"
            f"[bold]Max Tokens:[/bold] {config.model.max_tokens}\n\n"
            f"[bold]Database:[/bold] {config.database.host}:{config.database.port}/{config.database.database}\n"
            f"[bold]Memory:[/bold] {'Enabled' if config.memory.enabled else 'Disabled'}\n"
            f"[bold]MCP Server:[/bold] {config.mcp.server_url}\n"
            f"[bold]Debug Mode:[/bold] {config.agent.debug_mode}",
            title="BlitzAgent Configuration"
        ))
        
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")


def _show_chat_help():
    """Show chat help."""
    console.print(Panel.fit(
        "[bold]Available Commands:[/bold]\n\n"
        "[cyan]help[/cyan] - Show this help message\n"
        "[cyan]clear[/cyan] - Clear the screen\n"
        "[cyan]metrics[/cyan] - Show quick metrics\n"
        "[cyan]quit/exit/bye[/cyan] - Exit the chat\n\n"
        "[bold]Agent UI Playground:[/bold]\n"
        "For a better experience, try the Agent UI:\n"
        "• Run: blitzagent-playground\n"
        "• Install UI: npx create-agent-ui@latest\n"
        "• Open: http://localhost:3000\n\n"
        "[bold]Tips:[/bold]\n"
        "• Use natural language to ask questions\n"
        "• The agent can access your database and web\n"
        "• Reasoning steps are shown in real-time\n"
        "• Your conversation is saved automatically",
        title="Help"
    ))


def main():
    """Main CLI entry point."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main() 