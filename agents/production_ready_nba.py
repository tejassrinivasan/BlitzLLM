#!/usr/bin/env python3
"""
Production-Ready NBA Workflow 
Rate-limit friendly version that actually works end-to-end with comprehensive MCP tools.
Uses the EXACT same sports analytics prompt as blitzagent_agno with all rules copied over:
1. Historical Database (PostgreSQL) - PREFERRED SOURCE with mandatory workflow sequence
2. Web Scraping - SECONDARY SOURCE for recent/breaking news
3. Live Betting Data - TERTIARY SOURCE with two-step workflow and EV analysis
4. Intelligent question generation with database-focused prompting to create unique, targeted questions
"""

import asyncio
import logging
from datetime import datetime, date
import tweepy
from openai import AzureOpenAI
import random
import os
from pathlib import Path
import sys

# Add the blitzagent_agno path to import the agent factory
sys.path.append(str(Path(__file__).parent.parent / "blitz" / "src"))

from blitzagent_agno.agent_factory import create_agent, load_config, AgentType
from blitzagent_agno.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Twitter API Configuration
SHARED_CONSUMER_KEY = "IO0UIDgBKTrXby3Sl2zPz0vJO"
SHARED_CONSUMER_SECRET = "6hKlyZCwLCpVPZ4dxfCiISC7H4Sg61YJdxYr0nGqHrdBuUt1AF"

# @BlitzAnalytics credentials (for rate-limit-free tweet reading)
BLITZANALYTICS_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAL852AEAAAAArcVns1HPuR8uM8MhFdaqncOUcFw%3DTM16qakucHczkcg8MJ4GwamqpuUm0pCKESK2oHsR4i4hJ094LN"
BLITZANALYTICS_ACCESS_TOKEN = "1889746223613321216-ASI5OzBr1OJP6E4MbVAq9UKletu2HZ"
BLITZANALYTICS_ACCESS_SECRET = "aqJrBXgiNoJUhwiZRqOJ0kfWTWtaKWPSiEQVW7VdHLkuO"

# @tejsri01 credentials (for posting questions)
TEJSRI_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANHQ3AEAAAAA4k9DlSblc8ZgNmgCJWIPvQmlEb8%3DkxTdQkEG97f8v4md0Fzofo9KDnDl0jZuWF8oLVTJ139j5L813d"
TEJSRI_ACCESS_TOKEN = "1194703284583354370-AL4uu3upXQAkPklgOxTllOz6T3qFz0"
TEJSRI_ACCESS_SECRET = "MIBso7vI5D3tRrVUfCw0gX9Kd8CqyV4ZTXoMHjpcMyq9V"

# @BlitzAIBot credentials (for posting analytics responses - has blue check)
BLITZAI_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAL852AEAAAAAFDeKS7l%2FbmLY4Aqywrzfj316X9U%3DhMN7FrxP8RVKchRgx08G4vFwEk0XwiY2F1CJ0mk57AMhVFOUlW"
BLITZAI_ACCESS_TOKEN = "1930145656842399746-N75MTZ1FkOmhM52Ofyrw5XqKsNG1mA"
BLITZAI_ACCESS_SECRET = "zMIrda7t5kEjtVp4drnIlICEh6PyiQH5citssMs0m1tRl"

# Initialize Twitter clients
blitzanalytics_client = tweepy.Client(
    bearer_token=BLITZANALYTICS_BEARER_TOKEN,
    consumer_key=SHARED_CONSUMER_KEY,
    consumer_secret=SHARED_CONSUMER_SECRET,
    access_token=BLITZANALYTICS_ACCESS_TOKEN,
    access_token_secret=BLITZANALYTICS_ACCESS_SECRET,
    wait_on_rate_limit=True
)

tejsri_client = tweepy.Client(
    bearer_token=TEJSRI_BEARER_TOKEN,
    consumer_key=SHARED_CONSUMER_KEY,
    consumer_secret=SHARED_CONSUMER_SECRET,
    access_token=TEJSRI_ACCESS_TOKEN,
    access_token_secret=TEJSRI_ACCESS_SECRET,
    wait_on_rate_limit=True
)

blitzai_client = tweepy.Client(
    bearer_token=BLITZAI_BEARER_TOKEN,
    consumer_key=SHARED_CONSUMER_KEY,
    consumer_secret=SHARED_CONSUMER_SECRET,
    access_token=BLITZAI_ACCESS_TOKEN,
    access_token_secret=BLITZAI_ACCESS_SECRET,
    wait_on_rate_limit=True
)

NBA_KEYWORDS = [
    "NBA", "basketball", "points", "rebounds", "assists", "Lakers", "Warriors", 
    "Celtics", "Heat", "Nets", "playoff", "season", "game", "Curry",
    "LeBron", "Durant", "Giannis", "Luka", "Tatum", "Jokic", "scoring",
    "three-pointer", "dunk", "block", "steal", "franchise", "roster"
]

# Content to avoid - summer league, international basketball, AND other sports
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

def get_current_date():
    """Get current date for analytics context."""
    return date.today().strftime("%Y-%m-%d")

# Cache for recent replies to avoid repeated API calls
_tejsri_recent_replies_cache = None
_cache_timestamp = None

