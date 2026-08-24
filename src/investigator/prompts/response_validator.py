"""Validate LLM responses against expected schemas."""

import re
from typing import Optional

from src.utils import parse_json_response

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def _strip_fences(content: str) -> str:
    """Remove a surrounding markdown code fence, which LLMs add unprompted."""
    text = content.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    return text


class ResponseValidator:
    """Validate LLM responses and provide specific error messages."""

    @staticmethod
    def validate_query_response(content: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Validate that response contains valid SQL query.
        
        Returns:
            (is_valid, error_message, extracted_sql)
        """
        if not content or not content.strip():
            return False, "Empty response", None
        
        # Try to parse as JSON first (tolerating markdown fences)
        parsed = parse_json_response(content)
        if isinstance(parsed, dict):
            sql = str(parsed.get("sql", "")).strip()
            if sql:
                return True, None, sql
            return False, "JSON missing 'sql' field", None

        # If not JSON, treat as plain SQL
        sql = _strip_fences(content)
        if sql:
            return True, None, sql

        return False, "No valid SQL found", None
    
    @staticmethod
    def validate_analysis_response(content: str) -> tuple[bool, Optional[str], Optional[dict]]:
        """Validate that response contains valid analysis JSON.
        
        Returns:
            (is_valid, error_message, parsed_dict)
        """
        if not content or not content.strip():
            return False, "Empty response", None
        
        parsed = parse_json_response(content)
        if parsed is None:
            return False, "Invalid JSON: could not parse response", None
        if not isinstance(parsed, dict):
            return False, "Response is not a JSON object", None

        required_fields = ["verdict", "exact_result", "rationale"]
        missing = [f for f in required_fields if f not in parsed]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}", None

        valid_verdicts = ["found", "not_found", "inconclusive"]
        if parsed.get("verdict") not in valid_verdicts:
            return False, f"Invalid verdict: {parsed.get('verdict')}", None

        issue_state = parsed.get("issue_state")
        if issue_state is not None and issue_state not in {
            "issue_found", "no_issue_found", "needs_review"
        }:
            return False, f"Invalid issue_state: {issue_state}", None
        expected_state = {
            "found": "issue_found",
            "not_found": "no_issue_found",
            "inconclusive": "needs_review",
        }[parsed["verdict"]]
        if issue_state is not None and issue_state != expected_state:
            return False, "issue_state contradicts verdict", None

        return True, None, parsed

    @staticmethod
    def validate_decide_response(content: str) -> tuple[bool, Optional[str], Optional[dict]]:
        """Validate that response contains valid decision JSON.
        
        Returns:
            (is_valid, error_message, parsed_dict)
        """
        if not content or not content.strip():
            return False, "Empty response", None
        
        parsed = parse_json_response(content)
        if not isinstance(parsed, dict):
            return False, "Invalid JSON: could not parse response", None
        if "question" not in parsed:
            return False, "Missing required field: question", None
        return True, None, parsed
