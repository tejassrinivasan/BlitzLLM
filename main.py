# New API endpoints for B2B partners

import os
import json
import asyncio
import contextlib
from datetime import datetime
from typing import Optional, Dict, Any
import boto3
import uuid
from fastapi import FastAPI, HTTPException, Header, Security, Depends
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient
from pydantic import BaseModel
import asyncpg
from config import SQS_QUEUE_URL
from fastapi.security.api_key import APIKeyHeader
from utils import serialize_response, DecimalEncoder

from database_pool import (
    get_partner_pool,
    get_baseball_pool,
    set_partner_pool,
    set_baseball_pool,
    get_partner_db_pool,
    get_baseball_db_pool,
)
from dotenv import load_dotenv
import llm

load_dotenv()

app = FastAPI(title="BlitzLLM B2B API")

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    partner_id = get_partner_id_from_api_key(api_key)
    if not partner_id:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    return api_key

def get_partner_id_from_api_key(api_key: str) -> int | None:
    mapping = os.getenv("PARTNER_API_KEY_MAP", "{}")
    try:
        api_map = json.loads(mapping)
        return api_map.get(api_key)
    except Exception:
        return None

class InsightRequest(BaseModel):
    message: str
    custom_data: Optional[Dict[str, Any]] = None
    insight_length: Optional[str] = "short"
    league: Optional[str] = "mlb"
    search_the_web: Optional[bool] = False


class ConversationRequest(BaseModel):
    message: str
    custom_data: Optional[Dict[str, Any]] = None
    insight_length: Optional[str] = "short"
    league: Optional[str] = "mlb"
    search_the_web: Optional[bool] = False
    user_id: Optional[int] = None
    conversation_id: Optional[str] = ""
    message_id: Optional[int] = None
    retry: Optional[bool] = False


class FeedbackRequest(BaseModel):
    call_id: str
    helpful: bool


async def init_pools():
    """Initialize database connection pools on startup."""
    try:
        partner_pool = await get_partner_db_pool()
        set_partner_pool(partner_pool)
    except Exception as e:
        print(f"Failed to initialize partner pool: {e}")
    try:
        baseball_pool = await get_baseball_db_pool()
        set_baseball_pool(baseball_pool)
    except Exception as e:
        print(f"Failed to initialize baseball pool: {e}")


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

# --- SQS Queue Handling ---
sqs_task = None

async def send_to_sqs(message: dict):
    """Send a message to the configured SQS queue."""
    sqs = boto3.client("sqs", region_name="us-west-2")
    await asyncio.to_thread(
        sqs.send_message,
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(message),
    )


async def poll_sqs_queue():
    """Continuously poll SQS and process messages."""
    sqs = boto3.client("sqs", region_name="us-west-2")
    while True:
        try:
            resp = await asyncio.to_thread(
                sqs.receive_message,
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
            )
            for msg in resp.get("Messages", []):
                body = json.loads(msg["Body"])
                if body.get("type") == "generate_insights":
                    req = InsightRequest(**body["req"])
                    await process_generate_insights(
                        req, body.get("partner_id"), body["response_id"]
                    )
                elif body.get("type") == "conversation":
                    req = ConversationRequest(**body["req"])
                    await process_conversation(
                        req, body.get("partner_id"), body["response_id"]
                    )
                await asyncio.to_thread(
                    sqs.delete_message,
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=msg["ReceiptHandle"],
                )
        except Exception as e:
            print(f"Error processing SQS messages: {e}")
        await asyncio.sleep(1)


async def start_sqs_listener():
    global sqs_task
    sqs_task = asyncio.create_task(poll_sqs_queue())


async def stop_sqs_listener():
    global sqs_task
    if sqs_task:
        sqs_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sqs_task

app.add_event_handler("startup", start_sqs_listener)
app.add_event_handler("shutdown", stop_sqs_listener)


