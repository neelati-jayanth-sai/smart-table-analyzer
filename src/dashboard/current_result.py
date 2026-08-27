"""Render the current investigation as a human-readable result."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.analyzer import AnalysisOutcome
from src.dashboard.current_result_trust import (
    is_verified_finding,
    verified_findings,
    verified_issue_recommendations,
)
from src.models import InvestigationReport


def render(outcome: AnalysisOutcome, report: InvestigationReport, elapsed_seconds: int) -> None:
    """Render one fresh outcome; recommendations and proof are the main tabs."""
    context, result = outcome.context, outcome.result
    st.subheader(context.table_name)
    if result.status == "completed":
        st.success(f"Analysis complete in {elapsed_seconds}s. The sections below explain what to do and why.")
    else:
        st.warning(f"Analysis finished with status: {result.status.replace('_', ' ')}.")
    _summary(context.baseline, context.signals, report)
    recommendations, issues, proof, setup, run = st.tabs(
        ("Recommendations", "Issues", "Proof", "Table setup", "Run details")
    )
    with recommendations:
        _recommendations(report.findings)
    with issues:
        _issues(context.signals, report.findings)
    with proof:
        _proof(report.findings, report.trail)
    with setup:
        _setup(context.metadata)
    with run:
        _run_details(context, result, elapsed_seconds)


def _summary(baseline: dict[str, Any], signals: list[dict[str, Any]], report: InvestigationReport) -> None:
    score = baseline.get("overall")
    score_complete = baseline.get("score_status", "complete") == "complete"
    high = sum(signal.get("severity") == "HIGH" for signal in signals)
    left, middle, right = st.columns(3)
    left.metric(
        "Health score",
        f"{score:.1f}/100" if score_complete and isinstance(score, (int, float)) else "Not assessed",
    )
    if not score_complete:
        left.caption(str(baseline.get("score_reason") or "Required measurements were incomplete."))
    middle.metric("High-priority issues", str(high))
    right.metric("Verified evidence-backed findings", str(len(verified_findings(report.findings))))


def _recommendations(findings: list[dict[str, Any]]) -> None:
    st.markdown("### What should I do?")
    items = verified_issue_recommendations(findings)
    if not items:
        st.info("This run did not produce a verified action. Review Issues and Proof before changing the table.")
        return
    for finding in items:
        st.markdown(f"**{_title(finding.get('check_type'))}**")
        st.write(finding["recommendation"])
        if finding.get("actionable_sql"):
            st.caption("Suggested SQL — review it against your deployment process before running")
            st.code(finding["actionable_sql"], language="sql")


def _issues(signals: list[dict[str, Any]], findings: list[dict[str, Any]]) -> None:
    st.markdown("### What is the problem?")
    if not signals:
        st.info("No deterministic warning was recorded for this table.")
        return
    for signal in signals:
        name = str(signal.get("name") or "condition")
        title, impact = _signal_copy(name)
        severity = str(signal.get("severity") or "unknown").title()
        with st.expander(f"{severity}: {title}", expanded=severity == "High"):
            st.markdown("**What we found**")
            st.write(signal.get("detail") or "No measurement detail was recorded.")
            st.markdown("**Why it matters**")
            st.write(impact)
            if any(f.get("check_type") == name for f in findings):
                st.caption("The related check and its proof are in the Proof tab.")


def _proof(findings: list[dict[str, Any]], checks: list[dict[str, Any]]) -> None:
    st.markdown("### How do we know?")
    if not findings and not checks:
        st.info("No evidence was recorded.")
        return
    for finding in findings:
        status = "Verified" if is_verified_finding(finding) else "Evidence unavailable / needs review"
        st.markdown(f"**Check {finding.get('check_num', '?')}: {_title(finding.get('question') or finding.get('check_type'))}** · {status}")
        st.write(f"**Question:** {finding.get('question') or 'What did this check measure?'}")
        if is_verified_finding(finding):
            st.write(f"**Measured result:** {finding.get('exact_result') or 'Not recorded.'}")
        else:
            st.write(f"**Measurement status:** {finding.get('rationale') or 'The check could not be verified.'}")
        refs = finding.get("evidence_ids") or []
        st.caption(f"Evidence references: {', '.join(map(str, refs)) or 'none recorded'}")
    for entry in _canonical_trail(checks):
        query = entry.get("rewritten_query") or entry.get("query_text")
        if query:
            state = str(entry.get("execution_status") or "unknown").replace("_", " ")
            st.caption(f"Executed check {entry.get('check_num', '?')} · {state}")
            if entry.get("error"):
                st.error(str(entry["error"]))
            st.code(query, language="sql")


def _canonical_trail(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one authoritative execution per check, preferring success."""
    selected: dict[Any, dict[str, Any]] = {}
    for entry in checks:
        key = entry.get("check_num")
        current = selected.get(key)
        if current is None or (
            entry.get("execution_status") == "success"
            and current.get("execution_status") != "success"
        ):
            selected[key] = entry
    return [selected[key] for key in sorted(selected, key=lambda value: str(value))]


