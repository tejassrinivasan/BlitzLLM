"""Database models and enums."""

from enum import Enum


class MatchMode(str, Enum):
    """Matching modes for table scanning."""
    REGEX = "regex"
    BM25 = "bm25"
    JARO_WINKLER = "jaro_winkler"
    JACCARD = "jaccard" 