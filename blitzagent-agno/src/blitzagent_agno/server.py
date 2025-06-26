"""
FastAPI server for BlitzAgent Agno.

This module provides a web interface and REST API for the agent,
including chat endpoints, metrics dashboard, and admin features.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import structlog

from .agent import BlitzAgent, agent_context
from .agent_factory import RuntimeContext, RuntimeMode, ToneStyle
from .config import get_config, Config
from .metrics import MetricsMiddleware, get_metrics_collector
from .exceptions import BlitzAgentError, AuthenticationError


logger = structlog.get_logger(__name__)


# Pydantic models for API
class QueryRequest(BaseModel):
    """Request model for agent queries."""
    message: str = Field(..., description="Query message")
    user_id: Optional[str] = Field(None, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")
    stream: bool = Field(True, description="Enable streaming response")
    show_reasoning: bool = Field(True, description="Show reasoning steps")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class QueryResponse(BaseModel):
    """Response model for agent queries."""
    content: str
    reasoning_steps: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    timestamp: datetime
    duration_ms: int
    token_usage: Dict[str, int] = {}


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    components: Dict[str, Any]
    timestamp: str


class MetricsResponse(BaseModel):
    """Metrics response model."""
    total_queries: int
    total_errors: int
    avg_response_time_ms: float
    success_rate: float
    total_tokens_used: int
    avg_tokens_per_query: float
    active_sessions: int
    uptime_seconds: float


class ConversationHistoryRequest(BaseModel):
    """Request model for conversation history."""
    user_id: str
    session_id: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=100)


# Global agent instance
agent_instance: Optional[BlitzAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global agent_instance
    
    try:
        # Initialize agent with server context
        logger.info("Starting BlitzAgent server")
        context = RuntimeContext(mode=RuntimeMode.CONVERSATION, tone=ToneStyle.PROFESSIONAL)
        agent_instance = BlitzAgent(context=context)
        await agent_instance.initialize()
        logger.info("BlitzAgent initialized successfully")
        
        yield
        
    finally:
        # Cleanup
        if agent_instance:
            await agent_instance.cleanup()
        logger.info("BlitzAgent server shutdown complete")


def create_app(config: Optional[Config] = None) -> FastAPI:
    """Create FastAPI application."""
    if config is None:
        config = get_config()
    
    app = FastAPI(
        title="BlitzAgent Agno API",
        description="Advanced AI Agent with Reasoning and Memory",
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=config.server.cors_credentials,
        allow_methods=config.server.cors_methods,
        allow_headers=config.server.cors_headers,
    )
    
    # Add metrics middleware
    metrics_collector = get_metrics_collector()
    app.add_middleware(MetricsMiddleware, collector=metrics_collector)
    
    # Security
    security = HTTPBearer(auto_error=False) if config.security.api_key else None
    
    def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        """Verify API key if configured."""
        if config.security.api_key:
            if not credentials or credentials.credentials != config.security.api_key:
                raise HTTPException(status_code=401, detail="Invalid API key")
        return credentials
    
    # Routes
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Root endpoint with basic info."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>BlitzAgent Agno</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #333; text-align: center; }
                .feature { margin: 20px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #007bff; }
                .endpoints { background: #e9ecef; padding: 20px; border-radius: 5px; }
                .endpoint { margin: 10px 0; font-family: monospace; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 BlitzAgent Agno</h1>
                <p>Advanced AI Agent with Reasoning and Memory</p>
                
                <div class="feature">
                    <h3>✨ Features</h3>
                    <ul>
                        <li>Gemini 2.5 Pro reasoning model with streaming</li>
                        <li>PostgreSQL memory integration</li>
                        <li>Python MCP connectivity</li>
                        <li>Structured output with Pydantic</li>
                        <li>Real-time metrics and monitoring</li>
                    </ul>
                </div>
                
                <div class="endpoints">
                    <h3>🔗 API Endpoints</h3>
                    <div class="endpoint">POST /api/query - Send query to agent</div>
                    <div class="endpoint">GET /api/health - Health check</div>
                    <div class="endpoint">GET /api/metrics - Agent metrics</div>
                    <div class="endpoint">POST /api/history - Conversation history</div>
                    <div class="endpoint">WS /ws/chat - WebSocket chat</div>
                    <div class="endpoint">GET /docs - API documentation</div>
                </div>
            </div>
        </body>
        </html>
        """
    
    @app.post("/api/query", response_model=QueryResponse)
    async def query_agent(
        request: QueryRequest,
        background_tasks: BackgroundTasks,
        _: Any = Depends(verify_api_key)
    ):
        """Send query to the agent."""
        if not agent_instance:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        
        try:
            if request.stream:
                # For streaming, we need to use Server-Sent Events
                raise HTTPException(status_code=400, detail="Use /api/query/stream for streaming responses")
            
            response = await agent_instance.run(
                message=request.message,
                user_id=request.user_id,
                session_id=request.session_id,
                stream=False,
                show_reasoning=request.show_reasoning
            )
            
            return QueryResponse(
                content=response.content,
                reasoning_steps=response.reasoning_steps,
                tool_calls=response.tool_calls,
                metadata=response.metadata,
                timestamp=response.timestamp,
                duration_ms=response.duration_ms,
                token_usage=response.token_usage
            )
            
        except Exception as e:
            logger.error("Query failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
    
    @app.post("/api/query/stream")
    async def stream_query_agent(
        request: QueryRequest,
        _: Any = Depends(verify_api_key)
    ):
        """Stream query response from the agent."""
        if not agent_instance:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        
        async def generate_stream():
            try:
                streaming_response = await agent_instance.run(
                    message=request.message,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    stream=True,
                    show_reasoning=request.show_reasoning
                )
                
                async for chunk in streaming_response:
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                error_chunk = {
                    "type": "error",
                    "data": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
    
    @app.get("/api/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        if not agent_instance:
            return HealthResponse(
                status="initializing",
                components={},
                timestamp=datetime.utcnow().isoformat()
            )
        
        health = await agent_instance.health_check()
        return HealthResponse(
            status=health["status"],
            components=health["components"],
            timestamp=health["timestamp"]
        )
    
    @app.get("/api/metrics", response_model=MetricsResponse)
    async def get_metrics(_: Any = Depends(verify_api_key)):
        """Get agent metrics."""
        if not agent_instance:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        
        metrics = agent_instance.get_metrics()
        return MetricsResponse(
            total_queries=metrics.total_queries,
            total_errors=metrics.total_errors,
            avg_response_time_ms=metrics.avg_response_time_ms,
            success_rate=metrics.success_rate,
            total_tokens_used=metrics.total_tokens_used,
            avg_tokens_per_query=metrics.avg_tokens_per_query,
            active_sessions=metrics.active_sessions,
            uptime_seconds=metrics.uptime_seconds
        )
    
    @app.post("/api/history")
    async def get_conversation_history(
        request: ConversationHistoryRequest,
        _: Any = Depends(verify_api_key)
    ):
        """Get conversation history."""
        if not agent_instance:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        
        try:
            history = await agent_instance.get_conversation_history(
                user_id=request.user_id,
                session_id=request.session_id,
                limit=request.limit
            )
            
            return {
                "user_id": request.user_id,
                "session_id": request.session_id,
                "history": [
                    {
                        "message": entry.message,
                        "response": entry.response,
                        "is_agent_response": entry.is_agent_response,
                        "timestamp": entry.timestamp.isoformat(),
                        "metadata": entry.metadata
                    }
                    for entry in history
                ]
            }
            
        except Exception as e:
            logger.error("Failed to get history", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")
    
    @app.get("/api/tools")
    async def list_tools(_: Any = Depends(verify_api_key)):
        """List available tools."""
        if not agent_instance or not agent_instance.mcp_client:
            raise HTTPException(status_code=503, detail="Agent or MCP client not initialized")
        
        try:
            tools = await agent_instance.mcp_client.list_tools()
            return {"tools": tools}
            
        except Exception as e:
            logger.error("Failed to list tools", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")
    
    @app.post("/api/tools/{tool_name}/call")
    async def call_tool(
        tool_name: str,
        parameters: Dict[str, Any],
        _: Any = Depends(verify_api_key)
    ):
        """Call a specific tool."""
        if not agent_instance:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        
        try:
            result = await agent_instance.call_mcp_tool(tool_name, parameters)
            return {"tool": tool_name, "result": result}
            
        except Exception as e:
            logger.error("Tool call failed", tool_name=tool_name, error=str(e))
            raise HTTPException(status_code=500, detail=f"Tool call failed: {str(e)}")
    
    # WebSocket endpoint for real-time chat
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        """WebSocket endpoint for real-time chat."""
        await websocket.accept()
        
        if not agent_instance:
            await websocket.send_json({"type": "error", "data": "Agent not initialized"})
            await websocket.close()
            return
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                message = data.get("message", "")
                user_id = data.get("user_id")
                session_id = data.get("session_id")
                show_reasoning = data.get("show_reasoning", True)
                
                if not message:
                    continue
                
                # Send typing indicator
                await websocket.send_json({"type": "typing", "data": True})
                
                try:
                    # Stream response
                    streaming_response = await agent_instance.run(
                        message=message,
                        user_id=user_id,
                        session_id=session_id,
                        stream=True,
                        show_reasoning=show_reasoning
                    )
                    
                    async for chunk in streaming_response:
                        await websocket.send_json(chunk)
                    
                    # Send completion signal
                    await websocket.send_json({"type": "complete", "data": True})
                    
                except Exception as e:
                    await websocket.send_json({"type": "error", "data": str(e)})
                
                finally:
                    # Stop typing indicator
                    await websocket.send_json({"type": "typing", "data": False})
                    
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error("WebSocket error", error=str(e))
            await websocket.close()
    
    # Prometheus metrics endpoint
    @app.get("/metrics")
    async def prometheus_metrics():
        """Prometheus metrics endpoint."""
        metrics_collector = get_metrics_collector()
        metrics_text = metrics_collector.get_prometheus_metrics()
        return StreamingResponse(
            iter([metrics_text]),
            media_type="text/plain"
        )
    
    return app


def main():
    """Main server entry point."""
    config = get_config()
    
    # Create app
    app = create_app(config)
    
    # Start metrics server if enabled
    if config.monitoring.prometheus_enabled:
        try:
            metrics_collector = get_metrics_collector()
            metrics_collector.start_metrics_server(config.monitoring.prometheus_port)
        except Exception as e:
            logger.warning("Failed to start metrics server", error=str(e))
    
    # Run server
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload,
        workers=1,  # Must be 1 for lifespan events to work properly
        log_level=config.monitoring.log_level.lower()
    )


if __name__ == "__main__":
    main() 