"""Unavailable combined metadata aggregates never become zero-valued signals."""

from src.analyzer.signals import detect_signals


def test_failed_partition_aggregate_does_not_claim_unpartitioned():
    raw = {"failed_metrics": ["partition_stats"], "partition_count": 0}

    names = {signal["name"] for signal in detect_signals(raw, {}, None)}

    assert "measurement_unavailable" in names
    assert "unpartitioned" not in names
