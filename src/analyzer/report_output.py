"""Report persistence helpers for the analyzer execution path."""

from __future__ import annotations

import logging
from pathlib import Path

from src.reporting import ReportAssembler, ReportWriter
from src.validation import ClaimValidator

logger = logging.getLogger(__name__)


def count_unvalidated(db, investigation_id: int) -> int:
    """Return findings that do not resolve to authoritative evidence."""
    validator = ClaimValidator(db)
    return sum(
        1
        for finding in db.list_findings(investigation_id)
        if not validator.validate(investigation_id, finding).valid
    )


def write_report(
    db, investigation_id: int, output_dir: Path | str | None, output_path: Path | str | None
) -> Path | None:
    """Render a report without allowing rendering failure to lose findings."""
    if output_dir is None and output_path is None:
        return None
    try:
        report = ReportAssembler(db).assemble(investigation_id)
        return ReportWriter(output_dir or Path("reports")).write(report, output_path)
    except Exception:
        logger.exception("Report generation failed; findings remain in the database")
        return None
