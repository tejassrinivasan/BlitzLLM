# New API endpoints for B2B partners

import os
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Header, Security, Depends
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient
from pydantic import BaseModel
import asyncpg
from fastapi.security.api_key import APIKeyHeader

from database_pool import (
    get_partner_pool,
    get_baseball_pool,
    set_partner_pool,
    set_baseball_pool,
)

import llm

app = FastAPI(title="BlitzLLM B2B API")

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_valid_api_keys():
    keys = os.getenv("PARTNER_API_KEYS", "")
    return [k.strip() for k in keys.split(",") if k.strip()]

async def verify_api_key(api_key: str = Security(api_key_header)):
    valid_keys = get_valid_api_keys()
    if api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

class InsightRequest(BaseModel):
    question: str
    custom_data: Optional[Dict[str, Any]] = None
    partner_id: Optional[int] = None  # optional partner identifier
    user_id: Optional[int] = None
    conversation_id: Optional[int] = 0
    simple: Optional[bool] = False
    league: Optional[str] = "mlb"


class ConversationRequest(BaseModel):
    question: str
    custom_data: Optional[Dict[str, Any]] = None
    partner_id: Optional[int] = None
    user_id: Optional[int] = None
    conversation_id: Optional[int] = 0
    simple: Optional[bool] = False
    league: Optional[str] = "mlb"


class FeedbackRequest(BaseModel):
    call_id: str
    helpful: bool


async def init_pools():
    """Initialize database connection pools on startup."""
    partner_dsn = os.getenv("PARTNER_DB_DSN")
    baseball_dsn = os.getenv("BASEBALL_DB_DSN")
    if partner_dsn:
        partner_pool = await asyncpg.create_pool(dsn=partner_dsn)
        set_partner_pool(partner_pool)
    if baseball_dsn:
        baseball_pool = await asyncpg.create_pool(dsn=baseball_dsn)
        set_baseball_pool(baseball_pool)


async def close_pools():
    """Close database pools on shutdown."""
    partner_pool = get_partner_pool()
    if partner_pool:
        await partner_pool.close()
    baseball_pool = get_baseball_pool()
    if baseball_pool:
        await baseball_pool.close()


app.add_event_handler("startup", init_pools)
app.add_event_handler("shutdown", close_pools)


async def log_partner_call(
    partner_id: Optional[int],
    user_id: Optional[int],
    conversation_id: Optional[int],
    endpoint: str,
    question: str,
    custom_data: Optional[dict],
    sql_query: Optional[str],
    response_text: Optional[str],
    error: Optional[str] = None,
):
    """Store details of partner API calls for auditing."""
    pool = get_partner_pool()
    if not pool:
        return
    await pool.execute(
        """
        INSERT INTO calls (partner_id, user_id, conversation_id, endpoint, question, custom_data, sql_query, response_text, error)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        partner_id,
        user_id,
        conversation_id,
        endpoint,
        question,
        custom_data,
        sql_query,
        response_text,
        error,
    )


@app.post("/generate-insights")
async def generate_insights(req: InsightRequest, api_key: str = Depends(verify_api_key)):
    """Endpoint for partners to generate insights from a question and custom data."""
    try:
        openai_client = llm.get_openai_client()
        live_info = await llm.determine_live_endpoints(openai_client, req.question, league=req.league)
        live_data = None
        if live_info.get("needs_live_data"):
            live_data = await llm.fetch_upcoming_data(live_info.get("calls", []), live_info.get("keys", []), live_info.get("constraints"))

        search_results = await llm.perform_search(req.question, {})
        query_data = await llm.determine_sql_query(req.question, search_results, 0, include_history=False, league=req.league)
        sql_query = query_data.get("query") if query_data else None
        executed = None
        if query_data and query_data.get("type") in ("sql_query", "previous_results"):
            executed = await llm.execute_sql_query(sql_query, req.question, 0, previous_results=query_data.get("results") if query_data.get("reuse_results") else None)
        response = await llm.generate_text_response(
            req.question,
            executed,
            0,
            live_data,
            custom_data=req.custom_data,
            simple=req.simple,
            include_history=False,
            league=req.league,
        )
        await log_partner_call(
            req.partner_id,
            req.user_id,
            req.conversation_id,
            "generate_insights",
            req.question,
            req.custom_data,
            sql_query,
            response.get("text") if response else None,
        )
        return response
    except Exception as e:
        await log_partner_call(
            req.partner_id,
            req.user_id,
            req.conversation_id,
            "generate_insights",
            req.question,
            req.custom_data,
            None,
            None,
            str(e),
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/conversation")
async def conversation(req: ConversationRequest, api_key: str = Depends(verify_api_key)):
    """Endpoint for conversational flow with optional clarification."""
    try:
        history, history_context_sql, _, previous_results = await llm.prepare_history_for_sql(
            req.conversation_id,
            None,
            include_history=True,
        )
        formatted_history = llm.format_conversation_history_for_prompt(history)

        clarify = await llm.check_clarification(
            req.question,
            history,
            req.custom_data,
            league=req.league,
            history_context=formatted_history,
        )
        if clarify.get("type") == "clarify":
            await log_partner_call(
                req.partner_id,
                req.user_id,
                req.conversation_id,
                "conversation",
                req.question,
                req.custom_data,
                None,
                clarify.get("question"),
            )
            return {"clarify": clarify.get("question")}
        search_results = await llm.perform_search(req.question, {})
        query_data = await llm.determine_sql_query(
            req.question,
            search_results,
            req.conversation_id,
            include_history=False,
            league=req.league,
            history_context=history_context_sql,
            previous_results=previous_results,
        )
        sql_query = query_data.get("query") if query_data else None
        executed = await llm.execute_sql_query(sql_query, req.question, req.conversation_id)
        response = await llm.generate_text_response(
            req.question,
            executed,
            req.conversation_id,
            custom_data=req.custom_data,
            simple=req.simple,
            league=req.league,
            conversation_history=history,
            history_context=formatted_history,
        )
        await log_partner_call(
            req.partner_id,
            req.user_id,
            req.conversation_id,
            "conversation",
            req.question,
            req.custom_data,
            sql_query,
            response.get("text") if response else None,
        )
        return response
    except Exception as e:
        await log_partner_call(
            req.partner_id,
            req.user_id,
            req.conversation_id,
            "conversation",
            req.question,
            req.custom_data,
            None,
            None,
            str(e),
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/feedback")
async def feedback(req: FeedbackRequest, api_key: str = Depends(verify_api_key)):
    """Store user feedback in Azure Cosmos DB."""
    try:
        credential = DefaultAzureCredential()
        cosmos_client = CosmosClient(os.getenv("COSMOSDB_ENDPOINT"), credential=credential)
        database = cosmos_client.get_database_client("sports")
        container_name = "mlb-partner-feedback-helpful" if req.helpful else "mlb-partner-feedback-unhelpful"
        container = database.get_container_client(container_name)
        item = {
            "id": req.call_id,
        }
        container.upsert_item(item)
        return {"message": "Feedback recorded"}
    except Exception as e:
        print(f"Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
