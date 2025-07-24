"""Twitter MCP Server main module."""

import asyncio
import os
import json
import logging
from typing import Any, Dict, List, Optional
import tweepy
from tweepy.asynchronous import AsyncClient
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
import mcp.types as types
from pydantic import AnyUrl
from dotenv import load_dotenv
import httpx
from datetime import datetime, timedelta

load_dotenv()

# Shared developer app credentials
SHARED_CONSUMER_KEY = os.getenv("SHARED_CONSUMER_KEY")
SHARED_CONSUMER_SECRET = os.getenv("SHARED_CONSUMER_SECRET")

# Twitter API credentials - BlitzAIBot account
BLITZ_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
BLITZ_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
BLITZ_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_SECRET")

# Twitter API credentials - tejsri01 account  
USER_BEARER_TOKEN = os.getenv("TEJSRI_X_BEARER_TOKEN")
USER_ACCESS_TOKEN = os.getenv("TEJSRI_X_ACCESS_TOKEN")
USER_ACCESS_TOKEN_SECRET = os.getenv("TEJSRI_X_ACCESS_SECRET")

# Initialize Twitter clients
blitz_client = AsyncClient(
    bearer_token=BLITZ_BEARER_TOKEN,
    consumer_key=SHARED_CONSUMER_KEY,
    consumer_secret=SHARED_CONSUMER_SECRET,
    access_token=BLITZ_ACCESS_TOKEN,
    access_token_secret=BLITZ_ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True
) if all([BLITZ_BEARER_TOKEN, SHARED_CONSUMER_KEY, SHARED_CONSUMER_SECRET, BLITZ_ACCESS_TOKEN, BLITZ_ACCESS_TOKEN_SECRET]) else None

user_client = AsyncClient(
    bearer_token=USER_BEARER_TOKEN,
    consumer_key=SHARED_CONSUMER_KEY,
    consumer_secret=SHARED_CONSUMER_SECRET,
    access_token=USER_ACCESS_TOKEN,
    access_token_secret=USER_ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True
) if all([USER_BEARER_TOKEN, SHARED_CONSUMER_KEY, SHARED_CONSUMER_SECRET, USER_ACCESS_TOKEN, USER_ACCESS_TOKEN_SECRET]) else None

