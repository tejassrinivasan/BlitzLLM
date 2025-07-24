import os
import tweepy
import httpx
import asyncio
from dotenv import load_dotenv
import ssl
import aiohttp
import time
import datetime
import traceback
import re
from datetime import timedelta
import sys
from pathlib import Path

# Add the blitz source to path
sys.path.append(str(Path(__file__).parent.parent / 'blitz' / 'src'))

# Import NBA analytics function
from production_ready_nba import generate_mcp_analytics_response

load_dotenv()

# Twitter API Configuration (same as production_ready_nba.py)
SHARED_CONSUMER_KEY = "IO0UIDgBKTrXby3Sl2zPz0vJO"
SHARED_CONSUMER_SECRET = "6hKlyZCwLCpVPZ4dxfCiISC7H4Sg61YJdxYr0nGqHrdBuUt1AF"

# @BlitzAnalytics credentials (for rate-limit-free searching)
BLITZANALYTICS_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAL852AEAAAAArcVns1HPuR8uM8MhFdaqncOUcFw%3DTM16qakucHczkcg8MJ4GwamqpuUm0pCKESK2oHsR4i4hJ094LN"
BLITZANALYTICS_ACCESS_TOKEN = "1889746223613321216-ASI5OzBr1OJP6E4MbVAq9UKletu2HZ"
BLITZANALYTICS_ACCESS_SECRET = "aqJrBXgiNoJUhwiZRqOJ0kfWTWtaKWPSiEQVW7VdHLkuO"

# @BlitzAIBot credentials (for posting analytics responses - has blue check)
BLITZAI_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAL852AEAAAAAFDeKS7l%2FbmLY4Aqywrzfj316X9U%3DhMN7FrxP8RVKchRgx08G4vFwEk0XwiY2F1CJ0mk57AMhVFOUlW"
BLITZAI_ACCESS_TOKEN = "1930145656842399746-N75MTZ1FkOmhM52Ofyrw5XqKsNG1mA"
BLITZAI_ACCESS_SECRET = "zMIrda7t5kEjtVp4drnIlICEh6PyiQH5citssMs0m1tRl"

BOT_USERNAME = "@BlitzAIBot"

print(f"✅ BlitzAnalytics (search) + BlitzAIBot (post) credentials configured")

# Tweepy clients - separate for searching vs posting
from tweepy.asynchronous import AsyncClient

# BlitzAnalytics client for searching mentions (no rate limits)
search_client = AsyncClient(
    bearer_token=BLITZANALYTICS_BEARER_TOKEN,
    consumer_key=SHARED_CONSUMER_KEY,
    consumer_secret=SHARED_CONSUMER_SECRET,
    access_token=BLITZANALYTICS_ACCESS_TOKEN,
    access_token_secret=BLITZANALYTICS_ACCESS_SECRET,
    wait_on_rate_limit=True
)

# BlitzAIBot client for posting responses
post_client = AsyncClient(
    bearer_token=BLITZAI_BEARER_TOKEN,
    consumer_key=SHARED_CONSUMER_KEY,
    consumer_secret=SHARED_CONSUMER_SECRET,
    access_token=BLITZAI_ACCESS_TOKEN,
    access_token_secret=BLITZAI_ACCESS_SECRET,
    wait_on_rate_limit=True
)

# In-memory set to track threads the bot has replied to
replied_threads = set()
bot_user_id = None