async def get_tejsri_recent_replies():
    """Get tejsri01's recent replies once and cache them."""
    global _tejsri_recent_replies_cache, _cache_timestamp
    
    # Use cache if it's less than 5 minutes old
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    if (_tejsri_recent_replies_cache is not None and 
        _cache_timestamp is not None and 
        (now - _cache_timestamp).total_seconds() < 300):  # 5 minutes
        return _tejsri_recent_replies_cache
    
    try:
        # Get recent tweets from tejsri01 (last 48 hours)
        forty_eight_hours_ago = now - timedelta(hours=48)
        start_time_iso = forty_eight_hours_ago.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        print(f"   🔄 Fetching tejsri01's recent tweets for reply checking...")
        
        # Get tejsri01's recent tweets to check for replies (using BlitzAnalytics client with paid access)
        recent_tweets = blitzanalytics_client.get_users_tweets(
            id="1194703284583354370",  # tejsri01's user ID
            max_results=100,  # Check more tweets to be thorough
            tweet_fields=['created_at', 'referenced_tweets', 'text'],
            start_time=start_time_iso
        )
        
        replied_tweet_ids = set()
        if recent_tweets.data:
            for tweet in recent_tweets.data:
                # Check if this tweet references another tweet as a reply
                if hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets:
                    for ref in tweet.referenced_tweets:
                        if ref.type == 'replied_to':
                            replied_tweet_ids.add(str(ref.id))
        
        # Cache the results
        _tejsri_recent_replies_cache = replied_tweet_ids
        _cache_timestamp = now
        
        print(f"   ✅ Found {len(replied_tweet_ids)} tweets that tejsri01 has replied to")
        return replied_tweet_ids
        
    except Exception as e:
        print(f"   ⚠️ Error fetching recent replies: {e}")
        # Return empty set if we can't check
        return set()

async def has_tejsri_replied_to_tweet(tweet_id):
    """Check if tejsri01 has already replied to a specific tweet."""
    replied_tweets = await get_tejsri_recent_replies()
    return str(tweet_id) in replied_tweets

