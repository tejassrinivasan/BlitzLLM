# New API endpoints for B2B partners

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
import boto3

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
    partner_id = get_partner_id_from_api_key(api_key)
    if not partner_id:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

class InsightRequest(BaseModel):
    message: str
    search_the_web: Optional[bool] = False
    insight_length: Optional[str] = "detailed"
    custom_data: Optional[Dict[str, Any]] = None
    league: Optional[str] = "mlb"


class ConversationRequest(BaseModel):
    message: str
    custom_data: Optional[Dict[str, Any]] = None
    partner_id: Optional[int] = None
    user_id: Optional[int] = None
    conversation_id: Optional[int] = 0
    message_id: Optional[int] = None
    retry: Optional[bool] = False
    insight_length: Optional[str] = "detailed"
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


async def ensure_conversation(partner_id: int, user_id: int, conversation_id: int) -> int:
    pool = get_partner_pool()
    if not pool:
        return conversation_id or 0
    async with pool.acquire() as conn:
        if conversation_id:
            exists = await conn.fetchval(
                "SELECT 1 FROM conversations WHERE conversation_id=$1",
                conversation_id,
            )
            if exists:
                await conn.execute(
                    "UPDATE conversations SET updated_at=NOW() WHERE conversation_id=$1",
                    conversation_id,
                )
                return conversation_id
        row = await conn.fetchrow(
            """INSERT INTO conversations (partner_id, user_id) VALUES ($1,$2) RETURNING conversation_id""",
            partner_id,
            user_id,
        )
        return row["conversation_id"]


async def add_message(conversation_id: int, partner_id: int, message_id: int, role: str, content: str):
    pool = get_partner_pool()
    if not pool:
        return
    await pool.execute(
        """INSERT INTO messages (conversation_id, message_id, partner_id, role, content) VALUES ($1,$2,$3,$4,$5)""",
        conversation_id,
        message_id,
        partner_id,
        role,
        content,
    )

async def delete_messages_from(conversation_id: int, start_id: int):
    pool = get_partner_pool()
    if not pool:
        return
    await pool.execute(
        "DELETE FROM messages WHERE conversation_id=$1 AND message_id>=$2",
        conversation_id,
        start_id,
    )

async def store_insight(partner_id: int | None, insight_id: str, data: dict):
    """Store the insight JSON in S3 under the partner prefix."""
    s3 = boto3.client("s3")
    bucket = os.getenv("INSIGHTS_BUCKET", "blitz-insights")
    body = json.dumps({
        "response": data,
        "timestamp": datetime.utcnow().isoformat(),
    })
    key = f"{partner_id}/{insight_id}.json" if partner_id else f"{insight_id}.json"
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode())


