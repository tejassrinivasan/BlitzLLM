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
from fastapi import FastAPI

from .agent_factory import create_server_agent, RuntimeContext, RuntimeMode, ToneStyle
from .config import get_config, Config

logger = structlog.get_logger(__name__)


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
        # Load configuration
        if config is None:
            config = get_config()
        
        logger.info("Creating BlitzAgent FastAPI app", model_override=model_override)
        
        # Create runtime context for server mode
        context = RuntimeContext(
            mode=RuntimeMode.CONVERSATION,
            tone=ToneStyle.PROFESSIONAL
        )
        
        # Create the agent using the server agent factory
        agent = await create_server_agent(
            config=config,
            context=context,
            model_override=model_override
        )
        
        logger.info("BlitzAgent created successfully")
        
        # Create FastAPI app using Agno's wrapper
        fastapi_app = FastAPIApp(
            agent=agent,
            name="BlitzAgent",
            app_id="blitzagent",
            description="Advanced AI Agent for sports analytics and database insights with reasoning and memory capabilities.",
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
        
        # Run the async app creation in a new event loop
        async def _create_app():
            fastapi_app = await create_blitz_fastapi_app(
                model_override=model_override,
                port=port
            )
            return fastapi_app.get_app(use_async=True, prefix="/v1")
        
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Create the FastAPI app
        app = loop.run_until_complete(_create_app())
        
        # Add custom root endpoint for deployment verification
        @app.get("/")
        async def root():
            """Root endpoint for deployment verification."""
            return {
                "service": "BlitzAgent",
                "status": "running", 
                "description": "Advanced AI Agent for sports analytics and database insights",
                "version": "0.1.0",
                "endpoints": {
                    "chat": "/v1/run",
                    "docs": "/docs",
                    "health": "/health"
                },
                "model": model_override or "default"
            }
        
        @app.get("/health")
        async def health():
            """Health check endpoint for deployment monitoring."""
            return {
                "status": "healthy",
                "service": "BlitzAgent",
                "model": model_override or "default",
                "timestamp": asyncio.get_event_loop().time()
            }
        
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
    For production, use: uvicorn blitzagent_agno.app:app
    """
    import uvicorn
    
    # Get configuration
    config = get_config()
    port = int(os.getenv("PORT", str(config.server.port)))
    host = os.getenv("HOST", config.server.host)
    
    logger.info(f"Starting BlitzAgent FastAPI server on {host}:{port}")
    
    uvicorn.run(
        "blitzagent_agno.app:app",
        host=host,
        port=port,
        reload=config.server.auto_reload and not config.is_production(),
        workers=1,  # Use 1 worker for async app
        log_level="info"
    ) 