async def search_smart_nba_content(return_all=False):
    """Smart NBA content search using BlitzAnalytics (no rate limits) - LAST 24 HOURS ONLY."""
    print("🔍 Smart NBA content search (BlitzAnalytics - LAST 24 HOURS ONLY)...")
    
    # Multiple queries to get ORIGINAL content only from last 24 hours
    queries = [
        "#NBA OR #basketball -is:retweet -is:reply lang:en",
        "from:Lakers OR from:warriors OR from:celtics -is:retweet -is:reply lang:en",
        "from:nba OR from:espn_nba OR from:TheAthletic -is:retweet -is:reply lang:en", 
        "Stephen Curry OR LeBron James OR Giannis -is:retweet -is:reply lang:en",
        "NBA stats OR NBA analytics OR basketball analysis -is:retweet -is:reply lang:en",
        "from:nuggets OR from:heat OR from:mavericks -is:retweet -is:reply lang:en",
        "Luka Doncic OR Jayson Tatum OR Anthony Davis -is:retweet -is:reply lang:en",
        "from:BleacherReport OR from:SportsCenter OR from:BR_NBA -is:retweet -is:reply lang:en"
    ]
    
    all_tweets = []
    
    try:
        # Use multiple queries since we have no rate limits with BlitzAnalytics
        from datetime import datetime, timedelta, timezone
        
        # Calculate 24 hours ago in proper RFC3339 format for Twitter API
        twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24))
        # Format for Twitter API: yyyy-MM-dd'T'HH:mm:ss[.SSS]Z
        start_time_iso = twenty_four_hours_ago.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        print(f"   📅 Searching for tweets newer than: {start_time_iso}")
        
        for query in queries:  # Use ALL queries for maximum variety
            print(f"   Using query: {query}")
            
            tweets = blitzanalytics_client.search_recent_tweets(
                query=query,
                max_results=15,  # Slightly fewer per query but more diverse  
                tweet_fields=['created_at', 'author_id', 'public_metrics', 'text'],
                start_time=start_time_iso  # USE API-LEVEL FILTERING - most reliable
            )
            
            if tweets.data:
                print(f"      🔍 Found {len(tweets.data)} tweets from API")
                for tweet in tweets.data:
                    tweet_text_lower = tweet.text.lower()
                    
                    # STRICT retweet filter - catch retweets and old content that slip through
                    if (tweet.text.startswith('RT @') or 
                        tweet.text.startswith('rt @') or
                        'RT @' in tweet.text or
                        tweet.text.startswith('@') or  # Skip reply-like tweets
                        len(tweet.text.strip()) < 10):  # Skip very short tweets
                        print(f"      🚫 Skipping retweet/reply/short: {tweet.text[:50]}...")
                        continue
                    
                    # Double-check 24-hour filter (backup to API filtering)
                    try:
                        if tweet.created_at.tzinfo is None:
                            # If no timezone, assume UTC
                            tweet_time = tweet.created_at.replace(tzinfo=timezone.utc)
                        else:
                            tweet_time = tweet.created_at
                        
                        tweet_age_hours = (datetime.now(timezone.utc) - tweet_time).total_seconds() / 3600
                        
                        # Show tweet age for debugging
                        print(f"      📅 Tweet from {tweet_time.strftime('%Y-%m-%d %H:%M')} ({tweet_age_hours:.1f}h ago): {tweet.text[:50]}...")
                        
                        if tweet_age_hours > 24:
                            print(f"      ❌ Skipping - older than 24h ({tweet_age_hours:.1f}h)")
                            continue  # Skip tweets older than 24 hours
                            
                    except Exception as time_error:
                        print(f"      ⚠️ Time parsing error for tweet {tweet.id}: {time_error}")
                        continue
                    
                    # Check if it contains NBA content
                    has_nba_content = any(keyword.lower() in tweet_text_lower for keyword in NBA_KEYWORDS)
                    
                    # Additional NBA verification - must have explicit basketball references
                    has_explicit_nba = (
                        "nba" in tweet_text_lower or 
                        "basketball" in tweet_text_lower or
                        any(team in tweet_text_lower for team in ["lakers", "warriors", "celtics", "heat", "nets", "nuggets", "mavericks"]) or
                        any(player in tweet_text_lower for player in ["curry", "lebron", "durant", "giannis", "luka", "tatum", "jokic"])
                    )
                    
                    # STRICT NFL exclusion - if ANY NFL content detected, reject immediately
                    has_nfl_content = any(nfl.lower() in tweet_text_lower for nfl in [
                        "ravens", "lamar jackson", "quarterback", "qb", "nfl", "football", "touchdown", "yard", "patriots", "chiefs"
                    ])
                    
                    if has_nfl_content:
                        continue  # Skip NFL content immediately
                    
                    # Check if it contains excluded content (summer league, international, other sports)
                    has_excluded_content = any(excluded.lower() in tweet_text_lower for excluded in EXCLUDED_KEYWORDS)
                    
                    # Skip if too similar to recent content (avoid repetitive topics)
                    if len(all_tweets) > 0:
                        similar_found = False
                        for existing_tweet in all_tweets:
                            # Simple similarity check - if many same words, skip
                            tweet_words = set(tweet_text_lower.split())
                            existing_words = set(existing_tweet['text'].lower().split())
                            common_words = tweet_words.intersection(existing_words)
                            if len(common_words) > 3 and len(tweet_words) < 20:  # Avoid very similar tweets
                                similar_found = True
                                break
                        if similar_found:
                            continue
                    
                    # Check if tejsri01 has already replied to this tweet
                    has_already_replied = await has_tejsri_replied_to_tweet(tweet.id)
                    if has_already_replied:
                        print(f"      🔄 Skipping - tejsri01 already replied to this tweet")
                        continue
                    
                    # Only add if it has NBA content AND explicit NBA references AND doesn't have excluded content AND tejsri hasn't replied
                    if has_nba_content and has_explicit_nba and not has_excluded_content:
                        all_tweets.append({
                            'id': tweet.id,
                            'text': tweet.text,
                            'metrics': tweet.public_metrics,
                            'created_at': tweet.created_at
                        })
            else:
                print(f"      ❌ No tweets found for this query")
            
            # Small delay between queries to be respectful
            await asyncio.sleep(0.5)
                    
        print(f"   ✅ Found {len(all_tweets)} qualifying NBA tweets (excluded summer league/international)")
        
        if all_tweets:
            # Remove duplicates based on tweet ID
            unique_tweets = {tweet['id']: tweet for tweet in all_tweets}.values()
            all_tweets = list(unique_tweets)
            print(f"   ✅ After deduplication: {len(all_tweets)} unique tweets")
            
            # If return_all is True, return all tweets for intelligent selection
            if return_all:
                return all_tweets
            
            # Original behavior - score by engagement and recency, return best one
            scored_tweets = []
            for tweet in all_tweets:
                metrics = tweet['metrics']
                engagement_score = (
                    metrics['like_count'] * 2 +
                    metrics['retweet_count'] * 3 +
                    metrics['reply_count'] * 1
                )
                
                # Bonus for recent tweets (created in last 24 hours)
                hours_old = (datetime.now(tweet['created_at'].tzinfo) - tweet['created_at']).total_seconds() / 3600
                recency_bonus = max(0, 100 - hours_old * 2)  # Bonus decreases with age
                
                final_score = engagement_score + recency_bonus
                scored_tweets.append((final_score, tweet))
            
            # Sort by score and pick the best one
            scored_tweets.sort(key=lambda x: x[0], reverse=True)
            best_tweet = scored_tweets[0][1]
            
            # Verify selected tweet is recent
            tweet_time = best_tweet['created_at']
            if tweet_time.tzinfo is None:
                tweet_time = tweet_time.replace(tzinfo=timezone.utc)
            tweet_age_hours = (datetime.now(timezone.utc) - tweet_time).total_seconds() / 3600
            
            print(f"   ✅ Selected highest-scoring tweet: {best_tweet['text'][:60]}...")
            print(f"   📊 Engagement: {best_tweet['metrics']['like_count']} likes, {best_tweet['metrics']['retweet_count']} RTs")
            print(f"   📅 Tweet age: {tweet_age_hours:.1f} hours ago ({tweet_time.strftime('%Y-%m-%d %H:%M UTC')})")
            
            if tweet_age_hours > 24:
                print(f"   ⚠️ WARNING: Selected tweet is {tweet_age_hours:.1f}h old (>24h)!")
            
            return best_tweet
        
        return None if not return_all else []
        
    except Exception as e:
        print(f"   ❌ Search failed: {e}")
        return None if not return_all else []

