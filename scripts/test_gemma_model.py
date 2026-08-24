"""Quick test comparing gpt-oss-120b vs gemma-4-e4b-it on Dell AIA Gateway."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv

load_dotenv(repo_root / ".env", override=True)

from src.connectors import DellAIAAdapter


def _call_model(model: str, messages: list[dict], tools: list[dict] | None = None) -> dict:
    os.environ["LLM_MODEL"] = model
    adapter = DellAIAAdapter.from_env()
    return adapter.generate(messages, tools=tools)


def _print_result(label: str, result: dict) -> None:
    print(f"\n=== {label} ===")
    print(f"Content: {result.get('content')[:500]}...")
    print(f"Tool calls: {result.get('tool_calls')}")
    print(f"Keys: {list(result.keys())}")


def main() -> int:
    models = ["gpt-oss-120b", "gemma-4-e4b-it"]
    messages = [
        {
            "role": "user",
            "content": (
                "You are investigating an Iceberg table. "
                "Use the list_knowledge tool to find relevant knowledge, then fetch_knowledge to read it. "
                "Question: How do I check if data files are correctly sized?"
            ),
        }
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_knowledge",
                "description": "List available knowledge entries by topic.",
                "parameters": {
                    "type": "object",
                    "properties": {"topic": {"type": "string"}},
                    "required": ["topic"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_knowledge",
                "description": "Fetch the content of a knowledge entry.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "topic_path": {"type": "string"},
                    },
                    "required": ["source", "topic_path"],
                },
            },
        },
    ]

    simple_messages = [
        {
            "role": "user",
            "content": (
                "Respond with JSON: {\"question\": \"...\", \"check_type\": \"file_size|partitioning|skew|sort\"}"
            ),
        }
    ]

    for model in models:
        print(f"\n\n########## Testing model: {model} ##########")

        # 1. Simple JSON completion
        try:
            result = _call_model(model, simple_messages)
            _print_result("Simple JSON completion", result)
        except Exception as exc:
            print(f"Simple completion failed for {model}: {exc}")
            traceback.print_exc()

        # 2. Tool-call completion
        try:
            result = _call_model(model, messages, tools=tools)
            _print_result("Tool-call completion", result)
        except Exception as exc:
            print(f"Tool-call completion failed for {model}: {exc}")
            traceback.print_exc()

    return 0


if __name__ == "__main__":
    sys.exit(main())
