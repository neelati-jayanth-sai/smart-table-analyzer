"""Turn a query result into a draft finding."""

from __future__ import annotations

from src.context import PromptProfile
from src.investigator.critic import confidence_for
from src.investigator.prompts import build_analysis_prompt
from src.investigator.state import InvestigationState, validate_state
from src.models.state import AnalysisState

from ._logging import _logged
from .serialization import to_str, to_str_or_none


class ResultAnalysis:
    """Mixin: the Analyst turn, bounded by AnalystToolRunner."""

    @_logged
    def analyze_query_result(self, state: InvestigationState) -> InvestigationState:
        validate_state(state)
        prompt_context = self.context_engine.render(PromptProfile.ANALYSIS, state)
        prompt = build_analysis_prompt(prompt_context, state)
        response = self.analyst_tools.run(prompt, state)
        content = response.get("content", "")
        is_valid, error_msg, parsed = self.validator.validate_analysis_response(content)
        if not is_valid:
            parsed = {"verdict": "inconclusive", "exact_result": content,
                      "rationale": error_msg or "Could not parse LLM response", "evidence_ids": []}
        current_analysis = AnalysisState(
            verdict=str(parsed.get("verdict", "inconclusive")),
            exact_result=to_str(parsed.get("exact_result", "")),
            rationale=to_str(parsed.get("rationale", "")),
            evidence_ids=parsed.get("evidence_ids") or [],
            confidence=confidence_for(parsed, state),
            recommendation=to_str_or_none(parsed.get("recommendation")),
            alternatives=parsed.get("alternatives") or [],
            actionable_sql=to_str_or_none(parsed.get("actionable_sql")),
            needs_followup=bool(parsed.get("needs_followup")),
            followup_question=to_str_or_none(parsed.get("followup_question")),
        )
        return validate_state({**state, "current_analysis": current_analysis})