async def generate_smart_question(original_tweet=None):
    """Generate analytics question using agent with MCP database exploration tools."""
    print("🤖 Generating smart analytics question using agent with database exploration...")
    
    current_date = get_current_date()
    
    # Import BlitzAgent factory
    import sys
    from pathlib import Path
    from datetime import datetime
    
    blitz_path = Path(__file__).parent.parent / "blitz" / "src"
    if str(blitz_path) not in sys.path:
        sys.path.append(str(blitz_path))
    
    from blitzagent_agno.agent_factory import create_mcp_tools_async, create_agno_model, create_agno_storage, create_agno_memory, get_agent_instructions, RuntimeContext, RuntimeMode, ToneStyle
    from blitzagent_agno.config import Config, DatabaseConfig, ModelConfig
    from agno.tools.reasoning import ReasoningTools
    from agno.agent import Agent
    
    print("   🔧 Creating question generation agent with database exploration...")
    
    # Create database config for NBA using environment variables
    postgres_host = os.getenv("POSTGRES_HOST", "blitz-instance-1.cdu6kma429k4.us-west-2.rds.amazonaws.com")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db = os.getenv("POSTGRES_DATABASE", "nba")
    postgres_user = os.getenv("POSTGRES_USER", "postgres")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "_V8fn.eo62B(gZD|OcQcu~0|aP8[")
    postgres_ssl = os.getenv("POSTGRES_SSL", "true").lower() == "true"
    
    print(f"   🔍 Question gen database config: {postgres_user}@{postgres_host}:{postgres_port}/{postgres_db}, SSL: {postgres_ssl}")
    
    database_config = DatabaseConfig(
        host=postgres_host,
        port=postgres_port,
        database=postgres_db,
        user=postgres_user,
        password=postgres_password,
        ssl_mode="prefer" if postgres_ssl else "disable"  # Use prefer for GitHub Actions compatibility
    )
    
    # Create model config using environment variables
    model_config = ModelConfig(
        provider="azure_openai",
        name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY", "3RxOfsvJrx1vapAtdNJN8tAI5HhSTB2GLq0j3A61MMIOEVaKuo45JQQJ99BCACYeBjFXJ3w3AAABACOGCEvR"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://blitzgpt.openai.azure.com"),
        azure_deployment="gpt-4o",
        azure_api_version="2025-03-01-preview"
    )
    
    # Create complete config
    config = Config(
        database=database_config,
        model=model_config
    )
    
    # Create runtime context for question generation
    context = RuntimeContext(
        mode=RuntimeMode.INSIGHT,
        tone=ToneStyle.FRIENDLY
    )
    
    print("   🚀 Creating MCP tools for database exploration...")
    print(f"   🔗 Testing database connection: {database_config.user}@{database_config.host}:{database_config.port}/{database_config.database}")
    
    try:
        # Add timeout to MCP connection attempt
        import asyncio
        async with asyncio.timeout(90):  # Give it 90 seconds to match agent factory timeout
            async with create_mcp_tools_async(config, league="nba") as mcp_tools:
                print("   ✅ MCP tools connected for question generation!")
                
                # Create agent components  
                model_instance = await create_agno_model(config)
                storage = await create_agno_storage(config)
                memory = await create_agno_memory(config) if context.should_enable_memory() else None
                
                # Create tools list with MCP tools (EXCLUDING upload, validate, query as requested)
                tools = [ReasoningTools(add_instructions=True), mcp_tools]
                
                print(f"   🔧 Tools loaded for question generation: {len(tools)} tool groups")
                
                # Create question generation agent
                agent = Agent(
                    name="BlitzAgent Question Generator",
                    agent_id="blitz_question_gen",
                    tools=tools,
                    instructions="""
                    You are an expert NBA analytics question generator with access to comprehensive NBA data.
                    Your goal is to generate ONE compelling, specific NBA analytics question that leverages unique statistical insights.
                    
                    PROCESS:
                    1. First, explore what tables and data are available using get_database_documentation and search_tables and other types of questions we have answered in the past with recall_similar_db_queries
                    2. Use inspect to understand key table structures and available columns
                    3. Use sample to see what actual data looks like
                    4. Based on the Twitter context (if provided) and data exploration, generate a targeted question
                    
                    QUESTION REQUIREMENTS:
                    - Must be answerable with available NBA data 
                    - Should leverage unique insights only our analytics can provide
                    - Be specific to players, teams, or interesting statistical patterns
                    - Keep under 100 characters for Twitter
                    - Be engaging and likely to generate discussion
                    
                    AVOID:
                    - Generic questions available elsewhere
                    - Questions about current 2025 season (we're in offseason)
                    - Super granular play-by-play questions
                    - Questions about dunks, highlights, or individual plays
                    - Questions about specific moments
                    - Questions that don't leverage our unique analytics
                    - Questions about contract types, two-way contracts, G-League assignments, or contract comparisons
                    - Questions about rookie contracts, veteran minimums, or any contract-related performance
                    - NEVER ask about "two-way players", "two way contracts", "G-League", or contract status
                    
                    Return ONLY the final question, no explanations or additional text.

                    Here are examples of good questions:
                    Percent of the time Stephen Curry hits at least 6 threes in the season opener
                    What is Stephen Curry's career high in minutes played?
                    What is Stephen Curry's career low in minutes played?
                    What is the most offensive rebounds Stephen Curry recorded in a game during the 2023 season?
                    How many minutes does Stephen Curry average on the 1st night of a b2b?
                    Given Stephen Curry had 30+ points, what percent of the time did Draymond Green have 8 assists?
                    Given Stephen Curry had 30+ points, what is the average number of assists Draymond Green got?
                    How often in the 2024 season do at least 3 players on the Warriors score 15 points?
                    In what percent of games does Luka Doncic get 30+ points, and another player on his team also score 20+?
                    In what percent of games does Stephen Curry get 10+ points in the first quarter, and Draymond Green under 5+ points in the first quarter?
                    When Curry plays 40+ minutes, how often do the Warriors win?
                    Is Stephen Curry likely to score the most points on a given day?
                    How do teams perform in the final game of a long road trip (5+ games) this season
                    What is the average point differential in the first game back from a road stand?
                    How many times has a team had a 7+ game home stand in the last 10 years?
                    What is the average length of a home stand for each team this season?
                    What is the Warriors win percentage in home stands of 5+ games the past 5 seasons?
                    Do players play more minutes on their birthday?
                    Rank Lakers players by average PRA (points + rebounds + assists) and show LeBron's ranking
                    LeBron James average assists comparison between Mondays and Tuesdays
                    Most 3-point attempts by players with less than 25 minutes played
                    Compare LeBron James' PRA performance in Lakers wins vs losses to see performance differences
                    Show Lakers players' individual component rankings for points, rebounds, and assists separately, plus overall PRA ranking
                    Compare LeBron James and Anthony Davis PRA averages in games they both played together for the Lakers
                    Rank Lakers players by average PRA in recent seasons (2022+) to see current performance hierarchy
                    LeBron James shooting efficiency against Clippers vs Celtics
                    Frequency of 10+ three-point attempts in games with less than 30 minutes played
                    Kyrie Irving steal performance coming off a win vs coming off a loss
                    Calculate frequency of Damian Lillard games with 20+ points OR 5+ three-pointers made
                    Calculate frequency of Stephen Curry playoff games with 20+ points OR 5+ three-pointers made
                    Calculate frequency of Stephen Curry games with 25+ points OR 6+ three-pointers made
                    LeBron James home vs away performance against Clippers and Celtics
                    LeBron James average points against Warriors vs Wizards
                    Stephen Curry starter status distribution
                    LeBron James' scoring average over the last 10 games
                    Stephen Curry's scoring average over the last 10 games
                    Stephen Curry's assists comparison - first night vs second night of back-to-back games
                    How does Stephen Curry's assist performance differ between the first and second night of back-to-back games? Provide 20 examples.
                    Kyrie Irving combined defensive performance (steals + blocks) coming off losses
                    Kyrie Irving likelihood of 3+ steals coming off a loss
                    Calculate Warriors win rate when Stephen Curry gets 20+ points and 5+ three-pointers made
                    Highest 3-point attempts by bench players in a game?
                    How does Anthony Edwards perform in steals after different lengths of losing streaks?
                    Which big man has hit the most 3s in the 2000s?
                    In what percentage of his games did Stephen Curry lead in scoring?
                    Has Stephen Curry ever recorded a triple double?
                    Has Stephen Curry ever recorded a quadruple double?
                    Has Stephen Curry ever recorded a quintuple double?
                    Has Stephen Curry ever recorded a 5x5?
                    Who is the most recent player to record a triple double?
                    Who had the first triple double?
                    Who was the first player to record a five by five?
                    In games where Stephen Curry scores 40+, how many assists does he average? How does this compare to games where he scores less than 40?
                    Who averages the most rebounds per game in games where they played fewer than 25 minutes?
                    Which player had the highest percentage of their points from free throws in March 2022?
                    Which player had the highest percentage of their points from free throws in March 2022 (min 25 points scored)?
                    Which player averaged the most blocks during 4+ game road stands in the 2024 season?
                    Which player averaged the most blocks during 4+ game road stands this season (min 5 games)?
                    Which player averaged the most blocks during a single 4+ game road stand this season?
                    Has any team gone undefeated in a 5+ game road stand?
                    Find the player with the highest free throw percentage in March 2022 (min 20 attempts)
                    Find the player with the highest percentage of points from free throws in the entire 2022 season (min 200 points)
                    Find the player with the highest percentage of points from free throws in the entire 2020 season
                    Find the player with the highest percentage of points from free throws in March 2021 wins only (min 25 points)
                    Compare the average fouls in a Scott Foster refereed game versus an average NBA game?
                    What is Chris Paul's record in games where Scott Foster is reffing?
                    Chris Paul playoff record when Scott Foster officiates
                    player with best record when Scott Foster officiates
                    player with best record when Scott Foster officiates (min 10 games)
                    Stephen curry most consecutive games with 30+ points
                    Who had the most wins in games where they are at a rest disadvantage in 2021
                    What team has the most wins in games where they had 2+ more rest days than their opponent between 2020-2025 (show all teams)
                    What team has the most wins in games where they had 2+ more rest days than their opponent between 2020-2025
                    Find players with longest consecutive perfect free throw shooting streaks (min 3 attempts per game)
                    Find players with longest consecutive perfect free throw shooting streaks
                    Find Giannis Antetokounmpo's longest consecutive game streaks with double-doubles
                    Find Chris Paul's longest consecutive game streaks with 10+ assists
                    Find Russell Westbrook's longest consecutive triple-double streaks
                    Find Golden State Warriors longest winning streaks (5+ games)
                    Find Luka Doncic's highest 10-game rolling average scoring periods
                    Find Stephen Curry's longest consecutive game streaks with 5+ three-pointers made
                    Team turnover rates comparison: 0 days rest vs 2+ days rest analysis in regular season
                    Find Luka Dončić's highest 10-game rolling average scoring periods
                    Klay Thompson scoring breakdown when Stephen Curry scores 40+ points in same game
                    Warriors win rate when Curry scores under 20 points vs 20+ points in 2024 season
                    Lakers bench scoring correlation when LeBron James and Anthony Davis both score 25+ points in 2024
                    mean, median, std, middle 50% Stephen Curry rebounds broken down by season, by win/loss
                    mean, median, std, middle 50% Stephen Curry rebound rate broken down by season, by win/loss
                    Team win rate correlation with age gap between oldest and youngest teammates in 2024
                    Lebron James assists correlation with PRA in a game
                    Lebron James assists correlation with PRA in a game (show outliers)
                    Is 3PA for Stephen Curry correlated with his team winning
                    Find frequency where all 5 starters on a team score under 5 points in the 4th quarter (group by season type)
                    When the underdog wins the first quarter, how likely are they to win the game?
                    When the underdog has a moneyline of +400 or worse and wins the first quarter, how likely are they to win the game?
                    When the underdog has a moneyline of +300 or worse and wins the first quarter by at least 5 points, how likely are they to win the game?
                    When the underdog has a moneyline of at least +300 and wins the first half by at least 5 points, how likely are they to win the game?
                    When underdogs win the game, what percentage of the time does the over hit?
                    When favorites win the game by at least 10 points, what percentage of the time does the over hit?
                    In games where the spread was X (e.g. ±5.5), how often did the favorite cover the spread?
                    What are the most common point differentials?
                    When a team wins by 20+, how often did the over, under or push hit?
                    Do certain spreads have higher variance in outcomes?
                    Who was favored the most in the 2023 season?
                    Compare Stephen Curry's 3pm when favored versus when not for 2024 season
                    Compare Stephen Curry's 3pm when favored versus when not for in the 2024 calendar year
                    Compare Stephen Curry's average points scored by quarter when starting with Lebron James'
                    In games that enter the 4th quarter within 5 points, how many points does Stephen Curry average?
                    Team with greatest Total Distance Traveled in 2024 Regular Season
                    Heavy underdogs (+400) vs regular underdogs win rates when leading after 3 quarters
                    Longest single trip distance for any team in 2024 regular season
                    Longest single trip distance for any team in 2024 regular season (with 10 examples)
                    ROI of betting over Anthony Edwards points across in his career
                    ROI of betting under James Harden points across his last 10 games
                    ROI of betting over James Harden points across his last 10 games
                    ROI of betting over James Harden Total 3-Pointers Made in his last 20 games
                    ROI of betting under James Harden Total 3-Pointers Made in his last 20 games
                    How much would I have profited betting the under for James Harden Total Rebounds in his last 15 games
                    Profitability of betting over James Harden Total Assists in his L25 games
                    ROI of betting James Harden not to record a double double across his career
                    ROI of betting James Harden to record a double double across his career
                    ROI of betting James Harden Not To Record a Triple Double in his last 40 games
                    ROI of betting over James Harden PRA (Total Points, Rebounds, & Assists) across last 30 games
                    ROI of betting over James Harden points + assists across last 30 games
                    ROI of betting under James Harden points + rebounds across last 82 games
                    ROI of betting under James Harden assists + rebounds across last 82 games
                    ROI of betting under James Harden steals across last 82 games
                    ROI of betting over James Harden steals across last 82 games
                    ROI of betting over James Harden blocks across last 10 games
                    ROI of betting over James Harden turnovers across last 10 games
                    ROI of betting under James Harden STOCKS (steals + blocks)  across last 10 games
                    How often does Brandin Podziemski go over his points line when Stephen Curry is not in the game?
                    ROI of betting Chris Paul over points when Scott Foster officiates
                    ROI of betting Chris Paul under points when Scott Foster officiates
                    Compare the ROI of betting over versus under on Chris Paul points when Scott Foster referees
                    In games where Draymond Green went over his assists line, how often did Curry go over his points line
                    In games where Stephen Curry went over his points line, how often did Klay Thompson go under his points line
                    When Anthony Edwards goes over PRA, how often does the game go over total points?
                    Given Stephen Curry went over his assists line, what percent of the time do the opposing starting guards go over their assist line?
                    When his team fails to cover the spread, how often does Stephen Curry go over on points?
                    """,
                    model=model_instance,
                    storage=storage,
                    memory=memory,
                    enable_user_memories=False,
                    enable_session_summaries=False,
                    add_history_to_messages=False,
                    add_datetime_to_instructions=True,
                    markdown=False,
                )
                
                print("   ✅ Question generation agent created!")
                
                # Create context from original tweet if provided
                tweet_context = ""
                if original_tweet:
                    tweet_context = f"\nTwitter Context: {original_tweet['text']}\nEngagement: {original_tweet['metrics']['like_count']} likes, {original_tweet['metrics']['retweet_count']} retweets\n"
                
                # Question generation prompt
                question_prompt = f"""
                Current Date: {current_date} (NBA Offseason)
                
                {tweet_context}
                
                CRITICAL: DO NOT ask questions about two-way contracts, G-League, or contract types.
                If the tweet mentions contracts, focus on the TEAM or POSITION mentioned instead.
                
                Examples of how to handle contract tweets:
                - Tweet: "Lakers sign guard Chris Mañon to a two-way contract" 
                  → Ask about: "how did lakers guards perform last season" (focus on team + position)
                - Tweet: "Warriors sign center to two-way deal"
                  → Ask about: "what was warriors rebounding average last season" (focus on team + center stats)
                
                Always find the relevant team/position/player elements and ask about those instead.
                
                Additional formatting requirements for this question:
                - Use ALL LOWERCASE and casual language like a normal person asking
                - NO formal punctuation - sound natural and conversational
                - Make it relevant to current NBA discussions{' and the Twitter context above' if original_tweet else ''}
                
                Examples of the casual style wanted:
                - "how many threes did curry make last season in the 3rd quarter at home"
                - "team turnover rates comparison: 0 days rest vs 2+ days rest analysis in regular season"  
                - "who had more rebounds giannis or embiid in 2024 against the warriors"
                """
                
                print("   🎯 Agent exploring database and generating question...")
                response = await agent.arun(question_prompt)
                
                # Extract question from response
                if hasattr(response, 'content'):
                    question = response.content.strip()
                else:
                    question = str(response).strip()
                
                # Clean up the question
                question = question.replace('"', '').replace("'", "").strip()
                
                # Remove any extra explanations - just get the question
                lines = question.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and '?' in line and len(line) <= 150:  # Find the actual question
                        question = line
                        break
                
                print(f"   ✅ Generated targeted question: {question}")
                return question
            
    except Exception as e:
        print(f"   ❌ Agent question generation failed: {e}")
        print(f"   ❌ Error type: {type(e)}")
        raise  # No fallback - MCP tools must work or fail

