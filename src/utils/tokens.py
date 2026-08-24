"""Token counting adapters."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class TokenCounter(ABC):
    """Seam for counting tokens in text or message lists."""

    @abstractmethod
    def count(self, text: str) -> int:
        """Return the estimated token count for plain text."""
        raise NotImplementedError

    def count_messages(self, messages: list[dict]) -> int:
        """Return the estimated token count for a list of messages."""
        return self.count(json.dumps(messages, default=str))


class Char4TokenCounter(TokenCounter):
    """Fallback token estimator: one token per four characters."""

    def count(self, text: str) -> int:
        return len(text) // 4


class TiktokenTokenCounter(TokenCounter):
    """ tiktoken-backed token counter."""

    def __init__(self, encoding_name: str = "cl100k_base"):
        import tiktoken

        self._encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        return len(self._encoding.encode(text))


def get_token_counter(model: str | None = None) -> TokenCounter:
    """Return a token counter appropriate for the given model name."""
    if model is None:
        return Char4TokenCounter()
    try:
        import tiktoken
    except ImportError:
        return Char4TokenCounter()

    lowered = model.lower()
    if any(token in lowered for token in ("gpt-4o", "o200k", "o1", "o3")):
        try:
            return TiktokenTokenCounter("o200k_base")
        except KeyError:
            return Char4TokenCounter()
    if any(token in lowered for token in ("gpt-4", "gpt-3.5", "cl100k", "embedding")):
        try:
            return TiktokenTokenCounter("cl100k_base")
        except KeyError:
            return Char4TokenCounter()
    return Char4TokenCounter()
