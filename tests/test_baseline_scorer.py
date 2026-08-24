"""Tests for src/calculators/baseline_scorer.py (RC-5).

Tests exercise the score() seam only — no internals.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.calculators.baseline_scorer import score


def _raw(num_data_files=1000, total_data_file_bytes=100_000_000,
         delete_bytes=0, partition_count=5, snapshot_count=10,
         row_count=10_000_000) -> dict:
    return {
        "num_data_files": num_data_files,
        "total_data_file_bytes": total_data_file_bytes,
        "delete_bytes": delete_bytes,
        "partition_count": partition_count,
        "snapshot_count": snapshot_count,
        "row_count": row_count,
        "is_empty": row_count == 0 and num_data_files == 0,
    }


def _wp(avg_cpu_time_ns=0.0, avg_input_bytes=0.0, total_queries=0,
        scan_queries=0, column_usage=None) -> dict:
    return {
        "avg_cpu_time_ns": avg_cpu_time_ns,
        "avg_input_bytes": avg_input_bytes,
        "total_queries_analyzed": total_queries,
        "scan_queries_analyzed": scan_queries,
        "column_usage": column_usage or {},
    }


class TestOutputShape:
    def test_required_top_level_keys(self):
        r = score(_raw())
        for k in ("overall", "weakest", "dimensions"):
            assert k in r, f"Missing key: {k}"

    def test_five_scored_dimensions_present(self):
        dims = score(_raw())["dimensions"]
        for d in ("file_size", "scan_efficiency", "delete_overhead",
                  "manifest_organization", "partition_aware"):
            assert d in dims, f"Missing dimension: {d}"

    def test_raw_metrics_in_dimensions(self):
        dims = score(_raw())["dimensions"]
        for d in ("row_count", "num_data_files", "partition_count",
                  "snapshot_count", "is_empty"):
            assert d in dims, f"Missing raw metric: {d}"

    def test_weakest_is_nonempty_list_of_valid_dims(self):
        valid = {"file_size", "scan_efficiency", "delete_overhead",
                 "manifest_organization", "partition_aware"}
        r = score(_raw())
        assert isinstance(r["weakest"], list) and len(r["weakest"]) >= 1
        for d in r["weakest"]:
            assert d in valid, f"Unknown dim in weakest: {d}"

    def test_weakest_at_most_three_entries(self):
        assert len(score(_raw())["weakest"]) <= 3

    def test_overall_in_valid_range(self):
        r = score(_raw())
        assert 0.0 < r["overall"] <= 100.0


class TestAdaptiveWeighting:
    def test_differs_from_simple_mean(self):
        r = score(_raw(delete_bytes=50_000_000, total_data_file_bytes=100_000_000))
        dims = r["dimensions"]
        scored = ["file_size", "scan_efficiency", "delete_overhead",
                  "manifest_organization", "partition_aware"]
        simple_mean = sum(dims[d] for d in scored) / len(scored)
        assert abs(r["overall"] - simple_mean) > 0.01, (
            "overall equals simple mean — adaptive weighting not applied (RC-5)"
        )

    def test_high_delete_lowers_score(self):
        clean = score(_raw(delete_bytes=0, total_data_file_bytes=100_000_000))
        dirty = score(_raw(delete_bytes=80_000_000, total_data_file_bytes=100_000_000))
        assert dirty["overall"] < clean["overall"]

    def test_high_delete_in_weakest(self):
        r = score(_raw(delete_bytes=80_000_000, total_data_file_bytes=100_000_000))
        assert "delete_overhead" in r["weakest"]

    def test_no_partitions_lowers_score(self):
        assert score(_raw(partition_count=0))["overall"] < score(_raw(partition_count=20))["overall"]


class TestWorkloadEnrichment:
    def test_heavy_cpu_lowers_file_size_score(self):
        ideal_ns = 134_217_728  # ~134ms per 128 MB file at 1 GB/s
        heavy = 1000 * ideal_ns * 20  # 1000 files × 20× ideal
        no_wp = score(_raw(num_data_files=1000))
        # scan_queries=5 activates the has_scan_workload path
        with_wp = score(_raw(num_data_files=1000),
                        query_patterns=_wp(avg_cpu_time_ns=heavy, total_queries=50, scan_queries=5))
        assert with_wp["dimensions"]["file_size"] < no_wp["dimensions"]["file_size"]

    def test_heavy_scan_lowers_scan_efficiency(self):
        tb = 100_000_000
        heavy = score(_raw(total_data_file_bytes=tb),
                      query_patterns=_wp(avg_input_bytes=tb * 0.9, total_queries=50, scan_queries=10))
        light = score(_raw(total_data_file_bytes=tb),
                      query_patterns=_wp(avg_input_bytes=tb * 0.05, total_queries=50, scan_queries=10))
        assert heavy["dimensions"]["scan_efficiency"] < light["dimensions"]["scan_efficiency"]


class TestEdgeCases:
    def test_empty_table_flagged(self):
        r = score(_raw(row_count=0, num_data_files=0))
        assert r["dimensions"]["is_empty"] is True

    def test_empty_table_valid_overall(self):
        r = score(_raw(row_count=0, num_data_files=0))
        assert 0.0 < r["overall"] <= 100.0

    def test_zero_delete_bytes(self):
        r = score(_raw(delete_bytes=0))
        assert r["dimensions"]["delete_overhead"] == 100.0

    def test_no_workload_data_still_produces_score(self):
        r = score(_raw(), query_patterns=None)
        assert r["overall"] > 0


if __name__ == "__main__":
    groups = [TestOutputShape, TestAdaptiveWeighting,
              TestWorkloadEnrichment, TestEdgeCases]
    total = failed = 0
    for cls in groups:
        g = cls()
        for name in [m for m in dir(g) if m.startswith("test_")]:
            total += 1
            try:
                getattr(g, name)()
                print(f"PASS  {cls.__name__}.{name}")
            except Exception as e:
                print(f"FAIL  {cls.__name__}.{name}: {e}")
                failed += 1
    print(f"\n{total - failed}/{total} passed")
    sys.exit(failed)


class TestScoreExplanation:
    """The explanation must reconstruct the score it explains."""

    def test_contributions_sum_to_the_overall_score(self):
        from src.calculators.baseline_scorer import explain_score, score

        baseline = score({"num_data_files": 4000, "total_data_file_bytes": 32_000_000_000,
                          "partition_count": 430, "delete_bytes": 0, "row_count": 1000})
        explanation = explain_score(baseline["dimensions"])
        total = sum(row["contribution"] for row in explanation["rows"])
        assert abs(total - baseline["overall"]) < 0.5, (
            f"contributions {total} must reconstruct the score {baseline['overall']}"
        )

    def test_every_dimension_costs_points_or_none(self):
        from src.calculators.baseline_scorer import explain_score

        explanation = explain_score({"file_size": 50.0, "scan_efficiency": 100.0,
                                     "delete_overhead": 100.0, "manifest_organization": 90.0,
                                     "partition_aware": 100.0})
        assert all(row["impact"] <= 0 for row in explanation["rows"])
        assert explanation["rows"][0]["dimension"] == "file_size", "worst dimension comes first"

    def test_missing_dimensions_yield_an_empty_explanation(self):
        from src.calculators.baseline_scorer import explain_score

        assert explain_score({})["rows"] == []
