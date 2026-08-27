"""LLM tool loop for bounded, read-only evidence retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .evidence_access import EvidenceAccess, fetch_evidence_tool, list_evidence_tool

if TYPE_CHECKING:
    from src.database import InvestigationDb
    from src.query import QueryWorkbench


class AnalystToolRunner:
    """Bounded tool-calling loop for the analysis LLM turn.

    The selected deterministic skill has already executed before this loop.
    The LLM may inspect persisted evidence but cannot start hidden extra checks.
    """

    MAX_EVIDENCE_READS = 6
    MAX_TOOL_TURNS = 3

    def __init__(self, llm, workbench: "QueryWorkbench", db: "InvestigationDb"):
        self.llm = llm
        self.workbench = workbench
        self.db = db
        self.evidence = EvidenceAccess(db)

    def run(self, prompt: str, state: dict[str, Any]) -> dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]
        evidence_reads_used = 0
        response = self.llm.generate(messages, tools=self._available_tools(evidence_reads_used))

        for _ in range(self.MAX_TOOL_TURNS):
            tool_calls = self._recognized_calls(response)
            if not tool_calls:
                return response

            messages.append({"role": "assistant", "content": response.get("content", "")})
            calls_executed = 0
            for call in tool_calls:
                name = call["name"]
                if name in {"list_evidence", "fetch_evidence"} and evidence_reads_used < self.MAX_EVIDENCE_READS:
                    evidence_reads_used += 1
                    summary = self._execute_evidence_tool(name, call, state)
                else:
                    continue
                messages.append({"role": "user", "content": summary})
                calls_executed += 1

            tools = self._available_tools(evidence_reads_used)
            if not calls_executed or not tools:
                return self._final_response(messages)
            response = self.llm.generate(messages, tools=tools)

        return self._final_response(messages)

    def _available_tools(self, evidence_reads_used: int) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        if evidence_reads_used < self.MAX_EVIDENCE_READS:
            tools.extend([list_evidence_tool(), fetch_evidence_tool()])
        return tools

    @staticmethod
    def _recognized_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
        names = {"list_evidence", "fetch_evidence"}
        return [call for call in response.get("tool_calls", []) if call.get("name") in names]

    def _final_response(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        messages.append({
            "role": "user",
            "content": "Provide your final answer now as plain JSON without calling any tool.",
        })
        return self.llm.generate(messages)

    def _execute_evidence_tool(self, name: str, call: dict[str, Any], state: dict[str, Any]) -> str:
        arguments = call.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        if name == "list_evidence":
            return self.evidence.list(state["investigation_id"], arguments)
        return self.evidence.fetch(state["investigation_id"], arguments)
