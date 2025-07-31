#!/usr/bin/env python3
"""
Twitter NBA Agent using Pydantic AI Framework
Automated NBA content discovery and analytics posting system using Claude 4 Sonnet.
"""

import asyncio
import logging
import json
import random
from datetime import datetime, date
from typing import Optional, Any, Dict, List
from pathlib import Path
import tweepy
import os

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from dotenv import load_dotenv

from config import Config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Request models
class TwitterWorkflowRequest(BaseModel):
    """Request for Twitter workflow execution."""
    force_standalone: bool = Field(False, description="Force standalone question instead of searching for content")
    test_mode: bool = Field(False, description="Run in test mode without posting to Twitter")

class TwitterContent(BaseModel):
    """Twitter content model."""
    id: str
    text: str
    author_username: str
    metrics: Dict[str, int]
    created_at: str

# NBA Keywords for content filtering
NBA_KEYWORDS = [
    "NBA", "basketball", "points", "rebounds", "assists", "Lakers", "Warriors", 
    "Celtics", "Heat", "Nets", "playoff", "season", "game", "Curry",
    "LeBron", "Durant", "Giannis", "Luka", "Tatum", "Jokic", "scoring",
    "three-pointer", "dunk", "block", "steal", "franchise", "roster"
]

# Content to avoid
EXCLUDED_KEYWORDS = [
    "summer league", "summer-league", "summerleague", "vegas league", "las vegas",
    "FIBA", "international", "olympics", "team usa", "world cup", "eurobasket",
    "euroleague", "turkish league", "chinese league", "australian league", "nbl",
    "canada basketball", "germany basketball", "france basketball", "spain basketball",
    # NFL exclusions
    "NFL", "football", "Ravens", "quarterback", "touchdown", "yard", "Chiefs", "Bills",
    "Cowboys", "Patriots", "Steelers", "Packers", "49ers", "Eagles", "Giants", "Jets",
    "Lamar Jackson", "Josh Allen", "Patrick Mahomes", "Super Bowl", "NFL Draft"
]

# System prompt for NBA analytics (same as blitzagent)
NBA_ANALYTICS_PROMPT = """
You are an AI sports analytics agent with deep expertise in NBA data.
Your job is to analyze NBA questions and provide comprehensive, data-driven insights.

**CRITICAL: NBA DATABASE FOCUS**
- You are analyzing NBA basketball questions exclusively
- Always use league="nba" parameter for ALL MCP tools
- The system automatically connects to the NBA PostgreSQL database

**MANDATORY WORKFLOW SEQUENCE (FOLLOW EXACTLY, NO DEVIATIONS):**

**PHASE 1: SETUP (SEQUENTIAL)**
1. get_database_documentation(league="nba") 
2. recall_similar_db_queries(league="nba")

**PHASE 2: EXPLORATION (PARALLEL OK)**  
3. If needed: search_tables, inspect, sample (use sparingly)

**PHASE 3: EXECUTION (INTELLIGENT RETRY ALLOWED)**
4. query(league="nba") - Write comprehensive query
   **CRITICAL SQL REQUIREMENTS:**
   - SINGLE SQL statement ONLY - never multiple semicolon-separated queries
   - PostgreSQL prepared statements do NOT support multiple commands
   - Use JOINs, subqueries, CTEs within ONE statement if needed
   - NO: "SELECT ...; SELECT ...;" or multiple statements
5. validate() - Check the query results
6. **INTELLIGENT RETRY LOGIC:**
   - ✅ IF query FAILS (technical error) → Retry with inspect/sample/different query (MAX 2 retries)
   - ✅ IF validate says "inaccurate/poor results" → Retry with improved query (MAX 2 retries)
   - ✅ IF validate says "good/accurate" → STOP and return analysis

**RESPONSE STANDARDS**
- Provide comprehensive analysis with specific data points
- Include player/team names, statistics, time frames
- Focus on actionable basketball insights
- Use Twitter-friendly formatting (short paragraphs, emojis)
- End with a clear conclusion or prediction

**Twitter Response Guidelines:**
- Keep responses under 280 characters when possible, or use thread format
- Use basketball emojis (🏀 🔥 📊 ⭐ 🎯)
- Include relevant hashtags (#NBA #Basketball)
- Make insights accessible to casual fans

Today's Date: {current_date}

{user_context}
"""

