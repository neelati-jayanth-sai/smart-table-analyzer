"""The adaptive investigation loop."""

from .chain import MAX_FOLLOWUPS_PER_CHAIN
from .runner import run_checks_parallel

__all__ = ["MAX_FOLLOWUPS_PER_CHAIN", "run_checks_parallel"]
