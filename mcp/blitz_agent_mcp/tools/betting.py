"""Betting data tools for SportsData.io MLB odds API."""

import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime

import httpx
from mcp.server.fastmcp import Context
from pydantic import Field

from ..utils import serialize_response

__all__ = ["get_betting_events_by_date", "get_betting_markets_for_event"]

logger = logging.getLogger("blitz-agent-mcp")

# SportsData.io configuration
SPORTSDATA_BASE_URL = "https://api.sportsdata.io/v3/mlb/odds"
DEFAULT_API_KEY = "47ea9395aa1c4bf9906df741e846e979"  # You may want to move this to config


async def get_betting_events_by_date(
    ctx: Context,
    date: str = Field(..., description="Date in YYYY-MM-DD format (e.g., '2025-06-30')"),
    api_key: Optional[str] = Field(None, description="SportsData.io API key (optional, will use default if not provided)")
) -> Dict[str, Any]:
    """
    Fetch all betting events for a specific date from SportsData.io MLB odds API.
    
    This tool retrieves all MLB games scheduled for a given date along with their betting information.
    Each event includes team matchups, game details, and available betting markets.
    
    Usage Instructions:
    1. Provide a date in YYYY-MM-DD format
    2. Optionally provide your own SportsData.io API key
    3. Returns array of betting events with game and market information
    """
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format. Expected YYYY-MM-DD, got: {date}")
    
    # Use provided API key or default
    # Handle case where api_key might be a Field object or None
    if api_key is None or str(api_key).startswith('annotation='):
        key = DEFAULT_API_KEY
    else:
        key = api_key
    
    # Construct URL
    url = f"{SPORTSDATA_BASE_URL}/json/BettingEventsByDate/{date}"
    params = {"key": key}
    
    logger.info(f"Fetching betting events for date: {date}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Strip out the massive BettingMarkets arrays to reduce response size
            # Only keep essential event information for the first call
            simplified_events = []
            if isinstance(data, list):
                for event in data:
                    simplified_event = {
                        "BettingEventID": event.get("BettingEventID"),
                        "Name": event.get("Name"),
                        "GameID": event.get("GameID"),
                        "StartDate": event.get("StartDate"),
                        "GameStartTime": event.get("GameStartTime"),
                        "AwayTeam": event.get("AwayTeam"),
                        "HomeTeam": event.get("HomeTeam"),
                        "AwayTeamID": event.get("AwayTeamID"),
                        "HomeTeamID": event.get("HomeTeamID"),
                        "GameStatus": event.get("GameStatus"),
                        "AwayTeamScore": event.get("AwayTeamScore"),
                        "HomeTeamScore": event.get("HomeTeamScore"),
                        # Include count of available betting markets but not the full data
                        "BettingMarketsCount": len(event.get("BettingMarkets", []))
                    }
                    simplified_events.append(simplified_event)
            
            # Add metadata to response
            result = {
                "date": date,
                "events_count": len(simplified_events),
                "events": simplified_events,
                "api_endpoint": f"{url}?key={key}",
                "note": "Use get_betting_markets_for_event() with BettingEventID to get detailed odds and markets for specific games"
            }
            
            logger.info(f"Successfully fetched {result['events_count']} betting events for {date}")
            return serialize_response(result)
            
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code} when fetching betting events for {date}: {e.response.text}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    except httpx.RequestError as e:
        error_msg = f"Request error when fetching betting events for {date}: {str(e)}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error when fetching betting events for {date}: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def get_betting_markets_for_event(
    ctx: Context,
    event_id: int = Field(..., description="Betting event ID (e.g., 14219)"),
    market_type_filter: Optional[str] = Field(None, description="Filter by betting market type (e.g., 'Player Prop', 'Game Line', 'Team Prop'). Leave empty for all markets."),
    bet_type_filter: Optional[str] = Field(None, description="Filter by bet type (e.g., 'Hits', 'Home Runs', 'RBIs', 'Runs Scored'). Leave empty for all bet types."),
    player_name_filter: Optional[str] = Field(None, description="Filter by player name (e.g., 'Aaron Judge'). Leave empty for all players."),
    betting_period_type_id: int = Field(1, description="Filter by betting period (1=Full Game, 9=1st Inning, 11=3rd Inning, etc.). Default is 1 for full game."),
    api_key: Optional[str] = Field(None, description="SportsData.io API key (optional, will use default if not provided)")
) -> Dict[str, Any]:
    """
    Fetch betting markets and odds for a specific betting event from SportsData.io MLB odds API.
    
    This tool retrieves detailed betting information for a specific game with optional filtering
    to reduce response size and focus on specific bet types. Always includes only available betting markets.
    
    Usage Instructions:
    1. Provide a betting event ID (can be obtained from get_betting_events_by_date)
    2. Use filters to narrow down results:
       - market_type_filter: "Player Prop" for player stats, "Game Line" for moneylines/spreads
       - bet_type_filter: "Hits", "Home Runs", "RBIs" for specific player props
       - player_name_filter: Specific player name for player props
       - betting_period_type_id: 1=Full Game (default), 9=1st Inning, 11=3rd Inning, etc.
    3. For "singles props" or player hitting props, use market_type_filter="Player Prop"
    
    Examples:
    - Player hitting props: market_type_filter="Player Prop", bet_type_filter="Hits"
    - Specific player props: market_type_filter="Player Prop", player_name_filter="Aaron Judge"
    - Game lines only: market_type_filter="Game Line"
    - First inning bets: betting_period_type_id=9
    """
    
    # Handle case where parameters might be Field objects (when called directly from Python)
    # Extract actual values from Field objects if needed
    
    # Handle betting_period_type_id
    if hasattr(betting_period_type_id, 'default'):
        betting_period_type_id = betting_period_type_id.default
    
    # Handle market_type_filter
    if hasattr(market_type_filter, 'default'):
        market_type_filter = market_type_filter.default
    
    # Handle bet_type_filter  
    if hasattr(bet_type_filter, 'default'):
        bet_type_filter = bet_type_filter.default
    
    # Handle player_name_filter
    if hasattr(player_name_filter, 'default'):
        player_name_filter = player_name_filter.default
    
    # Use provided API key or default
    # Handle case where api_key might be a Field object or None
    if api_key is None or str(api_key).startswith('annotation=') or hasattr(api_key, 'default'):
        key = DEFAULT_API_KEY
    else:
        key = api_key
    
    # Construct URL
    url = f"{SPORTSDATA_BASE_URL}/json/BettingMarkets/{event_id}"
    params = {
        "key": key,
        "include": "available"  # Always include available markets
    }
    
    logger.info(f"Fetching betting markets for event ID: {event_id}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Apply filters to reduce response size and focus on relevant markets
            filtered_markets = []
            if isinstance(data, list):
                for market in data:
                    # Filter by betting period type ID
                    if market.get("BettingPeriodTypeID") != betting_period_type_id:
                        continue
                    
                    # Filter by market type if specified
                    if market_type_filter and market.get("BettingMarketType") != market_type_filter:
                        continue
                    
                    # Filter by bet type if specified
                    if bet_type_filter and market.get("BettingBetType") != bet_type_filter:
                        continue
                    
                    # Filter by player name if specified
                    if player_name_filter and market.get("PlayerName"):
                        if player_name_filter.lower() not in market.get("PlayerName", "").lower():
                            continue
                    
                    filtered_markets.append(market)
            
            # Add metadata to response
            filters_applied = {
                "betting_period_type_id": betting_period_type_id,
                "market_type_filter": market_type_filter,
                "bet_type_filter": bet_type_filter,
                "player_name_filter": player_name_filter
            }
            
            result = {
                "event_id": event_id,
                "include_available_only": True,
                "total_markets_from_api": len(data) if isinstance(data, list) else 0,
                "filtered_markets_count": len(filtered_markets),
                "filters_applied": filters_applied,
                "markets": filtered_markets,
                "api_endpoint": f"{url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            }
            
            logger.info(f"Successfully fetched and filtered {result['filtered_markets_count']} betting markets (from {result['total_markets_from_api']} total) for event {event_id}")
            return serialize_response(result)
            
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code} when fetching betting markets for event {event_id}: {e.response.text}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    except httpx.RequestError as e:
        error_msg = f"Request error when fetching betting markets for event {event_id}: {str(e)}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error when fetching betting markets for event {event_id}: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) 