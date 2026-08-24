"""Regression tests for case-sensitive Iceberg table-property collection."""

from __future__ import annotations

from src.analyzer.signals import detect_signals
from src.metadata.properties import load_table_properties
from src.models import ASSESSMENT_VERSION
from src.reporting.assessment_policy import assess
from tests.mocks import MockSpark
from tests.mocks.iceberg import caps_properties_table, healthy_table


def _signals(properties: dict) -> list[dict]:
    return detect_signals(
        {"num_data_files": 2, "total_data_file_bytes": 256 * 1024 * 1024},
        {"table_properties": properties},
        None,
    )


def test_mis_cased_known_property_is_not_effective_and_is_high_risk():
    table = caps_properties_table()
    properties = load_table_properties(MockSpark(table), table.name)

    assert "Write.Target-File-Size-Bytes" in properties["raw_properties"]
    assert properties["properties"]["write.target-file-size-bytes"] == str(128 * 1024 * 1024)
    warning = properties["caps_warnings"][0]
    assert warning["canonical_property"] == "write.target-file-size-bytes"
    assert warning["is_known_configuration"] is True
    assert warning["has_canonical_collision"] is True

    signal = next(signal for signal in _signals(properties) if signal["name"] == "table_property_naming")
    assert signal["severity"] == "HIGH"
    assert signal["metrics"]["collisions"] == ["Write.Target-File-Size-Bytes"]


def test_mis_cased_reserved_property_is_also_checked():
    table = healthy_table()
    table.properties = {"Format-Version": "2"}
    properties = load_table_properties(MockSpark(table), table.name)

    assert properties["properties"] == {}
    assert properties["caps_warnings"][0]["is_known_configuration"] is True
    assert next(signal for signal in _signals(properties) if signal["name"] == "table_property_naming")[
        "severity"
    ] == "HIGH"


def test_ddl_casing_overrides_a_normalized_show_properties_result():
    table = healthy_table()
    ddl = """
        CREATE TABLE cat.sch.orders USING iceberg
        TBLPROPERTIES ('Write.Target-File-Size-Bytes' = '268435456')
    """
    properties = load_table_properties(MockSpark(table), table.name, ddl=ddl)

    assert "Write.Target-File-Size-Bytes" in properties["raw_properties"]
    assert "write.target-file-size-bytes" not in properties["properties"]
    warning = next(
        item for item in properties["caps_warnings"]
        if item["property"] == "Write.Target-File-Size-Bytes"
    )
    assert warning["is_known_configuration"] is True
    assert next(signal for signal in _signals(properties) if signal["name"] == "table_property_naming")[
        "severity"
    ] == "HIGH"


def test_known_casing_risk_requires_report_review():
    table = caps_properties_table()
    properties = load_table_properties(MockSpark(table), table.name)

    assessment = assess(
        "completed",
        {"assessment_version": ASSESSMENT_VERSION, "signals": _signals(properties)},
        [],
        [],
    )

    assert assessment.state == "needs_review"
    assert "may be ignored" in assessment.reasons[0]


def test_mis_cased_custom_property_is_a_low_severity_caution():
    table = healthy_table()
    table.properties = {"Owner.Team": "analytics"}
    properties = load_table_properties(MockSpark(table), table.name)

    assert properties["properties"] == {}
    warning = properties["caps_warnings"][0]
    assert warning["is_known_configuration"] is False
    signals = _signals(properties)
    signal = next(signal for signal in signals if signal["name"] == "custom_property_naming")
    assert signal["severity"] == "LOW"
    assert "table_property_naming" not in {signal["name"] for signal in signals}
