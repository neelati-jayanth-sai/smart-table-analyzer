"""Deep seam for rendering InvestigationState into PromptContext objects."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from . import summarizers as cm
from src.context.helpers import format_metadata, partition_info, previous_error, weakest_dimensions
from src.models.state import InvestigationState
from src.utils.tokens import TokenCounter, get_token_counter

MAX_PROMPT_TOKENS = int(os.getenv("PROMPT_MAX_TOKENS", "8000"))


class PromptProfile(str, Enum):
    DECIDE = "decide"
    KNOWLEDGE = "knowledge"
    QUERY = "query"
    ANALYSIS = "analysis"


@dataclass(frozen=True)
class PromptContext:
    table_name: str
    baseline_summary: dict[str, Any] = field(default_factory=dict)
    findings_summary: list[dict[str, Any]] = field(default_factory=list)
    check_count: int = 0
    max_checks: int = 0
    current_question: str | None = None
    current_check_type: str | None = None
    metadata_text: str = ""
    partition_info: dict[str, Any] = field(default_factory=dict)
    knowledge_text: str = ""
    previous_error: str = ""
    query_result_summary: dict[str, Any] = field(default_factory=dict)
    knowledge_evidence_ids: list[str] = field(default_factory=list)
    table_properties: dict[str, Any] = field(default_factory=dict)
    column_analysis: dict[str, Any] = field(default_factory=dict)
    partition_analysis: dict[str, Any] = field(default_factory=dict)
    query_patterns: dict[str, Any] = field(default_factory=dict)


class ContextEngine(ABC):
    """Render a profile-specific PromptContext from an InvestigationState."""

    @abstractmethod
    def render(self, profile: PromptProfile, state: InvestigationState) -> PromptContext:
        raise NotImplementedError


_CONTEXT_LEVELS = [
    (3, 3, 2000, 200),
    (2, 2, 1200, 100),
    (1, 1, 600, 50),
    (0, 0, 0, 20),
]


class InvestigationContextEngine(ContextEngine):
    """Adapter that summarizes InvestigationState into profile-specific PromptContext objects."""

    def __init__(self, token_counter: TokenCounter | None = None, max_tokens: int | None = None):
        self._token_counter = token_counter or get_token_counter()
        self._max_tokens = max_tokens or MAX_PROMPT_TOKENS

    def render(self, profile: PromptProfile, state: InvestigationState) -> PromptContext:
        for max_items, max_rows, max_chars, max_total_cols in _CONTEXT_LEVELS:
            context = self._build_context(profile, state, max_items, max_rows, max_chars, max_total_cols)
            if self._fits(context):
                return context
        raise ValueError(f"Cannot render prompt context within {self._max_tokens} token budget")

    def _fits(self, context: PromptContext) -> bool:
        payload = {
            "table_name": context.table_name,
            "baseline_summary": context.baseline_summary,
            "findings_summary": context.findings_summary,
            "current_question": context.current_question,
            "current_check_type": context.current_check_type,
            "metadata_text": context.metadata_text,
            "partition_info": context.partition_info,
            "knowledge_text": context.knowledge_text,
            "previous_error": context.previous_error,
            "query_result_summary": context.query_result_summary,
            "knowledge_evidence_ids": context.knowledge_evidence_ids,
            "table_properties": context.table_properties,
            "column_analysis": context.column_analysis,
            "partition_analysis": context.partition_analysis,
            "query_patterns": context.query_patterns,
        }
        return self._token_counter.count(json.dumps(payload, default=str)) <= self._max_tokens

    def _build_context(
        self,
        profile: PromptProfile,
        state: InvestigationState,
        max_items: int,
        max_rows: int,
        max_chars: int,
        max_total_cols: int,
    ) -> PromptContext:
        table_name = state.get("table_name") or ""
        baseline = state.get("baseline_score") or {}
        metadata = state.get("table_metadata")
        pinfo = partition_info(metadata, baseline)
        check_count = state.get("check_count", 0)
        max_checks = state.get("max_checks", 0)
        current_question = state.get("current_question") or ""
        current_check_type = state.get("current_check_type") or "general"
        baseline_summary = {
            "overall": baseline.get("overall", "N/A"),
            "weakest": weakest_dimensions(baseline.get("dimensions") or {}, 3),
            "is_empty": (baseline.get("dimensions") or {}).get("is_empty", False),
            "row_count": (baseline.get("dimensions") or {}).get("row_count", 0),
            "num_data_files": (baseline.get("dimensions") or {}).get("num_data_files", 0),
        }
        findings_summary = cm.summarize_findings(state.get("findings", []), max_items)
        query_result_summary = cm.summarize_query_result(state.get("query_result"), max_rows)
        knowledge_refs = state.get("knowledge_consulted", [])
        knowledge_text = cm.prepare_knowledge_context(knowledge_refs, max_chars)
        knowledge_evidence_ids = [
            f"knowledge:{ref['source']}/{ref['topic_path']}@{ref['version']}"
            for ref in knowledge_refs
        ]
        summarized_metadata = cm.summarize_metadata(metadata, max_total_cols)
        metadata_text = format_metadata(table_name, summarized_metadata)
        prev_error = previous_error(state)
        table_properties = metadata.get("table_properties", {}) if metadata else {}
        column_analysis = metadata.get("column_analysis", {}) if metadata else {}
        partition_analysis = metadata.get("partition_analysis", {}) if metadata else {}
        query_patterns = (metadata or {}).get("query_patterns", {}) if metadata else {}

        if profile == PromptProfile.DECIDE:
            return PromptContext(
                table_name=table_name,
                baseline_summary=baseline_summary,
                findings_summary=findings_summary,
                check_count=check_count,
                max_checks=max_checks,
                partition_info=pinfo,
                column_analysis=column_analysis,
                query_patterns=query_patterns,
            )
        if profile == PromptProfile.KNOWLEDGE:
            return PromptContext(
                table_name=table_name,
                current_question=current_question,
                current_check_type=current_check_type,
            )
        if profile == PromptProfile.QUERY:
            return PromptContext(
                table_name=table_name,
                current_question=current_question,
                current_check_type=current_check_type,
                metadata_text=metadata_text,
                partition_info=pinfo,
                knowledge_text=knowledge_text,
                previous_error=prev_error,
                table_properties=table_properties,
                column_analysis=column_analysis,
                partition_analysis=partition_analysis,
                query_patterns=query_patterns,
            )
        if profile == PromptProfile.ANALYSIS:
            return PromptContext(
                table_name=table_name,
                check_count=check_count,
                current_question=current_question,
                current_check_type=current_check_type,
                query_result_summary=query_result_summary,
                knowledge_text=knowledge_text,
                knowledge_evidence_ids=knowledge_evidence_ids,
                column_analysis=column_analysis,
                query_patterns=query_patterns,
            )
        raise ValueError(f"Unknown prompt profile: {profile}")