async def ensure_conversation(partner_id: int, user_id: int, conversation_id: str | None) -> str:
    pool = get_partner_pool()
    if not pool:
        return conversation_id or ""
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
        new_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO conversations (conversation_id, partner_id, user_id) VALUES ($1,$2,$3)""",
            new_id,
            partner_id,
            user_id,
        )
        return new_id


async def add_message(conversation_id: str, partner_id: int, message_id: int, role: str, content: str):
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

async def delete_messages_from(conversation_id: str, start_id: int):
    pool = get_partner_pool()
    if not pool:
        return
    await pool.execute(
        "DELETE FROM messages WHERE conversation_id=$1 AND message_id>=$2",
        conversation_id,
        start_id,
    )

async def store_response(partner_id: int | None, response_id: str, data: dict):
    """Store the response JSON in S3 under the partner prefix."""
    s3 = boto3.client("s3")
    bucket = os.getenv("PARTNER_RESPONSES_BUCKET")
    body = json.dumps(
        serialize_response(data),
        cls=DecimalEncoder,
    )
    key = f"{partner_id}/{response_id}.json" if partner_id else f"{response_id}.json"
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode())

async def log_partner_call(
    partner_id: Optional[int],
    endpoint: str,
    partner_payload: dict,
    response_payload: Optional[dict] = None,
):
    """Store details of partner API calls for auditing."""
    pool = get_partner_pool()
    if not pool:
        return
    row = await pool.fetchrow(
        """
        INSERT INTO calls (partner_id, partner_payload, response_payload, endpoint, created_at)
        VALUES ($1, $2, $3, $4, NOW()) RETURNING call_id
        """,
        partner_id,
        json.dumps(partner_payload) if partner_payload is not None else None,
        json.dumps(response_payload) if response_payload is not None else None,
        endpoint,
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


async def store_error_response(partner_id: int | None, response_id: str, error_message: str, status_code: int = 500):
    """Store an error response in S3 under the partner prefix."""
    s3 = boto3.client("s3")
    bucket = os.getenv("PARTNER_RESPONSES_BUCKET")
    body = json.dumps({
        "status": "error",
        "error_message": serialize_response(error_message),
        "status_code": status_code,
        "timestamp": datetime.utcnow().isoformat(),
    }, cls=DecimalEncoder)
    key = f"{partner_id}/{response_id}.json" if partner_id else f"{response_id}.json"
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode())


async def process_generate_insights(req: InsightRequest, partner_id: int, response_id: str):
    """Background task to generate an insight and store it."""
    try:
        openai_client = llm.get_openai_client()

        quick = await llm.check_clarification(
            req.message,
            [],
            req.custom_data,
            league=req.league,
            history_context="",
        )
        if quick.get("type") == "answer":
            response = quick.get("response")
        else:
            live_info = await llm.determine_live_endpoints(openai_client, req.message, league=req.league)
            live_data = None
            if live_info.get("needs_live_data"):
                live_data = await llm.fetch_upcoming_data(
                    live_info.get("calls", []),
                    live_info.get("keys", []),
                    live_info.get("constraints"),
                )

            search_results = await llm.perform_search(req.message, {})
            query_data = await llm.determine_sql_query(
                req.message,
                search_results,
                0,
                include_history=False,
                league=req.league,
            )
            sql_query = query_data.get("query") if query_data else None
            executed = None
            if query_data and query_data.get("type") in ("sql_query", "previous_results"):
                executed = await llm.execute_sql_query(
                    sql_query,
                    previous_results=query_data.get("results") if query_data.get("reuse_results") else None,
                )

            web_results = None
            if req.search_the_web:
                web_results = await llm.search_the_web(req.message)

            response = await llm.generate_text_response(
                partner_prompt=req.message,
                query_data=executed,
                live_data=live_data,
                search_results=web_results,
                custom_data=req.custom_data,
                simple=req.insight_length == "short",
                include_history=False,
                league=req.league,
            )
        # Save complete request as partner payload
        partner_payload = {
            "message": req.message,
            "custom_data": req.custom_data,
            "league": req.league,
            "insight_length": req.insight_length,
            "search_the_web": req.search_the_web
        }

        # Build full response payload
        text_block = response.get("text")
        if isinstance(text_block, dict):
            resp_text = text_block.get("response")
            resp_explanation = text_block.get("explanation")
            resp_links = text_block.get("links")
        else:
            resp_text = text_block
            resp_explanation = response.get("explanation")
            resp_links = response.get("links")

        response_payload = {
            "response_id": response_id,
            "response": resp_text,
            "explanation": resp_explanation,
            "links": resp_links,
            "timestamp": datetime.utcnow().isoformat(),
        }

        call_id = await log_partner_call(
            partner_id,
            "generate_insights", 
            partner_payload,
            response_payload,
        )
        await store_response(partner_id, response_id, response_payload)
        await log_query(call_id, partner_id, locals().get("sql_query"), req.league)
    except Exception as e:
        error_message = str(e)
        await store_error_response(partner_id, response_id, error_message, 500)
        
        # Save complete request as partner payload even on error
        partner_payload = {
            "message": req.message,
            "custom_data": req.custom_data,
            "league": req.league,
            "insight_length": req.insight_length,
            "search_the_web": req.search_the_web
        }

        # Build error response payload
        response_payload = {
            "response_id": response_id,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await log_partner_call(
            partner_id,
            "generate_insights",
            partner_payload,
            response_payload,
        )


async def process_conversation(req: ConversationRequest, partner_id: int, response_id: str):
    """Background task to process a conversation request."""
    try:
        openai_client = llm.get_openai_client()
        next_msg_id = req.message_id
        if req.retry and req.message_id:
            await delete_messages_from(req.conversation_id, req.message_id)

        await add_message(req.conversation_id, partner_id, next_msg_id, "user", req.message)

        history, history_context_sql, _, previous_results = await llm.prepare_history_for_sql(
            req.conversation_id,
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
            prompt_type="CONVERSATION",
        )
        if clarify.get("type") == "clarify" or clarify.get("type") == "answer":
            response = clarify.get("response") 
        else:
            live_info = await llm.determine_live_endpoints(openai_client, req.message, league=req.league)
            live_data = None
            if live_info.get("needs_live_data"):
                live_data = await llm.fetch_upcoming_data(
                    live_info.get("calls", []),
                    live_info.get("keys", []),
                    live_info.get("constraints"),
                )

            search_results = await llm.perform_search(req.message, {}, history)
            query_data = await llm.determine_sql_query(
                req.message,
                search_results,
                req.conversation_id,
                include_history=False,
                league=req.league,
                history_context=history_context_sql,
                previous_results=previous_results,
                prompt_type="CONVERSATION",
            )
            sql_query = query_data.get("query") if query_data else None
            executed = None
            if query_data and query_data.get("type") in ("sql_query", "previous_results"):
                executed = await llm.execute_sql_query(
                    sql_query,
                    previous_results=query_data.get("results") if query_data.get("reuse_results") else None,
                )

            web_results = None
            if req.search_the_web:
                web_results = await llm.search_the_web(req.message)

            response = await llm.generate_text_response(
                req.message,
                executed,
                live_data=live_data,
                custom_data=req.custom_data,
                simple=req.insight_length == "short",
                include_history=True,
                league=req.league,
                search_results=web_results,
                conversation_history=history,
                history_context=formatted_history,
                prompt_type="CONVERSATION", 
            )

        partner_payload = {
            "user_id": req.user_id,
            "conversation_id": req.conversation_id,
            "message_id": req.message_id,
            "message": req.message,
            "insight_length": req.insight_length,
            "league": req.league,
            "custom_data": req.custom_data,
            "retry": req.retry
        }
        text_block = response.get("text")
        if isinstance(text_block, dict):
            resp_text = text_block.get("response")
            resp_explanation = text_block.get("explanation")
            resp_links = text_block.get("links")
        else:
            resp_text = text_block
            resp_explanation = response.get("explanation")
            resp_links = response.get("links")

        response_payload = {
            "response_id": response_id,
            "response": resp_text,
            "explanation": resp_explanation,
            "links": resp_links,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await add_message(req.conversation_id, partner_id, next_msg_id, "assistant", json.dumps(response))
        await store_response(partner_id, response_id, response_payload)
        call_id = await log_partner_call(
            partner_id,
            "conversation",
            partner_payload,
            response_payload,
        )
        await log_query(call_id, partner_id, sql_query, req.league)
    except Exception as e:
        error_message = str(e)
        await store_error_response(partner_id, response_id, error_message, 500)
        partner_payload = {
            "user_id": req.user_id,
            "conversation_id": req.conversation_id,
            "message_id": req.message_id,
            "message": req.message,
            "insight_length": req.insight_length,
            "league": req.league,
            "custom_data": req.custom_data,
            "retry": req.retry
        }
        response_payload = {
            "response_id": response_id,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await log_partner_call(
            partner_id,
            "conversation",
            partner_payload,
            response_payload,
        )


@app.post("/generate-insights", status_code=202)
async def generate_insights(
    req: InsightRequest,
    api_key: str = Depends(verify_api_key),
):
    """Schedule insight generation and return a response identifier."""
    partner_id = get_partner_id_from_api_key(api_key)
    if not partner_id:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    response_id = str(uuid.uuid4())
    try:
        await store_response(partner_id, response_id, {"status": "processing"})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to schedule processing") from e

    await send_to_sqs(
        {
            "type": "generate_insights",
            "req": req.dict(),
            "partner_id": partner_id,
            "response_id": response_id,
        }
    )

    return {"response_id": response_id}


@app.post("/conversation", status_code=202)
async def conversation(
    req: ConversationRequest,
    api_key: str = Depends(verify_api_key),
):
    """Schedule conversation processing and return identifiers."""
    partner_id = get_partner_id_from_api_key(api_key)
    if not partner_id:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    if req.message_id not in (None, 0) and not req.conversation_id:
        raise HTTPException(status_code=400, detail="message_id requires conversation_id")

    conv_id = await ensure_conversation(partner_id, req.user_id, req.conversation_id)
    req.conversation_id = conv_id

    pool = get_partner_pool()
    if req.message_id in (None, 0):
        if pool:
            async with pool.acquire() as conn:
                max_id = await conn.fetchval(
                    "SELECT MAX(message_id) FROM messages WHERE conversation_id=$1",
                    conv_id,
                )
                req.message_id = (max_id or 0) + 1
        else:
            req.message_id = 1

    response_id = str(uuid.uuid4())
    try:
        await store_response(partner_id, response_id, {"status": "processing"})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to schedule processing") from e

    await send_to_sqs(
        {
            "type": "conversation",
            "req": req.dict(),
            "partner_id": partner_id,
            "response_id": response_id,
        }
    )

    return {"conversation_id": conv_id, "response_id": response_id}


@app.get("/insights/{response_id}")
async def get_insight_response(response_id: str, api_key: str = Depends(verify_api_key)):
    """Retrieve a stored response from S3."""
    partner_id = get_partner_id_from_api_key(api_key)
    s3 = boto3.client("s3")
    bucket = os.getenv("PARTNER_RESPONSES_BUCKET")
    key = f"{partner_id}/{response_id}.json" if partner_id else f"{response_id}.json"
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read().decode())
        return data
    except Exception:
        raise HTTPException(status_code=404, detail="Response not found")

@app.get("/conversation/{response_id}")
async def get_conversation_response(
    response_id: str,
    api_key: str = Depends(verify_api_key)
):
    partner_id = get_partner_id_from_api_key(api_key)
    s3 = boto3.client("s3")
    bucket = os.getenv("PARTNER_RESPONSES_BUCKET")
    key = f"{partner_id}/{response_id}.json" if partner_id else f"{response_id}.json"
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read().decode())
        return data
    except Exception:
        raise HTTPException(status_code=404, detail="Conversation response not found")


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
