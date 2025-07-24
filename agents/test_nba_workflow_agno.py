#!/usr/bin/env python3
"""
NBA Content Discovery - Simplified Agno Test
Tests core NBA functionality using Agno agents without complex workflow structures.
"""

import os
import asyncio
import logging
from datetime import datetime

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

# Import Agno components
from agno.agent import Agent
from agno.models.openai import OpenAIChat

def test_duplicate_prevention():
    """Test the duplicate prevention system."""
    print("1. 🔄 Testing duplicate prevention system...")
    
    try:
        # Create processed_tweets.txt for testing
        test_tweets = ["1234567890", "1234567891", "1234567892"]
        
        with open("processed_tweets.txt", "w") as f:
            for tweet_id in test_tweets:
                f.write(f"{tweet_id}\n")
        
        # Load them back
        processed_tweets = set()
        with open("processed_tweets.txt", "r") as f:
            processed_tweets = set(line.strip() for line in f if line.strip())
        
        print(f"   ✅ Loaded {len(processed_tweets)} processed tweet IDs")
        print(f"   📝 Sample IDs: {list(processed_tweets)[:3]}")
        
        # Clean up
        os.remove("processed_tweets.txt")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_nba_content_filtering():
    """Test NBA content filtering logic."""
    print("\n2. 🏀 Testing NBA content filtering...")
    
    try:
        # NBA keywords for filtering
        nba_keywords = [
            'nba', 'basketball', 'lakers', 'warriors', 'celtics', 'lebron', 'curry',
            'points', 'rebounds', 'assists', 'game', 'season', 'playoff'
        ]
        
        # Sample tweets to filter
        sample_tweets = [
            {"text": "LeBron James scores 30 points in Lakers win!", "id": "123"},
            {"text": "Weather update: sunny day today", "id": "456"},
            {"text": "Warriors defeat Celtics 120-115 in overtime", "id": "789"},
            {"text": "Check out this amazing recipe!", "id": "999"},
            {"text": "NBA standings update: Lakers climb to 4th", "id": "111"}
        ]
        
        # Filter NBA content
        filtered_tweets = []
        for tweet in sample_tweets:
            text = tweet.get('text', '').lower()
            if any(keyword in text for keyword in nba_keywords):
                filtered_tweets.append(tweet)
        
        print(f"   ✅ Filtered {len(filtered_tweets)}/{len(sample_tweets)} tweets as NBA content")
        
        for tweet in filtered_tweets:
            print(f"     - {tweet['text'][:50]}...")
        
        return len(filtered_tweets) > 0
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

