"""The execution unit: every node one check passes through.

Composed from one mixin per responsibility so each stage stays readable and
independently testable:

    knowledge -> query -> execution -> analysis -> critic -> compaction
"""

from __future__ import annotations

import logging

from src.context import ContextEngine
from src.database import InvestigationDb
from src.database.knowledge_store import KnowledgeStore
from src.investigator.critic import CriticReview, FindingQualityGate
from src.investigator.knowledge import KnowledgeRetriever, KnowledgeToolRunner
from src.investigator.prompts import ResponseValidator
from src.investigator.state import InvestigationState, validate_state
from src.query import QueryWorkbench

from ._logging import _logged
from .analysis import ResultAnalysis
from .analyst_tools import AnalystToolRunner
from .compaction import FindingCompaction
from .execution import QueryExecution
from .query import QueryGeneration

logger = logging.getLogger(__name__)


class InvestigationNodes(
    QueryGeneration,
    QueryExecution,
    ResultAnalysis,
    CriticReview,
    FindingCompaction,
):
    """Holds the shared collaborators every node needs."""

    def __init__(
        self,
        llm,
        workbench: QueryWorkbench,
        knowledge_store: KnowledgeStore,
        db: InvestigationDb,
        context_engine: ContextEngine,
    ):
        self.llm = llm
        self.workbench = workbench
        self.knowledge = knowledge_store
        self.db = db
        self.context_engine = context_engine
        self.retriever = KnowledgeRetriever(knowledge_store)
        self.tool_runner = KnowledgeToolRunner(llm, knowledge_store, db, context_engine)
        self.analyst_tools = AnalystToolRunner(llm, workbench, db)
        self.validator = ResponseValidator()
        self.quality_gate = FindingQualityGate()

    @_logged
    def fetch_relevant_knowledge(self, state: InvestigationState) -> InvestigationState:
        """Retrieve knowledge for the current check only.

        Knowledge retrieval must never fail a check: the deterministic retriever
        backs up the LLM tool loop, and an empty result is a valid outcome.
        """
        validate_state(state)
        question = state.get("current_question") or ""
        check_type = state.get("current_check_type") or "general"

        try:
            refs = self.tool_runner.run(state)
        except Exception:
            logger.warning(
                "Knowledge tool loop failed; using deterministic retriever",
                exc_info=True,
                extra={"investigation_id": state["investigation_id"]},
            )
            refs = []

        if not refs:
            try:
                refs = self.retriever.search(question, check_type)
                for ref in refs:
                    self.db.record_knowledge_fetch(
                        state["investigation_id"], state["check_count"],
                        ref["source"], ref["topic_path"], ref["version"],
                    )
            except Exception:
                logger.warning(
                    "Knowledge retrieval failed; continuing without it",
                    exc_info=True,
                    extra={"investigation_id": state["investigation_id"]},
                )
                refs = []

        return validate_state({**state, "knowledge_consulted": refs})
