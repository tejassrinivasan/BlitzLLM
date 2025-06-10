import asyncio
import os
import json
import logging
import time
import httpx
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery, QueryType, QueryCaptionType, QueryAnswerType
from utils import serialize_response, get_azure_credential, get_token_provider, get_embedding, DecimalEncoder
from config import SEARCH_ENDPOINT, SEARCH_INDEX_NAME, OPENAI_ENDPOINT, OPENAI_API_VERSION
from prompts import (
    get_prompts,
)
from typing import Optional, List, Dict, Union
from database_pool import get_partner_pool, get_baseball_pool
from datetime import timedelta
from constants import ENDPOINT_LABELS, UPCOMING_ENDPOINTS, TABLE_DESCRIPTIONS
SERPAPI_KEY = "d0014298277f40474659cc6edb35fa2f0f33affc73a2190c1c116b254e03681e"

SPORTSDATA_API_KEY = os.getenv("SPORTSDATA_API_KEY")
BAKER_API_KEY = os.getenv("BAKER_API_KEY")


def get_openai_client() -> AsyncAzureOpenAI:
    """Return a configured AsyncAzureOpenAI client."""
    return AsyncAzureOpenAI(
        azure_endpoint=OPENAI_ENDPOINT,
        api_version=OPENAI_API_VERSION,
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

async def check_query_count(current_user: dict):
    try:
        partner_pool = get_partner_pool()
        async with partner_pool.acquire() as conn:
            user_info = await conn.fetchrow(
                "SELECT query_credits_remaining FROM metadata WHERE id = $1",
                current_user["id"],
            )
            if not user_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            if user_info["query_credits_remaining"] <= 0:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="You have reached your daily query limit. Please contact admin@blitzanalytics.co to upgrade your quota."
                )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error checking query count: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking query count"
        )

