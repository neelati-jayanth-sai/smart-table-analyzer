"""LLM tool definitions for knowledge retrieval."""

from __future__ import annotations

from typing import Any


def list_knowledge_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "list_knowledge",
            "description": "List available knowledge entry paths under a source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["iceberg", "iomete", "runbooks"],
                        "description": "Knowledge tree source",
                    },
                    "prefix": {
                        "type": "string",
                        "description": "Optional path prefix filter",
                    },
                },
                "required": ["source"],
            },
        },
    }


def fetch_knowledge_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "fetch_knowledge",
            "description": "Fetch the full text of one knowledge entry by path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["iceberg", "iomete", "runbooks"],
                    },
                    "topic_path": {"type": "string"},
                },
                "required": ["source", "topic_path"],
            },
        },
    }


def run_query_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "run_query",
            "description": (
                "Execute an additional read-only Spark SQL query against the table or its "
                "metadata tables (.files, .partitions, .snapshots, .history) to gather more "
                "evidence before finalizing your analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A single read-only SELECT/SHOW/DESCRIBE statement.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this additional query is needed.",
                    },
                },
                "required": ["sql"],
            },
        },
    }


def all_tools() -> list[dict[str, Any]]:
    return [list_knowledge_tool(), fetch_knowledge_tool(), run_query_tool()]