class TwitterNBAAgent:
    def __init__(self):
        """Initialize the Twitter NBA agent with Claude 4 Sonnet and MCP tools."""
        # Validate configuration
        Config.validate()
        
        # Initialize Claude 4 Sonnet model with thinking capabilities enabled
        self.model_settings = AnthropicModelSettings(
            anthropic_thinking={'type': 'enabled', 'budget_tokens': 2048},
        )
        self.model = AnthropicModel("claude-sonnet-4-20250514")
        
        # Initialize MCP server
        import os
        mcp_env = os.environ.copy()
        mcp_env["LOG_LEVEL"] = "INFO"
        mcp_env["SKIP_MCP_CONNECTION_TEST"] = "true"
        
        # Set correct database credentials for NBA
        correct_password = "_V8fn.eo62B(gZD|OcQcu~0|aP8["
        mcp_env["POSTGRES_PASSWORD"] = correct_password
        mcp_env["POSTGRES_NBA_PASSWORD"] = correct_password
        mcp_env["POSTGRES_USER"] = "postgres"
        mcp_env["POSTGRES_HOST"] = "blitz-instance-1.cdu6kma429k4.us-west-2.rds.amazonaws.com"
        mcp_env["POSTGRES_PORT"] = "5432"
        mcp_env["POSTGRES_SSL"] = "true"
        
        # Clear conflicting variables
        mcp_env.pop("DATABASE_URL", None)
        mcp_env.pop("POSTGRES_DATABASE", None)
        
        try:
            self.mcp_server = MCPServerStdio(
                command=Config.MCP_COMMAND,
                args=["--quiet"],
                env=mcp_env
            )
            logger.info("MCP server initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MCP server: {str(e)}")
            self.mcp_server = None
        
        # Create the Pydantic AI agent
        if self.mcp_server:
            self.agent = Agent(
                model=self.model,
                model_settings=self.model_settings,
                deps_type=str,  # Context string
                toolsets=[self.mcp_server],
                retries=3,
                end_strategy='early'
            )
            logger.info("NBA Analytics agent created with MCP tools")
        else:
            raise RuntimeError("Failed to initialize MCP server - NBA analytics won't work")
        
        # Add system prompt
        @self.agent.system_prompt
        def get_system_prompt(ctx) -> str:
            user_context = ctx.deps if ctx.deps else ""
            return NBA_ANALYTICS_PROMPT.format(
                current_date=datetime.now().strftime("%Y-%m-%d"),
                user_context=f"\n\n### Additional Context:\n{user_context}" if user_context else ""
            )
        
        # Initialize Twitter clients
        self._setup_twitter_clients()
        
        # Load processed tweets tracking
        self.processed_tweets_file = "processed_tweets.json"
        self.processed_tweets = self._load_processed_tweets()
    
    def _setup_twitter_clients(self):
        """Setup Twitter API clients for different accounts."""
        # BlitzAnalytics client (for searching content)
        self.blitzanalytics_client = tweepy.Client(
            bearer_token=Config.BLITZANALYTICS_BEARER_TOKEN,
            consumer_key=Config.SHARED_CONSUMER_KEY,
            consumer_secret=Config.SHARED_CONSUMER_SECRET,
            access_token=Config.BLITZANALYTICS_ACCESS_TOKEN,
            access_token_secret=Config.BLITZANALYTICS_ACCESS_SECRET,
            wait_on_rate_limit=True
        )
        
        # tejsri01 client (for posting questions)
        self.tejsri_client = tweepy.Client(
            bearer_token=Config.TEJSRI_BEARER_TOKEN,
            consumer_key=Config.SHARED_CONSUMER_KEY,
            consumer_secret=Config.SHARED_CONSUMER_SECRET,
            access_token=Config.TEJSRI_ACCESS_TOKEN,
            access_token_secret=Config.TEJSRI_ACCESS_SECRET,
            wait_on_rate_limit=True
        )
        
        # BlitzAIBot client (for posting analytics responses)
        self.blitzai_client = tweepy.Client(
            bearer_token=Config.BLITZAI_BEARER_TOKEN,
            consumer_key=Config.SHARED_CONSUMER_KEY,
            consumer_secret=Config.SHARED_CONSUMER_SECRET,
            access_token=Config.BLITZAI_ACCESS_TOKEN,
            access_token_secret=Config.BLITZAI_ACCESS_SECRET,
            wait_on_rate_limit=True
        )
        
        logger.info("Twitter clients initialized successfully")
    
    def _load_processed_tweets(self) -> set:
        """Load processed tweet IDs from file."""
        try:
            if os.path.exists(self.processed_tweets_file):
                with open(self.processed_tweets_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_tweet_ids', []))
            return set()
        except Exception as e:
            logger.error(f"Error loading processed tweets: {e}")
            return set()
    
    def _save_processed_tweet(self, tweet_id: str):
        """Save a processed tweet ID."""
        try:
            self.processed_tweets.add(tweet_id)
            
            # Keep only last 1000 to prevent file growth
            if len(self.processed_tweets) > 1000:
                self.processed_tweets = set(list(self.processed_tweets)[-1000:])
            
            data = {
                'processed_tweet_ids': list(self.processed_tweets),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.processed_tweets_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving processed tweet: {e}")
    
    async def search_nba_content(self) -> Optional[TwitterContent]:
        """Search for trending NBA content on Twitter."""
        try:
            # Search queries for NBA content
            search_queries = [
                "NBA -is:retweet lang:en",
                "basketball -is:retweet lang:en",
                "Lakers OR Warriors OR Celtics -is:retweet lang:en",
                "LeBron OR Curry OR Durant -is:retweet lang:en",
                "NBA stats -is:retweet lang:en",
                "NBA playoffs -is:retweet lang:en"
            ]
            
            for query in search_queries:
                try:
                    tweets = self.blitzanalytics_client.search_recent_tweets(
                        query=query,
                        max_results=20,
                        tweet_fields=['created_at', 'author_id', 'public_metrics', 'context_annotations'],
                        user_fields=['username'],
                        expansions=['author_id']
                    )
                    
                    if tweets.data:
                        # Filter and score tweets
                        scored_tweets = []
                        users_dict = {user.id: user for user in tweets.includes.get('users', [])}
                        
                        for tweet in tweets.data:
                            # Skip if already processed
                            if tweet.id in self.processed_tweets:
                                continue
                            
                            # Check if it's genuine NBA content
                            if self._is_quality_nba_content(tweet.text):
                                author = users_dict.get(tweet.author_id)
                                metrics = tweet.public_metrics
                                
                                # Score based on engagement
                                score = (
                                    metrics['like_count'] * 1 +
                                    metrics['retweet_count'] * 2 +
                                    metrics['reply_count'] * 1.5 +
                                    metrics['quote_count'] * 2
                                )
                                
                                scored_tweets.append({
                                    'tweet': tweet,
                                    'author': author,
                                    'score': score
                                })
                        
                        if scored_tweets:
                            # Sort by score and return best one
                            best_tweet = max(scored_tweets, key=lambda x: x['score'])
                            tweet_data = best_tweet['tweet']
                            author = best_tweet['author']
                            
                            content = TwitterContent(
                                id=tweet_data.id,
                                text=tweet_data.text,
                                author_username=author.username if author else "unknown",
                                metrics=dict(tweet_data.public_metrics),
                                created_at=tweet_data.created_at.isoformat() if tweet_data.created_at else ""
                            )
                            
                            logger.info(f"Found NBA content: {content.text[:80]}... (Score: {best_tweet['score']})")
                            return content
                
                except Exception as e:
                    logger.warning(f"Search query '{query}' failed: {e}")
                    continue
                    
                # Small delay between queries
                await asyncio.sleep(1)
            
            logger.info("No suitable NBA content found")
            return None
            
        except Exception as e:
            logger.error(f"Error searching NBA content: {e}")
            return None
    
    def _is_quality_nba_content(self, text: str) -> bool:
        """Check if tweet contains quality NBA content."""
        text_lower = text.lower()
        
        # Must contain NBA keywords
        has_nba_keyword = any(keyword.lower() in text_lower for keyword in NBA_KEYWORDS)
        if not has_nba_keyword:
            return False
        
        # Must not contain excluded keywords
        has_excluded = any(keyword.lower() in text_lower for keyword in EXCLUDED_KEYWORDS)
        if has_excluded:
            return False
        
        # Basic quality checks
        if len(text) < 20:  # Too short
            return False
        
        if text.count('#') > 5:  # Too many hashtags
            return False
        
        if 'http' in text_lower and text_lower.count('http') > 2:  # Too many links
            return False
        
        return True
    
    async def generate_analytics_question(self, content: Optional[TwitterContent] = None) -> str:
        """Generate an engaging NBA analytics question."""
        try:
            if content:
                # Generate contextual question based on content
                context = f"Based on this NBA content: '{content.text}'"
                prompt = f"""Generate an engaging NBA analytics question that relates to this content: "{content.text}"

The question should:
- Be specific and answerable with NBA data/statistics
- Encourage analytical discussion
- Be interesting to basketball fans
- Be suitable for Twitter (concise but engaging)
- Start with "@BlitzAIBot" to trigger the analytics response

Examples:
- "@BlitzAIBot What's LeBron's clutch shooting percentage this season compared to his career average?"
- "@BlitzAIBot How do the Lakers' defensive stats compare when Anthony Davis plays vs sits?"
- "@BlitzAIBot Which team has the best three-point defense in the league right now?"

Generate ONE question only, no explanation."""
            else:
                # Generate standalone question
                question_templates = [
                    "player performance analysis",
                    "team comparison",
                    "historical records",
                    "current season trends",
                    "clutch performance",
                    "defensive statistics",
                    "scoring efficiency",
                    "playoff implications"
                ]
                
                topic = random.choice(question_templates)
                prompt = f"""Generate an engaging NBA analytics question about {topic}.

The question should:
- Be specific and answerable with NBA data/statistics  
- Encourage analytical discussion
- Be interesting to basketball fans
- Be suitable for Twitter (concise but engaging)
- Start with "@BlitzAIBot" to trigger the analytics response

Generate ONE question only, no explanation."""
                context = ""
            
            # Use a simple text-based approach for question generation
            # since this is about generating creative questions, not complex analytics
            question_examples = [
                "@BlitzAIBot What's Stephen Curry's three-point percentage from different court zones this season?",
                "@BlitzAIBot How do the Celtics perform in clutch situations compared to last season?",
                "@BlitzAIBot Which NBA rookie has the best advanced stats so far this year?",
                "@BlitzAIBot What's the impact of rest days on LeBron's performance at his age?",
                "@BlitzAIBot How do the Lakers' defensive ratings change with different lineup combinations?",
                "@BlitzAIBot Which team has the most efficient offense in close games this season?",
                "@BlitzAIBot What's Giannis's scoring efficiency in the paint vs. previous seasons?",
                "@BlitzAIBot How do the Warriors' ball movement stats compare to their championship years?"
            ]
            
            # For now, use a random question with some contextual adaptation
            base_question = random.choice(question_examples)
            
            if content and any(name in content.text.lower() for name in ['lebron', 'curry', 'lakers', 'warriors', 'celtics']):
                # Try to adapt question to content
                for name in ['lebron', 'curry', 'lakers', 'warriors', 'celtics']:
                    if name in content.text.lower():
                        adapted_questions = [q for q in question_examples if name in q.lower()]
                        if adapted_questions:
                            base_question = random.choice(adapted_questions)
                            break
            
            logger.info(f"Generated question: {base_question}")
            return base_question
            
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            # Fallback question
            return "@BlitzAIBot What are the most impressive NBA stats from this week?"
    
    async def post_question(self, question: str, reply_to_tweet_id: Optional[str] = None, test_mode: bool = False) -> Optional[str]:
        """Post question tweet from @tejsri01 account."""
        try:
            if test_mode:
                logger.info(f"TEST MODE - Would post question: {question}")
                if reply_to_tweet_id:
                    logger.info(f"TEST MODE - Would reply to tweet: {reply_to_tweet_id}")
                return "test_question_tweet_id"
            
            if reply_to_tweet_id:
                # Post as reply
                response = self.tejsri_client.create_tweet(
                    text=question,
                    in_reply_to_tweet_id=reply_to_tweet_id
                )
            else:
                # Post standalone
                response = self.tejsri_client.create_tweet(text=question)
            
            if response.data:
                question_tweet_id = response.data['id']
                logger.info(f"✅ Posted question tweet: {question_tweet_id}")
                return question_tweet_id
            else:
                logger.error("❌ Failed to post question - no response data")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to post question: {e}")
            return None
    
    async def generate_analytics_response(self, question: str) -> str:
        """Generate comprehensive NBA analytics response using MCP tools."""
        try:
            # Clean question for analysis
            clean_question = question.replace("@BlitzAIBot", "").strip()
            
            # Run the agent with NBA analytics
            result = await self.agent.run(
                clean_question,
                deps=""  # No additional context needed
            )
            
            # Format response for Twitter
            response = result.output
            
            # Ensure response is Twitter-friendly
            if len(response) > 280:
                # If too long, try to break into thread format
                response = self._format_twitter_thread(response)
            
            logger.info(f"Generated analytics response: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"Error generating analytics response: {e}")
            return "🏀 I'm having trouble accessing the NBA database right now. Please try again later! #NBA #Basketball"
    
    def _format_twitter_thread(self, long_response: str) -> str:
        """Format long response as Twitter thread."""
        # For now, just truncate and add continuation indicator
        if len(long_response) <= 280:
            return long_response
        
        # Find a good break point
        truncated = long_response[:250]
        last_sentence = truncated.rfind('.')
        if last_sentence > 100:
            truncated = truncated[:last_sentence + 1]
        
        return truncated + " (1/🧵)"
    
    async def post_analytics_response(self, response: str, question_tweet_id: str, test_mode: bool = False) -> Optional[str]:
        """Post analytics response from @BlitzAIBot account."""
        try:
            if test_mode:
                logger.info(f"TEST MODE - Would post analytics response: {response}")
                logger.info(f"TEST MODE - Would reply to tweet: {question_tweet_id}")
                return "test_analytics_tweet_id"
            
            # Post as reply to the question
            twitter_response = self.blitzai_client.create_tweet(
                text=response,
                in_reply_to_tweet_id=question_tweet_id
            )
            
            if twitter_response.data:
                analytics_tweet_id = twitter_response.data['id']
                logger.info(f"✅ Posted analytics response: {analytics_tweet_id}")
                return analytics_tweet_id
            else:
                logger.error("❌ Failed to post analytics response - no response data")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to post analytics response: {e}")
            return None
    
    async def run_workflow(self, request: TwitterWorkflowRequest = None) -> Dict[str, Any]:
        """Run the complete NBA Twitter workflow."""
        if request is None:
            request = TwitterWorkflowRequest()
        
        workflow_result = {
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "steps": {},
            "test_mode": request.test_mode
        }
        
        try:
            logger.info("🏀 Starting NBA Twitter Workflow")
            
            # Step 1: Search for NBA content (unless forced standalone)
            nba_content = None
            if not request.force_standalone:
                logger.info("Step 1: Searching for NBA content...")
                nba_content = await self.search_nba_content()
                workflow_result["steps"]["content_search"] = {
                    "success": nba_content is not None,
                    "content_found": nba_content.model_dump() if nba_content else None
                }
            
            # Step 2: Generate question
            logger.info("Step 2: Generating NBA analytics question...")
            question = await self.generate_analytics_question(nba_content)
            workflow_result["steps"]["question_generation"] = {
                "success": bool(question),
                "question": question
            }
            
            # Step 3: Post question
            logger.info("Step 3: Posting question...")
            reply_to_id = nba_content.id if nba_content else None
            question_tweet_id = await self.post_question(question, reply_to_id, request.test_mode)
            workflow_result["steps"]["question_posting"] = {
                "success": bool(question_tweet_id),
                "tweet_id": question_tweet_id,
                "reply_to": reply_to_id
            }
            
            if not question_tweet_id:
                logger.error("Failed to post question - stopping workflow")
                return workflow_result
            
            # Mark content as processed
            if nba_content:
                self._save_processed_tweet(nba_content.id)
            
            # Step 4: Wait briefly
            logger.info("Step 4: Waiting before analytics response...")
            await asyncio.sleep(3)
            
            # Step 5: Generate analytics response
            logger.info("Step 5: Generating comprehensive analytics...")
            analytics_response = await self.generate_analytics_response(question)
            workflow_result["steps"]["analytics_generation"] = {
                "success": bool(analytics_response),
                "response": analytics_response
            }
            
            # Step 6: Post analytics response
            logger.info("Step 6: Posting analytics response...")
            analytics_tweet_id = await self.post_analytics_response(
                analytics_response, question_tweet_id, request.test_mode
            )
            workflow_result["steps"]["analytics_posting"] = {
                "success": bool(analytics_tweet_id),
                "tweet_id": analytics_tweet_id
            }
            
            if analytics_tweet_id:
                workflow_result["success"] = True
                logger.info("🏆 NBA Twitter Workflow completed successfully!")
            else:
                logger.error("Failed to post analytics response")
            
            return workflow_result
            
        except Exception as e:
            logger.error(f"Error in NBA workflow: {e}")
            workflow_result["error"] = str(e)
            return workflow_result

# Global agent instance
nba_twitter_agent = TwitterNBAAgent() 