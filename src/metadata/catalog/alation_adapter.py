"""Alation catalog context adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TablePatterns:
    """Usage patterns extracted from Alation catalog for a table."""

    common_joins: list[dict[str, Any]]
    common_filters: list[dict[str, Any]]
    downstream_count: int
    upstream_count: int
    stewards: list[str]
    custom_fields: dict[str, Any]
    popular_columns: list[dict[str, Any]]
    partition_columns: list[str] | None
    partition_definition: str | None
    table_comment: str | None
    table_sql: str | None
    table_type: str | None
    base_table_key: str | None


class AlationContextAdapter(ABC):
    """Adapter for retrieving catalog context from Alation."""

    @abstractmethod
    def get_table_patterns(self, table_name: str) -> TablePatterns:
        """Extract usage patterns for a table from Alation catalog."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Check if Alation connection is available."""
        raise NotImplementedError
