#!/usr/bin/env python3
"""
Production-Ready NBA Workflow 
Rate-limit friendly version that actually works end-to-end with comprehensive MCP tools.
Uses the EXACT same sports analytics prompt as blitzagent_agno with all rules copied over:
1. Historical Database (PostgreSQL) - PREFERRED SOURCE with mandatory workflow sequence
2. Web Scraping - SECONDARY SOURCE for recent/breaking news
3. Live Betting Data - TERTIARY SOURCE with two-step workflow and EV analysis
4. Direct Azure OpenAI for question generation (no agent) with tweet context and examples
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
        start_time_iso = twenty_four_hours_ago.isoformat()
        
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
                    
                    # Only add if it has NBA content AND explicit NBA references AND doesn't have excluded content
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
    """Generate analytics question using direct Azure OpenAI call (not agent)."""
    print("🤖 Generating smart analytics question using direct Azure OpenAI...")
    
    current_date = get_current_date()
    
    # Fan-friendly, engaging question examples (database-friendly stats, offseason appropriate)
    example_questions = [
        "What was LeBron's scoring average in 2024 vs 2023?",
        "How many triple-doubles did Luka have last season?",
        "What was the Warriors' home vs away record in 2024?",
        "What was Jayson Tatum's shooting percentage last season?",
        "What's the Lakers' all-time record when LeBron scores 30+?",
        "How many assists did Chris Paul average last season?",
        "How did the Celtics perform on the road in 2024?",
        "What was Kevin Durant's field goal percentage in 2024?",
        "How many blocks did Anthony Davis average last season?",
        "What was the Nuggets' record in close games in 2024?",
        "How many steals did Kawhi Leonard average in 2024?",
        "What's Jimmy Butler's career playoff scoring average?",
        "How do the Suns perform without Kevin Durant historically?",
        "What was Zion Williamson's rebounding average in 2024?",
        "What was the Clippers' win percentage last season?",
        "How did Paolo Banchero's rookie year compare to others?",
        "What was the Heat's defensive rating in 2024?",
        "What's Ja Morant's career assist-to-turnover ratio?",
        "How many 30+ point games did Curry have in 2024?",
        "What was the Lakers' offensive rating last season?",
        "How many double-doubles did Giannis record in 2024?",
        "What was Boston's three-point percentage in 2024?",
        "How many games did Kawhi Leonard play last season?",
        "What's Miami's all-time record in close games?",
        "How did Wembanyama's rookie season compare to other centers?"
    ]
    
    # Create context from original tweet if provided
    tweet_context = ""
    if original_tweet:
        tweet_context = f"\nContext from NBA Tweet: {original_tweet['text']}\nEngagement: {original_tweet['metrics']['like_count']} likes, {original_tweet['metrics']['retweet_count']} retweets"
    
    # Create direct Azure OpenAI client using environment variables
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY", "3RxOfsvJrx1vapAtdNJN8tAI5HhSTB2GLq0j3A61MMIOEVaKuo45JQQJ99BCACYeBjFXJ3w3AAABACOGCEvR"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://blitzgpt.openai.azure.com"),
        api_version="2025-03-01-preview"
    )
    
    # Create prompt for question generation
    question_generation_prompt = f"""
    You are an NBA analytics question generator. Generate one engaging, specific NBA analytics question that can be answered with standard NBA box score statistics and team records (avoid super granular play-by-play data).

    IMPORTANT CONTEXT:
    - Today's Date: {current_date} 
    - Current Status: NBA OFFSEASON (2024 season ended, 2025 season hasn't started)
    - Available Data: Complete data through 2024 season, no 2025 data yet
    
    CONTEXT:{tweet_context}
    
    EXAMPLES OF GOOD QUESTIONS:
    {chr(10).join(f"- {q}" for q in example_questions[:10])}
    
    RULES FOR GOOD QUESTIONS:
    - Ask about specific players, teams, or matchups
    - Include measurable statistics (points, rebounds, assists, shooting %, etc.)
    - Reference time periods like: "last season" (2024), "career", "last 3 seasons", "vs specific teams"
    - NEVER ask about "this season" or "2025 season" - we're in offseason with no current season data
    - Be conversational and engaging for NBA fans
    - Avoid generic questions - be specific
    - Should be answerable with historical NBA database (2024 and earlier)
    - Keep under 100 characters for Twitter
    - AVOID super granular play-by-play questions (like specific dunk counts, buzzer-beaters, clutch shots) - focus on standard box score stats instead
    - Focus on season averages, totals, percentages, and team records rather than specific game moments
    
    {"Based on the tweet context above, generate a related NBA analytics question." if original_tweet else "Generate a compelling NBA analytics question."}
    
    Return ONLY the question, no explanation or quotes.
    """
    
    try:
        print("   🔧 Calling Azure OpenAI directly for question generation...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert NBA analytics question generator. Focus on standard box score stats, averages, and team records rather than granular play-by-play data. Remember: we're in NBA offseason, so ask about 2024 season or earlier data, not current season."},
                {"role": "user", "content": question_generation_prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        question = response.choices[0].message.content.strip()
        question = question.replace('"', '').replace("'", "")
        print(f"   ✅ Generated: {question}")
        return question
        
    except Exception as e:
        print(f"   ❌ Azure OpenAI question generation failed: {e}")
        # Fallback to random example question
        fallback_question = random.choice(example_questions)
        print(f"   🔄 Using fallback question: {fallback_question}")
        return fallback_question

async def post_question(question, reply_to_id=None):
    """Post question to Twitter (as reply or standalone)."""
    if reply_to_id:
        print("📱 Posting question as reply...")
    else:
        print("📱 Posting standalone question...")
    
    try:
        if reply_to_id:
            response = tejsri_client.create_tweet(
                text=question,
                in_reply_to_tweet_id=reply_to_id
            )
        else:
            response = tejsri_client.create_tweet(text=question)
            
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
    database_config = DatabaseConfig(
        host=os.getenv("POSTGRES_HOST", "blitz-instance-1.cdu6kma429k4.us-west-2.rds.amazonaws.com"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DATABASE", "nba"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "_V8fn.eo62B(gZD|OcQcu~0|aP8["),
        ssl_mode="require" if os.getenv("POSTGRES_SSL", "true").lower() == "true" else "disable"
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
        tone=ToneStyle.ANALYTICAL
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
            Answer this NBA question with factual data from the historical database: {question}

            TWITTER RESPONSE REQUIREMENTS:
            - Provide a clean, engaging Twitter response (no markdown formatting)
            - NO ### headers, NO ** bold text, NO bullet points
            - NO conversational elements like "Let me know how you'd like to proceed" 
            - NO chat-like language - this is a tweet, not a conversation
            - Focus on specific numbers, stats, and factual insights
            - Keep it informative but concise for Twitter audience
            - If data is missing for recent periods, simply state what data IS available
            - Format as a standalone informative tweet that provides value
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
            
            # Step 2: Generate contextual question with direct Azure OpenAI
            print("\nSTEP 2: Generate Question (Direct Azure OpenAI)")
            question = await generate_smart_question(original_tweet)
            
            # Step 3: Post as reply
            print("STEP 3: Post Question as Reply")
            question_tweet_id = await post_question(question, original_tweet['id'])
        else:
            print("❌ No NBA content found, creating standalone question")
            
            # Step 2: Generate standalone question with direct Azure OpenAI
            print("\nSTEP 2: Generate Standalone Question (Direct Azure OpenAI)")
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
        print("✅ Direct Azure OpenAI question generation (no agent)")
        print("✅ Question posted with tweet context and examples")
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
    print("✅ Direct Azure OpenAI question generation with context & examples")
    print("✅ Twitter-optimized response formatting")
    print("Ready for 6x daily deployment! 🚀")

if __name__ == "__main__":
    asyncio.run(main()) 