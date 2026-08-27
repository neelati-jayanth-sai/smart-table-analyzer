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
        reconciliation: bool = False,
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

        from .selection import select_next_check

        self.db.set_status(investigation_id, "metadata_collected")
        self.db.set_status(investigation_id, "planning")
        self.db.set_status(investigation_id, "checks_running")
        from .loop import run_checks_parallel
        findings: list[dict[str, Any]] = []
        used: set[str] = set(context.completed_checks)
        selected_indices: list[int] = []
        start_index = len(context.findings)
        for index in range(start_index, start_index + max_checks):
            state = {**initial_state, "findings": findings, "check_count": index}
            choice = select_next_check(self.nodes, state, used, fallback=not reconciliation)
            if choice is None:
                break
            check_type, question = choice
            used.add(check_type)
            selected_indices.append(index)
            findings.extend(run_checks_parallel(
                self.nodes, state, [(index, check_type, question)], max_workers=1
            ))
        if not selected_indices:
            if start_index:
                stored = self.db.get_investigation(investigation_id)
                return InvestigationResult(
                    investigation_id=investigation_id,
                    status=stored.status if stored else "completed",
                    checks_completed=0,
                    findings=[], checks=self.db.list_trail(investigation_id),
                )
            self.db.complete_investigation(investigation_id, "failed")
            raise InvestigationError(f"Investigation {investigation_id} selected no registered checks")
        for finding in findings:
            context.record_finding(dict(finding))

        self.db.set_status(investigation_id, "evidence_validated")

        check_count = len(findings)
        # Nominal 6 nodes per completed check, matching StepBudget's model.
        step_count = check_count * 6
        planned_indices = set(selected_indices)
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
            "check_count": start_index + check_count,
            "step_count": step_count,
            "status": status,
        }
        self.db.complete_investigation(investigation_id, status, final_state)
        # The database refuses 'completed' without evidence; report what it stored.
        stored = self.db.get_investigation(investigation_id)
        status = stored.status if stored else status

        logger.info(
            "Investigation finished status=%s checks=%d findings=%d",
            status, len(selected_indices), len(findings),
            extra={"investigation_id": investigation_id},
        )

        return InvestigationResult(
            investigation_id=investigation_id,
            status=status,
            checks_completed=len(selected_indices),
            findings=[dict(f) for f in findings],
            checks=self.db.list_trail(investigation_id),
        )
