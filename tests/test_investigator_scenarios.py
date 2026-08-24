"""Investigator behaviour across realistic mock Iceberg tables.

Each scenario presents one class of problem. The suite asserts that the Legacy
Analyzer detects it, that the Investigator plans *different* checks in response,
that evidence survives hook and Spark failures, and that every finding it emits
carries a rationale, evidence, and a confidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.legacy_analyzer import LegacyAnalyzer
from src.analyzer.pipeline import SmartTableAnalyzer
from src.database import InvestigationDb, KnowledgeStore
from src.investigator.planner import plan_checks
from src.reporting import ReportAssembler
from src.reporting import render_markdown
from src.validation import ClaimValidator
from tests.mocks import SCENARIOS, MockSpark, ScriptedLLM

# scenario name -> the signal the Legacy Analyzer must raise for it
EXPECTED_SIGNAL = {
    "healthy": None,
    "partition_skew": "partition_skew",
    "small_files": "small_files",
    "missing_sort_order": "missing_sort_order",
    "delete_overhead": "delete_overhead",
    "table_property_naming": "table_property_naming",
    "empty": "empty_table",
}

PROBLEM_SCENARIOS = [n for n, s in EXPECTED_SIGNAL.items() if s and n != "empty"]


def build(scenario: str, tmp_path: Path, *, spark=None, llm=None, max_checks=2, max_retries=1):
    """Wire a full pipeline over one mock scenario."""
    table = SCENARIOS[scenario]()
    spark = spark or MockSpark(table)
    llm = llm or ScriptedLLM(table=table.name)
    if not llm.table:
        llm.table = table.name
    db_path = tmp_path / "investigation.db"
    db = InvestigationDb(db_path)
    analyzer = SmartTableAnalyzer(
        spark=spark,
        db=db,
        llm=llm,
        knowledge=KnowledgeStore(db_path, repo_root=tmp_path),
        max_checks=max_checks,
        max_retries=max_retries,
    )
    return table, spark, llm, db, analyzer


def context_for(scenario: str, spark=None):
    table = SCENARIOS[scenario]()
    spark = spark or MockSpark(table)
    return table, LegacyAnalyzer(spark).collect(table.name, "cat", "sch")


def finds(**overrides):
    """An `analysis` hook that reports a confirmed problem."""
    def _analysis(check_type, check_num, result):
        return {"verdict": "found", **overrides}
    return _analysis


# ---------------------------------------------------------------- detection


class TestSignalDetection:
    """The deterministic sensor layer must see the problem, and only that problem."""

    @pytest.mark.parametrize("scenario", list(EXPECTED_SIGNAL))
    def test_expected_signal_fires(self, scenario):
        _, context = context_for(scenario)
        names = {s["name"] for s in context.signals}
        expected = EXPECTED_SIGNAL[scenario]
        if expected is None:
            assert not names, f"healthy table raised spurious signals: {names}"
        else:
            assert expected in names, f"{scenario}: expected {expected}, got {names or 'none'}"

    @pytest.mark.parametrize("scenario", PROBLEM_SCENARIOS)
    def test_other_scenarios_signals_do_not_leak(self, scenario):
        """A skewed table must not also look like a small-files table."""
        _, context = context_for(scenario)
        names = {s["name"] for s in context.signals}
        others = {s for s in EXPECTED_SIGNAL.values() if s and s != EXPECTED_SIGNAL[scenario]}
        assert not (names & others), f"{scenario} leaked signals: {names & others}"

    def test_skew_signal_reports_the_measured_ratio(self):
        _, context = context_for("partition_skew")
        skew = next(s for s in context.signals if s["name"] == "partition_skew")
        assert skew["severity"] == "HIGH"
        assert skew["metrics"]["ratio"] > 20
        assert skew["metrics"]["max_rows"] == 40_000_000

    def test_small_files_signal_reports_the_measured_average(self):
        table, context = context_for("small_files")
        signal = next(s for s in context.signals if s["name"] == "small_files")
        assert signal["metrics"]["avg_file_bytes"] == int(table.avg_file_bytes)
        assert signal["metrics"]["num_data_files"] == 3000

    def test_signals_never_carry_a_recommendation(self):
        """The Legacy Analyzer measures; only the Investigator prescribes."""
        banned = ("should", "recommend", "consider", "run optimize", "you must")
        for scenario in EXPECTED_SIGNAL:
            _, context = context_for(scenario)
            for signal in context.signals:
                assert set(signal) == {"name", "severity", "detail", "metrics"}
                assert not any(word in signal["detail"].lower() for word in banned), signal

    def test_metadata_is_cached_on_the_context(self):
        table, context = context_for("healthy")
        assert context.metadata["table_name"] == table.name
        assert [c["name"] for c in context.metadata["columns"]] == [c for c, _ in table.columns]
        assert context.metadata["files"]["columns"], "Iceberg .files schema must be cached"
        assert context.metadata["partitions"]["columns"]


# ----------------------------------------------------------------- planning


class TestAdaptivePlanning:
    """The plan must follow the table's signals, not a fixed checklist."""

    @pytest.mark.parametrize(
        "scenario,expected_check",
        [
            ("partition_skew", "skew"),
            ("small_files", "file_size"),
            ("missing_sort_order", "sort"),
            ("delete_overhead", "delete_overhead"),
            ("table_property_naming", "table_properties"),
            ("empty", "empty_table"),
        ],
    )
    def test_signal_drives_the_first_hypothesis(self, scenario, expected_check):
        _, context = context_for(scenario)
        specs = plan_checks(context.to_state(1, max_checks=4), 4, nodes=None)
        assert specs[0][1] == expected_check, (
            f"{scenario}: first hypothesis was {specs[0][1]}, expected {expected_check}"
        )

    def test_different_tables_get_different_plans(self):
        """The whole point: two tables must not receive the same investigation."""
        plans = {}
        for scenario in PROBLEM_SCENARIOS:
            _, context = context_for(scenario)
            specs = plan_checks(context.to_state(1, max_checks=3), 3, nodes=None)
            plans[scenario] = [check_type for _, check_type, _ in specs]

        firsts = [plan[0] for plan in plans.values()]
        assert len(set(firsts)) == len(firsts), f"plans did not differentiate: {plans}"

    def test_healthy_table_falls_back_to_coverage(self):
        """With nothing suspicious, the plan is generic coverage, not silence."""
        _, context = context_for("healthy")
        specs = plan_checks(context.to_state(1, max_checks=3), 3, nodes=None)
        assert len(specs) == 3
        assert [ct for _, ct, _ in specs] == ["table_properties", "file_size", "skew"]

    def test_higher_severity_is_investigated_first(self):
        signals = [
            {"name": "snapshot_retention", "severity": "LOW", "detail": "", "metrics": {}},
            {"name": "partition_skew", "severity": "HIGH", "detail": "", "metrics": {}},
            {"name": "delete_overhead", "severity": "MEDIUM", "detail": "", "metrics": {}},
        ]
        state = {"signals": signals, "table_name": "t", "investigation_id": 1}
        order = [ct for _, ct, _ in plan_checks(state, 3, nodes=None)]
        assert order == ["skew", "delete_overhead", "snapshot_retention"]

    def test_llm_plan_is_used_when_available(self, tmp_path):
        llm = ScriptedLLM(plan=[("scan_efficiency", "Why do queries read the whole table?")])
        _, _, _, _, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=2)
        outcome = analyzer.analyze(SCENARIOS["partition_skew"]().name, "cat", "sch")
        questions = [f.question for f in outcome.result.findings and
                     analyzer.db.list_findings(outcome.investigation_id)]
        assert "Why do queries read the whole table?" in questions

    def test_planning_survives_an_llm_outage(self, tmp_path):
        """A planner outage must degrade to signal-derived hypotheses, not fail."""
        llm = ScriptedLLM(fail_on="Decide the single most valuable NEXT question")
        table, _, _, db, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=2)
        outcome = analyzer.analyze(table.name, "cat", "sch")
        findings = db.list_findings(outcome.investigation_id)
        assert findings, "investigation must still run when the planner LLM is down"
        assert findings[0].check_type == "skew"

    def test_planner_prompt_carries_the_measured_signals(self, tmp_path):
        table, _, llm, _, analyzer = build("small_files", tmp_path)
        analyzer.analyze(table.name, "cat", "sch")
        planning = llm.prompts("decide")
        assert planning, "the planner must consult the LLM"
        assert "Measured signals" in planning[0]
        assert "small_files" in planning[0]


