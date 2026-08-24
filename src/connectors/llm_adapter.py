"""LLM adapter interface and mock implementation."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any

from src.utils.tokens import Char4TokenCounter


class LLMAdapter(ABC):
    """Seam for LLM providers used by the investigator."""

    @abstractmethod
    def generate(
        self, messages: list[dict[str, str]], tools: list[dict] | None = None
    ) -> dict[str, Any]:
        """Generate an LLM response.

        Returns a dict with at least a 'content' key and optionally 'tool_calls'.
        """
        raise NotImplementedError

    def token_count(self, messages: list[dict]) -> int:
        """Estimate the token count for a message list."""
        return Char4TokenCounter().count_messages(messages)


class MockLLMAdapter(LLMAdapter):
    """Deterministic mock LLM for testing — thread-safe round-robin responses.

    Supports:
    - Round-robin response sequence
    - Call count tracking for retry validation
    - Optional response inspection via get_call_count()
    """

    def __init__(self, responses: list[dict[str, Any]] | None = None):
        self._responses = list(responses) if responses else []
        self._index = 0
        self._lock = threading.Lock()
        self._call_count = 0

    def _next(self) -> dict[str, Any]:
        if not self._responses:
            return {"content": "{}"}
        with self._lock:
            response = self._responses[self._index % len(self._responses)]
            self._index += 1
            self._call_count += 1
        return response

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict] | None = None
    ) -> dict[str, Any]:
        return self._next()

    def get_call_count(self) -> int:
        """Return total number of generate() calls made."""
        return self._call_count

    def reset(self) -> None:
        """Reset index and call count for test isolation."""
        with self._lock:
            self._index = 0
            self._call_count = 0
