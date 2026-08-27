"""A scripted LLM that answers by prompt kind.

Round-robin mocks break as soon as checks run concurrently, so this adapter
dispatches on what the prompt is asking for. Its analysis answers echo the real
numbers from the query result it was given, so findings stay consistent with the
mock Iceberg data instead of being canned strings.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from src.connectors.llm_adapter import LLMAdapter

# Stable markers from src/investigator/prompt_templates/*.txt
_DECIDE = "Decide the single most valuable NEXT question"
_ANALYSIS = "You are analysing the result"
_CRITIC = "reviewing another engineer's draft"

_CHECK_TYPE = re.compile(r"CHECK TYPE:\s*(\S+)")
_TRAIL_ID = re.compile(r'evidence ID "trail:(\d+)"')
_QUERY_RESULT = re.compile(r"QUERY RESULT:\n(.*?)\n\nReference knowledge:", re.DOTALL)
_DRAFT = re.compile(r"DRAFT FINDING:\n(\{.*?\n\})", re.DOTALL)
_PLANNED = re.compile(r'"verdict": "planned"')

class ScriptedLLM(LLMAdapter):
    """Deterministic stand-in for the Investigator's LLM.

    plan            : [(check_type, question), ...] the Investigator selects in
                      order; empty falls back to measured evidence.
    analysis        : callable(check_type, check_num, result) -> dict of
                      overrides merged into the analysis answer.
    critic_approves : whether the Critic approves the draft.
    fail_on         : raise on prompts containing this substring, simulating a
                      gateway outage for one prompt kind.
    """

    def __init__(
        self,
        *,
        table: str = "",
        plan: list[tuple[str, str]] | None = None,
        analysis: Callable[[str, int, dict], dict] | None = None,
        critic_approves: bool = True,
        fail_on: str | None = None,
    ):
        self.table = table
        self.plan = list(plan or [])
        self.analysis = analysis
        self.critic_approves = critic_approves
        self.fail_on = fail_on

        self.calls: list[str] = []
        self.prompts_by_kind: dict[str, list[str]] = {}

    # -------------------------------------------------------------- dispatch

    def generate(self, messages, tools=None) -> dict[str, Any]:
        prompt = messages[-1]["content"]
        self.calls.append(prompt)
        if self.fail_on and self.fail_on in prompt:
            raise RuntimeError("LLM gateway unavailable")

        kind = self._kind(prompt)
        self.prompts_by_kind.setdefault(kind, []).append(prompt)
        return getattr(self, f"_{kind}")(prompt)

    @staticmethod
    def _kind(prompt: str) -> str:
        if _DECIDE in prompt:
            return "decide"
        if _ANALYSIS in prompt:
            return "analysis"
        if _CRITIC in prompt:
            return "critic"
        return "knowledge"

    def prompts(self, kind: str) -> list[str]:
        return self.prompts_by_kind.get(kind, [])

    # --------------------------------------------------------------- answers

    def _decide(self, prompt: str) -> dict[str, Any]:
        already_planned = len(_PLANNED.findall(prompt))
        if already_planned >= len(self.plan):
            return {"content": ""}
        check_type, question = self.plan[already_planned]
        return {"content": json.dumps({
            "check_type": check_type,
            "question": question,
            "hypothesis": f"The signals suggest {check_type} is worth testing",
        })}

    def _analysis(self, prompt: str) -> dict[str, Any]:
        check_num = int(_TRAIL_ID.search(prompt).group(1))
        check_type = (_CHECK_TYPE.search(prompt) or _Null()).group(1)
        result = _parse_query_result(prompt)

        # A mock must not claim a problem by default; tests opt in via `analysis`.
        answer = {
            "verdict": "not_found",
            "exact_result": _describe(result),
            "rationale": (
                f"The {check_type} query returned {result.get('row_count', 0)} row(s); "
                f"the measured values are shown in the exact result."
            ),
            "evidence_ids": [f"trail:{check_num}"],
            "confidence": 0.88,
            "recommendation": f"Review {check_type} for {self.table}",
            "alternatives": [],
            "actionable_sql": None,
            "needs_followup": False,
            "followup_question": None,
        }
        if self.analysis:
            answer.update(self.analysis(check_type, check_num, result) or {})
        return {"content": json.dumps(answer, default=str)}

    def _critic(self, prompt: str) -> dict[str, Any]:
        draft = json.loads(_DRAFT.search(prompt).group(1))
        return {"content": json.dumps({
            "verdict": draft.get("verdict", "inconclusive"),
            "exact_result": draft.get("exact_result", ""),
            "rationale": draft.get("rationale", ""),
            "evidence_ids": draft.get("evidence_ids", []),
            "confidence": draft.get("confidence"),
            "recommendation": draft.get("recommendation"),
            "alternatives": draft.get("alternatives", []),
            "actionable_sql": draft.get("actionable_sql"),
            "needs_followup": draft.get("needs_followup", False),
            "followup_question": draft.get("followup_question"),
            "approved": self.critic_approves,
            "feedback": None if self.critic_approves else "Tighten the claim to the evidence",
        }, default=str)}

    def _knowledge(self, prompt: str) -> dict[str, Any]:
        return {"content": "", "tool_calls": []}


class _Null:
    """Stand-in match object so a missing CHECK TYPE degrades to 'general'."""

    @staticmethod
    def group(_index: int) -> str:
        return "general"


def _parse_query_result(prompt: str) -> dict[str, Any]:
    match = _QUERY_RESULT.search(prompt)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _describe(result: dict[str, Any]) -> str:
    """Render the query's real numbers as a Markdown table, as the prompt asks."""
    rows = result.get("rows") or []
    if not rows:
        return "The query returned no rows"
    columns = list(rows[0])
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join(["---"] * len(columns)) + "|"
    body = [
        "| " + " | ".join(_format(row.get(c)) for c in columns) + " |" for row in rows[:5]
    ]
    return "\n".join([header, divider, *body])


def _format(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.1f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)
