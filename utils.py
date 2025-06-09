import json
from datetime import datetime, date
from decimal import Decimal
import uuid
import os

class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that converts Decimal and datetime objects."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def serialize_response(data):
    """Recursively convert complex objects for JSON serialization."""
    if isinstance(data, dict):
        return {k: serialize_response(v) for k, v in data.items()}
    if isinstance(data, list):
        return [serialize_response(item) for item in data]
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    return data


def serialize_result(obj):
    """Serialize database records returned by asyncpg."""
    if isinstance(obj, dict):
        return {k: serialize_result(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_result(item) for item in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, "_asdict"):
        return serialize_result(dict(obj._asdict()))
    return obj

from azure.identity import DefaultAzureCredential
from fastapi import HTTPException


def get_azure_credential():
    """Return the default Azure credential."""
    if os.getenv("ENV") == "local":
        return DefaultAzureCredential()
    else:
        return DefaultAzureCredential(
            managed_identity_client_id="1ad4b11b-eb70-4c8a-9c72-0fa35ba3b16b"
        )


def get_token_provider(credential):
    """Create a callable that retrieves an access token."""
    def get_token():
        token = credential.get_token("https://cognitiveservices.azure.com/.default")
        return token.token
    return get_token

async def get_embedding(client, text: str, deployment: str) -> list:
    """Get an embedding vector using Azure OpenAI."""
    if not text:
        return []
    try:
        response = await client.embeddings.create(input=text, model=deployment)
        return response.data[0].embedding
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Embedding service failure") from exc
