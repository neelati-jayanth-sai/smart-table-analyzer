"""Contracts for the registered deterministic Investigator skills."""

from __future__ import annotations

import pytest

from src.investigator.skills import TemplateRenderError, get_skill, registered_check_ids, render


def test_each_registered_skill_has_an_inspectable_template_and_shape():
    for check_id in registered_check_ids():
        skill = get_skill(check_id)
        assert skill and skill.purpose and skill.interpretation
        assert skill.required_inputs == ("table_name",) and skill.failure_policy
        assert skill.template.expected_columns
        query = render(skill, "catalog.schema.orders")
        assert "catalog.schema.orders" in query
        assert "{" not in query and ";" not in query


def test_unknown_check_and_unsafe_table_never_render_sql():
    assert get_skill("SELECT * FROM secrets") is None
    skill = get_skill("file_size")
    assert skill is not None
    with pytest.raises(TemplateRenderError):
        render(skill, "catalog.schema.orders; DROP TABLE x")
