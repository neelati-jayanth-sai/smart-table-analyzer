"""Tests for dashboard analysis input and pipeline status events."""

from __future__ import annotations

import pytest

from src.dashboard import AnalysisRequest
from tests.test_investigator_scenarios import build


def test_analysis_request_accepts_a_fully_qualified_table():
    request = AnalysisRequest(table_name="cat.schema.orders")

    assert request.resolved_table() == ("cat", "schema", "cat.schema.orders")


def test_analysis_request_rejects_incomplete_or_unsafe_table_names():
    with pytest.raises(ValueError, match="full catalog.schema.table"):
        AnalysisRequest(table_name="orders").resolved_table()
    with pytest.raises(ValueError, match="full catalog.schema.table"):
        AnalysisRequest(table_name="cat.schema.orders; DROP TABLE x").resolved_table()


def test_analysis_request_uses_full_deep_for_legacy_profile_inputs():
    assert AnalysisRequest(table_name="orders").resolved_metadata_profile() == "deep"
    assert AnalysisRequest(table_name="orders", metadata_profile="shallow").resolved_metadata_profile() == "deep"
    assert AnalysisRequest(table_name="orders", metadata_profile="fast").resolved_metadata_profile() == "deep"
    assert AnalysisRequest(table_name="orders", metadata_profile="deep").resolved_metadata_profile() == "deep"


def test_analysis_request_uses_thorough_check_limit_for_legacy_inputs():
    assert AnalysisRequest(table_name="orders").resolved_max_checks() == 10
    assert AnalysisRequest(table_name="orders", max_checks=1).resolved_max_checks() == 10


def test_pipeline_emits_live_status_updates(tmp_path):
    table, _, _, _, analyzer = build("healthy", tmp_path, max_checks=1)
    updates = []
    analyzer.progress = updates.append

    analyzer.analyze(table.name, "cat", "sch", output_dir=tmp_path / "reports")

    stages = [update.stage for update in updates]
    assert stages[0] == "collecting_metadata"
    assert stages.index("profiling_columns") < stages.index("investigating")
    assert stages.index("investigating") < stages.index("profile_complete")
    assert stages[-2:] == ["rendering_report", "report_complete"]
