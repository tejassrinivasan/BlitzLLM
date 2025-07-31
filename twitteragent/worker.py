#!/usr/bin/env python3
"""
Background Worker for NBA Twitter Agent
Runs NBA workflow automation 6 times per day using schedule library.
"""

import asyncio
import schedule
import time
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pathlib import Path
import signal
import sys

from twitter_agent import nba_twitter_agent, TwitterWorkflowRequest
from config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nba_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NBAWorkerScheduler:
    """Background scheduler for NBA Twitter workflow."""
    
    def __init__(self):
        self.is_running = False
        self.execution_log_file = "execution_log.json"
        self.status_file = "worker_status.json"
        self.execution_history = self._load_execution_history()
        self.setup_signal_handlers()
        
        # Calculate schedule times (6 times per day = every 4 hours)
        self.schedule_times = [
            "06:00",  # 6 AM
            "10:00",  # 10 AM
            "14:00",  # 2 PM
            "18:00",  # 6 PM
            "22:00",  # 10 PM
            "02:00"   # 2 AM
        ]
        
        logger.info(f"NBA Worker Scheduler initialized")
        logger.info(f"Scheduled execution times: {', '.join(self.schedule_times)}")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.is_running = False
        self._update_status("stopped", "Received shutdown signal")
        sys.exit(0)
    
    def _load_execution_history(self) -> List[Dict[str, Any]]:
        """Load execution history from file."""
        try:
            if os.path.exists(self.execution_log_file):
                with open(self.execution_log_file, 'r') as f:
                    data = json.load(f)
                    return data.get('executions', [])
            return []
        except Exception as e:
            logger.error(f"Error loading execution history: {e}")
            return []
    
    def _save_execution_history(self):
        """Save execution history to file."""
        try:
            # Keep only last 100 executions
            if len(self.execution_history) > 100:
                self.execution_history = self.execution_history[-100:]
            
            data = {
                'executions': self.execution_history,
                'last_updated': datetime.now().isoformat(),
                'total_executions': len(self.execution_history)
            }
            
            with open(self.execution_log_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving execution history: {e}")
    
    def _update_status(self, status: str, message: str = "", last_execution: Dict[str, Any] = None):
        """Update worker status file."""
        try:
            status_data = {
                'status': status,
                'message': message,
                'last_updated': datetime.now().isoformat(),
                'worker_uptime': self._get_uptime(),
                'next_scheduled_run': self._get_next_scheduled_run(),
                'total_executions': len(self.execution_history),
                'last_execution': last_execution
            }
            
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating status: {e}")
    
    def _get_uptime(self) -> str:
        """Get worker uptime."""
        # This is a simple implementation - in production you'd track start time
        return "unknown"
    
    def _get_next_scheduled_run(self) -> str:
        """Get next scheduled run time."""
        try:
            next_run = schedule.next_run()
            if next_run:
                return next_run.isoformat()
            return "unknown"
        except:
            return "unknown"
    
    async def execute_workflow(self, test_mode: bool = False) -> Dict[str, Any]:
        """Execute the NBA Twitter workflow."""
        execution_start = datetime.now()
        logger.info(f"🚀 Starting NBA workflow execution at {execution_start}")
        
        execution_result = {
            'execution_id': f"exec_{int(execution_start.timestamp())}",
            'start_time': execution_start.isoformat(),
            'test_mode': test_mode,
            'success': False,
            'error': None,
            'workflow_result': None,
            'duration_seconds': 0
        }
        
        try:
            # Create workflow request
            workflow_request = TwitterWorkflowRequest(
                force_standalone=False,
                test_mode=test_mode
            )
            
            # Execute the workflow
            workflow_result = await nba_twitter_agent.run_workflow(workflow_request)
            
            execution_result['workflow_result'] = workflow_result
            execution_result['success'] = workflow_result.get('success', False)
            
            if execution_result['success']:
                logger.info("✅ NBA workflow execution completed successfully")
            else:
                logger.warning("⚠️ NBA workflow execution completed with issues")
                
        except Exception as e:
            logger.error(f"❌ NBA workflow execution failed: {e}")
            execution_result['error'] = str(e)
            execution_result['success'] = False
        
        finally:
            execution_end = datetime.now()
            execution_result['end_time'] = execution_end.isoformat()
            execution_result['duration_seconds'] = (execution_end - execution_start).total_seconds()
            
            # Log execution
            self.execution_history.append(execution_result)
            self._save_execution_history()
            
            # Update status
            status_msg = "Execution completed successfully" if execution_result['success'] else "Execution failed"
            self._update_status("running", status_msg, execution_result)
            
            logger.info(f"⏱️ Execution duration: {execution_result['duration_seconds']:.2f} seconds")
        
        return execution_result
    
    def schedule_jobs(self):
        """Schedule all NBA workflow jobs."""
        logger.info("Setting up scheduled jobs...")
        
        for schedule_time in self.schedule_times:
            schedule.every().day.at(schedule_time).do(self._run_scheduled_workflow)
            logger.info(f"📅 Scheduled NBA workflow for {schedule_time}")
        
        logger.info(f"✅ All {len(self.schedule_times)} jobs scheduled successfully")
    
    def _run_scheduled_workflow(self):
        """Wrapper to run async workflow in sync context."""
        try:
            logger.info("🔔 Scheduled execution triggered")
            
            # Handle event loop detection properly
            try:
                # Try to get the current event loop
                asyncio.get_running_loop()
                # We're in an event loop, need to run in a new thread with new loop
                self._run_in_new_thread()
            except RuntimeError:
                # No running event loop, safe to use asyncio.run()
                asyncio.run(self.execute_workflow(test_mode=False))
                
        except Exception as e:
            logger.error(f"Error in scheduled workflow: {e}")
    
    def _run_in_new_thread(self):
        """Run workflow in a new thread with its own event loop."""
        import threading
        import queue
        
        result_queue = queue.Queue()
        
        def thread_worker():
            try:
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the workflow
                result = loop.run_until_complete(self.execute_workflow(test_mode=False))
                result_queue.put(('success', result))
                
            except Exception as e:
                result_queue.put(('error', e))
            finally:
                loop.close()
        
        # Start thread and wait for completion
        thread = threading.Thread(target=thread_worker)
        thread.start()
        thread.join()
        
        # Get result
        try:
            status, result = result_queue.get_nowait()
            if status == 'error':
                raise result
        except queue.Empty:
            logger.error("Thread completed but no result received")
    
    async def run_test_workflow(self):
        """Run a test workflow execution."""
        logger.info("🧪 Running test workflow...")
        result = await self.execute_workflow(test_mode=True)
        return result
    
    def start_scheduler(self):
        """Start the background scheduler."""
        logger.info("🎯 Starting NBA Worker Scheduler")
        self.is_running = True
        
        # Update status
        self._update_status("starting", "Initializing scheduler")
        
        # Schedule jobs
        self.schedule_jobs()
        
        # Update status
        self._update_status("running", f"Scheduler active with {len(self.schedule_times)} daily executions")
        
        logger.info("🏀 NBA Twitter Bot is now running!")
        logger.info(f"⏰ Next execution: {self._get_next_scheduled_run()}")
        
        # Main scheduling loop
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        finally:
            self.stop_scheduler()
    
    def stop_scheduler(self):
        """Stop the scheduler."""
        logger.info("🛑 Stopping NBA Worker Scheduler")
        self.is_running = False
        schedule.clear()
        self._update_status("stopped", "Scheduler stopped")
        logger.info("👋 NBA Worker Scheduler stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current worker status."""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading status: {e}")
        
        return {
            'status': 'unknown',
            'message': 'Status file not available',
            'last_updated': datetime.now().isoformat()
        }
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self.execution_history:
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'success_rate': 0.0,
                'last_execution': None
            }
        
        successful = sum(1 for exec in self.execution_history if exec.get('success', False))
        failed = len(self.execution_history) - successful
        
        return {
            'total_executions': len(self.execution_history),
            'successful_executions': successful,
            'failed_executions': failed,
            'success_rate': (successful / len(self.execution_history)) * 100,
            'last_execution': self.execution_history[-1] if self.execution_history else None,
            'average_duration': sum(exec.get('duration_seconds', 0) for exec in self.execution_history) / len(self.execution_history)
        }

# Global scheduler instance
scheduler = NBAWorkerScheduler()

async def main():
    """Main function for testing or manual execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NBA Twitter Worker')
    parser.add_argument('--test', action='store_true', help='Run test workflow')
    parser.add_argument('--status', action='store_true', help='Show status')
    parser.add_argument('--stats', action='store_true', help='Show execution stats')
    parser.add_argument('--run-once', action='store_true', help='Run workflow once')
    
    args = parser.parse_args()
    
    if args.status:
        status = scheduler.get_status()
        print(json.dumps(status, indent=2))
        return
    
    if args.stats:
        stats = scheduler.get_execution_stats()
        print(json.dumps(stats, indent=2))
        return
    
    if args.test:
        logger.info("Running test workflow...")
        result = await scheduler.run_test_workflow()
        print(json.dumps(result, indent=2))
        return
    
    if args.run_once:
        logger.info("Running workflow once...")
        result = await scheduler.execute_workflow(test_mode=False)
        print(json.dumps(result, indent=2))
        return
    
    # Default: start the scheduler
    scheduler.start_scheduler()

if __name__ == "__main__":
    asyncio.run(main()) 