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

from .agent import BlitzAgent, agent_context
from .agent_factory import create_agent, AgentType
from .config import Config
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
    # structured: Optional[str] = typer.Option(None, "--structured", help="Use structured output: analysis"),
    # json_mode: bool = typer.Option(False, "--json-mode", help="Use JSON mode for structured output"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Configuration file path"),
):
    """Start interactive chat with the agent."""
    asyncio.run(_chat_mode(user_id, session_id, stream, reasoning, config_file))


@app.command()
def query(
    message: str = typer.Argument(..., help="Query message to send to the agent"),
    user_id: Optional[str] = typer.Option(None, "--user", "-u", help="User ID for session tracking"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming responses"),
    reasoning: bool = typer.Option(True, "--reasoning/--no-reasoning", help="Show reasoning steps"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format (text|json)"),
    # structured: Optional[str] = typer.Option(None, "--structured", help="Use structured output: analysis"),
    # json_mode: bool = typer.Option(False, "--json-mode", help="Use JSON mode for structured output"),
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
    # structured: Optional[str],
    # json_mode: bool,
    config_file: Optional[str]
):
    """Interactive chat mode."""
    try:
        # Validate environment
        validate_environment()
        
        console.print(Panel.fit(
            "[bold blue]BlitzAgent Agno[/bold blue]\n"
            "Advanced AI Agent with Reasoning and Memory\n\n"
            "Type 'quit', 'exit', or 'bye' to exit\n"
            "Type 'help' for available commands",
            title="Welcome"
        ))
        
        async with agent_context() as agent:
            console.print("[green]✓[/green] Agent initialized successfully\n")
            
            # Show user info
            if user_id:
                console.print(f"[dim]User ID: {user_id}[/dim]")
            if session_id:
                console.print(f"[dim]Session ID: {session_id}[/dim]")
            console.print()
            
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
                        metrics = agent.get_metrics()
                        console.print(f"\n[dim]Queries: {metrics['total_queries']}, "
                                    f"Avg Response: {metrics['avg_response_time_ms']:.1f}ms[/dim]\n")
                        continue
                    
                    if not message.strip():
                        continue
                    
                    # Send message to agent
                    console.print("\n[bold green]Agent:[/bold green]", end=" ")
                    
                    if stream:
                        await _stream_response(agent, message, user_id, session_id, reasoning)
                    else:
                        response = await agent.arun(
                            message,
                            user_id=user_id,
                            session_id=session_id,
                            stream=False,
                            show_reasoning=reasoning
                        )
                        console.print(Markdown(response.content))
                    
                    console.print()
                    
                except KeyboardInterrupt:
                    console.print("\n[yellow]Use 'quit' to exit properly[/yellow]")
                    continue
                except Exception as e:
                    console.print(f"\n[red]Error: {e}[/red]\n")
                    continue
                    
    except Exception as e:
        console.print(f"[red]Failed to start chat: {e}[/red]")
        sys.exit(1)


async def _single_query(
    message: str,
    user_id: Optional[str],
    session_id: Optional[str],
    stream: bool,
    reasoning: bool,
    output_format: str,
    # structured: Optional[str],
    # json_mode: bool,
    config_file: Optional[str]
):
    """Execute a single query."""
    try:
        async with agent_context() as agent:
            # Structured output temporarily disabled
            # Standard query
            if stream:
                await _stream_response(agent, message, user_id, session_id, reasoning)
            else:
                response = await agent.arun(
                    message,
                    user_id=user_id,
                    session_id=session_id,
                    stream=False,
                    show_reasoning=reasoning
                )
                
                if output_format == "json":
                    import json
                    output = {
                        "content": response.content,
                        "metadata": response.metadata,
                        "duration_ms": response.duration_ms,
                        "timestamp": response.timestamp.isoformat()
                    }
                    console.print(json.dumps(output, indent=2))
                else:
                    console.print(Markdown(response.content))
                    
    except Exception as e:
        console.print(f"[red]Query failed: {e}[/red]")
        sys.exit(1)


async def _stream_response(
    agent: BlitzAgent,
    message: str,
    user_id: Optional[str],
    session_id: Optional[str],
    show_reasoning: bool
):
    """Stream agent response."""
    streaming_response = await agent.arun(
        message,
        user_id=user_id,
        session_id=session_id,
        stream=True,
        show_reasoning=show_reasoning
    )
    
    content_parts = []
    
    async for chunk in streaming_response:
        if chunk.get("type") == "content":
            content = chunk.get("data", "")
            content_parts.append(str(content))
            console.print(str(content), end="")
        
        if show_reasoning and "reasoning" in chunk:
            console.print(f"\n[dim]💭 {chunk['reasoning']}[/dim]")


async def _stream_structured_response(
    structured_agent,
    message: str,
    user_id: Optional[str],
    session_id: Optional[str],
    show_reasoning: bool
):
    """Stream structured agent response (simplified)."""
    try:
        # Structured output agents don't stream well, so we run normally
        response = await structured_agent.arun(message)
        from rich.pretty import pprint
        pprint(response.content)
    except Exception as e:
        console.print(f"[red]Structured query failed: {e}[/red]")


async def _get_history(
    user_id: str,
    session_id: Optional[str],
    limit: int,
    config_file: Optional[str]
):
    """Get conversation history."""
    try:
        async with agent_context() as agent:
            history = await agent.get_conversation_history(
                user_id=user_id,
                session_id=session_id,
                limit=limit
            )
            
            if not history:
                console.print(f"[yellow]No conversation history found for user {user_id}[/yellow]")
                return
            
            console.print(f"\n[bold]Conversation History ({len(history)} entries)[/bold]\n")
            
            for entry in reversed(history):  # Show newest first
                timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if entry.is_agent_response:
                    console.print(f"[dim]{timestamp}[/dim] [green]Agent:[/green] {entry.message}")
                else:
                    console.print(f"[dim]{timestamp}[/dim] [blue]User:[/blue] {entry.message}")
                console.print()
                
    except Exception as e:
        console.print(f"[red]Failed to get history: {e}[/red]")
        sys.exit(1)


async def _health_check():
    """Perform health check."""
    try:
        console.print("Performing health check...")
        
        async with agent_context() as agent:
            health = await agent.health_check()
            
            status = health.get("status", "unknown")
            if status == "healthy":
                console.print("[green]✓[/green] Agent is healthy")
            else:
                console.print(f"[yellow]⚠[/yellow] Agent status: {status}")
            
            # Show component status
            components = health.get("components", {})
            for component, status_info in components.items():
                comp_status = status_info.get("status", "unknown")
                if comp_status == "healthy":
                    console.print(f"  [green]✓[/green] {component}")
                else:
                    console.print(f"  [red]✗[/red] {component}: {comp_status}")
                    if "error" in status_info:
                        console.print(f"    {status_info['error']}")
                        
    except Exception as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        sys.exit(1)


async def _show_metrics():
    """Display current metrics."""
    try:
        async with agent_context() as agent:
            metrics = agent.get_metrics()
            
            console.print(Panel.fit(
                f"[bold]Total Queries:[/bold] {metrics.total_queries}\n"
                f"[bold]Success Rate:[/bold] {metrics.success_rate:.1%}\n"
                f"[bold]Avg Response Time:[/bold] {metrics.avg_response_time_ms:.1f}ms\n"
                f"[bold]Total Tokens:[/bold] {metrics.total_tokens_used:,}\n"
                f"[bold]Active Sessions:[/bold] {metrics.active_sessions}\n"
                f"[bold]Uptime:[/bold] {metrics.uptime_seconds:.0f}s",
                title="Agent Metrics"
            ))
            
            if metrics.top_tools:
                console.print("\n[bold]Top Tools:[/bold]")
                for tool in metrics.top_tools[:5]:
                    console.print(f"  • {tool['tool']}: {tool['usage']} uses")
                    
    except Exception as e:
        console.print(f"[red]Failed to get metrics: {e}[/red]")
        sys.exit(1)


def _show_config():
    """Display current configuration."""
    try:
        config = Config()
        
        console.print(Panel.fit(
            f"[bold]Model:[/bold] {config.model.reasoning_model}\n"
            f"[bold]Database:[/bold] {config.database.host}:{config.database.port}/{config.database.database}\n"
            f"[bold]MCP Server:[/bold] {config.mcp.server_url}\n"
            f"[bold]Streaming:[/bold] {config.agent.enable_streaming}\n"
            f"[bold]Reasoning:[/bold] {config.agent.stream_reasoning}\n"
            f"[bold]Memory Retention:[/bold] {config.agent.memory_retention_days} days",
            title="Configuration"
        ))
        
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        sys.exit(1)


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