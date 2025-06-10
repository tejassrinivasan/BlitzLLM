import asyncpg
import os
import logging
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
logger = logging.getLogger(__name__)

# Global pool variables
partner_pool: Optional[asyncpg.Pool] = None
baseball_pool: Optional[asyncpg.Pool] = None

def get_partner_pool() -> Optional[asyncpg.Pool]:
    return partner_pool

def get_baseball_pool() -> Optional[asyncpg.Pool]:
    return baseball_pool

def set_partner_pool(pool: asyncpg.Pool):
    global partner_pool
    partner_pool = pool

def set_baseball_pool(pool: asyncpg.Pool):
    global baseball_pool
    baseball_pool = pool 

async def get_partner_db_pool() -> asyncpg.pool.Pool:
    """Create a connection pool to the partner database."""
    try:
        pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST"),
            port=5432,
            database=os.getenv("PARTNER_DB_NAME"),
            user=os.getenv("PARTNER_DB_USER"),
            password=os.getenv("PARTNER_DB_PASSWORD"),
            ssl="require",
            command_timeout=60,
            timeout=30,
            max_inactive_connection_lifetime=300.0,
            min_size=1,
            max_size=10,
        )
        logger.info("Successfully created partner database pool")
        return pool
    except Exception as exc:
        logger.exception("Partner database pool creation failed: %s", exc)
        raise

async def get_baseball_db_pool() -> asyncpg.pool.Pool:
    """Create a connection pool to the baseball database."""
    try:
        pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST"),
            port=5432,
            database=os.getenv("MLB_DB_NAME"),
            user=os.getenv("MLB_DB_USER"),
            password=os.getenv("MLB_DB_PASSWORD"),
            ssl="require",
            command_timeout=60,
            timeout=30,
            max_inactive_connection_lifetime=300.0,
            min_size=1,
            max_size=10,
        )
        logger.info("Successfully created baseball database pool")
        return pool
    except Exception as exc:
        logger.exception("Baseball database pool creation failed: %s", exc)
        raise
