# BlitzAgent Architecture: Agent Factory Pattern

## Overview

The BlitzAgent codebase now uses a clean **Agent Factory Pattern** to create different types of agents optimized for specific use cases. This eliminates code duplication and provides a consistent interface across all agent types.

## Problem Solved

**Before:** Agent creation was duplicated across multiple files:
- `agent.py` created the core BlitzAgent 
- `playground.py` created a separate Agno Agent wrapper
- `cli.py` used yet another approach
- Each file had its own agent configuration logic

**After:** Single factory creates all agent types with shared configuration and components.

## Agent Types

### 1. Basic Agent (`AgentType.BASIC`)
- **Purpose**: Core BlitzAgent functionality
- **Features**: Full semantic memory, MCP tools, streaming
- **Use Case**: Direct API usage, custom integrations
- **Returns**: `BlitzAgent` instance

### 2. CLI Agent (`AgentType.CLI`)
- **Purpose**: Command-line interface
- **Features**: Terminal-optimized output, reduced memory usage
- **Use Case**: CLI commands, scripting
- **Returns**: Agno `Agent` instance

### 3. Playground Agent (`AgentType.PLAYGROUND`)
- **Purpose**: Web playground interface
- **Features**: Human-in-the-loop, confirmation prompts, rich UI
- **Use Case**: Interactive web interface
- **Returns**: Agno `Agent` instance

### 4. Server Agent (`AgentType.SERVER`)
- **Purpose**: API server deployments
- **Features**: Structured responses, API-friendly format
- **Use Case**: REST APIs, microservices
- **Returns**: Agno `Agent` instance

### 5. Hybrid Playground Agent (`"hybrid_playground"`)
- **Purpose**: Best of both worlds
- **Features**: BlitzAgent core + Agno Playground compatibility
- **Use Case**: Advanced playground with full semantic memory
- **Returns**: `PlaygroundAgentWrapper` instance

### 6. Query Generator Agent (`AgentType.QUERY_GENERATOR`)
- **Purpose**: Generate multiple query variations from a base query
- **Features**: 6-step workflow, insight mode only, no memory
- **Use Case**: Creating diverse query sets for training and exploration
- **Returns**: Agno `Agent` instance

## Usage Examples

### Creating Different Agent Types

```python
from blitzagent_agno.agent_factory import (
    create_agent, AgentType, RuntimeContext, RuntimeMode, ToneStyle
)
from blitzagent_agno.config import load_config

# Load configuration
config = load_config()

# Create runtime context
context = RuntimeContext(
    mode=RuntimeMode.CONVERSATION,  # or INSIGHT
    tone=ToneStyle.PROFESSIONAL,    # or CASUAL, ANALYTICAL, etc.
    user_id="user_123",
    session_id="session_456"
)

# Create a basic agent
basic_agent = await create_agent(AgentType.BASIC, config, context)

# Create a CLI agent
cli_agent = await create_agent(AgentType.CLI, config, context)

# Create a playground agent
playground_agent = await create_agent(AgentType.PLAYGROUND, config, context)

# Create a server agent
server_agent = await create_agent(AgentType.SERVER, config, context)

# Create a query generator agent
query_generator = await create_agent(AgentType.QUERY_GENERATOR, config, context)

# Create a hybrid playground agent
hybrid_agent = await create_agent("hybrid_playground", config, context)
```

### Agent-Specific Features

```python
# Basic agent - full BlitzAgent features
response = await basic_agent.run("Query", stream=True, show_reasoning=True)

# CLI agent - optimized for terminal
response = await cli_agent.arun("Query")  # No markdown formatting

# Playground agent - web-optimized
response = await playground_agent.arun("Query")  # Rich formatting

# Server agent - API-optimized  
response = await server_agent.arun("Query")  # Structured response

# Query generator - creates multiple variations
response = await query_generator.arun(
    "Generate variations for: Find clutch NBA players"
)

# Hybrid agent - combines both approaches
response = await hybrid_agent.arun("Query")  # Full features + web compatibility
```

### Runtime Context Features

```python
# Insight mode - memory disabled, comprehensive analysis
insight_context = RuntimeContext(
    mode=RuntimeMode.INSIGHT,
    tone=ToneStyle.ANALYTICAL
)

# Conversation mode - memory enabled, brief responses
conversation_context = RuntimeContext(
    mode=RuntimeMode.CONVERSATION,
    tone=ToneStyle.CASUAL,
    user_id="user_123",
    session_id="chat_001"
)

# Custom instructions
custom_context = RuntimeContext(
    mode=RuntimeMode.INSIGHT,
    tone=ToneStyle.PROFESSIONAL,
    custom_instructions="Focus on defensive statistics and provide coaching recommendations"
)

# API deployment example
api_context = RuntimeContext(
    mode=RuntimeMode(request.json.get('mode', 'conversation')),
    tone=ToneStyle(request.json.get('tone', 'professional')),
    user_id=request.json.get('user_id'),
    session_id=request.json.get('session_id')
)
```

