"""Investigation orchestrator — the primary reasoning path.

Lifecycle, in order:

    metadata_collected -> planning -> checks_running -> evidence_validated
                       -> completed | failed

`completed` is reserved for investigations that produced at least one
evidence-backed finding. A run whose checks all failed is `failed`, never
`completed` with an empty finding attached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.database import InvestigationDb
from src.query import QueryWorkbench

from .state import StepBudget
from src.context import ContextEngine, InvestigationContext, InvestigationContextEngine
from .executors import InvestigationNodes
from .loop import MAX_FOLLOWUPS_PER_CHAIN
from .state import InvestigationState
from .status import final_status as _final_status

logger = logging.getLogger(__name__)


class InvestigationError(Exception):
    """Raised when an investigation cannot complete successfully."""


@dataclass(frozen=True)
class InvestigationResult:
    investigation_id: int
    status: str
    checks_completed: int
    findings: list[dict[str, Any]]
    checks: list[dict[str, Any]]


class Investigator:
    """Plan hypotheses, test them against evidence, and conclude."""

    def __init__(
        self,
        llm,
        workbench: QueryWorkbench,
        knowledge_retrieval,
        db: InvestigationDb,
        db_path: Path | str | None = None,
        max_checks: int = 50,
        max_retries_per_check: int = 3,
        context_engine: ContextEngine | None = None,
        max_workers: int = 1,
    ):
        self.db = db
        self.workbench = workbench
        self.max_checks = max_checks
        self.max_retries = max_retries_per_check
        self.max_workers = max_workers
        self.context_engine = context_engine or InvestigationContextEngine()
        self.nodes = InvestigationNodes(
            llm=llm,
            workbench=workbench,
            knowledge_store=knowledge_retrieval,
            db=db,
            context_engine=self.context_engine,
        )

    def run_investigation(
        self,
        investigation_id: int,
        table_name: str,
        baseline_score: dict[str, Any] | None = None,
        table_metadata: dict[str, Any] | None = None,
        context: InvestigationContext | None = None,
    ) -> InvestigationResult:
        """Run the adaptive investigation loop over an already-collected context.

        Metadata is never re-read here: it arrives on the context (or on
        `table_metadata`) from the Legacy Analyzer's single Spark pass.
        """
        if context is None:
            context = InvestigationContext(
                table_name=table_name,
                metadata=table_metadata or {},
                baseline=baseline_score or {},
                signals=list((baseline_score or {}).get("signals") or []),
            )
        context.investigation_id = investigation_id

        dims = context.baseline.get("dimensions") or {}
        max_checks = 1 if dims.get("is_empty") else self.max_checks
        step_budget = StepBudget(max_checks, self.max_retries)

        # Follow-ups get check numbers past the planned range; the state's
        # max_checks has to leave room for them.
        state_max_checks = max_checks * (1 + MAX_FOLLOWUPS_PER_CHAIN) + 1

        initial_state: InvestigationState = context.to_state(
            investigation_id,
            max_checks=state_max_checks,
            max_retries=self.max_retries,
            max_steps=step_budget.max_steps * (1 + MAX_FOLLOWUPS_PER_CHAIN),
            status="running",
        )

        from .planner import plan_checks

        self.db.set_status(investigation_id, "metadata_collected")

        self.db.set_status(investigation_id, "planning")
        try:
            check_specs = plan_checks(initial_state, max_checks, self.nodes)
        except Exception as exc:
            logger.exception("Hypothesis planning failed", extra={"investigation_id": investigation_id})
            self.db.complete_investigation(investigation_id, "failed")
            raise InvestigationError(
                f"Investigation {investigation_id} could not plan any check: {exc}"
            ) from exc

        if not check_specs:
            self.db.complete_investigation(investigation_id, "failed")
            raise InvestigationError(
                f"Investigation {investigation_id} produced no hypothesis to test"
            )

        self.db.set_status(investigation_id, "checks_running")
        from .loop import run_checks_parallel

        findings = run_checks_parallel(
            self.nodes, initial_state, check_specs, max_workers=self.max_workers
        )
        for finding in findings:
            context.record_finding(dict(finding))

        self.db.set_status(investigation_id, "evidence_validated")

        check_count = len(findings)
        # Nominal 6 nodes per completed check, matching StepBudget's model.
        step_count = check_count * 6
        planned_indices = {idx for idx, _, _ in check_specs}
        produced_indices = {f.get("check_num") for f in findings}
        status = _final_status(
            findings=findings,
            chains_concluded=len(planned_indices & produced_indices),
            chains_planned=len(planned_indices),
            step_count=step_count,
            max_steps=initial_state["max_steps"],
        )

        final_state = {
            **initial_state,
            "findings": findings,
            "check_count": check_count,
            "step_count": step_count,
            "status": status,
        }
        self.db.complete_investigation(investigation_id, status, final_state)
        # The database refuses 'completed' without evidence; report what it stored.
        stored = self.db.get_investigation(investigation_id)
        status = stored.status if stored else status

        logger.info(
            "Investigation finished status=%s checks=%d findings=%d",
            status, len(check_specs), len(findings),
            extra={"investigation_id": investigation_id},
        )

        return InvestigationResult(
            investigation_id=investigation_id,
            status=status,
            checks_completed=len(check_specs),
            findings=[dict(f) for f in findings],
            checks=self.db.list_trail(investigation_id),
        )
