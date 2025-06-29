"""
Data serialization utilities for converting DataFrames and other data structures.
"""

import re
from datetime import datetime
from typing import Any, Dict

import pandas as pd
from openai import AzureOpenAI

from config import MAX_DATA_ROWS, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION

__all__ = ["serialize_response"]


def tokenize(text: str) -> list[str]:
    """Tokenize text by splitting on common separators and filtering empty tokens."""
    return [token.lower() for token in re.split(r"[/._-]+", text) if token]


def get_azure_chat_client() -> AzureOpenAI:
    """Get an Azure Chat OpenAI client."""
    return AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def serialize_response(response: Any) -> Any:
    """Recursively serialize response to handle nested data types."""
    if isinstance(response, dict):
        return {key: serialize_response(value) for key, value in response.items()}
    elif isinstance(response, list):
        return [serialize_response(item) for item in response]
    else:
        return response


def serialize_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """
    Convert a pandas DataFrame to a JSON-serializable response format with pagination.

    Serializes DataFrame data including datetime objects and handles automatic truncation
    when the dataset exceeds MAX_DATA_ROWS.

    Args:
        df: The pandas DataFrame to convert and format

    Returns:
        Dictionary with 'data' (table structure), 'row_count' (total rows), and
        optional 'message' (truncation notice when data is truncated)
    """

    def serialize_value(v: Any) -> Any:
        """Serialize individual values, handling special types like datetime and NaN."""
        # Convert pandas and Python datetime objects to ISO format, handle NaT/NaN
        if pd.isna(v):
            return None
        if isinstance(v, datetime | pd.Timestamp):
            return v.isoformat()
        if isinstance(v, pd.Period):
            return v.asfreq("D").to_timestamp().isoformat()
        elif not hasattr(v, "__dict__"):
            return str(v)
        return v

    # Build rows including index, serializing each cell
    rows_with_indices = []
    for idx, row in df.iterrows():
        serialized_row = [serialize_value(idx)]
        for v in row.tolist():
            serialized_row.append(serialize_value(v))
        rows_with_indices.append(serialized_row)

    columns_with_index = ["index"] + df.columns.tolist()

    # Get total row count
    total_rows = len(rows_with_indices)

    # Handle truncation if needed
    is_truncated = total_rows > MAX_DATA_ROWS
    if is_truncated:
        rows_with_indices = rows_with_indices[:MAX_DATA_ROWS]

    table_data = {
        "type": "table",
        "columns": columns_with_index,
        "rows": rows_with_indices,
    }

    result = {"data": table_data, "row_count": total_rows}

    if is_truncated:
        result["message"] = (
            f"Results truncated to {MAX_DATA_ROWS} rows (showing {MAX_DATA_ROWS} of {total_rows} total rows)"
        )

    return result