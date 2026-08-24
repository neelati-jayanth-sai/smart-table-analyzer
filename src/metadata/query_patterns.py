"""IOMETE query log adapter for workload pattern extraction."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import sqlparse

from src.query._schema_grounding_core import _extract_sources

from .workload import QueryPatternAdapter, QueryPatterns


class IOMETEQueryPatternAdapter(QueryPatternAdapter):
    """Queries spark_catalog.iomete_system_db.activity_monitoring_compute_cluster."""

    _LOG_TABLE = "spark_catalog.iomete_system_db.activity_monitoring_compute_cluster"
    _PERF_RE = re.compile(r'(\w+)=(-?\d+)')

    def __init__(self, spark_session, query_log_table: str | None = None):
        self._spark = spark_session
        self._log_table = query_log_table or self._LOG_TABLE

    def is_available(self) -> bool:
        try:
            self._spark.sql(f"SELECT 1 FROM {self._log_table} LIMIT 1").collect()
            return True
        except Exception:
            return False

    def extract_patterns(self, table_name: str) -> QueryPatterns:
        try:
            all_rows = [
                row for row in self._fetch_rows(table_name, scan_only=False)
                if _is_single_target_query(row.sql_text, table_name)
            ]
            # Separate rows that actually scanned storage (totalInputBytes > 0)
            scan_rows = [r for r in all_rows
                         if self._parse_perf(r.performance_metrics).get("totalInputBytes", 0) > 0]
            # Use scan_rows for workload signals; fall back to all_rows for pattern extraction
            workload_rows = scan_rows if len(scan_rows) >= 5 else []
            if len(all_rows) < 5:
                return QueryPatterns(
                    column_usage=None, order_by_columns=None,
                    group_by_columns=None, total_queries_analyzed=len(all_rows),
                )
            sql_texts = [r.sql_text for r in all_rows if r.sql_text]
            perf_list = [self._parse_perf(r.performance_metrics) for r in workload_rows]
            return QueryPatterns(
                column_usage=self._extract_column_usage(sql_texts, table_name),
                order_by_columns=self._extract_order_by(sql_texts, table_name),
                group_by_columns=self._extract_group_by(sql_texts, table_name),
                total_queries_analyzed=len(all_rows),
                avg_cpu_time_ns=self._avg(perf_list, "totalCpuTime"),
                avg_input_bytes=self._avg(perf_list, "totalInputBytes"),
                scan_queries_analyzed=len(workload_rows),
            )
        except Exception:
            return QueryPatterns(
                column_usage=None, order_by_columns=None,
                group_by_columns=None, total_queries_analyzed=0,
            )

    def _fetch_rows(self, table_name: str, scan_only: bool = False) -> list[Any]:
        patterns = [table_name]
        if "." in table_name:
            patterns.append(table_name.split(".")[-1])
        scan_filter = (
            "AND performance_metrics LIKE '%totalInputBytes=%'"
            "AND performance_metrics NOT LIKE '%totalInputBytes=0%'"
        ) if scan_only else ""
        for pat in patterns:
            safe_pattern = _like_literal(pat)
            q = f"""
                SELECT sql_text, performance_metrics
                FROM {self._log_table}
                WHERE sql_text LIKE '%{safe_pattern}%' ESCAPE '\\\\'
                  AND sql_text IS NOT NULL
                  AND sql_text != 'DataFrame operation via Spark Connect'
                  AND completion_date >= date_sub(current_date, 30)
                  AND status = 'COMPLETED'
                  {scan_filter}
                ORDER BY start_time DESC
                LIMIT 1000
            """
            rows = self._spark.sql(q).collect()
            if rows:
                return rows
        return []
    def _parse_perf(self, metrics_str: str | None) -> dict[str, int]:
        if not metrics_str:
            return {}
        return {m.group(1): int(m.group(2)) for m in self._PERF_RE.finditer(metrics_str)}

    def _avg(self, perf_list: list[dict], key: str) -> float:
        vals = [p[key] for p in perf_list if key in p and p[key] > 0]
        return sum(vals) / len(vals) if vals else 0.0

    def _extract_column_usage(self, sql_texts: list[str], table_name: str) -> dict[str, int]:
        counter: Counter = Counter()
        short = table_name.split(".")[-1] if "." in table_name else table_name
        patterns = [rf'{table_name}\.(\w+)', rf'{short}\.(\w+)']
        for sql in sql_texts:
            for pat in patterns:
                for col in re.findall(pat, sql, re.IGNORECASE):
                    counter[col.lower()] += 1
        return dict(counter.most_common(20))

    def _extract_order_by(self, sql_texts: list[str], table_name: str) -> list[str]:
        counter: Counter = Counter()
        short = table_name.split(".")[-1] if "." in table_name else table_name
        patterns = [rf'{table_name}\.(\w+)', rf'{short}\.(\w+)']
        patterns = list(set(patterns))
        for sql in sql_texts:
            m = re.search(r'ORDER BY\s+(.*?)(?:LIMIT|HAVING|$)', sql, re.IGNORECASE | re.DOTALL)
            if m:
                order_by_clause = m.group(1)
                alias_pattern = rf'(?:FROM|JOIN)\s+(?:{re.escape(table_name)}|{re.escape(short)})\s+(?:AS\s+)?(\w+)'
                aliases = set(re.findall(alias_pattern, sql, re.IGNORECASE))
                aliases.add(table_name.lower())
                aliases.add(short.lower())
                
                for alias in aliases:
                    pat = rf'{re.escape(alias)}\.(\w+)'
                    for col in re.findall(pat, order_by_clause, re.IGNORECASE):
                        counter[col.lower()] += 1
                for col in re.findall(r'(\w+)', order_by_clause):
                    if col.upper() not in ('ASC', 'DESC'):
                        col_lower = col.lower()
                        if col_lower in aliases:
                            continue
                        for alias in aliases:
                            if re.search(rf'{re.escape(alias)}\.{re.escape(col_lower)}', sql, re.IGNORECASE):
                                counter[col_lower] += 1
                                break
                        if not re.search(r'\bJOIN\b', sql, re.IGNORECASE):
                            if re.search(rf'\b{re.escape(col_lower)}\b', sql, re.IGNORECASE):
                                counter[col_lower] += 1
        return [c for c, _ in counter.most_common(10)]
    def _extract_group_by(self, sql_texts: list[str], table_name: str) -> list[str]:
        counter: Counter = Counter()
        short = table_name.split(".")[-1] if "." in table_name else table_name
        patterns = [rf'{table_name}\.(\w+)', rf'{short}\.(\w+)']
        patterns = list(set(patterns))
        for sql in sql_texts:
            m = re.search(r'GROUP BY\s+(.*?)(?:ORDER BY|LIMIT|HAVING|$)', sql, re.IGNORECASE | re.DOTALL)
            if m:
                group_by_clause = m.group(1)
                alias_pattern = rf'(?:FROM|JOIN)\s+(?:{re.escape(table_name)}|{re.escape(short)})\s+(?:AS\s+)?(\w+)'
                aliases = set(re.findall(alias_pattern, sql, re.IGNORECASE))
                aliases.add(table_name.lower())
                aliases.add(short.lower())
                
                for alias in aliases:
                    pat = rf'{re.escape(alias)}\.(\w+)'
                    for col in re.findall(pat, group_by_clause, re.IGNORECASE):
                        counter[col.lower()] += 1
                for col in re.findall(r'(\w+)', group_by_clause):
                    col_lower = col.lower()
                    if col_lower in aliases:
                        continue
                    for alias in aliases:
                        if re.search(rf'{re.escape(alias)}\.{re.escape(col_lower)}', sql, re.IGNORECASE):
                            counter[col_lower] += 1
                            break
                    if not re.search(r'\bJOIN\b', sql, re.IGNORECASE):
                        if re.search(rf'\b{re.escape(col_lower)}\b', sql, re.IGNORECASE):
                            counter[col_lower] += 1
        return [c for c, _ in counter.most_common(10)]


def _like_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "''").replace("%", "\\%").replace("_", "\\_")


def _is_single_target_query(sql_text: str | None, table_name: str) -> bool:
    """Accept workload bytes only when one unambiguous target source was scanned."""
    if not sql_text:
        return False
    sources = [
        source
        for statement in sqlparse.parse(sql_text)
        for source, _ in _extract_sources(statement.tokens)
    ]
    target = table_name.casefold().strip("`")
    short = target.split(".")[-1]
    return len(sources) == 1 and sources[0].casefold().strip("`") in {target, short}