## Runtime Context System

### 🎯 Modes

- **INSIGHT Mode**: Memory disabled, comprehensive analysis with 2-3 key insights
- **CONVERSATION Mode**: Memory enabled, brief contextual responses

### 🎨 Tone Styles

- **PROFESSIONAL**: Expert, formal tone
- **CASUAL**: Friendly, easy-to-understand
- **ANALYTICAL**: Data-driven, detailed reasoning
- **CONCISE**: Brief, focused responses
- **DETAILED**: Comprehensive explanations
- **FRIENDLY**: Warm, approachable

### ⚙️ Context Configuration

```python
RuntimeContext(
    mode=RuntimeMode.INSIGHT,           # Memory disabled
    tone=ToneStyle.ANALYTICAL,          # Data-driven responses
    user_id="analyst_001",              # User tracking
    session_id="session_123",           # Session tracking
    custom_instructions="Focus on..."   # Additional instructions
)
```

## Factory Components

### Core Factory Functions

- `create_blitz_agent()` - Creates core BlitzAgent
- `create_playground_agent()` - Creates Agno playground agent
- `create_cli_agent()` - Creates CLI-optimized agent
- `create_server_agent()` - Creates server-optimized agent
- `create_query_generator_agent()` - Creates query variation generator
- `create_hybrid_playground_agent()` - Creates hybrid wrapper

### Shared Components

- `create_agno_model()` - Model configuration
- `create_mcp_tools()` - MCP server connection
- `create_agno_storage()` - PostgreSQL storage
- `create_agno_memory()` - Conversation memory
- `get_agent_instructions()` - Type-specific instructions

### Configuration

All agents share the same configuration system but apply different optimizations:

- **CLI**: Reduced memory, plain text output
- **Playground**: Rich formatting, confirmations enabled
- **Server**: Structured responses, API metadata
- **Hybrid**: Full features with playground compatibility

## Benefits

✅ **DRY Principle**: No code duplication across files  
✅ **Consistency**: Same configuration applies to all agent types  
✅ **Maintainability**: Single place to update agent creation logic  
✅ **Extensibility**: Easy to add new agent types  
✅ **Separation of Concerns**: Each agent type optimized for its use case  
✅ **Type Safety**: Clear interfaces and return types  

## File Structure

```
src/blitzagent_agno/
├── agent_factory.py          # 🆕 Factory for all agent types
├── agent.py                  # Core BlitzAgent class
├── playground.py             # Playground server (now uses factory)
├── cli.py                    # CLI interface (now uses factory)
├── server.py                 # API server (now uses factory)
└── config.py                 # Shared configuration

examples/
├── agent_types_demo.py       # 🆕 Demo of all agent types
├── query_generator_demo.py   # 🆕 Query generator agent demo
└── api_context_demo.py       # 🆕 API deployment with runtime context
```

## Adding New Agent Types

To add a new agent type:

1. Create a factory function in `agent_factory.py`:
```python
async def create_my_agent(config: Optional[Config] = None) -> Agent:
    # Custom agent configuration
    pass
```

2. Add to the factory registry:
```python
AGENT_FACTORIES = {
    # ... existing types
    "my_agent": create_my_agent,
}
```

3. Add agent type constant:
```python
class AgentType:
    # ... existing types
    MY_AGENT = "my_agent"
```

4. Use it:
```python
my_agent = await create_agent(AgentType.MY_AGENT, config)
```

## Migration Guide

### Old Way (Duplicated)
```python
# playground.py
agent = Agent(
    name="BlitzAgent", 
    tools=[...], 
    instructions="...", 
    model=model,
    # ... lots of configuration
)

# cli.py  
agent = Agent(
    name="BlitzAgent CLI",
    tools=[...],
    instructions="...",
    model=model,
    # ... duplicate configuration
)
```

### New Way (Factory)
```python
# playground.py
agent = await create_agent(AgentType.PLAYGROUND, config)

# cli.py
agent = await create_agent(AgentType.CLI, config)
```

## Demo

Run the demo to see all agent types in action:

```bash
cd blitzagent-agno
python examples/agent_types_demo.py
```

This architecture sets you up for success as you add more agent types and use cases! 🚀 