SEARCH_SERVICE_NAME = "blitz-ai-search"
SEARCH_INDEX_NAME = "blitz-mlb-index"
SEARCH_ENDPOINT = f"https://{SEARCH_SERVICE_NAME}.search.windows.net"

OPENAI_ENDPOINT = "https://blitzgpt.openai.azure.com/"
OPENAI_DEPLOYMENT = "text-embedding-ada-002"
OPENAI_API_VERSION = "2025-03-01-preview"
OPENAI_EMBEDDING_DIMENSIONS = 1536

COSMOSDB_ENDPOINT = "https://blitz-queries.documents.azure.com:443/"
DATABASE_NAME = "sports"
CONTAINER_NAME = "mlb-partner-feedback-helpful"
UNHELPFUL_CONTAINER_NAME = "mlb-partner-feedback-unhelpful"