async def get_conversation_history(conversation_id: str, current_message_id=None):
    """Retrieve conversation history from messages table."""
    try:
        partner_pool = get_partner_pool()
        async with partner_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT message_id, role, content
                FROM messages
                WHERE conversation_id = $1
                ORDER BY message_id ASC, created_at ASC
                """,
                conversation_id,
            )
            formatted_history = []
            for row in rows:
                msg = {
                    "id": row["message_id"],
                    "role": row["role"],
                    "content": row["content"] or "",
                }
                formatted_history.append(msg)
            user_message_count = sum(1 for r in rows if r["role"] == "user")
            return formatted_history, user_message_count
    except Exception as e:
        logging.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting conversation history: {str(e)}")

def format_conversation_history_for_prompt(history: list) -> str:
    """Format history into a compact string for LLM prompts."""
    if not history:
        return ""

    last_assistant_index = None
    for idx in range(len(history) - 1, -1, -1):
        if history[idx].get("role") == "assistant" and history[idx].get("content"):
            last_assistant_index = idx
            break

    if last_assistant_index is None:
        return ""

    relevant_history = history[: last_assistant_index + 1]

    pairs = []
    i = 0
    while i < len(relevant_history) - 1 and len(pairs) < 10:
        user_msg = relevant_history[i]
        assistant_msg = relevant_history[i + 1]
        if user_msg.get("role") == "user" and assistant_msg.get("role") == "assistant":
            pairs.append((user_msg, assistant_msg))
            i += 2
        else:
            i += 1

    lines = []
    for user_msg, assistant_msg in reversed(pairs):
        if assistant_msg.get("is_error") or assistant_msg.get("sqlQuery"):
            lines.append("You: [Too long to attach full response]")
        else:
            lines.append(f"You: {assistant_msg.get('content')}")
        lines.append(f"User: {user_msg.get('content')}")

    if len(relevant_history) > len(pairs) * 2:
        lines.append("Older messages may include clarifying questions.")

    return "\n".join(lines)


async def prepare_history_for_sql(
    conversation_id: str,
    current_message_id: int | None,
    include_history: bool,
    history: list | None = None,
):
    """Return history context and previous results for SQL generation."""
    if not include_history:
        return [], "", 0, []

    if history is None:
        history, user_message_count = await get_conversation_history(conversation_id, current_message_id)
    else:
        user_message_count = sum(1 for msg in history if msg.get("role") == "user")
    if history is None:
        history = []

    history_to_use = history
    if current_message_id is not None:
        current_idx = next((i for i, msg in enumerate(history) if msg.get("id") == current_message_id), -1)
        if current_idx >= 0:
            history_to_use = history[:current_idx]

    history_to_use = history_to_use[::-1]
    history_context = "CONVERSATION HISTORY (OLDEST TO NEWEST):\n"
    previous_results = []
    for i in range(len(history_to_use) - 1, 0, -2):
        assistant_msg = history_to_use[i - 1]
        user_msg = history_to_use[i]
        msg_num = (len(history_to_use) - i) // 2 + 1
        history_context += f"{msg_num}. User Question/Message: {user_msg['content']}\n"
        history_context += f"{msg_num}. Your Response: {assistant_msg['content']}\n"
        history_context += f"{msg_num}. Your SQL Query: {assistant_msg.get('sqlQuery', '')[:2000]}\n"
        history_context += f"{msg_num}. Your Query Results: {assistant_msg.get('results', '')[:2000]}\n"
        previous_results.append({
            "sqlQuery": assistant_msg.get("sqlQuery", ""),
            "results": assistant_msg.get("results", ""),
        })
        history_context += "---\n"

    return history, history_context, user_message_count, previous_results

async def check_clarification(
    partner_prompt: str,
    conversation_history: List[Dict] | None = None,
    custom_data: dict | None = None,
    league: str = "mlb",
    history_context: str | None = None,
    prompt_type: str = "INSIGHT"
):
    """Determine if clarification is needed or provide a direct answer."""
    try:
        openai_client = get_openai_client()

        # Use precomputed history context if provided
        if history_context is None:
            history_context = ""

        custom_section = f"Partner custom data: {json.dumps(custom_data)}" if custom_data else ""
        prompts = get_prompts(league, prompt_type)
        prompt = prompts["CLARIFICATION_USER_PROMPT"].format(
            history_context=history_context if history_context else 'No history provided.',
            partner_prompt=partner_prompt,
            custom_section=custom_section
        )
        system_prompt = prompts["CLARIFICATION_SYSTEM_PROMPT"].format(today_date=datetime.now().strftime('%m/%d/%Y'))
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=200,
        )

        content = response.choices[0].message.content.strip()
        if content.upper().startswith("CLARIFY:"):
            question = content[8:].strip()
            return {
                "type": "clarify",
                "response": {
                    "response": question,
                    "explanation": None,
                    "links": None,
                },
            }
        if content.upper().startswith("ANSWER:"):
            answer = content[7:].strip()
            return {
                "type": "answer",
                "response": {
                    "response": answer,
                    "explanation": None,
                    "links": None,
                },
            }
        return {"type": "proceed"}
    except Exception as e:
        print(f"Error determining clarification: {e}")
        return {"type": "proceed"}

async def determine_live_endpoints(
    client,
    partner_prompt: str,
    conversation_history: list | None = None,
    league: str = "mlb",
    history_context: str | None = None,
    prompt_type: str = "INSIGHT",
    custom_data: dict | None = None,
):
    """Determine if the question needs upcoming API data and what calls to make."""
    try:
        endpoints_info = "\n".join(UPCOMING_ENDPOINTS.get(league, []))

        if history_context is None:
            history_context = ""

        prompts = get_prompts(league, prompt_type)
        custom_section = f"Partner custom data: {json.dumps(custom_data)}" if custom_data else ""
        user_prompt_context = prompts["LIVE_ENDPOINTS_USER_PROMPT"].format(
            history_context=history_context if history_context else 'No history provided.',
            partner_prompt=partner_prompt,
            custom_section=custom_section
        )
        system_prompt = prompts["LIVE_ENDPOINTS_SYSTEM_PROMPT"].format(
            today_date=datetime.now().strftime('%Y-%m-%d'),
            endpoints_info=endpoints_info
        )

        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt_context}],
            temperature=0,
        )

        print(resp.choices[0].message.content.strip())

        try:
            parsed_response = json.loads(resp.choices[0].message.content.strip())
            if 'needs_live_data' not in parsed_response:
                return {"needs_live_data": False, "calls": [], "keys": [], "constraints": {}}
            if parsed_response.get("needs_live_data"):
                if "calls" not in parsed_response:
                    parsed_response["calls"] = []
                if "keys" not in parsed_response:
                    parsed_response["keys"] = []
                if "constraints" not in parsed_response:
                    parsed_response["constraints"] = {}
            else:
                parsed_response["calls"] = []
                parsed_response["keys"] = []
                parsed_response["constraints"] = {}
            return parsed_response
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from determine_live_endpoints: {e}")
            return {"needs_live_data": False, "calls": [], "keys": [], "constraints": {}}
    except Exception as e:
        print(f"Error in determine_live_endpoints: {e}")
        return {"needs_live_data": False, "calls": [], "keys": [], "constraints": {}}

async def _lookup_game_id(client: httpx.AsyncClient, date: str, team: str = None, player: str = None):
    """Fetch the game ID for a team or player on a given date."""
    try:
        if player and not team:
            player_id = await _lookup_player_id(client, player)
            if player_id:
                url = "https://api.sportsdata.io/v3/mlb/scores/json/PlayersByActive"
                r = await client.get(url, params={"key": SPORTSDATA_API_KEY})
                r.raise_for_status()
                players = r.json()
                for p in players:
                    if p.get("PlayerID") == player_id:
                        team = p.get("Team")
                        break

        if not team:
            return None

        url = f"https://api.sportsdata.io/v3/mlb/scores/json/ScoresBasicFinal/{date}"
        r = await client.get(url, params={"key": SPORTSDATA_API_KEY})
        r.raise_for_status()
        games = r.json()
        for g in games:
            if team in [g.get("HomeTeam"), g.get("AwayTeam")]:
                return g.get("GameID")
    except Exception as e:
        print(f"Error looking up game id: {e}")
    return None

async def _lookup_player_id(client: httpx.AsyncClient, player: str):
    """Fetch the player ID for a given player name."""
    try:
        url = "https://api.sportsdata.io/v3/mlb/scores/json/PlayersByActive"
        r = await client.get(url, params={"key": SPORTSDATA_API_KEY})
        r.raise_for_status()
        players = r.json()
        player = player.lower()
        for p in players:
            name = f"{p.get('FirstName', '')} {p.get('LastName', '')}".strip().lower()
            if name == player:
                return p.get("PlayerID")
    except Exception as e:
        print(f"Error looking up player id: {e}")
    return None

async def search_the_web(query: str):
    """Search the web via SerpAPI and return results."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={"engine": "google", "q": query, "api_key": SERPAPI_KEY},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"Error searching web: {e}")
        return None

