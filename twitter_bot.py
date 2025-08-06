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

load_dotenv()

# Twitter API credentials
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
API_KEY = os.getenv("X_CONSUMER_KEY")
API_SECRET = os.getenv("X_CONSUMER_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_SECRET")
BOT_USERNAME = os.getenv("X_BOT_NAME")  # e.g. "@MyBot"

# BlitzAgent API configuration
BLITZAGENT_API_URL = "https://blitzagent.onrender.com"
BLITZAGENT_API_KEY = os.getenv("BLITZAGENT_API_KEY")  # Required: Add this to your .env file

if not BLITZAGENT_API_KEY:
    print("WARNING: BLITZAGENT_API_KEY not found in environment variables. Add it to your .env file.")

# Tweepy client for posting replies
from tweepy.asynchronous import AsyncClient

client = AsyncClient(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
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
                parent = await client.get_tweet(parent_tweet_id, tweet_fields=["text", "author_id"])
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

async def process_mention(tweet):
    # Ignore retweets and tweets from the bot itself
    if tweet.author_id == bot_user_id or tweet.text.startswith("RT"):
        return
    # Only respond if there is an explicit mention
    if not await has_explicit_mention(tweet):
        return
    # Fetch the original tweet if this is a reply (thread context)
    thread_content = ""
    original_author = None
    original_author_username = None
    original_tweet_id = None
    current_author = None
    current_author_username = None
    current_author = tweet.author_id
    user_resp = await client.get_user(id=current_author)
    if user_resp and user_resp.data:
        current_author_username = user_resp.data.username

    if tweet.referenced_tweets:
        for ref in tweet.referenced_tweets:
            if ref["type"] == "replied_to":
                original_tweet = await client.get_tweet(ref["id"], tweet_fields=["text", "author_id"])
                print(original_tweet)
                if original_tweet and original_tweet.data:
                    thread_content = original_tweet.data["text"]
                    original_tweet_id = original_tweet.data["id"]
                    original_author = original_tweet.data["author_id"]
                    # Fetch the username of the original author
                    user_resp = await client.get_user(id=original_author)
                    if user_resp and user_resp.data:
                        original_author_username = user_resp.data.username
    # Fetch top 20 replies to the original tweet (if thread context exists)
    comment_highlights = None
    if original_tweet_id:
        query = f"conversation_id:{original_tweet_id} -from:{BOT_USERNAME.lstrip('@')}"
        try:
            replies_resp = await client.search_recent_tweets(query=query, max_results=20, tweet_fields=["text", "public_metrics", "author_id"])
            replies = replies_resp.data if replies_resp and replies_resp.data else []
            replies = sorted(replies, key=lambda x: x.public_metrics.get("like_count", 0) if hasattr(x, "public_metrics") else 0, reverse=True)
            top_replies = replies[:20]
            comments_text = "\n".join([reply.text for reply in top_replies])
            comment_highlights = comments_text
        except Exception as e:
            print(f"Error fetching replies: {e}")
            comment_highlights = None
    user_question = tweet.text.replace(BOT_USERNAME, "").strip()
    
    # Build extra context for Twitter response
    extra_context = "This is a Twitter reply. Keep response under 250 characters and be concise."
    if thread_content:
        extra_context += f" Original tweet: {thread_content}"
        if original_author_username:
            extra_context += f" (by @{original_author_username})"
    if current_author_username:
        extra_context += f" Current user: @{current_author_username}"
    if comment_highlights:
        extra_context += f" Top replies context: {comment_highlights[:500]}..."  # Limit context size
    
    payload = {
        "query": user_question,
        "extra_context": extra_context
    }
    
    if not BLITZAGENT_API_KEY:
        print("Error: BLITZAGENT_API_KEY not configured")
        reply_text = "Sorry, the bot is not properly configured."
        # Get username for reply
        user_resp = await client.get_user(id=tweet.author_id)
        author_username = user_resp.data.username if user_resp and user_resp.data else str(tweet.author_id)
        await client.create_tweet(
            text=f"@{author_username} {reply_text}",
            in_reply_to_tweet_id=tweet.id
        )
        return
        
    headers = {
        "Authorization": f"Bearer {BLITZAGENT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"Calling BlitzAgent API with payload: {payload}")
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.post(
            f"{BLITZAGENT_API_URL}/analyze",
            json=payload,
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                reply_text = data.get("response", "Sorry, I couldn't generate a response.")
                
                # Ensure response isn't too long - truncate if needed
                if len(reply_text) > 220:  # Leave room for @username
                    reply_text = reply_text[:217] + "..."
                    
            else:
                error_text = await resp.text()
                print(f"API Error {resp.status}: {error_text}")
                reply_text = "Sorry, there was an error processing your request."
    try:
        user_resp = await client.get_user(id=tweet.author_id)
        author_username = user_resp.data.username if user_resp and user_resp.data else tweet.author_id

        print(f"Reply text length: {len(reply_text)}")
        
        # Since BlitzAgent is instructed to keep responses under 250 chars, 
        # we should rarely need to split. Just post the single reply.
        await client.create_tweet(
            text=f"@{author_username} {reply_text}",
            in_reply_to_tweet_id=tweet.id
        )
            
    except Exception as e:
        print(f"Error replying: {e}")
        traceback.print_exc()
async def main():
    global bot_user_id
    me = await client.get_me()
    bot_user_id = me.data.id
    print(f"Bot user id: {bot_user_id}")
    
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

            mentions = await client.search_recent_tweets(**search_kwargs)

            tweets = mentions.data if mentions and mentions.data else []

            # Deduplicate and sort
            seen_ids = set()
            tweets = sorted(tweets, key=lambda x: int(x.id))
            for tweet in tweets:
                if tweet.id in seen_ids:
                    continue
                seen_ids.add(tweet.id)

                await process_mention(tweet)
                last_mention_id = tweet.id

            print("Sleeping for 60 seconds")
        except Exception as e:
            print(f"Error fetching or processing mentions: {e}")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())