"""LLM tool loop letting the Analyst fire additional read-only queries."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.models.state import QueryResultState
from src.investigator.knowledge import run_query_tool

if TYPE_CHECKING:
    from src.database import InvestigationDb
    from src.query import QueryWorkbench


class AnalystToolRunner:
    """Bounded tool-calling loop for the analysis LLM turn.

    Allows the LLM to request up to MAX_ADDITIONAL_QUERIES extra read-only
    Spark queries before it must commit to a final JSON answer. The final
    LLM call is always made without `tools`, forcing plain-content output.
    """

    MAX_ADDITIONAL_QUERIES = 2

    def __init__(self, llm, workbench: "QueryWorkbench", db: "InvestigationDb"):
        self.llm = llm
        self.workbench = workbench
        self.db = db

    def run(self, prompt: str, state: dict[str, Any]) -> dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]
        response = self.llm.generate(messages, tools=[run_query_tool()])

        queries_used = 0
        for _ in range(self.MAX_ADDITIONAL_QUERIES):
            tool_calls = [c for c in response.get("tool_calls", []) if c.get("name") == "run_query"]
            if not tool_calls:
                return response

            messages.append({"role": "assistant", "content": response.get("content", "")})
            for call in tool_calls:
                if queries_used >= self.MAX_ADDITIONAL_QUERIES:
                    break
                queries_used += 1
                summary = self._execute_tool_query(call, state)
                messages.append({"role": "user", "content": summary})

            if queries_used >= self.MAX_ADDITIONAL_QUERIES:
                break

            remaining = self.MAX_ADDITIONAL_QUERIES - queries_used
            tools = [run_query_tool()] if remaining > 0 else None
            response = self.llm.generate(messages, tools=tools)

        # Force a final, tool-free answer if the last response still wants tools.
        if [c for c in response.get("tool_calls", []) if c.get("name") == "run_query"]:
            messages.append({
                "role": "user",
                "content": (
                    "You have used the maximum number of additional queries. "
                    "Provide your final answer now as plain JSON without calling any tool."
                ),
            })
            response = self.llm.generate(messages)
        return response

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