async def fetch_upcoming_data(calls: List[dict], keys: List[str], constraints: dict = None):
    """Fetch and filter data from various SportsDataIO/Baker endpoints."""
    results = {}

    def is_trends_endpoint(url: str) -> bool:
        return "/trends/" in url

    def set_date_param(params: dict, date_str: str) -> dict:
        return {k: (date_str if k.lower() == "date" else v) for k, v in params.items()}

    def should_label_baker(url: str) -> bool:
        return "baker-api" in url or "Baker" in url

    def get_label(url: str) -> str:
        if any(endpoint in url for endpoint in ["PlayersByActive", "PlayersByFreeAgents", "teams", "ScoresBasicFinal", "BettingMarketsByGameID"]):
            return "Blitz Live"
        return "Blitz AI" if should_label_baker(url) else "Blitz"

    async with httpx.AsyncClient() as client:
        for call in calls:
            url = call.get("endpoint") or call.get("url")
            params = call.get("params", {})
            data = None

            if is_trends_endpoint(url):
                dates_to_try = [
                    datetime.now().strftime("%Y-%m-%d"),
                    (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                    (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
                ]
                
                for date_str in dates_to_try:
                    dated_params = set_date_param(params, date_str) if "date" in params else params
                    if "/players/" in url:
                        player_id = dated_params.get("playerid") or await _lookup_player_id(client, dated_params.get("player"))
                        if not player_id:
                            print(f"Unable to determine player ID for {dated_params.get('player')}")
                            break
                        formatted_url = url.format(playerid=player_id, **{k: v for k, v in dated_params.items() if k not in ["playerid", "player"]})
                    else:
                        formatted_url = url.format(**dated_params)

                    try:
                        r = await client.get(formatted_url, params={"key": BAKER_API_KEY if should_label_baker(url) else SPORTSDATA_API_KEY})
                        r.raise_for_status()
                        data = r.json()
                        if data not in ([], {}):
                            url = formatted_url
                            break
                    except Exception as e:
                        print(f"Error fetching {formatted_url}: {e}")

            elif "BettingMarketsByGameID" in url:
                game_id = params.get("gameID")
                player_name = params.get("player")
                if not game_id and (date := params.get("date")):
                    game_id = await _lookup_game_id(client, date, params.get("team"), player_name)
                if not game_id:
                    print(f"Unable to determine game ID for {params.get('team') or player_name} on {date}")
                    results[url] = None
                    continue

                if player_name:
                    constraints = constraints or {}
                    constraints.setdefault("filters", []).append({"PlayerName": player_name})

                merged_markets = {}
                for group_num in range(1000, 1010):
                    group_url = f"https://api.sportsdata.io/v3/mlb/odds/json/BettingMarketsByGameID/{game_id}/G{group_num}?key={SPORTSDATA_API_KEY}"
                    try:
                        r = await client.get(group_url)
                        r.raise_for_status()
                        for market in r.json():
                            key = market["BettingMarketID"]
                            existing = merged_markets.setdefault(key, market)
                            existing.setdefault("AvailableSportsbooks", []).extend([
                                sb for sb in market.get("AvailableSportsbooks", [])
                                if sb.get("SportsbookID") not in {s.get("SportsbookID") for s in existing["AvailableSportsbooks"]}
                            ])
                            existing.setdefault("BettingOutcomes", []).extend([
                                bo for bo in market.get("BettingOutcomes", [])
                                if bo.get("BettingOutcomeID") not in {b.get("BettingOutcomeID") for b in existing["BettingOutcomes"]}
                            ])
                    except Exception as e:
                        print(f"Error fetching {group_url}: {e}")
                data = [m for m in merged_markets.values() if m.get("BettingOutcomes")]

                if constraints:
                    filters = constraints.get("filters", [])
                    outcome_filters = [f for f in filters if any(k in f for k in ["BettingOutcomeTypeID", "BettingOutcomeType"])]
                    market_filters = [f for f in filters if not any(k in f for k in ["BettingOutcomeTypeID", "BettingOutcomeType"])]

                    def matches(obj, filters):
                        return all(obj.get(k) == v for f in filters for k, v in f.items())

                    data = [m for m in data if matches(m, market_filters)]
                    for m in data:
                        m["BettingOutcomes"] = [o for o in m.get("BettingOutcomes", []) if matches(o, outcome_filters)]
                    data = [m for m in data if m["BettingOutcomes"]]

                    print(f"[DEBUG] Filtered BettingMarketsByGameID data: {json.dumps(data, indent=2)}")

            else:
                try:
                    formatted_url = url.format(**params)
                    r = await client.get(formatted_url, params={"key": SPORTSDATA_API_KEY})
                    r.raise_for_status()
                    data = r.json()
                except KeyError as e:
                    print(f"Missing param {e} for {url}")
                except Exception as e:
                    print(f"Error fetching {url}: {e}")

            if url.startswith("https://baker-api.sportsdata.io/baker/v2/mlb/projections/players/full-season/") and isinstance(data, list):
                data = [
                    {
                        'PlayerID' if k == 'player_id' else ''.join(word.capitalize() for word in k.split('_')): v
                        for k, v in entry.items()
                    }
                    for entry in data
                ]

            if isinstance(data, list) and constraints:
                filters = constraints.get("filters", [])
                if filters:
                    data = [item for item in data if any(all(item.get(k) == v for k, v in f.items()) for f in filters)]
                if sort_key := constraints.get("sort_by"):
                    reverse = constraints.get("sort_order", "desc") == "desc"
                    data.sort(key=lambda x: (x.get(sort_key) is not None, x.get(sort_key)), reverse=reverse)
                if top_n := constraints.get("top_n"):
                    data = data[:top_n]

            if keys and isinstance(data, list) and not is_trends_endpoint(url) and "BettingMarketsByGameID" not in url:
                data = [{k: d[k] for k in keys if k in d} if isinstance(d, dict) else d for d in data]

            results[get_label(url)] = data
            print(f"[DEBUG] Results: {json.dumps(results, indent=2)}")

    return results

async def determine_sql_query(
    partner_prompt,
    search_results,
    conversation_id,
    current_message_id=None,
    include_history: bool = True,
    league: str = "mlb",
    history_context: str | None = None,
    previous_results: list | None = None,
    prompt_type: str = "INSIGHT"
):
    """Determines if a SQL query against the historical database is needed and generates it if so."""
    try:
        # Input validation
        if not partner_prompt or not partner_prompt.strip():
            return {
                "type": "error",
                "message": "Please provide a valid question"
            }

        history_context = history_context or ""
        previous_results = previous_results or []

        if include_history:
            print(history_context)

        # Initialize OpenAI client
        openai_client = get_openai_client()

        # Use initial prompt flow
        top_results = []
        for result in search_results[:3]:
            top_results.append({
                "UserPrompt": result.get("UserPrompt", ""),
                "Query": result.get("Query", "")
            })
        
        # Compose similar queries string
        similar_queries = ""
        if top_results:
            for i, result in enumerate(top_results):
                similar_queries += f"\n\n**Example {i+1}:**\n*User Question:* {result['UserPrompt']}\n*SQL Query:* `{result['Query']}`\n---"
        else:
            similar_queries = "\n\nNo similar historical queries provided for this context."

        # Compose table descriptions (from the original code)
        table_descriptions = TABLE_DESCRIPTIONS.get(league, "")
        
        prompts_set = get_prompts(league, prompt_type)
        system_prompt = prompts_set["SQL_QUERY_SYSTEM_PROMPT"].format(
            history_context=history_context if history_context else "This is the beginning of the conversation.",
            similar_queries=similar_queries,
            today_date=datetime.now().strftime("%Y-%m-%d"),
            table_descriptions=table_descriptions
        )

        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Partner's message: " + partner_prompt}
            ],
            temperature=0
        )

        response_text = response.choices[0].message.content.strip()
        print(response_text)
        
        # Check if we should use previous results or if no SQL is needed
        if response_text.startswith("USE_PREVIOUS_RESULTS"):
            try:
                # Extract just the number after "USE_PREVIOUS_RESULTS"
                results_index = int(response_text.replace("USE_PREVIOUS_RESULTS", ""))
                if results_index < len(previous_results):
                    return {
                        "type": "previous_results", # Changed type
                        "query": previous_results[results_index]["sqlQuery"],
                        "reuse_results": True,
                        "results": previous_results[results_index]["results"]
                    }
            except (ValueError, IndexError) as e:
                print(f"Error parsing USE_PREVIOUS_RESULTS: {e}")
                # Fall through to treat response_text as a query if parsing fails
        elif response_text == "NO_SQL_NEEDED":
            return {
                "type": "no_sql_needed",
                "query": None,
                "reuse_results": False
            }
        
        return {
            "type": "sql_query",
            "query": response_text,
            "reuse_results": False
        }
        
    except Exception as e:
        print(f"Error generating SQL query: {e}")
        print(f"Exception details: {type(e).__name__}")
        return {
            "type": "error",
            "message": "An error occurred while generating the SQL query"
        }