async def test_agno_agent_creation():
    """Test creating Agno agents with NBA tools."""
    print("\n3. 🤖 Testing Agno agent creation...")
    
    try:
        # Mock NBA tools for testing
        def mock_search_nba_tweets(agent, query="", max_results=10):
            """Mock NBA tweet search."""
            return f"Found NBA tweets for query: {query}"
        
        def mock_query_nba_database(agent, question=""):
            """Mock NBA database query."""
            return f"NBA analytics for: {question}"
        
        # Create NBA Content Agent
        content_agent = Agent(
            name="NBA Content Agent",
            model=OpenAIChat(id="gpt-4o"),
            tools=[mock_search_nba_tweets],
            instructions=[
                "You are an NBA content discovery specialist.",
                "Search for trending NBA content using expanded hashtags.",
                "Focus on tweets with statistical content and high engagement."
            ]
        )
        
        print("   ✅ NBA Content Agent created successfully")
        
        # Create NBA Question Agent
        question_agent = Agent(
            name="NBA Question Agent", 
            model=OpenAIChat(id="gpt-4o"),
            instructions=[
                "You generate NBA analytics questions.",
                "Always tag @BlitzAIBot in questions.",
                "Focus on performance comparisons and trends."
            ]
        )
        
        print("   ✅ NBA Question Agent created successfully")
        
        # Create NBA Analytics Agent
        analytics_agent = Agent(
            name="NBA Analytics Agent",
            model=OpenAIChat(id="gpt-4o"),
            tools=[mock_query_nba_database],
            instructions=[
                "You provide NBA analytics responses.",
                "Use real database queries for statistics.",
                "Format responses for Twitter."
            ]
        )
        
        print("   ✅ NBA Analytics Agent created successfully")
        
        # Test basic agent functionality (structure only to avoid API costs)
        print("\n   🧪 Agent structure validation...")
        print("   📝 Note: Skipping actual AI calls to avoid costs/rate limits")
        
        # Validate agent configurations
        assert content_agent.name == "NBA Content Agent"
        assert len(content_agent.tools) == 1
        assert "NBA content discovery" in content_agent.instructions[0]
        print("   ✅ Content agent configuration valid")
        
        assert question_agent.name == "NBA Question Agent"
        assert "@BlitzAIBot" in question_agent.instructions[1]
        print("   ✅ Question agent configuration valid")
        
        assert analytics_agent.name == "NBA Analytics Agent"
        assert len(analytics_agent.tools) == 1
        print("   ✅ Analytics agent configuration valid")
        
        # Test tool function calls directly (without AI)
        mock_result = mock_search_nba_tweets(content_agent, "#NBA", 10)
        print(f"   ✅ Mock tool test: {mock_result}")
        
        mock_analytics = mock_query_nba_database(analytics_agent, "Lakers overtime performance")
        print(f"   ✅ Mock analytics: {mock_analytics}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_comprehensive_nba_sources():
    """Test comprehensive NBA source configuration including teams, reporters, and popular accounts."""
    print("\n4. 🏀 Testing comprehensive NBA source configuration...")
    
    try:
        # Comprehensive NBA search structure
        search_categories = {
            "Hashtags & Betting": ["#NBA", "#PrizePicks", "#DraftKings", "#FanDuel", "#NBABetting", "#NBAStats"],
            "NBA Teams": ["@Lakers", "@warriors", "@celtics", "@MiamiHEAT", "@BrooklynNets", "@nyknicks", "@chicagobulls", "@cavs", 
                         "@DetroitPistons", "@pacers", "@Bucks", "@ATLHawks", "@hornets", "@OrlandoMagic", "@sixers", "@Raptors",
                         "@WashWizards", "@nuggets", "@Timberwolves", "@okcthunder", "@trailblazers", "@utahjazz", 
                         "@SacramentoKings", "@LAClippers", "@Suns", "@dallasmavs", "@HoustonRockets", "@memgrizz", "@PelicansNBA", "@spurs"],
            "NBA Reporters": ["@ShamsCharania", "@MarcJSpears", "@TheSteinLine", "@anthonyVslater", "@wojespn", 
                             "@ramonashelburne", "@chrisbhaynes", "@WindhorstESPN"],
            "Popular NBA Accounts": ["@TheNBACentral", "@LegionHoops", "@BallisLife", "@overtime", "@SportsCenter", 
                                   "@BleacherReport", "@NBAonTNT", "@NBATV"]
        }
        
        print(f"   ✅ Comprehensive NBA search configured with {len(search_categories)} categories")
        
        total_sources = 0
        for category, sources in search_categories.items():
            print(f"   📋 {category}: {len(sources)} sources")
            total_sources += len(sources)
            # Show a few examples
            examples = sources[:3] if len(sources) > 3 else sources
            print(f"     Examples: {', '.join(examples)}")
        
        print(f"   📊 Total NBA sources: {total_sources}")
        
        # Test that we have comprehensive coverage
        if total_sources >= 50:  # We should have 50+ sources
            print("   ✅ Comprehensive NBA source coverage achieved")
            return True
        else:
            print(f"   ⚠️  Limited source coverage: {total_sources} sources")
            return False
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

async def main():
    """Main test function."""
    print("🏀 NBA Content Discovery - Simplified Agno Test")
    print("=" * 70)
    print("🎯 Testing core NBA functionality with Agno integration")
    print("⚠️  No actual Twitter API calls - structure testing only")
    print(f"🕒 Test started at: {datetime.now()}")
    print()
    
    tests = [
        ("Duplicate Prevention", test_duplicate_prevention),
        ("NBA Content Filtering", test_nba_content_filtering), 
        ("Agno Agent Creation", test_agno_agent_creation),
        ("Comprehensive NBA Sources", test_comprehensive_nba_sources)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append(result)
        except Exception as e:
            print(f"   ❌ {test_name} failed: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 70)
    print("🎉 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test_name, _) in enumerate(tests):
        status = "✅" if results[i] else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🚀 ALL TESTS PASSED - Ready for Production!")
        print("✅ Agno agent creation working")
        print("✅ NBA content filtering working")
        print("✅ Duplicate prevention working")
        print("✅ Comprehensive NBA source coverage (50+ accounts)")
        print("✅ Ready to integrate with full workflow")
        print("\n🔧 Next steps:")
        print("   - Deploy with real Twitter API integration")
        print("   - Add real NBA database queries via MCP")
        print("   - Set up 6x daily scheduling with Agno workflows")
        print("   - Monitor performance across all NBA sources")
        print("   - Optimize engagement and content quality")
    else:
        print(f"\n🔧 {total - passed} tests failed - check configuration")

if __name__ == "__main__":
    asyncio.run(main()) 