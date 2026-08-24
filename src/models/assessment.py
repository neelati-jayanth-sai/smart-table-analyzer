"""Assessment state, kept separate from investigation lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field

ASSESSMENT_VERSION = "deterministic-v1"
ASSESSMENT_STATES = ("clean", "needs_review", "action_required", "incomplete")


@dataclass(frozen=True)
class Assessment:
    """The finalized conclusion a report can present about a table."""

    state: str
    reasons: list[str] = field(default_factory=list)
    required_review_checks: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.state not in ASSESSMENT_STATES:
            raise ValueError(f"Unknown assessment state: {self.state}")
