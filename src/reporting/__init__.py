"""Reporting seam: assemble validated findings, then render them."""

from src.models import InvestigationReport

from .assembler import ReportAssembler
from .markdown import render_markdown
from .writer import ReportWriter

__all__ = ["InvestigationReport", "ReportAssembler", "ReportWriter", "render_markdown"]