async def has_explicit_mention(tweet) -> bool:
    """
    Determines if the bot was explicitly mentioned.

    For replies: if the number of bot mentions in this tweet > number in parent,
    it's likely an intentional summon.
    """
    print(f"\n=== Analyzing mention in tweet {tweet.id} ===")
    print(f"Original tweet text: {tweet.text}")
    print(f"In reply to user ID: {getattr(tweet, 'in_reply_to_user_id', None)}")
    print(f"Bot user ID: {bot_user_id}")

    text = tweet.text or ""
    token = BOT_USERNAME.lower()
    mention_count = text.lower().count(token)
    print(f"Bot mention count in this tweet: {mention_count}")

    if mention_count == 0:
        print("No mentions found - returning False")
        return False

    # If it's a reply, compare to parent tweet
    if getattr(tweet, "in_reply_to_user_id", None):
        parent_tweet_id = None
        for ref in tweet.referenced_tweets or []:
            if ref["type"] == "replied_to":
                parent_tweet_id = ref["id"]
                break

        if parent_tweet_id:
            try:
                parent = await search_client.get_tweet(parent_tweet_id, tweet_fields=["text", "author_id"])
                parent_author_id = parent.data.get("author_id")
                parent_text = parent.data.text if parent and parent.data else ""
                parent_count = parent_text.lower().count(token)
                print(f"Bot mention count in parent: {parent_count}, {parent_author_id}, {parent_text}")

                # if parent post is the bot, all replies automatically @ the bot, so we need 2 in response
                if parent_author_id == bot_user_id:
                    return mention_count > parent_count + 1

                # if parent post is not the bot, we need to check if the reply has more bot mentions than the parent
                if mention_count > parent_count:
                    print("More bot mentions in reply than parent — treating as explicit")
                    return True
                else:
                    print("Bot mention not added in reply — treating as implicit")
                    return False
            except Exception as e:
                print(f"Error fetching parent tweet: {e}")
                # Fall back to default behavior
                pass

    # If not a reply or couldn't fetch parent — use position logic
    positions = [m.start() for m in re.finditer(re.escape(token), text.lower())]
    print(f"Found {len(positions)} mentions at positions: {positions}")

    if len(positions) > 1:
        print("Multiple mentions — treating as explicit")
        return True

    first_pos = positions[0]
    if first_pos > 0:
        print(f"Single mention found at position {first_pos} (not at start) — treating as explicit")
        return True

    print("Single mention at start, not replying to bot — treating as explicit")
    return True

async def generate_nba_response(user_question, thread_content=None, comment_highlights=None):
    """Generate NBA analytics response using the local NBA system."""
    print(f"🏀 Generating NBA response for: {user_question[:50]}...")
    
    try:
        # Create a comprehensive question with context
        if thread_content:
            full_question = f"Original tweet: {thread_content}\n\nUser question: {user_question}"
        else:
            full_question = user_question
            
        # Use the NBA analytics response generator
        response = await generate_mcp_analytics_response(full_question)
        
        if not response or len(response.strip()) < 10:
            # Fallback for short/empty responses
            return "I can provide NBA statistics and insights! Try asking about specific players, teams, or season performance."
            
        return response
        
    except Exception as e:
        print(f"❌ Error generating NBA response: {e}")
        traceback.print_exc()
        return "Sorry, I'm having trouble accessing NBA data right now. Please try again!"

