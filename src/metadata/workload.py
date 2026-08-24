"""Domain types for query pattern extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPatterns:
    """Query patterns extracted from IOMETE activity monitoring logs."""
    column_usage: dict[str, int] | None
    order_by_columns: list[str] | None
    group_by_columns: list[str] | None
    total_queries_analyzed: int
    avg_cpu_time_ns: float = 0.0
    avg_input_bytes: float = 0.0
    scan_queries_analyzed: int = 0  # queries where totalInputBytes > 0


class QueryPatternAdapter(ABC):
    @abstractmethod
    def extract_patterns(self, table_name: str) -> QueryPatterns:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError


class MockQueryPatternAdapter(QueryPatternAdapter):
    def is_available(self) -> bool:
        return True

    def extract_patterns(self, table_name: str) -> QueryPatterns:
        return QueryPatterns(
            column_usage={"customer_id": 100, "order_date": 95, "status": 80},
            order_by_columns=["order_date", "customer_id"],
            group_by_columns=["status", "customer_id"],
            total_queries_analyzed=50,
            avg_cpu_time_ns=50_000_000.0,
            avg_input_bytes=5_000_000.0,
        )