async def execute_sql_query(sql_query: dict, previous_results: list = None):
    """Execute the SQL query and return results."""
    try:
        if previous_results:
            return {
                "query": sql_query,
                "results": previous_results,
                "type": "previous_results"
            }
        else:
            # Execute the SQL query using PostgreSQL pool
            print("[DEBUG] About to get baseball pool...")
            baseball_pool = get_baseball_pool()
            print(f"[DEBUG] baseball_pool: {baseball_pool}")
            if baseball_pool is None:
                print("[ERROR] get_baseball_pool() returned None. Pool was not initialized.")
            print("Executing SQL query in PostgreSQL...")
            async with baseball_pool.acquire() as conn:
                # Extract any parameters from the query if needed
                print(f"[DEBUG] Executing SQL: {sql_query}")
                query_results = await conn.fetch(sql_query)
                # Convert records to dicts
                query_results = [dict(row) for row in query_results] if query_results else []
                print(f"[DEBUG] Query results: {query_results}")
                # Return results even if empty
                return {
                    "query": sql_query,
                    "results": query_results,
                    "type": "sql_query"
                }
    except Exception as e:
        logging.error(f"Error executing SQL query: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There was an error retrieving data from the database."
        )

async def perform_search(partner_prompt: str, current_user: dict, conversation_history: list | None = None):
    """Perform the initial search and ranking of results.

    If conversation history is provided, combine the last three user messages
    (including the current prompt) when generating embeddings and ranking.
    """
    try:
        # Initialize Azure OpenAI client
        openai_client = get_openai_client()

        search_text = partner_prompt
        if conversation_history:
            last_user_msgs = [m.get("content", "") for m in conversation_history if m.get("role") == "user"]
            last_user_msgs = last_user_msgs[-3:] + [partner_prompt]
            search_text = "\n".join(last_user_msgs)

        # Generate embedding for the search text
        user_prompt_vector = await get_embedding(openai_client, search_text, "text-embedding-ada-002")
        
        if not user_prompt_vector:
            print("Failed to generate embedding for the user prompt.")
            return None

        # Create a synchronous SearchClient with RBAC authentication
        search_client = SearchClient(
            endpoint=SEARCH_ENDPOINT,
            index_name=SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
        )
        
        print("Performing semantic hybrid search...")
        
        # Create a VectorizedQuery with our own embedding vector
        vector_query = VectorizedQuery(
            vector=user_prompt_vector,
            fields="UserPromptVector",
            k_nearest_neighbors=10,
            exhaustive=True
        )
        
        # Perform semantic hybrid search with our vector query
        results = search_client.search(
            search_text=search_text,
            vector_queries=[vector_query],
            select=["id", "UserPrompt", "Query", "AssistantPrompt"],
            query_type=QueryType.SEMANTIC,
            semantic_configuration_name="my-semantic-config",
            query_caption=QueryCaptionType.EXTRACTIVE,
            query_answer=QueryAnswerType.EXTRACTIVE,
            top=100
        )
        
        # Collect results for processing
        collected_results = []
        for result in results:
            collected_results.append(result)
            
        # Rank the results using GPT-4o-mini
        print("Ranking search results...")
        ranked_results = await rank_search_results(openai_client, search_text, collected_results)
        print(f"Top ranked prompts:")
        for result in ranked_results:
            print(f"- {result['UserPrompt']}")

        return ranked_results

    except HTTPException as e:
        if e.status_code == 429:
            print(f"Query credits limit exceeded: {e}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Query credits limit exceeded. Please try again tomorrow."
            )
        raise
    except Exception as e:
        print(f"Error performing search: {e}")
        print(f"Exception details: {type(e).__name__}")
        print("Make sure you have the necessary roles assigned to your identity.")
        return None

