"""Write a rendered report to disk with its JSON sidecar."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from src.models import InvestigationReport

from .markdown import render_markdown


class ReportWriter:
    def __init__(self, output_dir: Path | str):
        self.output_dir = Path(output_dir)

    def write(
        self, report: InvestigationReport, output_path: Path | str | None = None
    ) -> Path:
        path = Path(output_path) if output_path else self.output_dir / _default_name(report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report), encoding="utf-8")
        path.with_suffix(".json").write_text(
            json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8"
        )
        return path


def _default_name(report: InvestigationReport) -> str:
    table = re.sub(r"[^A-Za-z0-9]+", "_", report.table_name)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"investigation_{report.run_id}_{table}_{stamp}.md"
