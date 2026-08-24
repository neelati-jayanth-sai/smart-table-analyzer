"""Error guidance mapping for LLM retry prompts."""

import re
from typing import Dict


ERROR_GUIDANCE: Dict[str, str] = {
    "Statement type": (
        "Your response included explanatory text before/after the SQL. "
        "Return ONLY the SQL query as plain text, no markdown, no JSON wrapper."
    ),
    "Column.*not present": (
        "The column you referenced doesn't exist in the table metadata. "
        "Use only the columns listed in the metadata above."
    ),
    "Forbidden keyword": (
        "Your query contains a write operation (INSERT, UPDATE, DELETE, etc.). "
        "Use only SELECT, SHOW, DESCRIBE, or EXPLAIN."
    ),
    "JSON": (
        "Your response was not valid JSON. Return ONLY a JSON object with the exact schema specified."
    ),
    "not allowed": (
        "Your query was rejected by a safety hook. Ensure it's a read-only SELECT statement "
        "with no write operations or dangerous keywords."
    ),
    "Empty query": (
        "You returned an empty query. Provide a valid SQL SELECT statement."
    ),
}


def get_error_guidance(error_message: str) -> str:
    """Get specific guidance based on error message patterns."""
    if not error_message:
        return ""
    
    for pattern, guidance in ERROR_GUIDANCE.items():
        if re.search(pattern, error_message, re.IGNORECASE):
            return guidance
    
    # Default generic guidance
    return (
        "Review your response and ensure it follows the format specified. "
        "Return only the requested structure without additional commentary."
    )
