#!/usr/bin/env python3
"""
Main entry point for Twitter NBA Agent
Provides FastAPI interface for monitoring and control.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from config import Config
from twitter_agent import nba_twitter_agent, TwitterWorkflowRequest
from worker import scheduler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Request models
class ManualExecutionRequest(BaseModel):
    test_mode: bool = Field(False, description="Run in test mode without posting to Twitter")
    force_standalone: bool = Field(False, description="Force standalone question instead of searching for content")

class WorkerControlRequest(BaseModel):
    action: str = Field(..., description="Action to perform: start, stop, restart")

# Response models
class StatusResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    worker_status: Optional[Dict[str, Any]] = None
    agent_status: Optional[Dict[str, Any]] = None

# FastAPI app setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting Twitter NBA Agent API")
    
    # Validate configuration
    try:
        Config.validate()
        logger.info("Configuration validated successfully")
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    
    # Initialize agent (already done in twitter_agent.py)
    logger.info("NBA Twitter Agent initialized")
    
    # Start background worker
    await start_background_worker()
    
    yield
    
    # Shutdown background worker
    if scheduler.is_running:
        logger.info("Stopping background worker...")
        scheduler.stop_scheduler()
    
    logger.info("Shutting down Twitter NBA Agent API")

app = FastAPI(
    title="Twitter NBA Agent",
    description="Automated NBA content discovery and analytics posting system using Claude 4 Sonnet",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", response_model=StatusResponse)
async def root():
    """Root endpoint with basic status."""
    return StatusResponse(
        status="running",
        message="Twitter NBA Agent API is operational",
        timestamp=datetime.now().isoformat(),
        worker_status=scheduler.get_status(),
        agent_status={"mcp_available": nba_twitter_agent.mcp_server is not None}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "components": {
            "twitter_agent": "operational",
            "mcp_server": "available" if nba_twitter_agent.mcp_server else "unavailable",
            "scheduler": scheduler.get_status().get("status", "unknown")
        }
    }

@app.get("/status")
async def get_status():
    """Get detailed system status."""
    worker_status = scheduler.get_status()
    execution_stats = scheduler.get_execution_stats()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "worker": worker_status,
        "execution_stats": execution_stats,
        "agent": {
            "mcp_available": nba_twitter_agent.mcp_server is not None,
            "twitter_clients_initialized": True,
            "processed_tweets_count": len(nba_twitter_agent.processed_tweets)
        },
        "configuration": {
            "runs_per_day": Config.WORKER_RUNS_PER_DAY,
            "interval_hours": Config.WORKER_INTERVAL_HOURS,
            "log_level": Config.LOG_LEVEL
        }
    }

@app.post("/execute")
async def manual_execution(request: ManualExecutionRequest):
    """Manually trigger workflow execution."""
    try:
        logger.info(f"Manual execution requested - test_mode: {request.test_mode}")
        
        # Execute workflow
        result = await scheduler.execute_workflow(test_mode=request.test_mode)
        
        return {
            "message": "Workflow execution completed",
            "timestamp": datetime.now().isoformat(),
            "execution_result": result
        }
        
    except Exception as e:
        logger.error(f"Manual execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@app.post("/test")
async def test_workflow():
    """Run a test workflow without posting to Twitter."""
    try:
        logger.info("Test workflow requested")
        
        result = await scheduler.run_test_workflow()
        
        return {
            "message": "Test workflow completed",
            "timestamp": datetime.now().isoformat(),
            "test_result": result
        }
        
    except Exception as e:
        logger.error(f"Test workflow failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@app.get("/logs")
async def get_execution_logs(limit: int = 10):
    """Get recent execution logs."""
    try:
        stats = scheduler.get_execution_stats()
        history = scheduler.execution_history[-limit:] if scheduler.execution_history else []
        
        return {
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
            "recent_executions": history
        }
        
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")

@app.post("/worker/control")
async def control_worker(request: WorkerControlRequest, background_tasks: BackgroundTasks):
    """Control the background worker."""
    try:
        action = request.action.lower()
        
        if action == "start":
            if scheduler.is_running:
                return {"message": "Worker is already running", "timestamp": datetime.now().isoformat()}
            
            # Start scheduler in background
            background_tasks.add_task(scheduler.start_scheduler)
            return {"message": "Worker start initiated", "timestamp": datetime.now().isoformat()}
            
        elif action == "stop":
            if not scheduler.is_running:
                return {"message": "Worker is not running", "timestamp": datetime.now().isoformat()}
            
            scheduler.stop_scheduler()
            return {"message": "Worker stopped", "timestamp": datetime.now().isoformat()}
            
        elif action == "restart":
            if scheduler.is_running:
                scheduler.stop_scheduler()
            
            # Start scheduler in background
            background_tasks.add_task(scheduler.start_scheduler)
            return {"message": "Worker restart initiated", "timestamp": datetime.now().isoformat()}
            
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}. Use start, stop, or restart.")
            
    except Exception as e:
        logger.error(f"Worker control failed: {e}")
        raise HTTPException(status_code=500, detail=f"Worker control failed: {str(e)}")

@app.get("/config")
async def get_configuration():
    """Get current configuration (without sensitive data)."""
    return {
        "worker": {
            "runs_per_day": Config.WORKER_RUNS_PER_DAY,
            "interval_hours": Config.WORKER_INTERVAL_HOURS
        },
        "server": {
            "host": Config.HOST,
            "port": Config.PORT,
            "log_level": Config.LOG_LEVEL
        },
        "mcp": {
            "command": Config.MCP_COMMAND
        },
        "twitter": {
            "accounts_configured": {
                "blitz_analytics": bool(Config.BLITZANALYTICS_BEARER_TOKEN),
                "tejsri": bool(Config.TEJSRI_BEARER_TOKEN),
                "blitz_ai_bot": bool(Config.BLITZAI_BEARER_TOKEN)
            }
        }
    }

# Background worker startup
async def start_background_worker():
    """Start the background worker if not running."""
    if not scheduler.is_running:
        logger.info("Starting background worker...")
        # Run scheduler in a separate thread to avoid event loop conflicts
        import threading
        worker_thread = threading.Thread(target=scheduler.start_scheduler, daemon=True)
        worker_thread.start()

if __name__ == "__main__":
    import uvicorn
    
    # Note: Don't start background worker here, let it be started via FastAPI lifecycle
    # The lifespan function will handle worker startup
    
    # Start FastAPI server
    uvicorn.run(
        app, 
        host=Config.HOST, 
        port=Config.PORT, 
        log_level=Config.LOG_LEVEL.lower()
    ) 