"""Tests for evidence enforcement chain (CU-2 and CU-3).

CU-2: run_investigation.py must not fabricate evidence IDs post-investigation.
CU-3: FindingQualityGate must reject findings with empty evidence_ids.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import Finding
from src.investigator.critic import FindingQualityGate


def _make_finding(
    verdict: str = "found",
    rationale: str = "The file count is well above the threshold indicating compaction is needed",
    evidence_ids: list | None = None,
    check_num: int = 0,
) -> Finding:
    return Finding(
        check_num=check_num,
        question="Are files oversized?",
        exact_result="avg_file_size=512MB",
        verdict=verdict,
        rationale=rationale,
        evidence_ids=evidence_ids if evidence_ids is not None else [],
        recommendation="Run compaction",
        alternatives=[],
        validated=False,
        check_type="file_size",
    )


class TestCU3QualityGateRejectsEmptyEvidence:
    """CU-3: FindingQualityGate must not pass findings with no evidence IDs."""

    def test_empty_evidence_ids_rejected(self):
        """A finding with verdict=found but evidence_ids=[] must be rejected."""
        finding = _make_finding(verdict="found", evidence_ids=[])
        is_valid, reason = FindingQualityGate.validate(finding)
        assert not is_valid, (
            "FindingQualityGate passed a finding with empty evidence_ids — "
            "RC-2: the enforcement door is open"
        )
        assert reason is not None
        assert "evidence" in reason.lower(), f"Rejection reason should mention evidence, got: {reason}"

    def test_not_found_with_empty_evidence_ids_rejected(self):
        """verdict=not_found with no evidence is also inadmissible."""
        finding = _make_finding(verdict="not_found", evidence_ids=[])
        is_valid, reason = FindingQualityGate.validate(finding)
        assert not is_valid, "not_found verdict with empty evidence_ids must be rejected"

    def test_finding_with_valid_trail_id_passes(self):
        """A finding with a syntactically correct trail ID must pass."""
        finding = _make_finding(verdict="found", evidence_ids=["trail:0"])
        is_valid, reason = FindingQualityGate.validate(finding)
        assert is_valid, f"Valid finding with trail:0 was rejected: {reason}"

    def test_finding_with_knowledge_id_passes(self):
        """A finding with a knowledge evidence ID must pass."""
        finding = _make_finding(
            verdict="found",
            evidence_ids=["knowledge:iceberg/file-sizing-best-practices@abc123"],
        )
        is_valid, reason = FindingQualityGate.validate(finding)
        assert is_valid, f"Valid finding with knowledge ID was rejected: {reason}"

    def test_inconclusive_still_rejected_regardless_of_evidence(self):
        """inconclusive verdict is always rejected — evidence IDs don't change that."""
        finding = _make_finding(verdict="inconclusive", evidence_ids=["trail:0"])
        is_valid, reason = FindingQualityGate.validate(finding)
        assert not is_valid
        assert "inconclusive" in (reason or "").lower()

    def test_short_rationale_still_rejected(self):
        """Empty evidence check must not mask the existing rationale-length check."""
        finding = _make_finding(verdict="found", rationale="Too short", evidence_ids=["trail:0"])
        is_valid, reason = FindingQualityGate.validate(finding)
        assert not is_valid
        assert "rationale" in (reason or "").lower() or "short" in (reason or "").lower()


if __name__ == "__main__":
    t = TestCU3QualityGateRejectsEmptyEvidence()
    tests = [
        t.test_empty_evidence_ids_rejected,
        t.test_not_found_with_empty_evidence_ids_rejected,
        t.test_finding_with_valid_trail_id_passes,
        t.test_finding_with_knowledge_id_passes,
        t.test_inconclusive_still_rejected_regardless_of_evidence,
        t.test_short_rationale_still_rejected,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as e:
            print(f"FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(failed)
