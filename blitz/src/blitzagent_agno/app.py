"""
FastAPI App for BlitzAgent using Agno's FastAPIApp wrapper.

This module creates a production-ready FastAPI application using Agno's
FastAPIApp class, making it easy to deploy to services like Render.
"""

import asyncio
import os
import structlog
from typing import Optional

from agno.app.fastapi.app import FastAPIApp
from agno.agent import Agent
from agno.models.gemini import Gemini
from fastapi import FastAPI

from .config import get_config, Config

logger = structlog.get_logger(__name__)


async def create_simple_agent() -> Agent:
    """Create a simple agent for testing registration."""
    try:
        # Create a simple Gemini model
        model = Gemini(
            id="gemini-2.5-pro",
            api_key=os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY")),
            temperature=0
        )
        
        # Create minimal agent with explicit agent_id
        agent = Agent(
            name="BlitzAgent",
            agent_id="blitzagent",  # Simple ID
            model=model,
            description="AI agent for sports analytics",
            instructions="You are a helpful AI assistant for sports analytics.",
            markdown=True
        )
        
        logger.info(f"Simple agent created with ID: {agent.agent_id}")
        return agent
        
    except Exception as e:
        logger.error("Failed to create simple agent", error=str(e))
        raise


async def create_blitz_fastapi_app(
    config: Optional[Config] = None,
    model_override: Optional[str] = None,
    port: int = 8000
) -> FastAPIApp:
    """
    Create BlitzAgent FastAPI app using Agno's FastAPIApp wrapper.
    
    Args:
        config: Optional configuration override
        model_override: Optional model override (e.g., "gpt-4o", "gemini-2.5-pro")
        port: Port to run on
        
    Returns:
        Configured FastAPIApp instance
    """
    try:
        logger.info("Creating simplified BlitzAgent FastAPI app")
        
        # Create simple agent for testing
        agent = await create_simple_agent()
        
        logger.info("Simple agent created successfully")
        
        # Create FastAPI app using Agno's wrapper
        fastapi_app = FastAPIApp(
            agents=[agent],
            name="BlitzAgent",
            description="Simplified AI Agent for testing.",
        )
        
        logger.info(f"FastAPI app created, will serve on port {port}")
        return fastapi_app
        
    except Exception as e:
        logger.error("Failed to create FastAPI app", error=str(e))
        raise


def create_app() -> FastAPI:
    """
    Create and return the FastAPI app instance.
    This is the main entry point for deployment services like Render.
    """
    try:
        # Get model override from environment variable
        model_override = os.getenv("MODEL_OVERRIDE")
        port = int(os.getenv("PORT", "8000"))
        
        # Run the async app creation
        async def _create_app():
            fastapi_app = await create_blitz_fastapi_app(
                model_override=model_override,
                port=port
            )
            # Get the FastAPI app and add our custom endpoints
            app = fastapi_app.get_app(use_async=True)
            
            # Add custom endpoints to the extracted app
            @app.get("/")
            async def root():
                """Root endpoint for deployment verification."""
                return {
                    "service": "BlitzAgent",
                    "status": "running", 
                    "description": "Simplified AI Agent for testing",
                    "version": "0.1.0-simple",
                    "endpoints": {
                        "chat": "/v1/runs",
                        "status": "/v1/status", 
                        "docs": "/docs",
                        "health": "/health"
                    },
                    "model": model_override or "gemini-2.5-pro"
                }
            
            @app.get("/health")
            async def health():
                """Health check endpoint for deployment monitoring."""
                return {
                    "status": "healthy",
                    "service": "BlitzAgent",
                    "model": model_override or "gemini-2.5-pro",
                    "timestamp": 0
                }
            
            return app
        
        # Handle event loop properly
        try:
            # Check if we're already in an async context
            loop = asyncio.get_running_loop()
            # If we get here, we're in an async context, so we need to create a task
            import concurrent.futures
            import threading
            
            def run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(_create_app())
                finally:
                    new_loop.close()
            
            # Run in a separate thread with its own event loop
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_new_loop)
                app = future.result()
                
        except RuntimeError:
            # No event loop is running, we can create one
            app = asyncio.run(_create_app())
        

        
        logger.info("FastAPI app created successfully", model=model_override, port=port)
        return app
        
    except Exception as e:
        logger.error("Failed to create app", error=str(e))
        # Return a minimal error app
        from fastapi import FastAPI, HTTPException
        error_app = FastAPI(title="BlitzAgent Error")
        
        @error_app.get("/")
        async def error_root():
            return {
                "service": "BlitzAgent",
                "status": "error",
                "error": str(e),
                "message": "Service initialization failed"
            }
            
        @error_app.get("/health")
        async def error_health():
            raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
            
        return error_app


# Create the app instance for deployment
app = create_app()


if __name__ == "__main__":
    """
    Run the FastAPI app locally for development.
    For production, use: uvicorn blitz.app:app
    """
    import uvicorn
    
    # Get configuration
    try:
        config = get_config()
        port = int(os.getenv("PORT", str(config.server.port)))
        host = os.getenv("HOST", config.server.host)
    except:
        port = int(os.getenv("PORT", "8000"))
        host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting BlitzAgent FastAPI server on {host}:{port}")
    
    uvicorn.run(
        "blitz.app:app",
        host=host,
        port=port,
        reload=False,
        workers=1,
        log_level="info"
    ) 