async def store_conversation_history(partner_id: int | None, conversation_id: int):
    """Dump the conversation history to S3."""
    history, _ = await llm.get_conversation_history(conversation_id)
    s3 = boto3.client("s3")
    bucket = os.getenv("CONVERSATIONS_BUCKET", "blitz-conversations")
    body = json.dumps({
        "conversation_id": conversation_id,
        "messages": history,
        "timestamp": datetime.utcnow().isoformat(),
    })
    key = f"{partner_id}/{conversation_id}.json" if partner_id else f"{conversation_id}.json"
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode())


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
    row = await pool.fetchrow(
        """
        INSERT INTO calls (partner_id, user_id, conversation_id, endpoint, question, custom_data, sql_query, response_text, error)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING call_id
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
    return row["call_id"] if row else None

async def log_query(call_id: int, partner_id: Optional[int], sql_query: str, league: str):
    pool = get_partner_pool()
    if not pool or not sql_query:
        return
    await pool.execute(
        """
        INSERT INTO queries (call_id, partner_id, sql_query, reviewed, league)
        VALUES ($1, $2, $3, $4, $5)
        """,
        call_id,
        partner_id,
        sql_query,
        False,
        league,
    )


@app.post("/generate-insights", status_code=201)
async def generate_insights(req: InsightRequest, api_key: str = Depends(verify_api_key)):
    """Endpoint for partners to generate insights from a question and custom data."""
    try:
        partner_id = get_partner_id_from_api_key(api_key)
        if not partner_id:
            raise HTTPException(status_code=401, detail="Invalid or missing API Key")
        openai_client = llm.get_openai_client()

        quick = await llm.check_clarification(
            req.message,
            [],
            req.custom_data,
            league=req.league,
            history_context="",
        )
        if quick.get("type") == "answer":
            return {"insight": quick.get("answer")}

        live_info = await llm.determine_live_endpoints(openai_client, req.message, league=req.league)
        live_data = None
        if live_info.get("needs_live_data"):
            live_data = await llm.fetch_upcoming_data(live_info.get("calls", []), live_info.get("keys", []), live_info.get("constraints"))

        search_results = await llm.perform_search(req.message, {})
        query_data = await llm.determine_sql_query(req.message, search_results, 0, include_history=False, league=req.league)
        sql_query = query_data.get("query") if query_data else None
        executed = None
        if query_data and query_data.get("type") in ("sql_query", "previous_results"):
            executed = await llm.execute_sql_query(sql_query, req.message, 0, previous_results=query_data.get("results") if query_data.get("reuse_results") else None)

        web_results = None
        if req.search_the_web:
            web_results = await llm.search_the_web(req.message)
        response = await llm.generate_text_response(
            req.message,
            executed,
            0,
            live_data,
            custom_data=req.custom_data,
            simple=req.insight_length == "short",
            include_history=False,
            league=req.league,
            search_results=web_results,
        )
        import uuid
        insight_id = str(uuid.uuid4())
        await store_insight(partner_id, insight_id, response)

        call_id = await log_partner_call(
            partner_id,
            None,
            None,
            "generate_insights",
            req.message,
            req.custom_data,
            sql_query,
            response.get("text") if response else None,
        )
        await log_query(call_id, partner_id, sql_query, req.league)
        return {"insight_id": insight_id}
    except Exception as e:
        partner_id = locals().get('partner_id', None)
        await log_partner_call(
            partner_id,
            None,
            None,
            "generate_insights",
            req.message,
            req.custom_data,
            None,
            None,
            str(e),
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/conversation", status_code=201)
async def conversation(req: ConversationRequest, api_key: str = Depends(verify_api_key)):
    """Endpoint for conversational flow with optional clarification."""
    try:
        conv_id = await ensure_conversation(req.partner_id or 0, req.user_id or 0, req.conversation_id)

        if req.retry and req.message_id:
            await delete_messages_from(conv_id, req.message_id)
            next_msg_id = req.message_id
        else:
            history, _, _, _ = await llm.prepare_history_for_sql(conv_id, None, include_history=True)
            next_msg_id = len(history) + 1

        await add_message(conv_id, req.partner_id or 0, next_msg_id, "user", req.message)

        history, history_context_sql, _, previous_results = await llm.prepare_history_for_sql(
            conv_id,
            None,
            include_history=True,
        )
        formatted_history = llm.format_conversation_history_for_prompt(history)

        clarify = await llm.check_clarification(
            req.message,
            history,
            req.custom_data,
            league=req.league,
            history_context=formatted_history,
        )
        if clarify.get("type") == "clarify":
            call_id = await log_partner_call(
                req.partner_id,
                req.user_id,
                conv_id,
                "conversation",
                req.message,
                req.custom_data,
                None,
                clarify.get("question"),
            )
            await log_query(call_id, req.partner_id, None, req.league)
            return {"clarify": clarify.get("question"), "conversation_id": conv_id}
        search_results = await llm.perform_search(req.message, {})
        query_data = await llm.determine_sql_query(
            req.message,
            search_results,
            conv_id,
            include_history=False,
            league=req.league,
            history_context=history_context_sql,
            previous_results=previous_results,
        )
        sql_query = query_data.get("query") if query_data else None
        executed = await llm.execute_sql_query(sql_query, req.message, conv_id)
        response = await llm.generate_text_response(
            req.message,
            executed,
            conv_id,
            custom_data=req.custom_data,
            simple=req.insight_length == "short",
            league=req.league,
            conversation_history=history,
            history_context=formatted_history,
        )
        await add_message(conv_id, req.partner_id or 0, next_msg_id + 1, "assistant", json.dumps(response))
        await store_conversation_history(req.partner_id or 0, conv_id)

        call_id = await log_partner_call(
            req.partner_id,
            req.user_id,
            conv_id,
            "conversation",
            req.message,
            req.custom_data,
            sql_query,
            response.get("text") if response else None,
        )
        await log_query(call_id, req.partner_id, sql_query, req.league)
        response_with_id = response or {}
        if isinstance(response_with_id, dict):
            response_with_id["conversation_id"] = conv_id
        return response_with_id
    except Exception as e:
        await log_partner_call(
            req.partner_id,
            req.user_id,
            conv_id if 'conv_id' in locals() else req.conversation_id,
            "conversation",
            req.message,
            req.custom_data,
            None,
            None,
            str(e),
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.get("/insights/{insight_id}")
async def get_insight(insight_id: str, partner_id: int | None = None, api_key: str = Depends(verify_api_key)):
    """Retrieve a stored insight from S3."""
    s3 = boto3.client("s3")
    bucket = os.getenv("INSIGHTS_BUCKET", "blitz-insights")
    key = f"{partner_id}/{insight_id}.json" if partner_id else f"{insight_id}.json"
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read().decode())
        return data
    except Exception:
        raise HTTPException(status_code=404, detail="Insight not found")


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

def get_partner_id_from_api_key(api_key: str) -> int | None:
    mapping = os.getenv("PARTNER_API_KEY_MAP", "{}")
    try:
        api_map = json.loads(mapping)
        return api_map.get(api_key)
    except Exception:
        return None

@app.get("/conversation/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    api_key: str = Depends(api_key_header)
):
    partner_id = get_partner_id_from_api_key(api_key)
    if not partner_id:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    s3 = boto3.client("s3")
    bucket = os.getenv("CONVERSATIONS_BUCKET", "blitz-messages")
    key = f"{partner_id}/{conversation_id}.json"
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read().decode())
        return data
    except Exception:
        raise HTTPException(status_code=404, detail="Conversation not found")
