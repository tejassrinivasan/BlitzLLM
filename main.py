# New API endpoints for B2B partners

import os
import json
import asyncio
import contextlib
from datetime import datetime
from typing import Optional, Dict, Any
import boto3
import uuid
import time
from fastapi import FastAPI, HTTPException, Header, Security, Depends, BackgroundTasks
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient
from pydantic import BaseModel
import asyncpg
from config import SQS_QUEUE_URL
from fastapi.security.api_key import APIKeyHeader
from utils import serialize_response, DecimalEncoder
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Initialize common AWS clients and config values
SQS_CLIENT = boto3.client("sqs", region_name="us-west-2")
S3_CLIENT = boto3.client("s3")
S3_BUCKET = os.getenv("PARTNER_RESPONSES_BUCKET")
API_KEY_MAP = json.loads(os.getenv("PARTNER_API_KEY_MAP", "{}"))


async def verify_api_key(api_key: str = Security(api_key_header)):
    partner_id = get_partner_id_from_api_key(api_key)
    if not partner_id:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    return api_key


def get_partner_id_from_api_key(api_key: str) -> int | None:
    """Lookup the partner ID for the provided API key."""
    try:
        return API_KEY_MAP.get(api_key)
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
    user_id: Optional[str] = None
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
    await asyncio.to_thread(
        SQS_CLIENT.send_message,
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(message),
    )


async def poll_sqs_queue():
    """Continuously poll SQS and process messages."""
    while True:
        try:
            resp = await asyncio.to_thread(
                SQS_CLIENT.receive_message,
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
                    SQS_CLIENT.delete_message,
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


async def ensure_conversation(
    partner_id: int, user_id: int, conversation_id: str | None
) -> str:
    """Ensure a conversation exists and mark it as current."""
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
                    "UPDATE conversations SET updated_at=NOW(), is_current=TRUE WHERE conversation_id=$1",
                    conversation_id,
                )
                await conn.execute(
                    "UPDATE conversations SET is_current=FALSE WHERE user_id=$1 AND conversation_id<>$2",
                    user_id,
                    conversation_id,
                )
                return conversation_id
        new_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO conversations (conversation_id, partner_id, user_id, title, is_current) VALUES ($1,$2,$3,$4,TRUE)""",
            new_id,
            partner_id,
            user_id,
            "New Chat",
        )
        await conn.execute(
            "UPDATE conversations SET is_current=FALSE WHERE user_id=$1 AND conversation_id<>$2",
            user_id,
            new_id,
        )
        return new_id


async def add_message(
    conversation_id: str, partner_id: int, message_id: int, role: str, content: str
):
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


async def generate_title(client, user_prompt: str) -> str:
    """Generate a concise title for the conversation."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that generates very short, concise titles (max 6 words) for conversations based on user questions. "
                        f"Focus on the main topic or intent. **TODAY'S DATE:** {datetime.now().strftime('%Y-%m-%d')}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Generate a short title (max 6 words) for a conversation that starts with this question: "
                        f"{user_prompt}"
                    ),
                },
            ],
            temperature=0,
            max_tokens=30,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating title: {e}")
        return "New Chat"


def _s3_key(partner_id: int | None, response_id: str) -> str:
    return f"{partner_id}/{response_id}.json" if partner_id else f"{response_id}.json"


def _store_json(partner_id: int | None, response_id: str, data: dict) -> None:
    body = json.dumps(serialize_response(data), cls=DecimalEncoder)
    S3_CLIENT.put_object(
        Bucket=S3_BUCKET, Key=_s3_key(partner_id, response_id), Body=body.encode()
    )


def _load_json(partner_id: int | None, response_id: str) -> dict:
    obj = S3_CLIENT.get_object(
        Bucket=S3_BUCKET, Key=_s3_key(partner_id, response_id)
    )
    return json.loads(obj["Body"].read().decode())


async def store_response(partner_id: int | None, response_id: str, data: dict):
    """Store the response JSON in S3 under the partner prefix."""
    _store_json(partner_id, response_id, data)


async def fetch_response(partner_id: int | None, response_id: str) -> dict | None:
    """Retrieve a stored response from S3."""
    try:
        return _load_json(partner_id, response_id)
    except Exception:
        return None


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


async def log_query(
    call_id: int, partner_id: Optional[int], sql_query: str, league: str
):
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


