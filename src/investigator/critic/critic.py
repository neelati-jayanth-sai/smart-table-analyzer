"""The Critic: an adversarial pass over the Analyst's draft finding."""

from __future__ import annotations

import logging

from src.context import PromptProfile
from src.investigator.prompts import build_critic_prompt
from src.investigator.state import InvestigationState, validate_state
from src.models.state import AnalysisState

from ..executors._logging import _logged
from ..executors.serialization import to_str, to_str_or_none
from .sanitizers import confidence_for, sanitize_actionable_sql

logger = logging.getLogger(__name__)


class CriticReview:
    """Mixin: reject a draft that outruns its evidence, and correct what it can."""

    @_logged
    def review_finding(self, state: InvestigationState) -> InvestigationState:
        validate_state(state)
        draft_finding = state.get("current_analysis")
        if not draft_finding:
            return state

        prompt_context = self.context_engine.render(PromptProfile.ANALYSIS, state)
        from src.investigator.prompts import build_critic_prompt
        response = self.llm.generate(
            [{"role": "user", "content": build_critic_prompt(prompt_context, draft_finding, state)}]
        )
        content = response.get("content", "")
        is_valid, error_msg, parsed = self.validator.validate_analysis_response(content)
        if not is_valid:
            logger.warning("Critic returned invalid JSON, falling back to draft. Error: %s", error_msg)
            return state

        actionable_sql = sanitize_actionable_sql(
            to_str_or_none(parsed.get("actionable_sql")), state.get("table_name")
        )
        draft = dict(draft_finding)
        final_analysis = AnalysisState(
            verdict=str(parsed.get("verdict", "inconclusive")),
            exact_result=to_str(parsed.get("exact_result", "")),
            rationale=to_str(parsed.get("rationale", "")),
            evidence_ids=parsed.get("evidence_ids") or [],
            confidence=confidence_for(parsed, state, fallback=draft.get("confidence")),
            recommendation=to_str_or_none(parsed.get("recommendation")),
            alternatives=parsed.get("alternatives") or [],
            actionable_sql=actionable_sql,
            approved=parsed.get("approved", True),
            needs_followup=bool(parsed.get("needs_followup", draft.get("needs_followup"))),
            followup_question=to_str_or_none(
                parsed.get("followup_question") or draft.get("followup_question")
            ),
            critic_feedback=parsed.get("feedback"),
        )
        return validate_state({**state, "current_analysis": final_analysis})