async def post_question(question, reply_to_id=None):
    """Post question to Twitter (as reply or standalone)."""
    if reply_to_id:
        print("📱 Posting question as reply...")
    else:
        print("📱 Posting standalone question...")
    
    # Add @BlitzAIBot mention at the beginning of the question
    question_with_mention = f"@BlitzAIBot {question}"
    
    try:
        if reply_to_id:
            response = tejsri_client.create_tweet(
                text=question_with_mention,
                in_reply_to_tweet_id=reply_to_id
            )
        else:
            response = tejsri_client.create_tweet(text=question_with_mention)
            
        tweet_id = response.data['id']
        tweet_url = f"https://twitter.com/tejsri01/status/{tweet_id}"
        print(f"   ✅ Question posted: {tweet_url}")
        return tweet_id
        
    except Exception as e:
        print(f"   ❌ Failed to post question: {e}")
        return None

async def generate_mcp_analytics_response(question):
    """Generate analytics response using EXACT working playground pattern."""
    print(f"📊 Generating NBA analytics using EXACT playground pattern: {question[:50]}...")
    
    # Import BlitzAgent factory (exact same imports as playground)
    import sys
    from pathlib import Path
    from datetime import datetime
    
    blitz_path = Path(__file__).parent.parent / "blitz" / "src"
    if str(blitz_path) not in sys.path:
        sys.path.append(str(blitz_path))
    
    from blitzagent_agno.agent_factory import create_mcp_tools_async, create_agno_model, create_agno_storage, create_agno_memory, get_agent_instructions, upload_with_confirmation, RuntimeContext, RuntimeMode, ToneStyle
    from blitzagent_agno.config import Config, DatabaseConfig, ModelConfig
    from agno.tools.reasoning import ReasoningTools
    from agno.agent import Agent
    
    print("   🔧 Using EXACT working playground pattern...")
    print("   📋 Creating agent INSIDE MCP context (like playground)")
    
    # Create database config for NBA using environment variables
    postgres_host = os.getenv("POSTGRES_HOST", "blitz-instance-1.cdu6kma429k4.us-west-2.rds.amazonaws.com")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db = os.getenv("POSTGRES_DATABASE", "nba")
    postgres_user = os.getenv("POSTGRES_USER", "postgres")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "_V8fn.eo62B(gZD|OcQcu~0|aP8[")
    postgres_ssl = os.getenv("POSTGRES_SSL", "true").lower() == "true"
    
    print(f"   🔍 Analytics database config: {postgres_user}@{postgres_host}:{postgres_port}/{postgres_db}, SSL: {postgres_ssl}")
    
    database_config = DatabaseConfig(
        host=postgres_host,
        port=postgres_port,
        database=postgres_db,
        user=postgres_user,
        password=postgres_password,
        ssl_mode="prefer" if postgres_ssl else "disable"  # Use prefer for GitHub Actions compatibility
    )
    
    # Create model config using environment variables
    model_config = ModelConfig(
        provider="azure_openai",
        name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY", "3RxOfsvJrx1vapAtdNJN8tAI5HhSTB2GLq0j3A61MMIOEVaKuo45JQQJ99BCACYeBjFXJ3w3AAABACOGCEvR"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://blitzgpt.openai.azure.com"),
        azure_deployment="gpt-4o",
        azure_api_version="2025-03-01-preview"
    )
    
    # Create complete config
    config = Config(
        database=database_config,
        model=model_config
    )
    
    # Create runtime context for NBA analytics
    context = RuntimeContext(
        mode=RuntimeMode.INSIGHT,
        tone=ToneStyle.FRIENDLY
    )
    
    print("   🚀 Creating MCP tools async context...")
    print(f"   🔗 Database: {database_config.user}@{database_config.host}:{database_config.port}/{database_config.database}")
    print(f"   🔗 Azure OpenAI: {model_config.azure_endpoint}")
    
    # Use the exact working playground pattern - agent created INSIDE MCP context
    try:
        async with create_mcp_tools_async(config, league="nba") as mcp_tools:
            print("   ✅ MCP tools connected successfully!")
            
            # Create agent components (exact same as playground)
            model_instance = await create_agno_model(config)
            storage = await create_agno_storage(config)
            memory = await create_agno_memory(config) if context.should_enable_memory() else None
            
            # Create tools list with MCP tools properly included (exact same as playground)
            tools = [ReasoningTools(add_instructions=True), mcp_tools, upload_with_confirmation]
            
            print(f"   🔧 Tools loaded: {len(tools)} tool groups")
            
            # Create agent (exact same pattern as playground)
            agent = Agent(
                name="BlitzAgent NBA",
                agent_id="blitz_nba",
                tools=tools,
                instructions=get_agent_instructions("production", context),
                model=model_instance,
                storage=storage,
                memory=memory,
                enable_user_memories=context.should_enable_memory(),
                enable_session_summaries=context.should_enable_memory(),
                add_history_to_messages=True,
                num_history_responses=5 if context.should_enable_memory() else 1,
                add_datetime_to_instructions=True,
                markdown=True,
            )
            
            print("   ✅ Agent created successfully with MCP tools!")
            print("   🎯 Executing NBA analytics...")
            
            # Twitter-optimized analytics prompt with proper formatting
            twitter_prompt = f"""
            Answer this NBA question with accurate stats and data: {question}

            TWITTER RESPONSE REQUIREMENTS:
            - Provide a casual, engaging Twitter response (no markdown formatting)
            - NO ### headers, NO ** bold text, NO bullet points
            - NO conversational elements like "Let me know how you'd like to proceed" 
            - NO overly analytical language or academic tone
            - NO mentions of databases, data sources, or technical infrastructure
            - Keep it casual and informative - MAX 250 characters including hashtags
            - NO emojis - just clean, casual basketball language
            - Simply answer the question with relevant stats and context
            - Make it sound like a knowledgeable sports fan sharing insights, not a research paper
            - If you don't have specific data, just say "I don't have that info" - no technical explanations
            - End with relevant hashtags (#NBA #PlayerName)
            """
            
            response = await agent.arun(twitter_prompt)
            
            print("   ✅ Agent completed!")
            print(f"   🎯 Response type: {type(response)}")
            
            # Extract content from response
            if hasattr(response, 'content'):
                response_text = response.content
                print(f"   📝 Content length: {len(response_text)} characters")
            else:
                response_text = str(response)
                print(f"   📝 String length: {len(response_text)} characters")
            
            print(f"   📄 Response preview: {response_text[:100]}{'...' if len(response_text) > 100 else ''}")
            
            return response_text
    
    except Exception as e:
        print(f"   ❌ MCP connection failed: {e}")
        print(f"   ❌ Error type: {type(e)}")
        raise