# ------------------------------------------------------------ investigation


class TestInvestigationPerScenario:
    @pytest.mark.parametrize("scenario", PROBLEM_SCENARIOS + ["healthy"])
    def test_investigation_produces_evidence_backed_findings(self, scenario, tmp_path):
        table, _, _, db, analyzer = build(scenario, tmp_path)
        outcome = analyzer.analyze(table.name, "cat", "sch", output_dir=tmp_path / "reports")

        findings = db.list_findings(outcome.investigation_id)
        assert findings, f"{scenario} produced no findings"
        validator = ClaimValidator(db)
        for finding in findings:
            assert finding.evidence_ids, f"{scenario} check {finding.check_num} cites no evidence"
            assert finding.confidence is not None
            assert 0.0 <= finding.confidence <= 1.0
            assert len(finding.rationale) >= 20, f"thin rationale: {finding.rationale!r}"
            assert validator.validate(outcome.investigation_id, finding).valid

    @pytest.mark.parametrize("scenario", PROBLEM_SCENARIOS)
    def test_findings_quote_real_numbers_from_the_mock_table(self, scenario, tmp_path):
        """Evidence must trace back to the mock's metadata, not to canned text."""
        table, _, _, db, analyzer = build(scenario, tmp_path)
        outcome = analyzer.analyze(table.name, "cat", "sch")

        trail = db.list_trail(outcome.investigation_id)
        assert trail, "queries must be recorded in the audit trail"
        assert all(entry["query_text"] for entry in trail)
        assert any(entry["execution_status"] == "success" for entry in trail)

    def test_skew_investigation_measures_the_dominant_partition(self, tmp_path):
        table, _, _, db, analyzer = build(
            "partition_skew", tmp_path, llm=ScriptedLLM(analysis=finds()), max_checks=1
        )
        outcome = analyzer.analyze(table.name, "cat", "sch")
        finding = db.list_findings(outcome.investigation_id)[0]
        assert finding.check_type == "skew"
        assert "40,000,000" in finding.exact_result, (
            f"the finding should quote the skewed partition's row count: {finding.exact_result}"
        )

    def test_small_files_investigation_measures_the_file_sizes(self, tmp_path):
        table, _, _, db, analyzer = build(
            "small_files", tmp_path, llm=ScriptedLLM(analysis=finds()), max_checks=1
        )
        outcome = analyzer.analyze(table.name, "cat", "sch")
        finding = db.list_findings(outcome.investigation_id)[0]
        assert finding.check_type == "file_size"
        assert "3,000" in finding.exact_result, f"expected the file count: {finding.exact_result}"

    def test_healthy_table_yields_no_root_causes(self, tmp_path):
        table, _, _, db, analyzer = build("healthy", tmp_path, max_checks=3)
        outcome = analyzer.analyze(table.name, "cat", "sch", output_dir=tmp_path / "reports")
        report = ReportAssembler(db).assemble(outcome.investigation_id)
        assert report.root_causes == [], "a healthy table must not produce root causes"
        assert "No confirmed problems" in render_markdown(report)

    def test_empty_table_asks_exactly_one_question(self, tmp_path):
        table, _, _, db, analyzer = build("empty", tmp_path, max_checks=5)
        outcome = analyzer.analyze(table.name, "cat", "sch")
        assert len(db.list_findings(outcome.investigation_id)) == 1

    def test_lifecycle_states_are_recorded_in_order(self, tmp_path):
        """The run must advance through the lifecycle, not jump to a verdict."""
        table, _, _, db, analyzer = build("partition_skew", tmp_path, max_checks=2)
        seen: list[str] = []
        original = db.set_status
        db.set_status = lambda inv_id, status: (seen.append(status), original(inv_id, status))[1]

        outcome = analyzer.analyze(table.name, "cat", "sch")
        assert seen == [
            "metadata_collected", "planning", "checks_running", "evidence_validated"
        ], seen
        assert db.get_investigation(outcome.investigation_id).status in ("completed", "failed")

    def test_metadata_is_read_once_per_investigation(self, tmp_path):
        table, spark, _, _, analyzer = build("partition_skew", tmp_path, max_checks=3)
        analyzer.analyze(table.name, "cat", "sch")
        assert spark.table_reads.count(table.name) == 2, (
            f"base table schema + sample only; got {spark.table_reads}"
        )
        for suffix in ("files", "partitions", "snapshots", "history"):
            assert spark.table_reads.count(f"{table.name}.{suffix}") == 1