# Create the server instance
server = Server("twitter-mcp")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available Twitter tools."""
    return [
        Tool(
            name="search_tweets",
            description="Search for tweets based on query, hashtags, or accounts",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (can include hashtags, usernames, keywords)"
                    },
                    "max_results": {
                        "type": "integer", 
                        "description": "Maximum number of tweets to return (default: 10, max: 100)",
                        "default": 10
                    },
                    "hours_back": {
                        "type": "integer",
                        "description": "How many hours back to search (default: 24)",
                        "default": 24
                    },
                    "include_media": {
                        "type": "boolean",
                        "description": "Whether to include media information",
                        "default": False
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="post_tweet",
            description="Post a tweet from the specified account",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Tweet text content (max 280 characters)"
                    },
                    "account": {
                        "type": "string",
                        "enum": ["blitz", "user"],
                        "description": "Which account to post from (blitz=BlitzAIBot, user=tejsri01)"
                    },
                    "reply_to_tweet_id": {
                        "type": "string",
                        "description": "Tweet ID to reply to (optional)"
                    },
                    "media_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of media IDs to attach (optional)"
                    }
                },
                "required": ["text", "account"]
            }
        ),
        Tool(
            name="get_tweet_details",
            description="Get detailed information about a specific tweet",
            inputSchema={
                "type": "object",
                "properties": {
                    "tweet_id": {
                        "type": "string",
                        "description": "ID of the tweet to get details for"
                    },
                    "include_conversation": {
                        "type": "boolean",
                        "description": "Whether to include conversation context",
                        "default": False
                    }
                },
                "required": ["tweet_id"]
            }
        ),
        Tool(
            name="get_user_tweets",
            description="Get recent tweets from a specific user",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username (without @) to get tweets from"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of tweets to return (default: 10)",
                        "default": 10
                    },
                    "exclude_replies": {
                        "type": "boolean",
                        "description": "Whether to exclude replies",
                        "default": True
                    }
                },
                "required": ["username"]
            }
        ),
        Tool(
            name="get_trending_hashtags",
            description="Get trending hashtags for NBA/basketball",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location for trends (default: 'worldwide')",
                        "default": "worldwide"
                    }
                }
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls for Twitter operations."""
    if arguments is None:
        arguments = {}

    try:
        if name == "search_tweets":
            return await search_tweets(arguments)
        elif name == "post_tweet":
            return await post_tweet(arguments)
        elif name == "get_tweet_details":
            return await get_tweet_details(arguments)
        elif name == "get_user_tweets":
            return await get_user_tweets(arguments)
        elif name == "get_trending_hashtags":
            return await get_trending_hashtags(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

async def search_tweets(args: dict) -> list[types.TextContent]:
    """Search for tweets based on query."""
    query = args.get("query")
    max_results = min(args.get("max_results", 10), 100)
    hours_back = args.get("hours_back", 24)
    include_media = args.get("include_media", False)

    if not query:
        return [types.TextContent(type="text", text="Error: Query is required")]

    # Use user client for searches (read-only operations)
    client = user_client or blitz_client
    if not client:
        return [types.TextContent(type="text", text="Error: No Twitter client available")]

    try:
        # Calculate start time
        start_time = datetime.now() - timedelta(hours=hours_back)
        
        # Tweet fields to include
        tweet_fields = ["created_at", "author_id", "public_metrics", "text", "context_annotations", "referenced_tweets"]
        if include_media:
            tweet_fields.extend(["attachments"])

        # Search for tweets
        tweets = await client.search_recent_tweets(
            query=query,
            max_results=max_results,
            start_time=start_time.isoformat(),
            tweet_fields=tweet_fields,
            user_fields=["username", "name", "verified"],
            expansions=["author_id", "attachments.media_keys"] if include_media else ["author_id"]
        )

        if not tweets or not tweets.data:
            return [types.TextContent(type="text", text="No tweets found")]

        # Format results
        results = []
        users_map = {user.id: user for user in tweets.includes.get('users', [])} if tweets.includes else {}
        media_map = {media.media_key: media for media in tweets.includes.get('media', [])} if tweets.includes and include_media else {}

        for tweet in tweets.data:
            author = users_map.get(tweet.author_id)
            author_info = f"@{author.username} ({author.name})" if author else f"User ID: {tweet.author_id}"
            
            tweet_info = {
                "id": tweet.id,
                "author": author_info,
                "text": tweet.text,
                "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                "metrics": tweet.public_metrics.__dict__ if hasattr(tweet, 'public_metrics') else {},
                "url": f"https://twitter.com/i/status/{tweet.id}"
            }

            # Add media info if requested
            if include_media and hasattr(tweet, 'attachments') and tweet.attachments:
                media_keys = tweet.attachments.get('media_keys', [])
                tweet_info["media"] = []
                for media_key in media_keys:
                    if media_key in media_map:
                        media = media_map[media_key]
                        tweet_info["media"].append({
                            "type": media.type,
                            "url": getattr(media, 'url', None),
                            "preview_image_url": getattr(media, 'preview_image_url', None)
                        })

            results.append(tweet_info)

        return [types.TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error searching tweets: {str(e)}")]

async def post_tweet(args: dict) -> list[types.TextContent]:
    """Post a tweet from the specified account."""
    text = args.get("text")
    account = args.get("account")
    reply_to_tweet_id = args.get("reply_to_tweet_id")
    media_ids = args.get("media_ids", [])

    if not text or not account:
        return [types.TextContent(type="text", text="Error: Text and account are required")]

    if len(text) > 280:
        return [types.TextContent(type="text", text="Error: Tweet text exceeds 280 characters")]

    # Select the appropriate client
    client = blitz_client if account == "blitz" else user_client
    if not client:
        return [types.TextContent(type="text", text=f"Error: No client available for account: {account}")]

    try:
        # Prepare tweet parameters
        tweet_params = {"text": text}
        if reply_to_tweet_id:
            tweet_params["in_reply_to_tweet_id"] = reply_to_tweet_id
        if media_ids:
            tweet_params["media_ids"] = media_ids

        # Post the tweet
        response = await client.create_tweet(**tweet_params)
        
        if response and response.data:
            tweet_id = response.data["id"]
            return [types.TextContent(type="text", text=json.dumps({
                "success": True,
                "tweet_id": tweet_id,
                "url": f"https://twitter.com/i/status/{tweet_id}",
                "account": account
            }, indent=2))]
        else:
            return [types.TextContent(type="text", text="Error: Failed to post tweet")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error posting tweet: {str(e)}")]

async def get_tweet_details(args: dict) -> list[types.TextContent]:
    """Get detailed information about a specific tweet."""
    tweet_id = args.get("tweet_id")
    include_conversation = args.get("include_conversation", False)

    if not tweet_id:
        return [types.TextContent(type="text", text="Error: Tweet ID is required")]

    client = user_client or blitz_client
    if not client:
        return [types.TextContent(type="text", text="Error: No Twitter client available")]

    try:
        # Get tweet details
        tweet = await client.get_tweet(
            tweet_id,
            tweet_fields=["created_at", "author_id", "public_metrics", "text", "context_annotations", "referenced_tweets", "attachments"],
            user_fields=["username", "name", "verified"],
            expansions=["author_id", "attachments.media_keys", "referenced_tweets.id"]
        )

        if not tweet or not tweet.data:
            return [types.TextContent(type="text", text="Tweet not found")]

        # Format tweet details
        tweet_data = tweet.data
        users_map = {user.id: user for user in tweet.includes.get('users', [])} if tweet.includes else {}
        author = users_map.get(tweet_data.author_id)

        result = {
            "id": tweet_data.id,
            "text": tweet_data.text,
            "author": {
                "id": tweet_data.author_id,
                "username": author.username if author else None,
                "name": author.name if author else None,
                "verified": author.verified if author else None
            },
            "created_at": tweet_data.created_at.isoformat() if tweet_data.created_at else None,
            "metrics": tweet_data.public_metrics.__dict__ if hasattr(tweet_data, 'public_metrics') else {},
            "url": f"https://twitter.com/i/status/{tweet_data.id}"
        }

        # Add conversation context if requested
        if include_conversation and hasattr(tweet_data, 'referenced_tweets'):
            result["conversation"] = []
            for ref_tweet in tweet_data.referenced_tweets:
                if ref_tweet.type == "replied_to":
                    parent_tweet = await client.get_tweet(ref_tweet.id, tweet_fields=["text", "author_id"], expansions=["author_id"])
                    if parent_tweet and parent_tweet.data:
                        parent_author = users_map.get(parent_tweet.data.author_id)
                        result["conversation"].append({
                            "id": parent_tweet.data.id,
                            "text": parent_tweet.data.text,
                            "author_username": parent_author.username if parent_author else None
                        })

        return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error getting tweet details: {str(e)}")]

async def get_user_tweets(args: dict) -> list[types.TextContent]:
    """Get recent tweets from a specific user."""
    username = args.get("username")
    max_results = min(args.get("max_results", 10), 100)
    exclude_replies = args.get("exclude_replies", True)

    if not username:
        return [types.TextContent(type="text", text="Error: Username is required")]

    client = user_client or blitz_client
    if not client:
        return [types.TextContent(type="text", text="Error: No Twitter client available")]

    try:
        # Get user by username
        user = await client.get_user(username=username)
        if not user or not user.data:
            return [types.TextContent(type="text", text="User not found")]

        user_id = user.data.id

        # Get user's tweets
        tweets = await client.get_users_tweets(
            user_id,
            max_results=max_results,
            exclude_replies=exclude_replies,
            tweet_fields=["created_at", "public_metrics", "text"]
        )

        if not tweets or not tweets.data:
            return [types.TextContent(type="text", text="No tweets found")]

        # Format results
        results = []
        for tweet in tweets.data:
            tweet_info = {
                "id": tweet.id,
                "text": tweet.text,
                "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                "metrics": tweet.public_metrics.__dict__ if hasattr(tweet, 'public_metrics') else {},
                "url": f"https://twitter.com/i/status/{tweet.id}"
            }
            results.append(tweet_info)

        return [types.TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error getting user tweets: {str(e)}")]

async def get_trending_hashtags(args: dict) -> list[types.TextContent]:
    """Get trending hashtags (simplified implementation)."""
    # This is a simplified implementation
    # In practice, you might want to search for popular NBA-related hashtags
    nba_hashtags = [
        "#NBA", "#basketball", "#NBATwitter", "#Hoops", "#NBAPlayoffs",
        "#March Madness", "#NBADraft", "#NBATrade", "#NBAStats", "#Ballislife"
    ]
    
    return [types.TextContent(type="text", text=json.dumps({
        "trending_nba_hashtags": nba_hashtags,
        "note": "These are popular NBA-related hashtags. For real-time trends, use the search_tweets tool with these hashtags."
    }, indent=2))]

async def main():
    """Main function to run the MCP server."""
    # Import here to avoid issues with async
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="twitter-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main()) 