async def rank_search_results(client, query_text, search_results):
    """Rank search results using GPT-4o-mini to find the most relevant matches."""
    try:
        # Format the search results and user prompt for ranking
        prompt = f"""
        USER QUESTION:
        {query_text}

        SEARCH RESULTS:
        {json.dumps([{
            'id': result['id'],
            'prompt': result['UserPrompt']
        } for result in search_results], indent=2)}

        Return only a JSON array of document IDs in order of relevance to the user's message or the one's you think would be answered with a similar PostgreSQL query. 
        Format: "doc_id1", "doc_id2", "doc_id3", ...]
        Only include documents that are actually relevant - you don't need to return all of them.
        Don't include ```json at the beginning or end of the response or any other special characters.
        """

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are an expert on baseball and PostgreSQL. Your job is to see which questions from the search results are most similar to the user's question in terms of meaning/intent or the ones you think would be answered with a similar PostgreSQL query. **TODAY'S DATE:** {datetime.now().strftime('%Y-%m-%d')}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        # Parse the response to get ordered document IDs
        try:
            ranked_ids = json.loads(response.choices[0].message.content.strip())
            
            # Create a mapping of document ID to full document
            doc_map = {doc['id']: doc for doc in search_results}
            
            # Get the full documents in ranked order
            ranked_results = [doc_map[doc_id] for doc_id in ranked_ids if doc_id in doc_map]
            
            # Return top 3 results
            return ranked_results[:3]
            
        except json.JSONDecodeError:
            print("Failed to parse ranking response as JSON")
            return search_results[:3]  # Fall back to first 3 results
            
    except Exception as e:
        print(f"Error ranking search results: {e}")
        return search_results[:3]  # Fall back to first 3 results