# --------------------------------------------------------------- resilience


class TestHookFailures:
    """A blocked query degrades one check; it never ends the investigation."""

    def _run(self, tmp_path, bad_sql, scenario="partition_skew", max_checks=2):
        table = SCENARIOS[scenario]()
        llm = ScriptedLLM(table=table.name, sql={"skew": bad_sql.format(table=table.name)})
        _, spark, _, db, analyzer = build(scenario, tmp_path, llm=llm, max_checks=max_checks)
        outcome = analyzer.analyze(table.name, "cat", "sch", output_dir=tmp_path / "reports")
        return db, outcome

    def test_write_statement_is_blocked_and_recorded(self, tmp_path):
        db, outcome = self._run(tmp_path, "DROP TABLE {table}")
        violations = db.list_hook_violations(outcome.investigation_id)
        assert violations, "a DROP must be blocked by the read-only hook"
        assert violations[0]["hook_name"] == "ReadOnlyHook"

    def test_query_outside_the_whitelisted_schema_is_blocked(self, tmp_path):
        db, outcome = self._run(tmp_path, "SELECT COUNT(*) FROM other_cat.other_sch.secrets")
        violations = db.list_hook_violations(outcome.investigation_id)
        assert violations and violations[0]["hook_name"] == "SchemaWhitelistHook"

    def test_hallucinated_column_is_blocked_by_schema_grounding(self, tmp_path):
        db, outcome = self._run(
            tmp_path, "SELECT SUM(bytes_written_total) FROM {table}.files"
        )
        violations = db.list_hook_violations(outcome.investigation_id)
        assert violations and violations[0]["hook_name"] == "SqlGroundingHook"
        assert "bytes_written_total" in violations[0]["reason"]

    def test_investigation_continues_past_a_blocked_check(self, tmp_path):
        db, outcome = self._run(tmp_path, "DROP TABLE {table}", max_checks=2)
        findings = db.list_findings(outcome.investigation_id)
        assert len(findings) >= 2, "the other planned check must still run"
        statuses = {e["execution_status"] for e in db.list_trail(outcome.investigation_id)}
        assert "hook_failed" in statuses and "success" in statuses

    def test_report_warns_about_blocked_queries(self, tmp_path):
        db, outcome = self._run(tmp_path, "DROP TABLE {table}")
        report = ReportAssembler(db).assemble(outcome.investigation_id)
        assert any("blocked by a safety hook" in w for w in report.warnings), report.warnings
        assert "Blocked queries" in render_markdown(report)

    def test_blocked_check_is_retried_before_giving_up(self, tmp_path):
        db, outcome = self._run(tmp_path, "DROP TABLE {table}")
        violations = db.list_hook_violations(outcome.investigation_id)
        assert len(violations) >= 2, "a blocked query must be retried, not abandoned"


