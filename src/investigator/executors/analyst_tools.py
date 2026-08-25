"""LLM tool loop for bounded read-only queries and evidence retrieval."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.models.state import QueryResultState
from src.investigator.knowledge import run_query_tool

from .evidence_access import EvidenceAccess, fetch_evidence_tool, list_evidence_tool

if TYPE_CHECKING:
    from src.database import InvestigationDb
    from src.query import QueryWorkbench


class AnalystToolRunner:
    """Bounded tool-calling loop for the analysis LLM turn.

    Allows the LLM to request bounded read-only Spark queries and persisted
    evidence for its current investigation before it commits to JSON output.
    """

    MAX_ADDITIONAL_QUERIES = 2
    MAX_EVIDENCE_READS = 6
    MAX_TOOL_TURNS = 6

    def __init__(self, llm, workbench: "QueryWorkbench", db: "InvestigationDb"):
        self.llm = llm
        self.workbench = workbench
        self.db = db
        self.evidence = EvidenceAccess(db)

    def run(self, prompt: str, state: dict[str, Any]) -> dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]
        queries_used = 0
        evidence_reads_used = 0
        response = self.llm.generate(messages, tools=self._available_tools(queries_used, evidence_reads_used))

        for _ in range(self.MAX_TOOL_TURNS):
            tool_calls = self._recognized_calls(response)
            if not tool_calls:
                return response

            messages.append({"role": "assistant", "content": response.get("content", "")})
            calls_executed = 0
            for call in tool_calls:
                name = call["name"]
                if name == "run_query" and queries_used < self.MAX_ADDITIONAL_QUERIES:
                    queries_used += 1
                    summary = self._execute_tool_query(call, state)
                elif name in {"list_evidence", "fetch_evidence"} and evidence_reads_used < self.MAX_EVIDENCE_READS:
                    evidence_reads_used += 1
                    summary = self._execute_evidence_tool(name, call, state)
                else:
                    continue
                messages.append({"role": "user", "content": summary})
                calls_executed += 1

            tools = self._available_tools(queries_used, evidence_reads_used)
            if not calls_executed or not tools:
                return self._final_response(messages)
            response = self.llm.generate(messages, tools=tools)

        return self._final_response(messages)

    def _available_tools(self, queries_used: int, evidence_reads_used: int) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        if queries_used < self.MAX_ADDITIONAL_QUERIES:
            tools.append(run_query_tool())
        if evidence_reads_used < self.MAX_EVIDENCE_READS:
            tools.extend([list_evidence_tool(), fetch_evidence_tool()])
        return tools

    @staticmethod
    def _recognized_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
        names = {"run_query", "list_evidence", "fetch_evidence"}
        return [call for call in response.get("tool_calls", []) if call.get("name") in names]

    def _final_response(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        messages.append({
            "role": "user",
            "content": "Provide your final answer now as plain JSON without calling any tool.",
        })
        return self.llm.generate(messages)

    def _execute_tool_query(self, call: dict[str, Any], state: dict[str, Any]) -> str:
        args = call.get("arguments", {})
        sql = args.get("sql")
        if not sql:
            return "run_query error: no 'sql' argument provided."

        result = self.workbench.execute_query(sql)
        status = "success" if result.success else "error"
        if result.hook_result and not result.hook_result.is_valid:
            status = "hook_failed"
            self.db.record_hook_violation(
                state["investigation_id"], state["check_count"], sql,
                result.hook_result.hook_name, result.hook_result.error_message,
            )
        qrs = QueryResultState(**{k: getattr(result, k) for k in QueryResultState.__annotations__})
        self.db.record_query(
            state["investigation_id"], state["check_count"], "analyst_tool_query",
            result.query, result.rewritten_query, qrs, status,
            result.execution_time_ms, result.error,
        )

        if not result.success:
            if status == "hook_failed":
                return f"run_query result for `{sql}`: ERROR — {result.error}. (Remember to use the fully-qualified table name: {state['table_name']})"
            return f"run_query result for `{sql}`: ERROR — {result.error}"
        return (
            f"run_query result for `{sql}`: {result.row_count} row(s) — "
            f"{json.dumps(result.rows, default=str)}"
        )

    def _execute_evidence_tool(self, name: str, call: dict[str, Any], state: dict[str, Any]) -> str:
        arguments = call.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        if name == "list_evidence":
            return self.evidence.list(state["investigation_id"], arguments)
        return self.evidence.fetch(state["investigation_id"], arguments)
