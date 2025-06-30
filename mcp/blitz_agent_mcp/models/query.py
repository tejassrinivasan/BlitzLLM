"""Query model for SQL queries."""

from typing import Optional, Union
from pydantic import BaseModel, Field, model_validator
from models.connection import Connection


class Query(BaseModel):
    """Query model for both database queries and file queries."""
    
    code: str = Field(default="", description="SQL query string to execute. Must match the SQL dialect of the data source.")
    query: str = Field(default="", description="SQL query string (alias for code). For backward compatibility and ease of use.")
    description: str = Field(default="", description="A clear business-focused description of what the query does including tables and transformations used.")
    connection: Connection = Field(default=None, description="Query data source. If not provided, uses the configured PostgreSQL database.")
    
    @model_validator(mode='after')
    def validate_code_or_query(self):
        """Ensure either code or query is provided, and normalize to code."""
        if not self.code and not self.query:
            raise ValueError("Either 'code' or 'query' must be provided")
        
        # If query is provided but code is not, use query as code
        if self.query and not self.code:
            self.code = self.query
        
        # If code is provided but query is not, set query for consistency
        if self.code and not self.query:
            self.query = self.code
            
        # Auto-generate description if not provided
        if not self.description or self.description == "":
            self.description = f"SQL query execution: {self.code[:100]}{'...' if len(self.code) > 100 else ''}"
            
        return self
    
    @property
    def dialect(self) -> str:
        """Get the SQL dialect based on the connection URL."""
        # For now, assume PostgreSQL
        return "postgresql" 