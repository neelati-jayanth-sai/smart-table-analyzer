"""Deep metadata profiling contract over the hermetic Iceberg mock."""

from __future__ import annotations

from src.analyzer.legacy_analyzer import LegacyAnalyzer
from src.analyzer.collection_stage import report_core_findings
from src.metadata.collection_profile import MetadataCollectionProfile

from tests.mocks.iceberg import SCENARIOS
from tests.mocks.spark import MockSpark


def test_deep_profiles_every_primitive_column_in_bounded_batches():
    table = SCENARIOS["healthy"]()
    extra_columns = [(f"late_identifier_{index}", "string") for index in range(18)]
    table.columns += extra_columns + [("attributes", "struct<code:string>"), ("payload", "binary")]
    table.column_stats.update({name: (index + 1, 0) for index, (name, _) in enumerate(extra_columns)})
    context = LegacyAnalyzer(
        MockSpark(table), MetadataCollectionProfile.from_name("deep")
    ).collect(table.name)

    analysis = context.metadata["column_analysis"]
    stats = analysis["column_stats"]

    assert context.metadata["collection_contract"]["column_profile"] == (
        "all_primitive_columns_in_bounded_batches"
    )
    assert analysis["total_columns_declared"] == len(table.columns)
    assert analysis["total_columns_analyzed"] == 24
    assert analysis["total_columns_skipped"] == 2
    assert analysis["batch_count"] == 3
    assert stats["late_identifier_17"]["status"] == "completed"
    assert stats["late_identifier_17"]["cardinality"] == 18
    assert stats["attributes"] == {
        "type": "struct<code:string>", "status": "skipped", "skipped": True,
        "reason": "non_primitive_type",
    }


def test_core_collection_makes_profile_status_explicit_before_full_profile():
    table = SCENARIOS["healthy"]()
    analyzer = LegacyAnalyzer(MockSpark(table), MetadataCollectionProfile.from_name("deep"))

    context = analyzer.collect_core(table.name)

    assert context.metadata["column_analysis"] == {"status": "pending_full_profile"}
    completed = analyzer.complete_profile(context)
    assert completed.metadata["column_analysis"]["status"] == "completed"


def test_property_casing_signal_is_rendered_as_a_human_progress_message():
    table = SCENARIOS["table_property_naming"]()
    context = LegacyAnalyzer(MockSpark(table)).collect_core(table.name)
    updates = []

    report_core_findings(lambda stage, message, _: updates.append((stage, message)), context, 1)

    assert any("Iceberg expects 'write.target-file-size-bytes'" in message for _, message in updates)


def test_deep_records_range_hints_without_collecting_raw_distributions():
    table = SCENARIOS["healthy"]()
    context = LegacyAnalyzer(
        MockSpark(table), MetadataCollectionProfile.from_name("deep")
    ).collect(table.name)

    stats = context.metadata["column_analysis"]["column_stats"]

    assert stats["amount"]["distribution_hint"]["kind"] == "range"
    assert stats["region"]["distribution_hint"] == {
        "kind": "not_assessed", "reason": "type_has_no_low_cost_range"
    }


def test_deep_records_each_empty_or_failed_column_explicitly():
    empty = SCENARIOS["empty"]()
    empty_context = LegacyAnalyzer(
        MockSpark(empty), MetadataCollectionProfile.from_name("deep")
    ).collect(empty.name)
    empty_stats = empty_context.metadata["column_analysis"]["column_stats"]
    assert set(empty_stats) == {name for name, _ in empty.columns}
    assert {entry["reason"] for entry in empty_stats.values()} == {"empty_table"}

    failed = SCENARIOS["healthy"]()
    failed.columns += [("late_healthy", "string"), ("late_broken", "string")]
    failed.column_stats.update({"late_healthy": (2, 0), "late_broken": (2, 0)})
    failed_context = LegacyAnalyzer(
        MockSpark(failed, fail_on="late_broken"), MetadataCollectionProfile.from_name("deep")
    ).collect(failed.name)
    failed_stats = failed_context.metadata["column_analysis"]["column_stats"]

    assert failed_stats["late_broken"]["status"] == "failed"
    assert failed_stats["late_healthy"]["status"] == "completed"
    assert failed_context.metadata["column_analysis"]["total_columns_failed"] == 1