async def generate_text_response(
    partner_prompt: str,
    query_data: dict | None,
    live_data: dict | None = None,
    search_results: dict | None = None,
    custom_data: dict | None = None,
    simple: bool = False,
    include_history: bool = True,
    league: str = "mlb",
    conversation_history: list | None = None,
    history_context: str | None = None,
    prompt_type: str = "INSIGHT"
):
    print("[DEBUG] generate_text_response called with:")
    print("  partner_prompt:", partner_prompt)
    print("  query_data:", query_data)
    print("  live_data:", live_data)
    print("  search_results:", search_results)
    print("  custom_data:", custom_data)
    print("  simple:", simple)
    print("  include_history:", include_history)
    print("  league:", league)
    print("  conversation_history:", conversation_history)
    print("  history_context:", history_context)
    try:
        historical_query = None
        historical_results = None
        if query_data:
            if query_data.get("type") == "sql_query" or query_data.get("type") == "previous_results":
                historical_query = query_data.get('query')
                historical_results = query_data.get('results')
            # If type is "no_sql_needed", historical_query and historical_results remain None

        # Generate a response based on the query results and message history
        text_response = await generate_response(
            partner_prompt=partner_prompt,
            sql_query=historical_query,      # Pass historical SQL query (can be None)
            query_results=historical_results,    # Pass historical results (can be None)
            live_data=live_data,             # Pass live data (can be None)
            search_results=search_results,
            custom_data=custom_data,
            simple=simple,
            include_history=include_history,
            league=league,
            conversation_history=conversation_history,
            history_context=history_context,
            prompt_type=prompt_type,
        )
        
        # Store the SQL query in a format that's easier to retrieve
        metadata = {
            'sqlQuery': historical_query  # Store just the query string (can be None)
        }
        
        return {
            "text": text_response,
            "sqlQuery": metadata,  # Return the simplified metadata
            "postgresqlResults": historical_results,  # Include the historical results (can be None)
            "upcomingResults": live_data # Include live data (can be None)
        }

    except Exception as e:
        print(f"Error generating response: {e}")
        return None