async def process_mention(tweet):
    # Ignore retweets and tweets from the bot itself
    if tweet.author_id == bot_user_id or tweet.text.startswith("RT"):
        return
        
    # Only respond if there is an explicit mention
    if not await has_explicit_mention(tweet):
        return
        
    print(f"🎯 Processing explicit mention from tweet {tweet.id}")
    
    # Fetch the original tweet if this is a reply (thread context)
    thread_content = ""
    original_author = None
    original_author_username = None
    original_tweet_id = None
    current_author = None
    current_author_username = None
    current_author = tweet.author_id
    
    user_resp = await search_client.get_user(id=current_author)
    if user_resp and user_resp.data:
        current_author_username = user_resp.data.username

    if tweet.referenced_tweets:
        for ref in tweet.referenced_tweets:
            if ref["type"] == "replied_to":
                original_tweet = await search_client.get_tweet(ref["id"], tweet_fields=["text", "author_id"])
                print(original_tweet)
                if original_tweet and original_tweet.data:
                    thread_content = original_tweet.data["text"]
                    original_tweet_id = original_tweet.data["id"]
                    original_author = original_tweet.data["author_id"]
                    # Fetch the username of the original author
                    user_resp = await search_client.get_user(id=original_author)
                    if user_resp and user_resp.data:
                        original_author_username = user_resp.data.username
                        
    # Fetch top 20 replies to the original tweet (if thread context exists)
    comment_highlights = None
    if original_tweet_id:
        query = f"conversation_id:{original_tweet_id} -from:{BOT_USERNAME.lstrip('@')}"
        try:
            replies_resp = await search_client.search_recent_tweets(query=query, max_results=20, tweet_fields=["text", "public_metrics", "author_id"])
            replies = replies_resp.data if replies_resp and replies_resp.data else []
            replies = sorted(replies, key=lambda x: x.public_metrics.get("like_count", 0) if hasattr(x, "public_metrics") else 0, reverse=True)
            top_replies = replies[:20]
            comments_text = "\n".join([reply.text for reply in top_replies])
            comment_highlights = comments_text
        except Exception as e:
            print(f"Error fetching replies: {e}")
            comment_highlights = None
    
    user_question = tweet.text.replace(BOT_USERNAME, "").strip()
    
    # Generate NBA response using local system
    reply_text = await generate_nba_response(user_question, thread_content, comment_highlights)
    
    try:
        user_resp = await search_client.get_user(id=tweet.author_id)
        author_username = user_resp.data.username if user_resp and user_resp.data else tweet.author_id

        print(f"Reply text length: {len(reply_text)}")
        
        # Split long responses into multiple tweets
        if len(reply_text) > 4000:
            chunks = []
            current_chunk = []
            lines = reply_text.split('\n')
            current_length = 0
            
            i = 0
            while i < len(lines):
                line = lines[i]
                
                # Look ahead to see if next line is blank
                next_is_blank = (i + 1 < len(lines) and not lines[i + 1].strip())
                
                # If adding this line would exceed limit
                if current_length + len(line) + 2 > 3900:  # Leave room for username and continuation marker
                    # Only split at blank lines
                    last_blank = -1
                    for j in range(len(current_chunk)-1, -1, -1):
                        if not current_chunk[j].strip():
                            last_blank = j
                            break
                            
                    if last_blank >= 0:
                        # Split at last blank line
                        chunks.append('\n'.join(current_chunk[:last_blank]))
                        current_chunk = current_chunk[last_blank+1:]
                        current_length = sum(len(l) + 1 for l in current_chunk)
                    elif not current_chunk:
                        # If chunk is empty, force add current line
                        current_chunk.append(line)
                        current_length = len(line) + 1
                        i += 1
                        continue
                    else:
                        # Keep accumulating until we find a blank line
                        current_chunk.append(line)
                        current_length += len(line) + 1
                        i += 1
                        continue
                
                current_chunk.append(line)
                current_length += len(line) + 1
                
                # Add blank line if present
                if next_is_blank:
                    current_chunk.append('')
                    current_length += 1
                    i += 2
                else:
                    i += 1
            
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                
            # Post the thread of replies using BlitzAIBot
            previous_tweet_id = tweet.id
            for i, chunk in enumerate(chunks):
                text = f"@{author_username} {chunk}"
                if i < len(chunks) - 1:
                    text += "\n\nMore ⬇️"
                    
                response = await post_client.create_tweet(
                    text=text,
                    in_reply_to_tweet_id=previous_tweet_id
                )
                previous_tweet_id = response.data["id"]
                print(f"✅ Posted thread part {i+1}/{len(chunks)}")
        else:
            await post_client.create_tweet(
                text=f"@{author_username} {reply_text}",
                in_reply_to_tweet_id=tweet.id
            )
            print(f"✅ Posted single reply to @{author_username}")
            
    except Exception as e:
        print(f"Error replying: {e}")
        traceback.print_exc()

async def main():
    global bot_user_id
    me = await post_client.get_me()  # Use post_client to get BlitzAIBot's info
    bot_user_id = me.data.id
    print(f"🤖 BlitzAIBot mention listener started!")
    print(f"Bot user id: {bot_user_id}")
    print(f"Listening for mentions to: {BOT_USERNAME}")
    
    last_mention_id = None

    while True:
        try:
            # Get tweets from the last 5 minutes
            five_minutes_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)
            start_time_str = five_minutes_ago.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            query = f"@{BOT_USERNAME.lstrip('@')}"
            search_kwargs = {
                "query": f"@{BOT_USERNAME.lstrip('@')}",
                "tweet_fields": [
                    "author_id",
                    "referenced_tweets", 
                    "text",
                    "created_at",
                    "in_reply_to_user_id",
                ],
                "max_results": 100,
            }

            if last_mention_id:
                search_kwargs["since_id"] = last_mention_id
            else:
                # First run: only search tweets from last minute to avoid blast
                one_min_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1)
                search_kwargs["start_time"] = one_min_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

            mentions = await search_client.search_recent_tweets(**search_kwargs)  # Use search_client for searching

            tweets = mentions.data if mentions and mentions.data else []

            # Deduplicate and sort
            seen_ids = set()
            tweets = sorted(tweets, key=lambda x: int(x.id))
            
            processed_count = 0
            for tweet in tweets:
                if tweet.id in seen_ids:
                    continue
                seen_ids.add(tweet.id)

                await process_mention(tweet)
                processed_count += 1
                last_mention_id = tweet.id

            if processed_count > 0:
                print(f"📊 Processed {processed_count} mentions")
            else:
                print("💤 No new mentions found")
                
        except Exception as e:
            print(f"❌ Error fetching or processing mentions: {e}")
            traceback.print_exc()
            
        print("⏰ Sleeping for 60 seconds...")
        await asyncio.sleep(60)


if __name__ == "__main__":
    print("🚀 Starting BlitzAIBot NBA Mention Listener...")
    asyncio.run(main()) 