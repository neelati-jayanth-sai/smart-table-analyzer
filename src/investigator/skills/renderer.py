"""Safely render checked-in SQL templates for deterministic skills."""

from __future__ import annotations

import re
from pathlib import Path

from .models import CheckSkill

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_TEMPLATE_DIR = Path(__file__).with_name("sql")


class TemplateRenderError(ValueError):
    """The check request cannot safely become a query."""


def render(skill: CheckSkill, table_name: str) -> str:
    """Render the declared table placeholder and reject all other substitution."""
    if not _IDENTIFIER.fullmatch(table_name):
        raise TemplateRenderError("table name must be a dotted SQL identifier")
    template = (_TEMPLATE_DIR / skill.template.filename).read_text(encoding="utf-8")
    if template.count("{table_name}") != 1:
        raise TemplateRenderError(f"invalid template {skill.template.identifier}")
    if "{" in template.replace("{table_name}", ""):
        raise TemplateRenderError(f"undeclared placeholder in {skill.template.identifier}")
    return template.format(table_name=table_name).strip()

