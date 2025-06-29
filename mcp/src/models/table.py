"""Table model for database tables."""

from typing import Optional
from pydantic import BaseModel, Field
from models.connection import Connection


class Table(BaseModel):
    """Database table identifier."""
    
    table_name: str = Field(
        ...,
        description="Database table name (e.g. 'players', 'batting_stats', 'pitchingstatsgame')."
    )
    connection: Connection = Field(default=None, description="Table connection. If not provided, uses the configured PostgreSQL database.") 