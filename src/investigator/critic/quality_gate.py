"""Quality gates for investigation findings."""

from typing import Optional
from src.database import Finding


class FindingQualityGate:
    """Validate finding quality before recording."""
    
    PLACEHOLDER_PATTERNS = [
        "could not parse",
        "error",
        "unknown",
        "n/a",
        "not available",
        "failed to",
        "unable to"
    ]
    
    @staticmethod
    def validate(finding: Finding) -> tuple[bool, Optional[str]]:
        """Validate that a finding meets quality standards.
        
        Returns:
            (is_valid, rejection_reason)
        """
        # Reject inconclusive findings
        if finding.verdict == "inconclusive":
            return False, "Finding has inconclusive verdict"
        
        # Require meaningful rationale (at least 20 characters)
        if len(finding.rationale) < 20:
            return False, f"Rationale too short ({len(finding.rationale)} chars)"
        
        # Check for placeholder text in rationale
        if len(finding.rationale) < 100:
            rationale_lower = finding.rationale.lower()
            for pattern in FindingQualityGate.PLACEHOLDER_PATTERNS:
                if pattern in rationale_lower:
                    return False, f"Rationale contains placeholder: '{pattern}'"
        
        # Check for placeholder text in exact_result
        if finding.exact_result:
            if len(str(finding.exact_result)) < 100:
                result_lower = str(finding.exact_result).lower()
                for pattern in FindingQualityGate.PLACEHOLDER_PATTERNS:
                    if pattern in result_lower:
                        return False, f"Exact result contains placeholder: '{pattern}'"
        
        if not finding.evidence_ids:
            return False, "Finding has no evidence IDs"

        return True, None
    
    @staticmethod
    def should_retry(finding: Finding) -> bool:
        """Determine if a failed finding should trigger a retry."""
        # Retry on inconclusive findings
        if finding.verdict == "inconclusive":
            return True
        
        # Retry on validation failures
        is_valid, _ = FindingQualityGate.validate(finding)
        return not is_valid
