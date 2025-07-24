#!/usr/bin/env python3
"""
NBA Twitter Bot System - Run Both Bots

This script manages both NBA Twitter bots:
1. Scheduled NBA Analytics Bot (finds tweets, posts questions & analytics)
2. Mention Listener Bot (responds to @BlitzAIBot mentions with NBA analytics)

Usage:
    python run_both_bots.py

Features:
- 🏀 NBA-only content filtering (no NFL/other sports)
- 📊 Real NBA statistics and analytics
- ⏰ 24-hour tweet filtering for freshness  
- 🎯 Smart variety in tweet selection
- 💬 Instant response to mentions

Author: BlitzLLM Team
"""

import asyncio
import subprocess
import signal
import sys
import os
from pathlib import Path

# Add blitz source to path
sys.path.append(str(Path(__file__).parent.parent / 'blitz' / 'src'))

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n🛑 Shutting down NBA Twitter bots...")
    sys.exit(0)

async def run_scheduled_bot():
    """Run the scheduled NBA workflow"""
    from nba_scheduler import run_scheduled_workflow
    
    print("📅 Starting scheduled NBA workflow bot...")
    while True:
        try:
            await run_scheduled_workflow()
            print("⏰ Workflow completed, waiting 30 minutes...")
            await asyncio.sleep(1800)  # 30 minutes between runs
        except Exception as e:
            print(f"❌ Scheduled bot error: {e}")
            await asyncio.sleep(300)  # 5 minutes on error

async def run_mention_listener():
    """Run the mention listener bot"""
    from mention_listener_nba import main as mention_main
    
    print("👂 Starting mention listener bot...")
    while True:
        try:
            await mention_main()
        except Exception as e:
            print(f"❌ Mention listener error: {e}")
            await asyncio.sleep(60)  # 1 minute on error

async def main():
    """Run both bots concurrently"""
    print("🚀 Starting NBA Twitter Bot System")
    print("=" * 50)
    print("🏀 NBA Analytics & Question Generation")
    print("💬 Mention Response System")
    print("📊 Real-time NBA Statistics")
    print("=" * 50)
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run both bots concurrently
    await asyncio.gather(
        run_scheduled_bot(),
        run_mention_listener(),
        return_exceptions=True
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🏁 NBA Twitter bots stopped.")
    except Exception as e:
        print(f"💥 System error: {e}")
        sys.exit(1) 