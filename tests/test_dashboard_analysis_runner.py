"""Tests for dashboard analysis input and pipeline status events."""

from __future__ import annotations

import pytest

from src.dashboard import AnalysisRequest
from tests.test_investigator_scenarios import build


def test_analysis_request_accepts_a_fully_qualified_table():
    request = AnalysisRequest(table_name="cat.schema.orders", catalog_name="wrong", schema_name="wrong")

    assert request.resolved_table() == ("cat", "schema", "cat.schema.orders")


def test_analysis_request_constructs_a_table_from_catalog_and_schema():
    request = AnalysisRequest(table_name="orders", catalog_name="cat", schema_name="schema")

    assert request.resolved_table() == ("cat", "schema", "cat.schema.orders")


def test_analysis_request_rejects_an_incomplete_table_location():
    with pytest.raises(ValueError, match="full catalog.schema.table"):
        AnalysisRequest(table_name="orders", catalog_name="cat").resolved_table()


def test_analysis_request_maps_shallow_to_the_fast_collector_profile():
    assert AnalysisRequest(table_name="orders").resolved_metadata_profile() == "fast"
    assert AnalysisRequest(table_name="orders", metadata_profile="deep").resolved_metadata_profile() == "deep"


def test_pipeline_emits_live_status_updates(tmp_path):
    table, _, _, _, analyzer = build("healthy", tmp_path, max_checks=1)
    updates = []
    analyzer.progress = updates.append

    analyzer.analyze(table.name, "cat", "sch", output_dir=tmp_path / "reports")

    assert [update.stage for update in updates] == [
        "collecting_metadata",
        "investigating",
        "rendering_report",
        "report_complete",
    ]
