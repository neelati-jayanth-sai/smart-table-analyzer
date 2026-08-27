"""Regression tests for evidence measurements at production and fixture scales."""

from src.analyzer.signals import detect_signals
from src.utils import human_bytes


def test_human_bytes_preserves_sub_megabyte_measurements():
    assert human_bytes(3_542) == "3.5 KB"
    assert human_bytes(20_000) == "20 KB"
    assert human_bytes(134_217_728) == "134.2 MB"


def test_small_file_signal_cites_fixture_scale(monkeypatch):
    monkeypatch.setenv("STA_TARGET_FILE_BYTES", "20000")
    signals = detect_signals(
        {"num_data_files": 24, "total_data_file_bytes": 85_008}, {}, None
    )
    detail = next(signal["detail"] for signal in signals if signal["name"] == "small_files")
    assert detail == "Average data file is 3.5 KB against a 20 KB target"
