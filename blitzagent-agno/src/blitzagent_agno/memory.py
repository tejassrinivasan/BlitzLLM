"""
Memory management for BlitzAgent using PostgreSQL.

This module provides persistent memory capabilities for the agent,
including conversation history, user preferences, and session management.
"""

import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

import asyncpg
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


logger = structlog.get_logger(__name__)


@dataclass
class ConversationEntry:
    """Single conversation entry."""
    id: Optional[int] = None
    user_id: str = ""
    session_id: Optional[str] = None
    message: str = ""
    response: Optional[str] = None
    is_agent_response: bool = False
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class UserSession:
    """User session information."""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any]
    conversation_count: int = 0


class AgentMemory:
    """
    PostgreSQL-based memory system for the agent.
    
    Provides persistent storage for:
    - Conversation history
    - User sessions
    - Agent preferences
    - Contextual memory
    """
    
    def __init__(
        self,
        connection_url: str,
        retention_days: int = 30,
        max_conversations: int = 1000,
        compression_enabled: bool = True,
        pool_size: int = 10,
        max_overflow: int = 20
    ):
        """Initialize the memory system."""
        self.connection_url = connection_url
        self.retention_days = retention_days
        self.max_conversations = max_conversations
        self.compression_enabled = compression_enabled
        
        # Database connection
        self.engine = None
        self.async_session = None
        self.pool = None
        
        # Configuration
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        
        self.logger = logger.bind(component="memory")
    
    async def initialize(self) -> None:
        """Initialize the memory system and create tables."""
        try:
            # Create async engine
            self.engine = create_async_engine(
                self.connection_url.replace("postgresql://", "postgresql+asyncpg://"),
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                echo=False
            )
            
            # Create session factory
            self.async_session = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create connection pool for direct queries
            self.pool = await asyncpg.create_pool(
                self.connection_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Create tables
            await self._create_tables()
            
            # Start cleanup task
            asyncio.create_task(self._cleanup_task())
            
            self.logger.info(
                "Memory system initialized",
                retention_days=self.retention_days,
                max_conversations=self.max_conversations,
                compression_enabled=self.compression_enabled
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize memory system", error=str(e))
            raise
    
    async def _create_tables(self) -> None:
        """Create necessary database tables."""
        create_tables_sql = """
        -- Conversations table
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            session_id VARCHAR(255),
            message TEXT NOT NULL,
            response TEXT,
            is_agent_response BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'
        );
        
        -- User sessions table
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id VARCHAR(255) PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'
        );
        
        -- User preferences table
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id VARCHAR(255) PRIMARY KEY,
            preferences JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Agent context table for long-term memory
        CREATE TABLE IF NOT EXISTS agent_context (
            id SERIAL PRIMARY KEY,
            context_key VARCHAR(255) NOT NULL,
            context_value JSONB NOT NULL,
            user_id VARCHAR(255),
            session_id VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at TIMESTAMP WITH TIME ZONE
        );
        
        -- Conversation summaries for compression
        CREATE TABLE IF NOT EXISTS conversation_summaries (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            session_id VARCHAR(255),
            summary TEXT NOT NULL,
            conversation_count INTEGER DEFAULT 0,
            start_time TIMESTAMP WITH TIME ZONE,
            end_time TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Create indexes separately
        CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_last_activity ON user_sessions(last_activity);
        CREATE INDEX IF NOT EXISTS idx_agent_context_key ON agent_context(context_key);
        CREATE INDEX IF NOT EXISTS idx_agent_context_user_id ON agent_context(user_id);
        CREATE INDEX IF NOT EXISTS idx_summaries_user_id ON conversation_summaries(user_id);
        CREATE INDEX IF NOT EXISTS idx_summaries_session_id ON conversation_summaries(session_id);
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(create_tables_sql)
        
        self.logger.info("Database tables created successfully")
    
    async def store_conversation(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
        response: Optional[str] = None,
        is_agent_response: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Store a conversation entry."""
        try:
            # Generate session_id if not provided
            if not session_id:
                session_id = self._generate_session_id(user_id)
            
            # Prepare metadata
            if metadata is None:
                metadata = {}
            
            # Store conversation
            async with self.pool.acquire() as conn:
                conversation_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (
                        user_id, session_id, message, response, 
                        is_agent_response, metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    user_id, session_id, message, response,
                    is_agent_response, json.dumps(metadata)
                )
                
                # Update session activity
                await self._update_session_activity(conn, user_id, session_id)
            
            self.logger.debug(
                "Conversation stored",
                conversation_id=conversation_id,
                user_id=user_id,
                session_id=session_id,
                is_agent_response=is_agent_response
            )
            
            return conversation_id
            
        except Exception as e:
            self.logger.error(
                "Failed to store conversation",
                error=str(e),
                user_id=user_id,
                session_id=session_id
            )
            raise
    
    async def get_conversation_history(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 10,
        include_summaries: bool = True
    ) -> List[ConversationEntry]:
        """Get conversation history for a user."""
        try:
            async with self.pool.acquire() as conn:
                if session_id:
                    # Get specific session history
                    rows = await conn.fetch(
                        """
                        SELECT id, user_id, session_id, message, response, 
                               is_agent_response, timestamp, metadata
                        FROM conversations
                        WHERE user_id = $1 AND session_id = $2
                        ORDER BY timestamp DESC
                        LIMIT $3
                        """,
                        user_id, session_id, limit
                    )
                else:
                    # Get recent conversations across all sessions
                    rows = await conn.fetch(
                        """
                        SELECT id, user_id, session_id, message, response, 
                               is_agent_response, timestamp, metadata
                        FROM conversations
                        WHERE user_id = $1
                        ORDER BY timestamp DESC
                        LIMIT $2
                        """,
                        user_id, limit
                    )
                
                conversations = []
                for row in rows:
                    metadata = json.loads(row['metadata']) if row['metadata'] else {}
                    conversations.append(ConversationEntry(
                        id=row['id'],
                        user_id=row['user_id'],
                        session_id=row['session_id'],
                        message=row['message'],
                        response=row['response'],
                        is_agent_response=row['is_agent_response'],
                        timestamp=row['timestamp'],
                        metadata=metadata
                    ))
                
                # Include summaries if requested
                if include_summaries and session_id:
                    summaries = await self._get_conversation_summaries(conn, user_id, session_id)
                    # Insert summaries at the beginning (oldest first)
                    for summary in reversed(summaries):
                        conversations.insert(0, ConversationEntry(
                            user_id=user_id,
                            session_id=session_id,
                            message=f"[SUMMARY] {summary['summary']}",
                            is_agent_response=False,
                            timestamp=summary['created_at'],
                            metadata={"type": "summary", "conversation_count": summary['conversation_count']}
                        ))
            
            return conversations
            
        except Exception as e:
            self.logger.error(
                "Failed to get conversation history",
                error=str(e),
                user_id=user_id,
                session_id=session_id
            )
            raise
    
    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[UserSession]:
        """Get user sessions."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT s.session_id, s.user_id, s.created_at, s.last_activity, s.metadata,
                           COUNT(c.id) as conversation_count
                    FROM user_sessions s
                    LEFT JOIN conversations c ON s.session_id = c.session_id
                    WHERE s.user_id = $1
                    GROUP BY s.session_id, s.user_id, s.created_at, s.last_activity, s.metadata
                    ORDER BY s.last_activity DESC
                    LIMIT $2
                    """,
                    user_id, limit
                )
                
                sessions = []
                for row in rows:
                    metadata = json.loads(row['metadata']) if row['metadata'] else {}
                    sessions.append(UserSession(
                        session_id=row['session_id'],
                        user_id=row['user_id'],
                        created_at=row['created_at'],
                        last_activity=row['last_activity'],
                        metadata=metadata,
                        conversation_count=row['conversation_count']
                    ))
                
                return sessions
                
        except Exception as e:
            self.logger.error(
                "Failed to get user sessions",
                error=str(e),
                user_id=user_id
            )
            raise
    
    async def store_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> None:
        """Store user preferences."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO user_preferences (user_id, preferences)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id)
                    DO UPDATE SET 
                        preferences = $2,
                        updated_at = NOW()
                    """,
                    user_id, json.dumps(preferences)
                )
            
            self.logger.debug("User preferences stored", user_id=user_id)
            
        except Exception as e:
            self.logger.error(
                "Failed to store user preferences",
                error=str(e),
                user_id=user_id
            )
            raise
    
    async def get_user_preferences(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get user preferences."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT preferences FROM user_preferences WHERE user_id = $1",
                    user_id
                )
                
                if row:
                    return json.loads(row['preferences'])
                return {}
                
        except Exception as e:
            self.logger.error(
                "Failed to get user preferences",
                error=str(e),
                user_id=user_id
            )
            return {}
    
    async def store_context(
        self,
        context_key: str,
        context_value: Any,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> None:
        """Store agent context for later retrieval."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_context (
                        context_key, context_value, user_id, session_id, expires_at
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    context_key, json.dumps(context_value), user_id, session_id, expires_at
                )
            
            self.logger.debug(
                "Context stored",
                context_key=context_key,
                user_id=user_id,
                session_id=session_id
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to store context",
                error=str(e),
                context_key=context_key
            )
            raise
    
    async def get_context(
        self,
        context_key: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[Any]:
        """Retrieve agent context."""
        try:
            async with self.pool.acquire() as conn:
                conditions = ["context_key = $1"]
                params = [context_key]
                
                if user_id:
                    conditions.append(f"user_id = ${len(params) + 1}")
                    params.append(user_id)
                
                if session_id:
                    conditions.append(f"session_id = ${len(params) + 1}")
                    params.append(session_id)
                
                # Add expiration check
                conditions.append("(expires_at IS NULL OR expires_at > NOW())")
                
                query = f"""
                    SELECT context_value
                    FROM agent_context
                    WHERE {' AND '.join(conditions)}
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                
                row = await conn.fetchrow(query, *params)
                
                if row:
                    return json.loads(row['context_value'])
                return None
                
        except Exception as e:
            self.logger.error(
                "Failed to get context",
                error=str(e),
                context_key=context_key
            )
            return None
    
    async def compress_conversations(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        threshold: int = 50
    ) -> None:
        """Compress old conversations into summaries."""
        if not self.compression_enabled:
            return
        
        try:
            async with self.pool.acquire() as conn:
                # Get conversations that need compression
                conversations = await conn.fetch(
                    """
                    SELECT id, message, response, timestamp
                    FROM conversations
                    WHERE user_id = $1 
                    AND ($2 IS NULL OR session_id = $2)
                    AND timestamp < NOW() - INTERVAL '7 days'
                    ORDER BY timestamp ASC
                    LIMIT $3
                    """,
                    user_id, session_id, threshold
                )
                
                if len(conversations) < threshold:
                    return  # Not enough conversations to compress
                
                # Create summary (this would ideally use an LLM)
                summary = self._create_conversation_summary(conversations)
                
                # Store summary
                await conn.execute(
                    """
                    INSERT INTO conversation_summaries (
                        user_id, session_id, summary, conversation_count,
                        start_time, end_time
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    user_id, session_id, summary, len(conversations),
                    conversations[0]['timestamp'], conversations[-1]['timestamp']
                )
                
                # Delete compressed conversations
                conversation_ids = [c['id'] for c in conversations]
                await conn.execute(
                    "DELETE FROM conversations WHERE id = ANY($1)",
                    conversation_ids
                )
            
            self.logger.info(
                "Conversations compressed",
                user_id=user_id,
                session_id=session_id,
                compressed_count=len(conversations)
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to compress conversations",
                error=str(e),
                user_id=user_id
            )
    
    async def _update_session_activity(
        self,
        conn,
        user_id: str,
        session_id: str
    ) -> None:
        """Update session activity timestamp."""
        await conn.execute(
            """
            INSERT INTO user_sessions (session_id, user_id, last_activity)
            VALUES ($1, $2, NOW())
            ON CONFLICT (session_id)
            DO UPDATE SET last_activity = NOW()
            """,
            session_id, user_id
        )
    
    async def _get_conversation_summaries(
        self,
        conn,
        user_id: str,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Get conversation summaries for a session."""
        rows = await conn.fetch(
            """
            SELECT summary, conversation_count, created_at
            FROM conversation_summaries
            WHERE user_id = $1 AND session_id = $2
            ORDER BY created_at ASC
            """,
            user_id, session_id
        )
        
        return [dict(row) for row in rows]
    
    def _generate_session_id(self, user_id: str) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.utcnow().isoformat()
        data = f"{user_id}_{timestamp}".encode()
        return hashlib.md5(data).hexdigest()[:16]
    
    def _create_conversation_summary(self, conversations: List[Dict[str, Any]]) -> str:
        """Create a summary of conversations (simplified version)."""
        # This is a simple implementation - in production, you'd use an LLM
        total_conversations = len(conversations)
        topics = set()
        
        for conv in conversations:
            # Simple keyword extraction
            words = conv['message'].lower().split()
            for word in words:
                if len(word) > 5:  # Simple heuristic for important words
                    topics.add(word)
        
        main_topics = list(topics)[:5]  # Top 5 topics
        
        return f"Summary of {total_conversations} conversations covering topics: {', '.join(main_topics)}"
    
    async def _cleanup_task(self) -> None:
        """Background task for cleaning up old data."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up expired contexts
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM agent_context WHERE expires_at < NOW()"
                    )
                    
                    # Clean up old conversations beyond retention period
                    cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
                    await conn.execute(
                        "DELETE FROM conversations WHERE timestamp < $1",
                        cutoff_date
                    )
                    
                    # Clean up inactive sessions
                    session_cutoff = datetime.utcnow() - timedelta(days=7)
                    await conn.execute(
                        "DELETE FROM user_sessions WHERE last_activity < $1",
                        session_cutoff
                    )
                
                self.logger.debug("Memory cleanup completed")
                
            except Exception as e:
                self.logger.error("Memory cleanup failed", error=str(e))
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on memory system."""
        try:
            async with self.pool.acquire() as conn:
                # Test database connectivity
                await conn.fetchval("SELECT 1")
                
                # Get basic statistics
                stats = await conn.fetchrow(
                    """
                    SELECT 
                        (SELECT COUNT(*) FROM conversations) as total_conversations,
                        (SELECT COUNT(*) FROM user_sessions) as total_sessions,
                        (SELECT COUNT(*) FROM agent_context) as total_contexts
                    """
                )
                
                return {
                    "status": "healthy",
                    "database": "connected",
                    "statistics": dict(stats)
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.pool:
            await self.pool.close()
        
        if self.engine:
            await self.engine.dispose()
        
        self.logger.info("Memory system cleanup completed") 