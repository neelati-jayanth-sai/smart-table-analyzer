"""Reporting seam: assemble validated findings, then render them."""

from src.models import InvestigationReport

from .assembler import ReportAssembler
from .markdown import render_markdown
from .pdf_renderer import render_pdf
from .writer import ReportWriter

__all__ = ["InvestigationReport", "ReportAssembler", "ReportWriter", "render_markdown", "render_pdf"]
