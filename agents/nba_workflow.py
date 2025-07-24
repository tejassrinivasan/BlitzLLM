#!/usr/bin/env python3
"""
NBA Content Discovery Workflow - Agno Implementation
Orchestrates the complete NBA Twitter automation flow using Agno workflows.
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.workflow import Workflow
from agno.storage.sqlite import SqliteStorage

# Simple step data classes (since agno.workflow.v2.types doesn't exist)
class StepInput:
    def __init__(self, previous_step_content=None, **kwargs):
        self.previous_step_content = previous_step_content
        for key, value in kwargs.items():
            setattr(self, key, value)

class StepOutput:
    def __init__(self, content, success=True, **kwargs):
        self.content = content
        self.success = success
        for key, value in kwargs.items():
            setattr(self, key, value)

class Step:
    def __init__(self, name, description=None, agent=None, executor=None, **kwargs):
        self.name = name
        self.description = description
        self.agent = agent
        self.executor = executor
        for key, value in kwargs.items():
            setattr(self, key, value)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment setup for local testing
os.environ["AZURE_OPENAI_API_KEY"] = "3RxOfsvJrx1vapAtdNJN8tAI5HhSTB2GLq0j3A61MMIOEVaKuo45JQQJ99BCACYeBjFXJ3w3AAABACOGCEvR"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://blitzgpt.openai.azure.com/"
os.environ["AZURE_OPENAI_DEPLOYMENT"] = "gpt-4o"
os.environ["AZURE_OPENAI_API_VERSION"] = "2025-03-01-preview"

# Twitter credentials
os.environ["SHARED_CONSUMER_KEY"] = "IO0UIDgBKTrXby3Sl2zPz0vJO"
os.environ["SHARED_CONSUMER_SECRET"] = "6hKlyZCwLCpVPZ4dxfCiISC7H4Sg61YJdxYr0nGqHrdBuUt1AF"
os.environ["TEJSRI_X_BEARER_TOKEN"] = "AAAAAAAAAAAAAAAAAAAAANHQ3AEAAAAA4k9DlSblc8ZgNmgCJWIPvQmlEb8%3DkxTdQkEG97f8v4md0Fzofo9KDnDl0jZuWF8oLVTJ139j5L813d"
os.environ["TEJSRI_X_ACCESS_TOKEN"] = "1194703284583354370-AL4uu3upXQAkPklgOxTllOz6T3qFz0"
os.environ["TEJSRI_X_ACCESS_SECRET"] = "MIBso7vI5D3tRrVUfCw0gX9Kd8CqyV4ZTXoMHjpcMyq9V"
os.environ["X_BEARER_TOKEN"] = "AAAAAAAAAAAAAAAAAAAAAL852AEAAAAAFDeKS7l%2FbmLY4Aqywrzfj316X9U%3DhMN7FrxP8RVKchRgx08G4vFwEk0XwiY2F1CJ0mk57AMhVFOUlW"
os.environ["X_ACCESS_TOKEN"] = "1930145656842399746-N75MTZ1FkOmhM52Ofyrw5XqKsNG1mA"
os.environ["X_ACCESS_SECRET"] = "zMIrda7t5kEjtVp4drnIlICEh6PyiQH5citssMs0m1tRl"


# ============================================================================
# TWITTER TOOLS - Available to all agents
# ============================================================================

def load_processed_tweets() -> set:
    """Load previously processed tweet IDs from file."""
    try:
        processed_file = "processed_tweets.txt"
        if os.path.exists(processed_file):
            with open(processed_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    except Exception as e:
        logger.error(f"Error loading processed tweets: {e}")
        return set()

def save_processed_tweet(tweet_id: str):
    """Save a processed tweet ID to file."""
    try:
        processed_file = "processed_tweets.txt"
        with open(processed_file, 'a') as f:
            f.write(f"{tweet_id}\n")
        logger.info(f"Saved processed tweet ID: {tweet_id}")
    except Exception as e:
        logger.error(f"Error saving processed tweet: {e}")

def filter_nba_content(tweets: list) -> list:
    """Filter tweets to only include genuine NBA content."""
    nba_keywords = [
        'nba', 'basketball', 'lakers', 'warriors', 'celtics', 'heat', 'nets', 'knicks',
        'bulls', 'cavaliers', 'pistons', 'pacers', 'bucks', 'hawks', 'hornets', 'magic',
        'sixers', '76ers', 'raptors', 'wizards', 'nuggets', 'timberwolves', 'thunder',
        'blazers', 'jazz', 'kings', 'clippers', 'suns', 'mavericks', 'rockets', 'grizzlies',
        'pelicans', 'spurs', 'lebron', 'curry', 'durant', 'giannis', 'luka', 'tatum',
        'points', 'rebounds', 'assists', 'steals', 'blocks', 'field goal', 'three point',
        'game', 'season', 'playoff', 'championship', 'mvp', 'dpoy', 'roty'
    ]
    
    filtered_tweets = []
    for tweet in tweets:
        text = tweet.get('text', '').lower()
        # Check if tweet contains NBA-related keywords
        if any(keyword in text for keyword in nba_keywords):
            filtered_tweets.append(tweet)
        else:
            logger.info(f"Skipping non-NBA tweet: {text[:50]}...")
    
    return filtered_tweets

def search_nba_tweets(agent: Agent, query: str = "NBA_COMPREHENSIVE", max_results: int = 10) -> str:
    """Search for NBA-related tweets using real Twitter MCP client with comprehensive sources."""
    try:
        import sys
        sys.path.append('..')
        
        # Use real Twitter MCP client
        import asyncio
        from tweepy.asynchronous import AsyncClient
        
        async def _search_tweets():
            # Use tejsri's bearer token for search
            client = AsyncClient(
                bearer_token=os.getenv("TEJSRI_X_BEARER_TOKEN", "AAAAAAAAAAAAAAAAAAAAANHQ3AEAAAAA4k9DlSblc8ZgNmgCJWIPvQmlEb8%3DkxTdQkEG97f8v4md0Fzofo9KDnDl0jZuWF8oLVTJ139j5L813d"),
                wait_on_rate_limit=True
            )
            
            # Define different NBA search categories to avoid query length limits
            if query == "NBA_COMPREHENSIVE":
                search_queries = [
                    # Hashtags and betting
                    "#NBA OR #PrizePicks OR #DraftKings OR #FanDuel OR #NBABetting OR #NBAStats",
                    # Top teams 
                    "from:Lakers OR from:warriors OR from:celtics OR from:MiamiHEAT OR from:BrooklynNets OR from:nyknicks OR from:chicagobulls OR from:cavs",
                    # More teams
                    "from:DetroitPistons OR from:pacers OR from:Bucks OR from:ATLHawks OR from:hornets OR from:OrlandoMagic OR from:sixers OR from:Raptors",
                    # West teams
                    "from:WashWizards OR from:nuggets OR from:Timberwolves OR from:okcthunder OR from:trailblazers OR from:utahjazz OR from:SacramentoKings OR from:LAClippers",
                    # More west teams
                    "from:Suns OR from:dallasmavs OR from:HoustonRockets OR from:memgrizz OR from:PelicansNBA OR from:spurs",
                    # Top NBA reporters
                    "from:ShamsCharania OR from:MarcJSpears OR from:TheSteinLine OR from:anthonyVslater OR from:wojespn",
                    # More reporters
                    "from:ramonashelburne OR from:chrisbhaynes OR from:WindhorstESPN",
                    # Popular NBA accounts
                    "from:TheNBACentral OR from:LegionHoops OR from:BallisLife OR from:overtime OR from:SportsCenter OR from:BleacherReport OR from:NBAonTNT OR from:NBATV"
                ]
            else:
                search_queries = [query]
            
            all_tweets = []
            
            for search_query in search_queries:
                try:
                    search_results = await client.search_recent_tweets(
                        query=f"{search_query} -is:retweet lang:en",
                        max_results=min(max_results, 15),  # Limit per query to get variety
                        tweet_fields=["author_id", "created_at", "public_metrics", "text", "attachments"],
                        expansions=["author_id", "attachments.media_keys"],
                        media_fields=["url", "type", "preview_image_url"]
                    )
            
                    if search_results and search_results.data:
                        # Get user info for this search
                        users = {user.id: user for user in (search_results.includes.get('users', []) if search_results.includes else [])}
                        media = {m.media_key: m for m in (search_results.includes.get('media', []) if search_results.includes else [])}
                        
                        for tweet in search_results.data:
                            user = users.get(tweet.author_id)
                            tweet_media = []
                            
                            # Get media attachments
                            if hasattr(tweet, 'attachments') and tweet.attachments:
                                for media_key in tweet.attachments.get('media_keys', []):
                                    if media_key in media:
                                        m = media[media_key]
                                        tweet_media.append({
                                            "type": m.type,
                                            "url": getattr(m, 'url', None),
                                            "preview_url": getattr(m, 'preview_image_url', None)
                                        })
                            
                            all_tweets.append({
                                "id": tweet.id,
                                "text": tweet.text,
                                "author": f"@{user.username if user else 'unknown'}",
                                "author_name": user.name if user else "Unknown",
                                "created_at": str(tweet.created_at),
                                "metrics": {
                                    "like_count": tweet.public_metrics.get('like_count', 0),
                                    "retweet_count": tweet.public_metrics.get('retweet_count', 0),
                                    "reply_count": tweet.public_metrics.get('reply_count', 0),
                                    "quote_count": tweet.public_metrics.get('quote_count', 0)
                                },
                                "media": tweet_media,
                                "url": f"https://twitter.com/{user.username if user else 'unknown'}/status/{tweet.id}",
                                "source_query": search_query  # Track which query found this tweet
                            })
                
                except Exception as search_error:
                    logger.warning(f"Search query failed: {search_query}, Error: {search_error}")
                    continue
            
            # Remove duplicates and filter processed tweets
            processed_tweets = load_processed_tweets()
            unique_tweets = {}
            
            for tweet in all_tweets:
                tweet_id = str(tweet['id'])
                if tweet_id not in processed_tweets and tweet_id not in unique_tweets:
                    unique_tweets[tweet_id] = tweet
            
            tweets = list(unique_tweets.values())
            
            # Filter to only NBA content
            tweets = filter_nba_content(tweets)
            
            # Sort by engagement and limit results
            tweets.sort(key=lambda t: t['metrics']['like_count'] + t['metrics']['retweet_count'] * 2, reverse=True)
            tweets = tweets[:max_results]
            
            return tweets
        
        # Run the async function
        if asyncio.get_event_loop().is_running():
            # If we're already in an event loop, create a new one
            import threading
            result = []
            exception = []
            
            def run_in_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    result.append(new_loop.run_until_complete(_search_tweets()))
                except Exception as e:
                    exception.append(e)
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            if exception:
                raise exception[0]
            tweets = result[0]
        else:
            tweets = asyncio.run(_search_tweets())
        
        logger.info(f"Found {len(tweets)} NBA tweets for query: {query}")
        return json.dumps(tweets, indent=2)
        
    except Exception as e:
        logger.error(f"Error searching NBA tweets: {e}")
        return f"Error searching tweets: {str(e)}"

def post_tweet(agent: Agent, text: str, account: str = "tejsri01", reply_to: str = None) -> str:
    """Post a tweet from specified account using real Twitter API."""
    try:
        import asyncio
        from tweepy.asynchronous import AsyncClient
        
        async def _post_tweet():
            # Select the right credentials based on account
            if account == "tejsri01":
                client = AsyncClient(
                    bearer_token=os.getenv("TEJSRI_X_BEARER_TOKEN", "AAAAAAAAAAAAAAAAAAAAANHQ3AEAAAAA4k9DlSblc8ZgNmgCJWIPvQmlEb8%3DkxTdQkEG97f8v4md0Fzofo9KDnDl0jZuWF8oLVTJ139j5L813d"),
                    consumer_key=os.getenv("SHARED_CONSUMER_KEY", "IO0UIDgBKTrXby3Sl2zPz0vJO"),
                    consumer_secret=os.getenv("SHARED_CONSUMER_SECRET", "6hKlyZCwLCpVPZ4dxfCiISC7H4Sg61YJdxYr0nGqHrdBuUt1AF"),
                    access_token=os.getenv("TEJSRI_X_ACCESS_TOKEN", "1194703284583354370-AL4uu3upXQAkPklgOxTllOz6T3qFz0"),
                    access_token_secret=os.getenv("TEJSRI_X_ACCESS_SECRET", "MIBso7vI5D3tRrVUfCw0gX9Kd8CqyV4ZTXoMHjpcMyq9V"),
                    wait_on_rate_limit=True
                )
            else:  # BlitzAIBot
                client = AsyncClient(
                    bearer_token=os.getenv("X_BEARER_TOKEN", "AAAAAAAAAAAAAAAAAAAAAL852AEAAAAAFDeKS7l%2FbmLY4Aqywrzfj316X9U%3DhMN7FrxP8RVKchRgx08G4vFwEk0XwiY2F1CJ0mk57AMhVFOUlW"),
                    consumer_key=os.getenv("SHARED_CONSUMER_KEY", "IO0UIDgBKTrXby3Sl2zPz0vJO"),
                    consumer_secret=os.getenv("SHARED_CONSUMER_SECRET", "6hKlyZCwLCpVPZ4dxfCiISC7H4Sg61YJdxYr0nGqHrdBuUt1AF"),
                    access_token=os.getenv("X_ACCESS_TOKEN", "1930145656842399746-N75MTZ1FkOmhM52Ofyrw5XqKsNG1mA"),
                    access_token_secret=os.getenv("X_ACCESS_SECRET", "zMIrda7t5kEjtVp4drnIlICEh6PyiQH5citssMs0m1tRl"),
                    wait_on_rate_limit=True
                )
            
            # Post the tweet
            response = await client.create_tweet(
                text=text,
                in_reply_to_tweet_id=reply_to
            )
            
            if response and response.data:
                tweet_id = response.data['id']
                username = "tejsri01" if account == "tejsri01" else "BlitzAIBot"
                url = f"https://twitter.com/{username}/status/{tweet_id}"
                
                return {
                    "success": True,
                    "tweet_id": tweet_id,
                    "url": url,
                    "account": account,
                    "text": text,
                    "reply_to": reply_to
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to post tweet",
                    "account": account
                }
        
        # Run the async function
        if asyncio.get_event_loop().is_running():
            # If we're already in an event loop, create a new one
            import threading
            result = []
            exception = []
            
            def run_in_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    result.append(new_loop.run_until_complete(_post_tweet()))
                except Exception as e:
                    exception.append(e)
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            if exception:
                raise exception[0]
            post_result = result[0]
        else:
            post_result = asyncio.run(_post_tweet())
        
        logger.info(f"Posted tweet from @{account}: {text[:50]}...")
        return json.dumps(post_result, indent=2)
        
    except Exception as e:
        logger.error(f"Error posting tweet: {e}")
        return f"Error posting tweet: {str(e)}"


# ============================================================================
# NBA DATABASE TOOLS - Available to all agents  
# ============================================================================

def query_nba_database(agent: Agent, question: str) -> str:
    """Query NBA database using real Blitz MCP client."""
    try:
        import sys
        sys.path.append('..')
        from twitter_llm_utils import generate_twitter_response
        import asyncio
        
        async def _query_nba():
            response = await generate_twitter_response(
                user_message=question,
                thread_content=None,
                original_author=None,
                current_author="tejsri01",
                comment_highlights=None
            )
            return response.get("text", "No response generated")
        
        # Run the async function
        if asyncio.get_event_loop().is_running():
            import threading
            result = []
            exception = []
            
            def run_in_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    result.append(new_loop.run_until_complete(_query_nba()))
                except Exception as e:
                    exception.append(e)
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            if exception:
                raise exception[0]
            nba_response = result[0]
        else:
            nba_response = asyncio.run(_query_nba())
        
        logger.info(f"Generated NBA analytics for: {question}")
        return nba_response
        
    except Exception as e:
        logger.error(f"Error querying NBA database: {e}")
        return f"Error querying database: {str(e)}"

def inspect_nba_tables(agent: Agent, table_name: str = None) -> str:
    """Inspect NBA database tables to understand available data."""
    try:
        import sys
        sys.path.append('../mcp')
        from blitz_agent_mcp.tools.inspect import inspect
        import asyncio
        
        async def _inspect_tables():
            if table_name:
                # Inspect specific table
                result = await inspect(table=table_name, league="nba")
                return f"Table: {table_name}\n{result}"
            else:
                # Get schema for all NBA tables
                tables = ["games", "players", "teams", "player_stats", "team_stats", "standings"]
                results = []
                for table in tables:
                    try:
                        result = await inspect(table=table, league="nba")
                        results.append(f"=== {table.upper()} TABLE ===\n{result}\n")
                    except:
                        continue
                return "\n".join(results)
        
        # Run the async function
        if asyncio.get_event_loop().is_running():
            import threading
            result = []
            exception = []
            
            def run_in_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    result.append(new_loop.run_until_complete(_inspect_tables()))
                except Exception as e:
                    exception.append(e)
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            if exception:
                raise exception[0]
            inspection_result = result[0]
        else:
            inspection_result = asyncio.run(_inspect_tables())
        
        logger.info(f"Inspected NBA database tables")
        return inspection_result
        
    except Exception as e:
        logger.error(f"Error inspecting NBA tables: {e}")
        return f"Error inspecting tables: {str(e)}"

def analyze_tweet_image(agent: Agent, image_url: str, tweet_text: str) -> str:
    """Analyze images in tweets using Azure OpenAI vision."""
    try:
        from openai import AsyncAzureOpenAI
        import asyncio
        
        async def _analyze_image():
            client = AsyncAzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION")
            )
            
            response = await client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Analyze this NBA image from a tweet. Tweet text: '{tweet_text}'. Describe what you see and identify any players, teams, stats, or game situations that could be used for NBA analytics questions."},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
                max_tokens=300
            )
            
            return response.choices[0].message.content
        
        # Run the async function
        if asyncio.get_event_loop().is_running():
            import threading
            result = []
            exception = []
            
            def run_in_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    result.append(new_loop.run_until_complete(_analyze_image()))
                except Exception as e:
                    exception.append(e)
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            if exception:
                raise exception[0]
            analysis_result = result[0]
        else:
            analysis_result = asyncio.run(_analyze_image())
        
        logger.info(f"Analyzed tweet image: {image_url}")
        return analysis_result
        
    except Exception as e:
        logger.error(f"Error analyzing tweet image: {e}")
        return f"Error analyzing image: {str(e)}"


# ============================================================================
# WORKFLOW AGENTS
# ============================================================================

# 1. NBA Content Discovery Agent
nba_content_discoverer = Agent(
    name="NBA Content Discoverer",
    model=OpenAIChat(id="gpt-4o"),
    tools=[search_nba_tweets, analyze_tweet_image],
    instructions=[
        "You are an NBA content discovery specialist with access to comprehensive NBA sources.",
        "Search NBA content from: Official team accounts (all 30 teams), top reporters (Shams, Woj, Marc Stein, etc.), popular NBA accounts (TheNBACentral, LegionHoops, etc.), hashtags (#NBA, #PrizePicks, etc.).",
        "CRITICAL: Only select tweets that are genuinely about NBA basketball - skip any non-NBA content.",
        "Find tweets about: Player performances, game highlights, trade news, statistical achievements, injury reports, betting scenarios, breaking news.",
        "Prioritize: Breaking news from verified reporters, official team announcements, viral moments, statistical content with high engagement.",
        "If tweets contain images, use analyze_tweet_image to understand visual content.",
        "Focus on content with good engagement metrics and clear analytical potential.",
        "Include image analysis results when available.",
        "The system searches 8 different query categories, filters duplicates, and skips already processed tweets.",
        "Return the best NBA-specific tweet in JSON format with all details including source query information."
    ],
)

# 2. Question Generation Agent  
nba_question_generator = Agent(
    name="NBA Question Generator",
    model=OpenAIChat(id="gpt-4o"),
    tools=[inspect_nba_tables, analyze_tweet_image],
    instructions=[
        "You are an NBA question generation expert.",
        "Generate engaging questions based on NBA content that can be answered with data.",
        "IMPORTANT: Use inspect_nba_tables to understand what data is available before generating questions.",
        "Consider image content if the tweet contains visuals - use analyze_tweet_image if needed.",
        "Create questions about performance comparisons, team trends, situational analysis, or betting scenarios.",
        "Examples: 'How do the Lakers and Warriors compare in overtime win percentage over the last 5 seasons?'",
        "Make questions specific to actual database columns and tables available.",
        "Always tag @BlitzAIBot in your questions.",
        "Keep questions under 200 characters and avoid quotes or emojis.",
        "Return only the question text, nothing else."
    ],
)

# 3. Tweet Posting Agent
nba_tweet_poster = Agent(
    name="NBA Tweet Poster", 
    model=OpenAIChat(id="gpt-4o"),
    tools=[post_tweet],
    instructions=[
        "You are responsible for posting NBA questions on Twitter.",
        "Post the generated question from the @tejsri01 account.",
        "Always use the post_tweet tool with account='tejsri01'.",
        "Return the posting result with tweet URL and details."
    ],
)

# 4. NBA Analytics Agent
nba_analytics_agent = Agent(
    name="NBA Analytics Specialist",
    model=OpenAIChat(id="gpt-4o"), 
    tools=[query_nba_database, inspect_nba_tables],
    instructions=[
        "You are an NBA analytics expert providing data-driven answers.",
        "Use query_nba_database to get real NBA statistics and analysis.",
        "Use inspect_nba_tables if you need to understand available data structure.",
        "Provide comprehensive answers with specific numbers, percentages, and context.",
        "Include historical comparisons and relevant trends when applicable.",
        "Format responses for Twitter (under 280 characters or use thread format).",
        "Be authoritative but conversational in your analysis.",
        "Always cite data sources and time periods when providing statistics."
    ],
)

# 5. Response Posting Agent
nba_response_poster = Agent(
    name="NBA Response Poster",
    model=OpenAIChat(id="gpt-4o"),
    tools=[post_tweet],
    instructions=[
        "You are responsible for posting NBA analytics responses on Twitter.",
        "Post the analytics response from the @BlitzAIBot account as a reply.",
        "Always mention @tejsri01 at the start of the response.",
        "Use the post_tweet tool with account='BlitzAIBot' and include reply_to parameter.",
        "Return the posting result with tweet URL and details."
    ],
)


# ============================================================================
# CUSTOM WORKFLOW FUNCTIONS
# ============================================================================

def select_best_nba_content(step_input: StepInput) -> StepOutput:
    """Process discovered NBA content and select the most interesting tweet."""
    try:
        tweets_data = step_input.previous_step_content
        
        if not tweets_data:
            return StepOutput(
                content="No NBA content found",
                success=False
            )
        
        # Parse tweets data
        tweets = json.loads(tweets_data)
        if not tweets:
            return StepOutput(
                content="No tweets in response", 
                success=False
            )
        
        # Score tweets based on engagement and content
        best_tweet = None
        best_score = 0
        
        for tweet in tweets:
            metrics = tweet.get('metrics', {})
            engagement_score = metrics.get('like_count', 0) + metrics.get('retweet_count', 0) * 2
            
            # Bonus for certain keywords
            text = tweet.get('text', '').lower()
            content_bonus = 0
            if any(word in text for word in ['record', 'season', 'stats', 'points', 'wins', 'shoots', 'makes', 'percentage']):
                content_bonus = 500
            
            # Extra bonus for tweets with images (more engaging)
            if tweet.get('media') and len(tweet.get('media', [])) > 0:
                content_bonus += 300
                
            total_score = engagement_score + content_bonus
            
            if total_score > best_score:
                best_score = total_score
                best_tweet = tweet
        
        if best_tweet:
            logger.info(f"Selected tweet with score {best_score}: {best_tweet['text'][:50]}...")
            
            # Add media URLs for easy access
            if best_tweet.get('media'):
                logger.info(f"Tweet contains {len(best_tweet['media'])} media attachments")
            
            # Save this tweet as processed to avoid duplicates
            save_processed_tweet(str(best_tweet['id']))
            
            return StepOutput(
                content=json.dumps(best_tweet, indent=2),
                success=True
            )
        else:
            return StepOutput(
                content="No suitable tweet found",
                success=False
            )
            
    except Exception as e:
        logger.error(f"Error selecting NBA content: {e}")
        return StepOutput(
            content=f"Error processing content: {str(e)}",
            success=False
        )

def extract_question_for_analytics(step_input: StepInput) -> StepOutput:
    """Extract and clean the question for NBA analytics processing."""
    try:
        question = step_input.previous_step_content
        
        if not question:
            return StepOutput(
                content="No question to analyze",
                success=False
            )
        
        # Clean the question (remove @BlitzAIBot mention)
        clean_question = question.replace("@BlitzAIBot", "").strip()
        
        logger.info(f"Extracted question for analytics: {clean_question}")
        
        return StepOutput(
            content=clean_question,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error extracting question: {e}")
        return StepOutput(
            content=f"Error extracting question: {str(e)}",
            success=False
        )

def prepare_response_with_context(step_input: StepInput) -> StepOutput:
    """Prepare the final response with context from the posted question."""
    try:
        analytics_response = step_input.previous_step_content
        
        # Get the question tweet details from earlier steps
        question_tweet_data = step_input.get_step_content("post_question")
        
        if question_tweet_data:
            question_tweet = json.loads(question_tweet_data)
            tweet_id = question_tweet.get('tweet_id')
            
            response_data = {
                "analytics_response": analytics_response,
                "reply_to_tweet_id": tweet_id,
                "formatted_response": f"@tejsri01 {analytics_response}"
            }
            
            return StepOutput(
                content=json.dumps(response_data, indent=2),
                success=True
            )
        else:
            # Fallback without reply context
            response_data = {
                "analytics_response": analytics_response,
                "reply_to_tweet_id": None,
                "formatted_response": f"@tejsri01 {analytics_response}"
            }
            
            return StepOutput(
                content=json.dumps(response_data, indent=2),
                success=True
            )
            
    except Exception as e:
        logger.error(f"Error preparing response: {e}")
        return StepOutput(
            content=f"Error preparing response: {str(e)}",
            success=False
        )


# ============================================================================
# NBA CONTENT DISCOVERY WORKFLOW
# ============================================================================

nba_workflow = Workflow(
    name="NBA Content Discovery Workflow",
    description="Automated NBA Twitter content discovery and analytics response system",
    storage=SqliteStorage(
        table_name="nba_workflow",
        db_file="tmp/nba_workflow.db",
        mode="workflow_v2",
    ),
    steps=[
        # Step 1: Discover NBA Content
        Step(
            name="discover_content",
            description="Search for trending NBA content on Twitter",
            agent=nba_content_discoverer,
        ),
        
        # Step 2: Select Best Content
        Step(
            name="select_content", 
            description="Process and select the most engaging NBA content",
            executor=select_best_nba_content,
        ),
        
        # Step 3: Generate Question
        Step(
            name="generate_question",
            description="Generate an engaging NBA analytics question",
            agent=nba_question_generator,
        ),
        
        # Step 4: Post Question Tweet
        Step(
            name="post_question",
            description="Post the question from @tejsri01 account",
            agent=nba_tweet_poster,
        ),
        
        # Step 5: Extract Question for Analytics
        Step(
            name="extract_question",
            description="Clean and prepare question for analytics processing", 
            executor=extract_question_for_analytics,
        ),
        
        # Step 6: Generate NBA Analytics
        Step(
            name="generate_analytics",
            description="Generate data-driven NBA analytics response",
            agent=nba_analytics_agent,
        ),
        
        # Step 7: Prepare Response Context
        Step(
            name="prepare_response",
            description="Prepare response with reply context",
            executor=prepare_response_with_context,
        ),
        
        # Step 8: Post Analytics Response
        Step(
            name="post_response",
            description="Post analytics response from @BlitzAIBot account",
            agent=nba_response_poster,
        ),
    ],
)


# ============================================================================
# WORKFLOW EXECUTION & SCHEDULING
# ============================================================================

async def run_nba_discovery_cycle():
    """Run a single NBA content discovery cycle."""
    try:
        logger.info("🏀 Starting NBA Content Discovery Cycle")
        
        response = nba_workflow.run(
            message="Discover trending NBA content and create engaging analytics interaction",
            markdown=True,
        )
        
        if response.success:
            logger.info("✅ NBA Content Discovery Cycle completed successfully")
            
            # Extract results for logging
            final_step = response.steps[-1] if response.steps else None
            if final_step:
                logger.info(f"📱 Final result: {final_step.response_content[:100]}...")
                
        else:
            logger.error("❌ NBA Content Discovery Cycle failed")
            
        return response
        
    except Exception as e:
        logger.error(f"Error in NBA discovery cycle: {e}")
        raise

def schedule_nba_workflow():
    """Schedule the NBA workflow to run 6 times daily."""
    import schedule
    import time
    
    # Schedule 6 times daily: 8AM, 12PM, 4PM, 8PM, 12AM, 4AM
    schedule.every().day.at("08:00").do(lambda: asyncio.run(run_nba_discovery_cycle()))
    schedule.every().day.at("12:00").do(lambda: asyncio.run(run_nba_discovery_cycle()))
    schedule.every().day.at("16:00").do(lambda: asyncio.run(run_nba_discovery_cycle()))
    schedule.every().day.at("20:00").do(lambda: asyncio.run(run_nba_discovery_cycle()))
    schedule.every().day.at("00:00").do(lambda: asyncio.run(run_nba_discovery_cycle()))
    schedule.every().day.at("04:00").do(lambda: asyncio.run(run_nba_discovery_cycle()))
    
    logger.info("📅 NBA Workflow scheduled to run 6 times daily")
    logger.info("⏰ Schedule: 8AM, 12PM, 4PM, 8PM, 12AM, 4AM")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main():
    """Main function for testing the workflow."""
    
    print("🏀 NBA Content Discovery Workflow - Agno Implementation")
    print("=" * 70)
    print("🎯 This workflow will:")
    print("   1. Search for NBA tweets")
    print("   2. Generate a question") 
    print("   3. Post the question from @tejsri01")
    print("   4. Answer the question with NBA analytics")
    print("   5. Post the reply from @BlitzAIBot")
    print()
    
    # Test single cycle
    print("Running single test cycle...")
    response = await run_nba_discovery_cycle()
    
    if response.success:
        print("\n🎉 Workflow completed successfully!")
        print(f"📊 Total steps executed: {len(response.steps)}")
        
        # Show step results
        for i, step in enumerate(response.steps, 1):
            print(f"   Step {i} ({step.step_name}): {'✅' if step.success else '❌'}")
            
    else:
        print("\n❌ Workflow failed")

if __name__ == "__main__":
    # For testing - run single cycle
    asyncio.run(main())
    
    # For production - uncomment to run scheduled
    # schedule_nba_workflow() 