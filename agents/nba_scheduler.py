#!/usr/bin/env python3
"""
NBA Twitter Bot Scheduler - 6x Daily Automated Posting
Features: Smart tweet selection, duplicate avoidance, engagement prioritization
"""

import asyncio
import schedule
import time
import logging
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add the blitz package to the path
sys.path.append(str(Path(__file__).parent.parent / "blitz" / "src"))

# Import our production workflow
import production_ready_nba
from production_ready_nba import search_smart_nba_content, generate_smart_question, generate_mcp_analytics_response, post_question, post_analytics_response

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nba_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File to track processed tweets
PROCESSED_TWEETS_FILE = "processed_tweets.json"
SCHEDULING_LOG_FILE = "scheduling_log.json"

def load_processed_tweets():
    """Load list of already processed tweet IDs."""
    try:
        if os.path.exists(PROCESSED_TWEETS_FILE):
            with open(PROCESSED_TWEETS_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get('processed_tweet_ids', []))
        return set()
    except Exception as e:
        logger.error(f"Error loading processed tweets: {e}")
        return set()

def save_processed_tweet(tweet_id):
    """Save a tweet ID as processed."""
    try:
        processed_tweets = load_processed_tweets()
        processed_tweets.add(str(tweet_id))
        
        # Keep only last 1000 processed tweets to prevent file from growing too large
        if len(processed_tweets) > 1000:
            processed_tweets = set(list(processed_tweets)[-1000:])
        
        data = {
            'processed_tweet_ids': list(processed_tweets),
            'last_updated': datetime.now().isoformat()
        }
        
        with open(PROCESSED_TWEETS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error saving processed tweet: {e}")

def log_scheduling_run(success, tweet_id=None, question=None, error=None):
    """Log details about each scheduled run."""
    try:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'tweet_id': tweet_id,
            'question': question,
            'error': str(error) if error else None
        }
        
        # Load existing log
        log_data = []
        if os.path.exists(SCHEDULING_LOG_FILE):
            with open(SCHEDULING_LOG_FILE, 'r') as f:
                log_data = json.load(f)
        
        # Add new entry
        log_data.append(log_entry)
        
        # Keep only last 100 entries
        if len(log_data) > 100:
            log_data = log_data[-100:]
        
        # Save updated log
        with open(SCHEDULING_LOG_FILE, 'w') as f:
            json.dump(log_data, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error logging scheduling run: {e}")

def calculate_tweet_score(tweet, processed_tweets):
    """Calculate an intelligent score for tweet selection."""
    if str(tweet['id']) in processed_tweets:
        return -1  # Already processed
    
    metrics = tweet['metrics']
    
    # Base engagement score
    engagement_score = (
        metrics['like_count'] * 2 +
        metrics['retweet_count'] * 3 +
        metrics['reply_count'] * 1
    )
    
    # Recency bonus (prefer tweets from last 24 hours)
    hours_old = (datetime.now(tweet['created_at'].tzinfo) - tweet['created_at']).total_seconds() / 3600
    recency_bonus = max(0, 100 - hours_old * 2)
    
    # Question potential bonus
    text_lower = tweet['text'].lower()
    question_potential = 0
    
    # High question potential keywords
    star_players = ['curry', 'lebron', 'luka', 'giannis', 'tatum', 'durant', 'davis', 'jokic']
    popular_teams = ['lakers', 'warriors', 'celtics', 'heat', 'nets', 'nuggets']
    stats_keywords = ['points', 'rebounds', 'assists', 'wins', 'record', 'season', 'game']
    
    for player in star_players:
        if player in text_lower:
            question_potential += 50
            
    for team in popular_teams:
        if team in text_lower:
            question_potential += 30
            
    for stat in stats_keywords:
        if stat in text_lower:
            question_potential += 20
    
    # Avoid low-potential content
    low_potential = ['injury report', 'suspended', 'fine', 'trade rumor', 'contract details']
    for low in low_potential:
        if low in text_lower:
            question_potential -= 30
    
    # Heavily penalize signing/roster moves (like Koloko) to avoid repetition
    if any(roster in text_lower for roster in ['sign', 'signed', 'signing', 'two-way', 'roster', 'waive', 'waived']):
        question_potential -= 100  # Heavy penalty for roster moves
    
    # News vs performance bonus (prefer performance stories)
    if any(perf in text_lower for perf in ['scored', 'recorded', 'shot', 'made', 'hit']):
        question_potential += 40
    
    # Diversity bonus - prefer different types of content
    content_variety_bonus = 0
    if any(stat in text_lower for stat in ['season high', 'career high', 'record', 'milestone']):
        content_variety_bonus += 60  # Prefer achievement stories
    if any(game in text_lower for game in ['tonight', 'last night', 'game winner', 'overtime']):
        content_variety_bonus += 80  # Prefer game stories
    
    # Final score calculation
    final_score = engagement_score + recency_bonus + question_potential + content_variety_bonus
    
    return final_score

async def select_best_tweet():
    """Select the best tweet for question generation with smart scoring."""
    logger.info("🔍 Starting intelligent tweet selection...")
    
    try:
        # Get processed tweets to avoid duplicates
        processed_tweets = load_processed_tweets()
        logger.info(f"📝 Loaded {len(processed_tweets)} previously processed tweets")
        
        # Search for ALL tweets to enable intelligent selection
        all_tweets = await search_smart_nba_content(return_all=True)
        if not all_tweets:
            logger.warning("No tweets found from search")
            return None
            
        logger.info(f"🔍 Found {len(all_tweets)} total tweets for intelligent selection")
        
        # Score all tweets using intelligent algorithm
        scored_tweets = []
        for tweet in all_tweets:
            score = calculate_tweet_score(tweet, processed_tweets)
            if score > 0:  # Only consider unprocessed tweets with positive scores
                scored_tweets.append((score, tweet))
        
        if not scored_tweets:
            logger.warning("❌ No suitable unprocessed tweets found")
            return None
        
        # Sort by score (highest first) and select from top candidates
        scored_tweets.sort(key=lambda x: x[0], reverse=True)
        
        # Add some randomization to avoid always picking the same type of content
        # Select from top 5 tweets to add variety
        top_candidates = scored_tweets[:min(5, len(scored_tweets))]
        import random
        selected_score, selected_tweet = random.choice(top_candidates)
        
        logger.info(f"✅ Selected tweet (score: {selected_score:.1f}): {selected_tweet['text'][:60]}...")
        logger.info(f"📊 Engagement: {selected_tweet['metrics']['like_count']} likes, {selected_tweet['metrics']['retweet_count']} RTs")
        logger.info(f"🎯 Selected from top {len(top_candidates)} candidates for variety")
        
        return selected_tweet
        
    except Exception as e:
        logger.error(f"Error in tweet selection: {e}")
        return None

async def run_scheduled_workflow():
    """Run the NBA workflow with intelligent tweet selection and duplicate avoidance."""
    logger.info("🚀 Starting scheduled NBA workflow...")
    
    try:
        # Select best available tweet
        selected_tweet = await select_best_tweet()
        
        if not selected_tweet:
            logger.warning("❌ No suitable tweet found, skipping this run")
            log_scheduling_run(success=False, error="No suitable tweet found")
            return
        
        # Generate question
        logger.info("🤖 Generating question...")
        question = await generate_smart_question(selected_tweet)
        
        # Post question as reply
        logger.info("📱 Posting question...")
        question_tweet_id = await post_question(question, selected_tweet['id'])
        
        if not question_tweet_id:
            logger.error("❌ Failed to post question")
            log_scheduling_run(success=False, error="Failed to post question")
            return
        
        # Wait before analytics response
        logger.info("⏳ Waiting before analytics response...")
        await asyncio.sleep(3)
        
        # Generate analytics response
        logger.info("📊 Generating analytics response...")
        analytics_response = await generate_mcp_analytics_response(question)
        
        # Post analytics response
        logger.info("🤖 Posting analytics response...")
        response_tweet_id = await post_analytics_response(analytics_response, question_tweet_id)
        
        if response_tweet_id:
            # Mark tweet as processed
            save_processed_tweet(selected_tweet['id'])
            
            logger.info("🎉 Workflow completed successfully!")
            logger.info(f"🔗 Question: https://twitter.com/tejsri01/status/{question_tweet_id}")
            logger.info(f"🔗 Response: https://twitter.com/BlitzAIBot/status/{response_tweet_id}")
            
            log_scheduling_run(
                success=True,
                tweet_id=selected_tweet['id'],
                question=question
            )
        else:
            logger.error("❌ Failed to post analytics response")
            log_scheduling_run(success=False, error="Failed to post analytics response")
            
    except Exception as e:
        logger.error(f"❌ Scheduled workflow failed: {e}")
        log_scheduling_run(success=False, error=str(e))

def run_workflow_sync():
    """Synchronous wrapper for the async workflow."""
    try:
        asyncio.run(run_scheduled_workflow())
    except Exception as e:
        logger.error(f"Error in sync wrapper: {e}")

def setup_schedule():
    """Set up the 6 times daily schedule."""
    logger.info("📅 Setting up 6x daily NBA Twitter schedule...")
    
    # Schedule 6 times throughout the day for maximum engagement
    schedule.every().day.at("07:00").do(run_workflow_sync)  # Morning
    schedule.every().day.at("10:30").do(run_workflow_sync)  # Mid-morning
    schedule.every().day.at("13:00").do(run_workflow_sync)  # Lunch
    schedule.every().day.at("16:30").do(run_workflow_sync)  # Afternoon
    schedule.every().day.at("19:00").do(run_workflow_sync)  # Early evening
    schedule.every().day.at("21:30").do(run_workflow_sync)  # Prime time
    
    logger.info("✅ Schedule configured for 6 daily runs:")
    logger.info("   • 07:00 - Morning engagement")
    logger.info("   • 10:30 - Mid-morning activity")
    logger.info("   • 13:00 - Lunch time")
    logger.info("   • 16:30 - Afternoon peak")
    logger.info("   • 19:00 - Early evening")
    logger.info("   • 21:30 - Prime time")

def main():
    """Main scheduler function."""
    logger.info("🏀 NBA Twitter Bot Scheduler Starting...")
    logger.info("🎯 6x daily automated NBA analytics posting")
    logger.info("✅ Features: Smart tweet selection, duplicate avoidance, engagement optimization")
    
    setup_schedule()
    
    logger.info("🔄 Scheduler running... Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("⏹️ Scheduler stopped by user")
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")

if __name__ == "__main__":
    main() 