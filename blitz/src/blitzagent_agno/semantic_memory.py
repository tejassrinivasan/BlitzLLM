"""
Semantic Memory for BlitzAgent using pgvector.

This module implements semantic recall functionality similar to Mastra's memory system,
using PostgreSQL with pgvector extension for vector similarity search.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

import asyncpg
import numpy as np
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from .config import Config, MemoryConfig, SemanticRecallConfig
from .exceptions import BlitzAgentError

logger = structlog.get_logger(__name__)


@dataclass
class Message:
    """Represents a message in the conversation."""
    
    id: str
    content: str
    role: str  # 'user', 'assistant', 'tool'
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    resource_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None


@dataclass
class SemanticMatch:
    """Represents a semantically similar message match."""
    
    message: Message
    similarity: float
    context_messages: List[Message] = None


class SemanticMemory:
    """
    Semantic memory implementation with pgvector.
    
    Provides semantic recall functionality for retrieving contextually relevant
    messages from conversation history using vector similarity search.
    """
    
    def __init__(self, config: Config):
        """Initialize semantic memory."""
        self.config = config
        self.memory_config = config.memory or MemoryConfig()
        self.recall_config = self.memory_config.semantic_recall
        
        # Database connection
        self.db_url = (
            config.memory_database.get_connection_url() 
            if config.memory_database 
            else config.database.get_connection_url()
        )
        
        # OpenAI client for embeddings
        if config.model.provider == "azure_openai":
            from openai import AsyncAzureOpenAI
            self.openai_client = AsyncAzureOpenAI(
                api_key=config.model.api_key,
                azure_endpoint=config.model.azure_endpoint,
                api_version=config.model.azure_api_version
            )
            self.embedding_deployment = getattr(config.model, 'azure_embedding_deployment', 'text-embedding-ada-002')
            self.fallback_openai_client = None
        else:
            self.openai_client = AsyncOpenAI(api_key=config.model.api_key)
            self.embedding_deployment = None
            self.fallback_openai_client = None
        
        self.logger = logger.bind(component="semantic_memory")
        
        # Connection pool
        self._pool: Optional[asyncpg.Pool] = None
        
        self.logger.info(
            "Semantic memory initialized",
            enabled=self.memory_config.enabled,
            semantic_recall=self.recall_config.enabled,
            vector_store=self.memory_config.vector_store.provider,
            embedding_model=self.recall_config.embedding_model
        )
    
    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        try:
            # Create connection pool
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            
            # Create tables
            await self._create_tables()
            
            self.logger.info("Semantic memory database initialized")
            
        except Exception as e:
            self.logger.error("Failed to initialize semantic memory", error=str(e))
            raise BlitzAgentError(f"Semantic memory initialization failed: {e}") from e
    
    async def _create_tables(self) -> None:
        """Create necessary database tables."""
        async with self._pool.acquire() as conn:
            # Enable pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create messages table
            messages_table = f"""
            CREATE TABLE IF NOT EXISTS {self.memory_config.storage.table_name} (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT NOT NULL,
                role VARCHAR(20) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                user_id VARCHAR(255),
                session_id VARCHAR(255),
                thread_id VARCHAR(255),
                resource_id VARCHAR(255),
                metadata JSONB DEFAULT '{{}}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """
            await conn.execute(messages_table)
            
            # Create embeddings table with proper vector type
            embeddings_table = f"""
            CREATE TABLE IF NOT EXISTS {self.memory_config.vector_store.table_name} (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                message_id UUID REFERENCES {self.memory_config.storage.table_name}(id) ON DELETE CASCADE,
                embedding public.vector({self.memory_config.vector_store.dimension}) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """
            await conn.execute(embeddings_table)
            
            # Create indexes
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.memory_config.storage.table_name}_user_id 
                ON {self.memory_config.storage.table_name}(user_id);
            """)
            
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.memory_config.storage.table_name}_session_id 
                ON {self.memory_config.storage.table_name}(session_id);
            """)
            
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.memory_config.storage.table_name}_resource_id 
                ON {self.memory_config.storage.table_name}(resource_id);
            """)
            
            # Create vector similarity index
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.memory_config.vector_store.table_name}_embedding 
                ON {self.memory_config.vector_store.table_name} 
                USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
            """)
    
    async def store_message(
        self,
        content: str,
        role: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a message and its embedding."""
        if not self.memory_config.enabled:
            return ""
        
        try:
            # Generate embedding
            embedding = await self._generate_embedding(content)
            
            async with self._pool.acquire() as conn:
                # Insert message
                message_id = await conn.fetchval(f"""
                    INSERT INTO {self.memory_config.storage.table_name} 
                    (content, role, user_id, session_id, thread_id, resource_id, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                """, content, role, user_id, session_id, thread_id, resource_id, json.dumps(metadata or {}))
                
                # Insert embedding - ensure proper vector conversion
                await conn.execute(f"""
                    INSERT INTO {self.memory_config.vector_store.table_name} 
                    (message_id, embedding)
                    VALUES ($1, $2::public.vector)
                """, message_id, str(embedding))
                
                self.logger.debug(
                    "Message stored with embedding",
                    message_id=str(message_id),
                    role=role,
                    user_id=user_id,
                    session_id=session_id
                )
                
                return str(message_id)
                
        except Exception as e:
            self.logger.error("Failed to store message", error=str(e), content=content[:100])
            raise BlitzAgentError(f"Failed to store message: {e}") from e
    
    async def semantic_recall(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        top_k: Optional[int] = None,
        message_range: Optional[int] = None,
        scope: Optional[str] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[SemanticMatch]:
        """Perform semantic recall to find similar messages."""
        if not self.memory_config.enabled or not self.recall_config.enabled:
            return []
        
        # Use config defaults if not provided
        top_k = top_k or self.recall_config.top_k
        message_range = message_range or self.recall_config.message_range
        scope = scope or self.recall_config.scope
        similarity_threshold = similarity_threshold or self.recall_config.similarity_threshold
        
        try:
            start_time = time.time()
            
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            # Build search conditions based on scope
            where_conditions = []
            params = [query_embedding, top_k]
            param_count = 2
            
            if scope == "thread" and thread_id:
                param_count += 1
                where_conditions.append(f"m.thread_id = ${param_count}")
                params.append(thread_id)
            elif scope == "resource" and resource_id:
                param_count += 1
                where_conditions.append(f"m.resource_id = ${param_count}")
                params.append(resource_id)
            elif user_id:
                param_count += 1
                where_conditions.append(f"m.user_id = ${param_count}")
                params.append(user_id)
            
            where_clause = " AND " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Search for similar messages
            async with self._pool.acquire() as conn:
                similarity_results = await conn.fetch(f"""
                    SELECT 
                        m.id, m.content, m.role, m.timestamp, m.user_id, m.session_id, 
                        m.thread_id, m.resource_id, m.metadata,
                        1 - (e.embedding <=> $1::public.vector) as similarity
                    FROM {self.memory_config.storage.table_name} m
                    JOIN {self.memory_config.vector_store.table_name} e ON m.id = e.message_id
                    WHERE 1 - (e.embedding <=> $1::public.vector) >= {similarity_threshold}
                    {where_clause}
                    ORDER BY e.embedding <=> $1::public.vector
                    LIMIT $2
                """, str(query_embedding), *params[1:])
                
                matches = []
                for row in similarity_results:
                    # Create message object
                    message = Message(
                        id=str(row['id']),
                        content=row['content'],
                        role=row['role'],
                        timestamp=row['timestamp'],
                        user_id=row['user_id'],
                        session_id=row['session_id'],
                        thread_id=row['thread_id'],
                        resource_id=row['resource_id'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                    
                    # Get context messages if requested
                    context_messages = []
                    if message_range > 0:
                        context_messages = await self._get_context_messages(
                            conn, message.id, message_range, user_id, session_id, thread_id
                        )
                    
                    matches.append(SemanticMatch(
                        message=message,
                        similarity=float(row['similarity']),
                        context_messages=context_messages
                    ))
                
                duration = (time.time() - start_time) * 1000
                self.logger.info(
                    "Semantic recall completed",
                    query_length=len(query),
                    matches_found=len(matches),
                    duration_ms=duration,
                    scope=scope,
                    top_k=top_k
                )
                
                return matches
                
        except Exception as e:
            self.logger.error("Semantic recall failed", error=str(e), query=query[:100])
            raise BlitzAgentError(f"Semantic recall failed: {e}") from e
    
    async def _get_context_messages(
        self,
        conn: asyncpg.Connection,
        message_id: str,
        message_range: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> List[Message]:
        """Get context messages around a specific message."""
        try:
            # Get message timestamp
            timestamp = await conn.fetchval(f"""
                SELECT timestamp FROM {self.memory_config.storage.table_name} 
                WHERE id = $1
            """, message_id)
            
            if not timestamp:
                return []
            
            # Build context query conditions
            where_conditions = ["m.id != $1"]
            params = [message_id, timestamp, message_range, timestamp, message_range]
            
            if session_id:
                where_conditions.append("m.session_id = $6")
                params.append(session_id)
            elif thread_id:
                where_conditions.append("m.thread_id = $6")
                params.append(thread_id)
            elif user_id:
                where_conditions.append("m.user_id = $6")
                params.append(user_id)
            
            where_clause = " AND ".join(where_conditions)
            
            # Get context messages (before and after)
            context_results = await conn.fetch(f"""
                (
                    SELECT m.id, m.content, m.role, m.timestamp, m.user_id, m.session_id, 
                           m.thread_id, m.resource_id, m.metadata
                    FROM {self.memory_config.storage.table_name} m
                    WHERE {where_clause} AND m.timestamp < $2
                    ORDER BY m.timestamp DESC
                    LIMIT $3
                )
                UNION ALL
                (
                    SELECT m.id, m.content, m.role, m.timestamp, m.user_id, m.session_id, 
                           m.thread_id, m.resource_id, m.metadata
                    FROM {self.memory_config.storage.table_name} m
                    WHERE {where_clause} AND m.timestamp > $4
                    ORDER BY m.timestamp ASC
                    LIMIT $5
                )
                ORDER BY timestamp ASC
            """, *params)
            
            context_messages = []
            for row in context_results:
                context_messages.append(Message(
                    id=str(row['id']),
                    content=row['content'],
                    role=row['role'],
                    timestamp=row['timestamp'],
                    user_id=row['user_id'],
                    session_id=row['session_id'],
                    thread_id=row['thread_id'],
                    resource_id=row['resource_id'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                ))
            
            return context_messages
            
        except Exception as e:
            self.logger.warning("Failed to get context messages", error=str(e))
            return []
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI."""
        try:
            if self.config.model.provider == "azure_openai":
                # Use the Azure embedding deployment
                embedding_deployment = (
                    self.embedding_deployment or 
                    self.recall_config.embedding_model
                )
                response = await self.openai_client.embeddings.create(
                    model=embedding_deployment,
                    input=text
                )
                return response.data[0].embedding
            else:
                # For regular OpenAI
                response = await self.openai_client.embeddings.create(
                    model=self.recall_config.embedding_model,
                    input=text
                )
                return response.data[0].embedding
            
        except Exception as e:
            embedding_model = (
                self.embedding_deployment if self.config.model.provider == "azure_openai" 
                else self.recall_config.embedding_model
            )
            self.logger.error(
                "Failed to generate embedding", 
                error=str(e), 
                provider=self.config.model.provider,
                model=embedding_model
            )
            raise BlitzAgentError(f"Failed to generate embedding: {e}") from e
    
    async def cleanup_old_messages(self) -> int:
        """Clean up old messages based on retention policy."""
        if not self.memory_config.enabled:
            return 0
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(
                days=self.memory_config.storage.max_message_age_days
            )
            
            async with self._pool.acquire() as conn:
                # Delete old messages (embeddings will be cascade deleted)
                deleted_count = await conn.fetchval(f"""
                    DELETE FROM {self.memory_config.storage.table_name}
                    WHERE timestamp < $1
                    RETURNING COUNT(*)
                """, cutoff_date)
                
                self.logger.info(
                    "Cleaned up old messages",
                    deleted_count=deleted_count,
                    cutoff_date=cutoff_date.isoformat()
                )
                
                return deleted_count or 0
                
        except Exception as e:
            self.logger.error("Failed to cleanup old messages", error=str(e))
            return 0
    
    async def get_message_history(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Message]:
        """Get message history with optional filtering."""
        if not self.memory_config.enabled:
            return []
        
        try:
            # Build query conditions
            where_conditions = []
            params = []
            param_count = 0
            
            if user_id:
                param_count += 1
                where_conditions.append(f"user_id = ${param_count}")
                params.append(user_id)
            
            if session_id:
                param_count += 1
                where_conditions.append(f"session_id = ${param_count}")
                params.append(session_id)
            
            if thread_id:
                param_count += 1
                where_conditions.append(f"thread_id = ${param_count}")
                params.append(thread_id)
            
            if resource_id:
                param_count += 1
                where_conditions.append(f"resource_id = ${param_count}")
                params.append(resource_id)
            
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Add limit and offset
            param_count += 1
            params.append(limit)
            param_count += 1
            params.append(offset)
            
            async with self._pool.acquire() as conn:
                results = await conn.fetch(f"""
                    SELECT id, content, role, timestamp, user_id, session_id, 
                           thread_id, resource_id, metadata
                    FROM {self.memory_config.storage.table_name}
                    {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ${param_count - 1} OFFSET ${param_count}
                """, *params)
                
                messages = []
                for row in results:
                    messages.append(Message(
                        id=str(row['id']),
                        content=row['content'],
                        role=row['role'],
                        timestamp=row['timestamp'],
                        user_id=row['user_id'],
                        session_id=row['session_id'],
                        thread_id=row['thread_id'],
                        resource_id=row['resource_id'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    ))
                
                return messages
                
        except Exception as e:
            self.logger.error("Failed to get message history", error=str(e))
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on semantic memory."""
        try:
            if not self._pool:
                return {"status": "unhealthy", "error": "No database connection"}
            
            async with self._pool.acquire() as conn:
                # Test basic connectivity
                await conn.fetchval("SELECT 1")
                
                # Check if tables exist
                tables_exist = await conn.fetchval(f"""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_name IN ('{self.memory_config.storage.table_name}', 
                                        '{self.memory_config.vector_store.table_name}')
                """)
                
                # Get message count
                message_count = await conn.fetchval(f"""
                    SELECT COUNT(*) FROM {self.memory_config.storage.table_name}
                """)
                
                return {
                    "status": "healthy",
                    "tables_exist": tables_exist == 2,
                    "message_count": message_count,
                    "config": {
                        "enabled": self.memory_config.enabled,
                        "semantic_recall": self.recall_config.enabled,
                        "embedding_model": self.recall_config.embedding_model
                    }
                }
                
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._pool:
            await self._pool.close()
            self.logger.info("Semantic memory cleanup completed") 