async def post_analytics_response(response_text, question_tweet_id):
    """Post analytics response from @BlitzAIBot."""
    print("🤖 Posting analytics response from @BlitzAIBot...")
    
    try:
        response = blitzai_client.create_tweet(
            text=response_text,
            in_reply_to_tweet_id=question_tweet_id
        )
        tweet_id = response.data['id']
        tweet_url = f"https://twitter.com/BlitzAIBot/status/{tweet_id}"
        print(f"   ✅ Analytics response posted: {tweet_url}")
        return tweet_id
        
    except Exception as e:
        print(f"   ❌ Failed to post analytics response: {e}")
        return None

async def run_production_workflow():
    """Run production-ready NBA workflow."""
    current_date = get_current_date()
    print("🏀 PRODUCTION NBA WORKFLOW")
    print("=" * 50)
    print(f"📅 Current Date: {current_date}")
    print("🚀 Smart NBA search → Question → Comprehensive MCP Analytics (DB → Web → Betting)")
    print()
    
    try:
        # Step 1: Smart NBA content search
        print("STEP 1: Smart NBA Content Discovery")
        original_tweet = await search_smart_nba_content()
        
        if original_tweet:
            print(f"📋 Found content: {original_tweet['text'][:80]}...")
            print(f"📊 Engagement: {original_tweet['metrics']['like_count']} likes")
            
            # Step 2: Generate contextual question with intelligent context analysis
            print("\nSTEP 2: Generate Question (Intelligent Context Analysis)")
            question = await generate_smart_question(original_tweet)
            
            # Step 3: Post as reply
            print("STEP 3: Post Question as Reply")
            question_tweet_id = await post_question(question, original_tweet['id'])
        else:
            print("❌ No NBA content found, creating standalone question")
            
            # Step 2: Generate standalone question with intelligent context analysis
            print("\nSTEP 2: Generate Standalone Question (Intelligent Context Analysis)")
            question = await generate_smart_question()
            
            # Step 3: Post standalone
            print("STEP 3: Post Standalone Question")
            question_tweet_id = await post_question(question)
        
        if not question_tweet_id:
            print("❌ Failed to post question, exiting")
            return
        
        # Step 4: Wait
        print("\nSTEP 4: Waiting before analytics response...")
        await asyncio.sleep(3)
        
        # Step 5: Generate analytics using comprehensive MCP tools with proper hierarchy
        print("STEP 5: Comprehensive MCP Analytics Generation (DB → Web → Betting)")
        analytics_response = await generate_mcp_analytics_response(question)
        
        # Step 6: Post analytics
        print("STEP 6: Post Analytics Response")
        response_tweet_id = await post_analytics_response(analytics_response, question_tweet_id)
        
        print()
        print("🎉 PRODUCTION WORKFLOW COMPLETED!")
        print("=" * 50)
        print("✅ Used smart NBA content discovery")
        print("✅ Used EXACT comprehensive sports analytics prompt from blitzagent_agno")
        print("✅ Proper MCP tool hierarchy: Historical DB → Web Scraping → Betting Data")
        print("✅ Intelligent question generation with database-focused prompting")
        print("✅ Question posted showcasing unique database capabilities")
        print("✅ Analytics response with full workflow validation")
        print(f"✅ Current date context: {current_date}")
        print(f"✅ Question Tweet ID: {question_tweet_id}")
        print(f"✅ Response Tweet ID: {response_tweet_id}")
        print()
        print("🔗 LIVE LINKS:")
        print(f"   Question: https://twitter.com/tejsri01/status/{question_tweet_id}")
        if response_tweet_id:
            print(f"   Response: https://twitter.com/BlitzAIBot/status/{response_tweet_id}")
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        logger.exception("Production workflow error")

async def main():
    """Main function."""
    current_date = get_current_date()
    print(f"🕒 Starting PRODUCTION NBA workflow at: {datetime.now()}")
    print(f"📅 Current Date: {current_date}")
    print("🚀 Rate-limit friendly NBA automation with comprehensive MCP tools & proper hierarchy")
    print("🎯 REAL TWITTER POSTING")
    print()
    
    await run_production_workflow()
    
    print()
    print("🏆 PRODUCTION WORKFLOW COMPLETE!")
    print("NBA analytics thread posted to Twitter with EXACT agno rules!")
    print("✅ All MCP tool hierarchy rules copied from blitzagent_agno")
    print("✅ Intelligent question generation with database-focused prompting")
    print("✅ Twitter-optimized response formatting")
    print("Ready for 6x daily deployment! 🚀")

if __name__ == "__main__":
    asyncio.run(main()) 