"""
Structured output models for BlitzAgent sports analytics responses.

This module defines Pydantic models for structured outputs that ensure
consistent response formats for sports analytics queries.
"""

from typing import List, Literal
from pydantic import BaseModel, Field


class SportsLink(BaseModel):
    """Link information for players, teams, or matchups."""
    type: Literal["player", "team", "matchup"] = Field(
        ..., 
        description="Type of the link: player, team, or matchup"
    )
    name: str = Field(
        ..., 
        description="Name of the player, team, or matchup (for matchups: Away Team @ Home Team)"
    )


class SportsAnalysisResponse(BaseModel):
    """Structured response for sports analytics queries."""
    
    analysis: str = Field(
        ..., 
        description="1-2 sentence powerful response to the user's question. Include any links to webscraped URLs or API endpoint sources in parentheses."
    )
    explanation: str = Field(
        ..., 
        description="Brief explanation of analysis methodology and data sources used"
    )
    links: List[SportsLink] = Field(
        default_factory=list,
        description="Links to related players, teams, or matchups. Empty array if no links are needed."
    ) 