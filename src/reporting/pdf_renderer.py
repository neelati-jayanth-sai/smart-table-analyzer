"""Render the canonical Markdown investigation report as an in-memory PDF."""

from __future__ import annotations

from io import BytesIO
import re
from typing import Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

from src.models import InvestigationReport

from .markdown import render_markdown


def render_pdf(report: InvestigationReport) -> bytes:
    """Return the same canonical report content as a readable PDF document."""
    return render_markdown_pdf(render_markdown(report), report.table_name)


def render_markdown_pdf(markdown: str, table_name: str) -> bytes:
    """Render the supported Markdown subset emitted by ``render_markdown``."""
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=letter,
        title=f"Investigation Report - {table_name}",
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.65 * inch,
    )
    document.build(list(_flowables(markdown)), onFirstPage=_footer, onLaterPages=_footer)
    return stream.getvalue()


def _flowables(markdown: str) -> Iterable[object]:
    styles = _styles()
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            code, index = _code_block(lines, index + 1)
            yield Preformatted("\n".join(code), styles["code"], maxLineLength=100)
            yield Spacer(1, 8)
            continue
        if line.startswith("#"):
            heading, index = _heading(line, index, styles)
            yield heading
            continue
        if _is_table_start(lines, index):
            table, index = _table(lines, index, styles)
            yield table
            yield Spacer(1, 8)
            continue
        if line.startswith("> "):
            yield Paragraph(_inline(line[2:]), styles["quote"])
        elif line.lstrip().startswith("- "):
            indent = len(line) - len(line.lstrip())
            yield Paragraph(_inline(line.lstrip()[2:]), styles["bullet" if not indent else "nested_bullet"])
        else:
            yield Paragraph(_inline(line.strip()), styles["body"])
        yield Spacer(1, 5)
        index += 1


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("report_title", parent=base["Title"], fontSize=18, leading=22, spaceAfter=12),
        "heading2": ParagraphStyle("report_h2", parent=base["Heading2"], fontSize=14, leading=18, spaceBefore=10),
        "heading3": ParagraphStyle("report_h3", parent=base["Heading3"], fontSize=11, leading=14, spaceBefore=7),
        "body": ParagraphStyle("report_body", parent=base["BodyText"], fontSize=9, leading=12),
        "bullet": ParagraphStyle("report_bullet", parent=base["BodyText"], fontSize=9, leading=12, leftIndent=12, bulletIndent=2),
        "nested_bullet": ParagraphStyle("report_nested_bullet", parent=base["BodyText"], fontSize=9, leading=12, leftIndent=25, bulletIndent=15),
        "quote": ParagraphStyle("report_quote", parent=base["BodyText"], fontSize=9, leading=12, leftIndent=12, textColor=colors.HexColor("#555555")),
        "code": ParagraphStyle("report_code", fontName="Courier", fontSize=7.2, leading=9, leftIndent=8, rightIndent=8, backColor=colors.HexColor("#F4F6F8")),
        "table": ParagraphStyle("report_table", parent=base["BodyText"], fontSize=7.5, leading=9),
    }


def _heading(line: str, index: int, styles: dict[str, ParagraphStyle]) -> tuple[Paragraph, int]:
    level = len(line) - len(line.lstrip("#"))
    style = {1: "title", 2: "heading2"}.get(level, "heading3")
    return Paragraph(_inline(line[level:].strip()), styles[style]), index + 1


def _code_block(lines: list[str], index: int) -> tuple[list[str], int]:
    code: list[str] = []
    while index < len(lines) and not lines[index].startswith("```"):
        code.append(lines[index])
        index += 1
    return code, min(index + 1, len(lines))


def _is_table_start(lines: list[str], index: int) -> bool:
    return index + 1 < len(lines) and lines[index].startswith("|") and _is_table_rule(lines[index + 1])


def _is_table_rule(line: str) -> bool:
    return line.startswith("|") and all(set(cell.strip()) <= {"-", ":"} for cell in _cells(line))


def _table(lines: list[str], index: int, styles: dict[str, ParagraphStyle]) -> tuple[Table, int]:
    rows = [_cells(lines[index])]
    index += 2
    while index < len(lines) and lines[index].startswith("|"):
        rows.append(_cells(lines[index]))
        index += 1
    columns = max(map(len, rows))
    data = [
        [Paragraph(_inline(cell), styles["table"]) for cell in row + [""] * (columns - len(row))]
        for row in rows
    ]
    table = Table(data, repeatRows=1, colWidths=[6.1 * inch / columns] * columns, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E7EEF8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9EADBE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table, index


def _cells(line: str) -> list[str]:
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _inline(text: str) -> str:
    safe = escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    return re.sub(r"`(.+?)`", r'<font name="Courier">\1</font>', safe)


def _footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#536273"))
    canvas.drawString(document.leftMargin, 0.38 * inch, "Smart Table Analyzer - Investigation Report")
    canvas.drawRightString(letter[0] - document.rightMargin, 0.38 * inch, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()
