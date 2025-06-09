from typing import Optional
import asyncpg

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