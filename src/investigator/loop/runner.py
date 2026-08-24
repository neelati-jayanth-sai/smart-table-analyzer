"""Fan out the planned hypotheses and collect their findings."""

from __future__ import annotations

import itertools
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from src.models.state import FindingState, InvestigationState

from .chain import _run_chain

if TYPE_CHECKING:
    from ..executors import InvestigationNodes

logger = logging.getLogger(__name__)


class _CheckNumbers:
    """Hand out unique check numbers to follow-ups across concurrent chains."""

    def __init__(self, start: int):
        self._counter = itertools.count(start)
        self._lock = threading.Lock()

    def next(self) -> int:
        with self._lock:
            return next(self._counter)


def run_checks_parallel(
    nodes: "InvestigationNodes",
    state: InvestigationState,
    check_specs: list[tuple[int, str, str]],
    max_workers: int = 1,
) -> list[FindingState]:
    """Run planned hypothesis chains with bounded shared-session concurrency.

    A chain that raises is logged and skipped — one failed hypothesis never ends
    the investigation.
    """
    if not check_specs:
        return []

    numbers = _CheckNumbers(len(check_specs))
    results: dict[int, list[FindingState]] = {}
    t0 = time.monotonic()

    with ThreadPoolExecutor(max_workers=min(max_workers, len(check_specs))) as pool:
        futures = {
            pool.submit(_run_chain, nodes, state, idx, ct, q, numbers): idx
            for idx, ct, q in check_specs
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:
                logger.exception("Chain for check %d raised", idx)
                results[idx] = []

    elapsed = time.monotonic() - t0
    findings = [f for i in sorted(results) for f in results[i]]
    logger.info(
        "%d check(s) produced %d finding(s) in %.1fs",
        len(check_specs), len(findings), elapsed,
    )
    return findings