async def store_error_response(
    partner_id: int | None, response_id: str, error_message: str, status_code: int = 500
):
    """Store an error response in S3 under the partner prefix."""
    error_data = {
        "status": "error",
        "error_message": serialize_response(error_message),
        "status_code": status_code,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _store_json(partner_id, response_id, error_data)


def extract_response_parts(
    response: dict,
) -> tuple[str | None, str | None, list | None]:
    """Extract text, explanation and links from an LLM response."""
    text_block = response.get("text")
    if isinstance(text_block, dict):
        return (
            text_block.get("response"),
            text_block.get("explanation"),
            text_block.get("links"),
        )
    return text_block, response.get("explanation"), response.get("links")


async def process_generate_insights(
    req: InsightRequest, partner_id: int, response_id: str
):
    """Background task to generate an insight and store it."""
    try:
        openai_client = llm.get_openai_client()

        # Save complete request as partner payload
        partner_payload = {
            "message": req.message,
            "custom_data": req.custom_data,
            "league": req.league,
            "insight_length": req.insight_length,
            "search_the_web": req.search_the_web,
        }

        web_results = None
        if req.search_the_web:
            web_results_raw = await llm.search_the_web(req.message, req.league)
            if web_results_raw.get("error"):
                await store_error_response(
                    partner_id, response_id, web_results_raw.get("explanation"), 500
                )
                return
            web_results = (
                llm.format_web_results(web_results_raw) if web_results_raw else None
            )
            print(f"Web results: {web_results}")

        quick = await llm.check_clarification(
            req.message,
            [],
            req.custom_data,
            league=req.league,
            history_context="",
            web_results=web_results,
        )
        if quick.get("type") == "answer":
            response_payload = {
                "response_id": response_id,
                "response": quick.get("response"),
                "explanation": quick.get("explanation"),
                "links": quick.get("links"),
                "timestamp": datetime.utcnow().isoformat(),
            }

            call_id = await log_partner_call(
                partner_id,
                "generate_insights",
                partner_payload,
                response_payload,
            )
            await store_response(partner_id, response_id, response_payload)
            return
        else:
            live_info = await llm.determine_live_endpoints(
                openai_client, req.message, league=req.league, web_results=web_results
            )
            live_data = None
            if live_info.get("needs_live_data"):
                live_data = await llm.fetch_upcoming_data(
                    live_info.get("calls", []),
                    live_info.get("keys", []),
                    live_info.get("constraints"),
                )

            search_results = await llm.perform_search(req.message, {})
            if isinstance(search_results, dict) and search_results.get("error"):
                await store_error_response(
                    partner_id, response_id, search_results.get("explanation"), 500
                )
                return

            query_data = await llm.determine_sql_query(
                req.message,
                search_results,
                0,
                include_history=False,
                league=req.league,
            )
            if isinstance(query_data, dict) and query_data.get("error"):
                await store_error_response(
                    partner_id, response_id, query_data.get("explanation"), 500
                )
                return

            sql_query = query_data.get("query") if query_data else None
            executed = None
            if query_data and query_data.get("type") in (
                "sql_query",
                "previous_results",
            ):
                executed = await llm.execute_sql_query(
                    sql_query,
                    previous_results=(
                        query_data.get("results")
                        if query_data.get("reuse_results")
                        else None
                    ),
                )
            if isinstance(executed, dict) and executed.get("error"):
                await store_error_response(
                    partner_id, response_id, executed.get("explanation"), 500
                )
                return

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
            if isinstance(response, dict) and response.get("error"):
                await store_error_response(
                    partner_id, response_id, response.get("explanation"), 500
                )
                return

        # Build full response payload
        resp_text, resp_explanation, resp_links = extract_response_parts(response)

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
            "search_the_web": req.search_the_web,
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


async def process_conversation(
    req: ConversationRequest, partner_id: int, response_id: str
):
    """Background task to process a conversation request."""
    try:
        openai_client = llm.get_openai_client()
        next_msg_id = req.message_id
        if req.retry and req.message_id:
            await delete_messages_from(req.conversation_id, req.message_id)

        await add_message(
            req.conversation_id, partner_id, next_msg_id, "user", req.message
        )

        history, history_context_sql, _, previous_results = (
            await llm.prepare_history_for_sql(
                req.conversation_id,
                None,
                include_history=True,
            )
        )
        formatted_history = llm.format_conversation_history_for_prompt(history)
        
        print(f"Formatted history: {formatted_history}")
        partner_payload = {
            "user_id": req.user_id,
            "conversation_id": req.conversation_id,
            "message_id": req.message_id,
            "message": req.message,
            "insight_length": req.insight_length,
            "league": req.league,
            "custom_data": req.custom_data,
            "retry": req.retry,
        }

        web_results = None
        if req.search_the_web:
            web_results_raw = await llm.search_the_web(req.message, req.league)
            if web_results_raw.get("error"):
                await store_error_response(
                    partner_id, response_id, web_results_raw.get("explanation"), 500
                )
                return
            web_results = (
                llm.format_web_results(web_results_raw) if web_results_raw else None
            )

        clarify = await llm.check_clarification(
            req.message,
            history,
            req.custom_data,
            league=req.league,
            history_context=formatted_history,
            prompt_type="CONVERSATION",
            web_results=web_results,
        )
        if clarify.get("type") == "clarify" or clarify.get("type") == "answer":
            response_payload = {
                "response_id": response_id,
                "response": clarify.get("response"),
                "explanation": clarify.get("explanation"),
                "links": clarify.get("links"),
                "timestamp": datetime.utcnow().isoformat(),
            }

            call_id = await log_partner_call(
                partner_id,
                "conversation",
                partner_payload,
                response_payload,
            )
            await store_response(partner_id, response_id, response_payload)
            return
        else:
            live_info = await llm.determine_live_endpoints(
                openai_client, req.message, league=req.league, web_results=web_results
            )
            live_data = None
            if live_info.get("needs_live_data"):
                live_data = await llm.fetch_upcoming_data(
                    live_info.get("calls", []),
                    live_info.get("keys", []),
                    live_info.get("constraints"),
                )

            search_results = await llm.perform_search(req.message, {}, history)
            if isinstance(search_results, dict) and search_results.get("error"):
                await store_error_response(
                    partner_id, response_id, search_results.get("explanation"), 500
                )
                return

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
            if isinstance(query_data, dict) and query_data.get("error"):
                await store_error_response(
                    partner_id, response_id, query_data.get("explanation"), 500
                )
                return

            sql_query = query_data.get("query") if query_data else None
            executed = None
            if query_data and query_data.get("type") in (
                "sql_query",
                "previous_results",
            ):
                executed = await llm.execute_sql_query(
                    sql_query,
                    previous_results=(
                        query_data.get("results")
                        if query_data.get("reuse_results")
                        else None
                    ),
                )
            if isinstance(executed, dict) and executed.get("error"):
                await store_error_response(
                    partner_id, response_id, executed.get("explanation"), 500
                )
                return

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
            if isinstance(response, dict) and response.get("error"):
                await store_error_response(
                    partner_id, response_id, response.get("explanation"), 500
                )
                return

        resp_text, resp_explanation, resp_links = extract_response_parts(response)

        response_payload = {
            "response_id": response_id,
            "response": resp_text,
            "explanation": resp_explanation,
            "links": resp_links,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await add_message(
            req.conversation_id,
            partner_id,
            next_msg_id,
            "assistant",
            json.dumps(response),
        )
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
            "retry": req.retry,
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
        raise HTTPException(
            status_code=500, detail="Failed to schedule processing"
        ) from e

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
        raise HTTPException(
            status_code=400, detail="message_id requires conversation_id"
        )

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
        raise HTTPException(
            status_code=500, detail="Failed to schedule processing"
        ) from e

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
async def get_insight_response(
    response_id: str, api_key: str = Depends(verify_api_key)
):
    """Retrieve a stored insight response from S3."""
    partner_id = get_partner_id_from_api_key(api_key)
    data = await fetch_response(partner_id, response_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Response not found")
    return data


@app.get("/conversation/{response_id}")
async def get_conversation_response(
    response_id: str, api_key: str = Depends(verify_api_key)
):
    """Retrieve a stored conversation response from S3."""
    partner_id = get_partner_id_from_api_key(api_key)
    data = await fetch_response(partner_id, response_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Conversation response not found")
    return data


@app.post("/feedback")
async def feedback(req: FeedbackRequest, api_key: str = Depends(verify_api_key)):
    """Store user feedback in Azure Cosmos DB."""
    try:
        credential = DefaultAzureCredential()
        cosmos_client = CosmosClient(
            os.getenv("COSMOSDB_ENDPOINT"), credential=credential
        )
        database = cosmos_client.get_database_client("sports")
        container_name = (
            "mlb-partner-feedback-helpful"
            if req.helpful
            else "mlb-partner-feedback-unhelpful"
        )
        container = database.get_container_client(container_name)
        item = {
            "id": req.call_id,
        }
        container.upsert_item(item)
        return {"message": "Feedback recorded"}
    except Exception as e:
        print(f"Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Simple in-memory task storage for streaming demo
conversation_tasks: dict = {}

@app.post('/api/conversations/{conversation_id}/messages/stream')
async def create_message_stream(
    conversation_id: str,
    message: Dict[str, Any],
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
):
    """Accept a message and stream a dummy response while storing it."""
    task_id = f"{conversation_id}_{int(time.time())}"
    conversation_tasks[task_id] = {"status": "processing", "step": "Generating response..."}

    partner_id = get_partner_id_from_api_key(api_key)
    pool = get_partner_pool()
    openai_client = llm.get_openai_client()

    async def process():
        user_text = message.get("content", "")
        title = None
        if pool:
            async with pool.acquire() as conn:
                max_id = await conn.fetchval(
                    "SELECT MAX(message_id) FROM messages WHERE conversation_id=$1",
                    conversation_id,
                )
                next_id = (max_id or 0) + 1
                await add_message(conversation_id, partner_id, next_id, "user", user_text)

                if message.get("generate_title"):
                    title = await generate_title(openai_client, user_text)
                    await conn.execute(
                        "UPDATE conversations SET title=$1 WHERE conversation_id=$2",
                        title,
                        conversation_id,
                    )

                # Generate the real assistant response
                assistant_response = await llm.generate_text_response(
                    partner_prompt=user_text,
                    query_data=None,
                    live_data=None,
                    search_results=None,
                    custom_data=None,
                    simple=True,
                    include_history=True,
                    league="mlb",
                    conversation_history=None,
                    history_context="",
                    prompt_type="CONVERSATION",
                )
                # Extract the text response (if dict, get 'response', else str)
                response_text = (
                    assistant_response.get('response') if isinstance(assistant_response, dict) else str(assistant_response)
                )
                await add_message(
                    conversation_id,
                    partner_id,
                    next_id + 1,
                    "assistant",
                    response_text,
                )
                await conn.execute(
                    "UPDATE conversations SET updated_at=NOW() WHERE conversation_id=$1",
                    conversation_id,
                )

        await asyncio.sleep(1)
        conversation_tasks[task_id].update(
            {
                "status": "complete",
                "user_message": {
                    "conversation_id": conversation_id,
                    "role": "user",
                    "content": user_text,
                },
                "assistant_message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "title": title,
            }
        )
        await asyncio.sleep(180)
        conversation_tasks.pop(task_id, None)

    background_tasks.add_task(process)
    return {"task_id": task_id}

@app.get('/api/tasks/{task_id}')
async def get_task_status(task_id: str, api_key: str = Depends(verify_api_key)):
    return conversation_tasks.get(task_id, {"status": "not_found"})

@app.post('/api/tasks/{task_id}/cancel')
async def cancel_task(task_id: str, api_key: str = Depends(verify_api_key)):
    task = conversation_tasks.get(task_id)
    if not task:
        return {"status": "not_found"}
    task["status"] = "cancelled"
    return {"status": "cancelled"}


@app.get("/api/users/{user_id}/conversations")
async def list_user_conversations(user_id: str, api_key: str = Depends(verify_api_key)):
    """Return all conversations for a user."""
    partner_id = get_partner_id_from_api_key(api_key)
    pool = get_partner_pool()
    if not pool:
        return []
    rows = await pool.fetch(
        "SELECT conversation_id AS id, COALESCE(title,'New Chat') AS title, is_current, created_at, updated_at FROM conversations WHERE partner_id=$1 AND user_id=$2 ORDER BY updated_at DESC",
        partner_id,
        user_id,
    )
    return [dict(r) for r in rows]


@app.post("/api/conversations")
async def create_conversation(
    payload: Optional[dict] = None,
    api_key: str = Depends(verify_api_key),
):
    """Create a new conversation for the user."""
    partner_id = get_partner_id_from_api_key(api_key)
    user_id = (payload or {}).get("user_id", 0) if isinstance(payload, dict) else 0
    conv_id = await ensure_conversation(partner_id, user_id, None)
    return {"id": conv_id}


@app.get("/api/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str, api_key: str = Depends(verify_api_key)):
    """Return messages for a conversation."""
    partner_id = get_partner_id_from_api_key(api_key)
    pool = get_partner_pool()
    if not pool:
        return []
    rows = await pool.fetch(
        "SELECT message_id AS id, role, content, created_at FROM messages WHERE conversation_id=$1 AND partner_id=$2 ORDER BY message_id",
        conversation_id,
        partner_id,
    )
    return [dict(r) for r in rows]


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, api_key: str = Depends(verify_api_key)):
    partner_id = get_partner_id_from_api_key(api_key)
    pool = get_partner_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="No DB connection")
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM messages WHERE conversation_id=$1 AND partner_id=$2", conversation_id, partner_id)
        result2 = await conn.execute("DELETE FROM conversations WHERE conversation_id=$1 AND partner_id=$2", conversation_id, partner_id)
        if (result == "DELETE 0" and result2 == "DELETE 0"):
            raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}