async def generate_response(
    partner_prompt,
    sql_query,
    query_results,
    live_data: dict | None = None,
    search_results: dict | None = None,
    custom_data: dict | None = None,
    simple: bool = False,
    include_history: bool = True,
    league: str = "mlb",
    conversation_history: list | None = None,
    history_context: str | None = None,
    prompt_type: str = "INSIGHT"
):
    print("[DEBUG] generate_response called with:")
    print("  partner_prompt:", partner_prompt)
    print("  sql_query:", sql_query)
    print("  query_results:", query_results)
    print("  live_data:", live_data)
    print("  search_results:", search_results)
    print("  custom_data:", custom_data)
    print("  simple:", simple)
    print("  include_history:", include_history)
    print("  league:", league)
    print("  conversation_history:", conversation_history)
    print("  history_context:", history_context)
    print("  prompt_type:", prompt_type)
    credential = None # Initialize credential to None
    client = None
    frontend_base_url = os.getenv("FRONT_END_BASE_URL", "https://www.blitzanalytics.co")  # Add default fallback if needed
    try:
        # Use Azure AD Token Authentication
        credential = get_azure_credential() # Get the Azure credential
        if not credential:
             raise ValueError("Failed to get Azure credentials.") # Raise error if credential is None

        token_provider = get_token_provider(credential) # Get the token provider function

        client = get_openai_client()

        # Serialize results to JSON string for the prompt
        results_str = json.dumps(query_results, cls=DecimalEncoder, indent=2) if query_results else ""
        live_data_str = json.dumps(live_data, cls=DecimalEncoder, indent=2) if live_data else ""
        web_data_str = json.dumps(search_results, cls=DecimalEncoder, indent=2) if search_results else ""

        # Limit results size to avoid exceeding token limits
        max_results_length = 15000 # Adjust as needed
        if len(results_str) > max_results_length:
            results_str = results_str[:max_results_length] + "\n... (results truncated)"

        if include_history:
            conversation_history = conversation_history or []
        else:
            conversation_history = []

        history_context = history_context or ""

        custom_section = ""
        if custom_data:
            custom_section = f"Partner custom data: {json.dumps(custom_data)}\n"
        prompts_set = get_prompts(league, prompt_type)
        # Select system prompt based on insight length (simple/detailed)
        if simple:
            system_message = prompts_set.get("SIMPLE_RESPONSE_SYSTEM_PROMPT")
            if not system_message:
                raise ValueError("SIMPLE_RESPONSE_SYSTEM_PROMPT not found in prompts_set")
        else:
            system_message = prompts_set["DETAILED_RESPONSE_SYSTEM_PROMPT"]
        system_message = system_message.format(custom_data_section=custom_section)
        system_message += f"\n\n**TODAY'S DATE:** {datetime.now().strftime('%Y-%m-%d')}"

        # Prepare fallback/default values for prompt variables
        sql_query_str = sql_query if sql_query else "No historical SQL query was generated or needed."
        results_str_final = results_str if results_str else "No historical query results provided or query was not run."
        live_data_str_final = live_data_str if live_data_str else "No live/upcoming data provided or needed."

        # Select user prompt template based on prompt_type
        if prompt_type == "CONVERSATION":
            user_prompt_template = prompts_set["RESPONSE_USER_PROMPT_CONVERSATION"]
            prompt = user_prompt_template.format(
                history_context=history_context or "",
                partner_prompt=partner_prompt,
                custom_section=custom_section,
                sql_query=sql_query_str,
                results_str=results_str_final,
                live_data_str=live_data_str_final,
            )
        else:
            user_prompt_template = prompts_set["RESPONSE_USER_PROMPT_INSIGHT"]
            prompt = user_prompt_template.format(
                partner_prompt=partner_prompt,
                custom_section=custom_section,
                sql_query=sql_query_str,
                results_str=results_str_final,
                live_data_str=live_data_str_final,
            )

        messages = [{"role": "system", "content": system_message}]
        # Add history only if it's a non-empty list
        if include_history and isinstance(conversation_history, list) and conversation_history:
            # Optional: Validate items in history before adding
            valid_history = [msg for msg in conversation_history if isinstance(msg, dict) and "role" in msg and "content" in msg]
            if valid_history:
                messages.extend(valid_history) # Use extend instead of unpacking
        elif include_history:
            print(f"Conversation history for {conversation_id} contained invalid items: {conversation_history}")

        messages.append({"role": "user", "content": prompt + "\nWEB_RESULTS:\n" + web_data_str})

        print("[DEBUG] LLM system_message:", system_message)
        print("[DEBUG] LLM prompt:", prompt)
        print("[DEBUG] LLM messages:", messages)

        completion = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        response_content = completion.choices[0].message.content
        print(response_content)

        if response_content.strip().startswith("```markdown"):
            response_content = response_content.strip()[11:]
        if response_content.strip().endswith("```"):
            response_content = response_content.strip()[:-3]
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            return {"insight": response_content.strip()}

    except Exception as e:
        # Log the specific error during client interaction
        print(f"Error during Azure OpenAI client interaction in generate_response: {e}")
        # Fallback response
        return "Error generating analysis. Please try again."
    finally:
        # Safely close the credential client if it exists and has an async close method
        if credential and hasattr(credential, 'close') and asyncio.iscoroutinefunction(credential.close):
             try:
                 await credential.close()
             except Exception as close_err:
                 print(f"Error closing Azure credential: {close_err}")