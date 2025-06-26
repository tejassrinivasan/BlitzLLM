"""Database models and enums."""

from enum import Enum


class MatchMode(str, Enum):
    """Matching modes for table scanning."""
    REGEX = "regex"
    TF_IDF = "tf_idf"
    JARO_WINKLER = "jaro_winkler"
    JACCARD = "jaccard" 