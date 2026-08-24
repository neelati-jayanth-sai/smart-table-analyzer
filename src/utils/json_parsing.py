"""Parse JSON responses from the LLM."""

from __future__ import annotations

import json
from typing import Any


def parse_json_response(content: str) -> Any | None:
    """Extract JSON from an LLM response, tolerating markdown fences and preceding text."""
    text = (content or "").strip()
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end != -1:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end != -1:
            text = text[start:end].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
