"""Deterministic collection and the top-level analysis pipeline."""

from .legacy_analyzer import LegacyAnalyzer
from .metrics import MetadataUnavailable
from .pipeline import AnalysisOutcome, SmartTableAnalyzer
from .signals import detect_signals

__all__ = [
    "AnalysisOutcome",
    "LegacyAnalyzer",
    "MetadataUnavailable",
    "SmartTableAnalyzer",
    "detect_signals",
]
