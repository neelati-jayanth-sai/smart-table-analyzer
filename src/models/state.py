"""State schema for investigations."""

from __future__ import annotations

from typing import Any

from typing_extensions import NotRequired, TypedDict


class KnowledgeReference(TypedDict):
    source: str
    topic_path: str
    version: str
    content: NotRequired[str]


class QueryResultState(TypedDict):
    success: bool
    query: NotRequired[str | None]
    rewritten_query: NotRequired[str | None]
    rows: NotRequired[list[dict[str, Any]] | None]
    schema: NotRequired[list[dict[str, str]] | None]
    row_count: NotRequired[int | None]
    execution_time_ms: NotRequired[int | None]
    error: NotRequired[str | None]


class AnalysisState(TypedDict):
    verdict: str
    exact_result: str
    rationale: str
    evidence_ids: list[str]
    confidence: NotRequired[float | None]
    recommendation: NotRequired[str | None]
    alternatives: NotRequired[list[str]]
    actionable_sql: NotRequired[str | None]
    approved: NotRequired[bool]
    needs_followup: NotRequired[bool]
    followup_question: NotRequired[str | None]
    critic_feedback: NotRequired[str | None]


class FindingState(TypedDict):
    check_num: int
    question: str
    exact_result: str
    verdict: str
    rationale: str
    evidence_ids: list[str]
    confidence: NotRequired[float | None]
    recommendation: NotRequired[str | None]
    alternatives: NotRequired[list[str]]
    validated: bool
    check_type: NotRequired[str | None]
    actionable_sql: NotRequired[str | None]


class InvestigationState(TypedDict):
    investigation_id: int
    table_name: str
    baseline_score: dict[str, Any]
    check_count: int
    max_checks: int
    retry_count: int
    max_retries: int
    step_count: int
    max_steps: int
    status: str
    current_question: NotRequired[str | None]
    current_check_type: NotRequired[str | None]
    current_query: NotRequired[str | None]
    query_result: NotRequired[QueryResultState | None]
    execution_status: NotRequired[str]
    current_analysis: NotRequired[AnalysisState | None]
    knowledge_consulted: NotRequired[list[KnowledgeReference]]
    findings: NotRequired[list[FindingState]]
    asked_questions: NotRequired[list[str]]
    table_metadata: NotRequired[dict[str, Any] | None]
    signals: NotRequired[list[dict[str, Any]]]
    context_usage: NotRequired[dict[str, Any]]  # Track token usage per prompt type
    critic_feedback: NotRequired[str | None]
