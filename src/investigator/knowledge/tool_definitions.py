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


def run_check_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "run_check",
            "description": (
                "Run one registered deterministic diagnostic check. SQL is selected by the "
                "system; never provide SQL or query text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "check_type": {
                        "type": "string",
                        "enum": ["empty_table", "file_size", "skew", "partitioning", "partition_suggestions", "sort", "delete_overhead", "manifest_organization", "snapshot_retention", "table_properties", "scan_efficiency"],
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this additional query is needed.",
                    },
                },
                "required": ["check_type"],
            },
        },
    }


def all_tools() -> list[dict[str, Any]]:
    return [list_knowledge_tool(), fetch_knowledge_tool(), run_check_tool()]