def _setup(metadata: dict[str, Any]) -> None:
    st.markdown("### Table definition used for this run")
    partition = metadata.get("partition_analysis") or {}
    if partition.get("table_ddl"):
        st.caption("DDL observed during metadata collection")
        st.code(partition["table_ddl"], language="sql")
    properties = metadata.get("table_properties") or {}
    warnings = properties.get("caps_warnings") or []
    if warnings:
        st.warning("A property was found with mixed-case spelling. The key may not be effective until it is written with Iceberg's canonical lowercase name.")
        for warning in warnings:
            property_name = str(warning.get("property") or "Not recorded")
            canonical = str(warning.get("canonical_property") or "Not recorded")
            raw_properties = properties.get("raw_properties") or {}
            observed_value = raw_properties.get(property_name, "Not recorded")
            st.table(
                [
                    {"Evidence": "Property found", "Observed value": property_name},
                    {"Evidence": "Correct Iceberg key", "Observed value": canonical},
                    {"Evidence": "Value observed", "Observed value": str(observed_value)},
                ]
            )
            st.caption(
                "Why this matters: the runtime may ignore a non-canonical key. "
                "This evidence identifies the casing problem; it does not by itself prove the setting was ignored."
            )
    st.caption("Properties observed by the collector")
    raw_properties = properties.get("raw_properties") or {}
    if raw_properties:
        st.table(
            [{"Key": str(key), "Value": str(value)} for key, value in raw_properties.items()]
        )
    else:
        st.info("No table properties were returned by the collector.")


def _run_details(context: Any, result: Any, elapsed_seconds: int) -> None:
    st.markdown("### Run details")
    st.write(f"**Status:** {str(result.status).replace('_', ' ').title()}")
    st.write(f"**Elapsed time:** {elapsed_seconds}s")
    st.write(f"**Snapshot:** {getattr(context, 'snapshot_id', None) or 'not recorded'}")
    st.write(f"**Investigation ID:** {getattr(context, 'investigation_id', None) or 'not recorded'}")
    st.write(f"**Evidence references collected:** {len(getattr(context, 'evidence_refs', []))}")
    metadata = getattr(context, "metadata", {})
    st.write(f"**Collection profile:** {metadata.get('collection_profile', 'not recorded')}")
    observation = metadata.get("observation") or {}
    st.write(f"**Observation consistency:** {observation.get('consistency', 'not recorded')}")


def _title(value: Any) -> str:
    return str(value or "Investigation check").replace("_", " ").replace("-", " ").title()


def _signal_copy(name: str) -> tuple[str, str]:
    copies = {
        "small_files": ("Many files are smaller than the target", "Small files add planning and read overhead and can make maintenance jobs more expensive."),
        "undersized_partitions": ("Some partitions are too small", "Small partitions can keep producing small files even when the table has a healthy total size."),
        "table_property_naming": ("A table property uses mixed-case spelling", "The configured key may not match the runtime's canonical property name. Confirm the effective setting before relying on it."),
    }
    return copies.get(name, (_title(name), "The collector recorded this condition; use the measured detail and proof to decide whether it needs action."))