class TestSqlExecutionFailures:
    """Spark-side errors are evidence about the check, not a reason to stop."""

    def test_failing_query_does_not_end_the_investigation(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        spark = MockSpark(table, fail_on=r"AS partition_count")
        _, _, _, db, analyzer = build("partition_skew", tmp_path, spark=spark, max_checks=2)
        outcome = analyzer.analyze(table.name, "cat", "sch", output_dir=tmp_path / "reports")

        assert db.list_findings(outcome.investigation_id), "other checks must still conclude"
        trail = db.list_trail(outcome.investigation_id)
        assert any(e["execution_status"] == "error" for e in trail)
        assert any(e["error_message"] for e in trail)

    def test_failure_is_retried_with_the_error_in_the_prompt(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        spark = MockSpark(table, fail_on=r"AS partition_count")
        llm = ScriptedLLM(table=table.name)
        _, _, _, db, analyzer = build(
            "partition_skew", tmp_path, spark=spark, llm=llm, max_checks=1, max_retries=2
        )
        analyzer.analyze(table.name, "cat", "sch")

        retry_prompts = [p for p in llm.prompts("query") if "ERROR:" in p]
        assert retry_prompts, "a failed query must be retried with its error in the prompt"
        assert "simulated Spark failure" in retry_prompts[0]

    def test_report_warns_about_failed_queries(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        spark = MockSpark(table, fail_on=r"AS partition_count")
        _, _, _, db, analyzer = build("partition_skew", tmp_path, spark=spark, max_checks=2)
        outcome = analyzer.analyze(table.name, "cat", "sch")
        report = ReportAssembler(db).assemble(outcome.investigation_id)
        assert any("failed or timed out" in w for w in report.warnings), report.warnings

    def test_total_spark_outage_is_not_reported_as_an_empty_table(self, tmp_path):
        """An unreachable table must not be mistaken for a clean, empty one."""
        from src.analyzer.legacy_analyzer import MetadataUnavailable

        table = SCENARIOS["partition_skew"]()
        spark = MockSpark(table, fail_on=r"SELECT")
        _, _, _, db, analyzer = build("partition_skew", tmp_path, spark=spark, max_checks=2)

        with pytest.raises(MetadataUnavailable, match="unreachable, not empty"):
            analyzer.analyze(table.name, "cat", "sch")
        assert db.get_investigation(1).status == "failed"

    def test_partial_metadata_failure_still_yields_a_baseline(self, tmp_path):
        """Losing one metric must not lose the whole collection pass."""
        from src.analyzer.legacy_analyzer import collect_raw_metrics

        table = SCENARIOS["partition_skew"]()
        spark = MockSpark(table, fail_on=r"\.snapshots")
        metrics = collect_raw_metrics(spark, table.name)

        assert metrics["failed_metrics"] == ["snapshot_count"]
        assert metrics["num_data_files"] == 207
        assert metrics["is_empty"] is False


# --------------------------------------------------------------------- loop


class TestAdaptiveLoop:
    """Hypothesis -> SQL -> Evidence -> Decide -> Repeat."""

    def _followup_once(self):
        """Ask for one follow-up on the first check only."""
        def _analysis(check_type, check_num, result):
            if check_num == 0:
                return {
                    "needs_followup": True,
                    "followup_question": "Which partitions hold the excess bytes?",
                }
            return {}
        return _analysis

    def test_followup_creates_a_second_check(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        llm = ScriptedLLM(table=table.name, analysis=self._followup_once())
        _, _, _, db, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=1)
        outcome = analyzer.analyze(table.name, "cat", "sch")

        findings = db.list_findings(outcome.investigation_id)
        assert len(findings) == 2, f"expected hypothesis + follow-up, got {len(findings)}"
        assert findings[1].question == "Which partitions hold the excess bytes?"

    def test_followup_gets_its_own_evidence_id(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        llm = ScriptedLLM(table=table.name, analysis=self._followup_once())
        _, _, _, db, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=1)
        outcome = analyzer.analyze(table.name, "cat", "sch")

        findings = db.list_findings(outcome.investigation_id)
        check_nums = [f.check_num for f in findings]
        assert len(set(check_nums)) == len(check_nums), "follow-ups need unique check numbers"
        assert findings[1].evidence_ids == [f"trail:{findings[1].check_num}"]
        assert ClaimValidator(db).validate(outcome.investigation_id, findings[1]).valid

    def test_loop_is_bounded(self, tmp_path):
        """An LLM that always wants another test must still terminate."""
        from src.investigator.loop import MAX_FOLLOWUPS_PER_CHAIN

        table = SCENARIOS["partition_skew"]()
        llm = ScriptedLLM(
            table=table.name,
            analysis=lambda ct, n, r: {
                "needs_followup": True, "followup_question": f"And what about step {n}?"
            },
        )
        _, _, _, db, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=1)
        outcome = analyzer.analyze(table.name, "cat", "sch")

        findings = db.list_findings(outcome.investigation_id)
        assert len(findings) == 1 + MAX_FOLLOWUPS_PER_CHAIN

    def test_no_followup_concludes_after_one_check(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        _, _, _, db, analyzer = build("partition_skew", tmp_path, max_checks=1)
        outcome = analyzer.analyze(table.name, "cat", "sch")
        assert len(db.list_findings(outcome.investigation_id)) == 1

    def test_followup_question_reaches_the_query_prompt(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        llm = ScriptedLLM(table=table.name, analysis=self._followup_once())
        _, _, _, _, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=1)
        analyzer.analyze(table.name, "cat", "sch")
        assert any(
            "Which partitions hold the excess bytes?" in p for p in llm.prompts("query")
        ), "the follow-up must drive a new SQL generation"


# ------------------------------------------------------------------ quality


class TestCriticAndQuality:
    def test_critic_rejection_is_retried(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        llm = ScriptedLLM(table=table.name, critic_approves=False)
        _, _, _, db, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=1)
        analyzer.analyze(table.name, "cat", "sch")
        assert len(llm.prompts("critic")) >= 2, "a rejected draft must get another pass"

    def test_finding_without_evidence_is_not_recorded_as_valid(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        llm = ScriptedLLM(table=table.name, analysis=lambda ct, n, r: {"evidence_ids": []})
        _, _, _, db, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=1)
        outcome = analyzer.analyze(table.name, "cat", "sch")

        assert outcome.result.status == "failed", "no evidence means no conclusion"
        for finding in db.list_findings(outcome.investigation_id):
            assert finding.verdict == "inconclusive"

    def test_confidence_is_derived_when_the_llm_omits_it(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        llm = ScriptedLLM(table=table.name, analysis=lambda ct, n, r: {"confidence": None})
        _, _, _, db, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=1)
        outcome = analyzer.analyze(table.name, "cat", "sch")

        finding = db.list_findings(outcome.investigation_id)[0]
        assert finding.confidence is not None and finding.confidence > 0

    def test_out_of_range_confidence_is_clamped(self, tmp_path):
        table = SCENARIOS["partition_skew"]()
        llm = ScriptedLLM(table=table.name, analysis=lambda ct, n, r: {"confidence": 42})
        _, _, _, db, analyzer = build("partition_skew", tmp_path, llm=llm, max_checks=1)
        outcome = analyzer.analyze(table.name, "cat", "sch")
        assert db.list_findings(outcome.investigation_id)[0].confidence == 1.0

    def test_report_renders_every_section_for_a_real_scenario(self, tmp_path):
        table = SCENARIOS["small_files"]()
        llm = ScriptedLLM(table=table.name, analysis=finds())
        _, _, _, db, analyzer = build("small_files", tmp_path, llm=llm, max_checks=2)
        outcome = analyzer.analyze(table.name, "cat", "sch", output_dir=tmp_path / "reports")

        markdown = render_markdown(ReportAssembler(db).assemble(outcome.investigation_id))
        for heading in (
            "## 1. Executive Summary", "## 2. Root Causes", "## 3. Evidence",
            "## 4. SQL Validation", "## 5. Recommendations", "## 6. Metadata Appendix",
        ):
            assert heading in markdown
        assert "confidence" in markdown.lower()
        assert "trail:" in markdown
