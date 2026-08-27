# Running investigations

This guide covers the mandatory full investigation workflow for an Apache
Iceberg table; a table DDL is not required as input.

## Prerequisites

- Python 3.11 or later.
- Network access and credentials for the target IOMETE environment.
- A Dell AIA Gateway-compatible LLM endpoint.
- A Spark Connect-compatible PySpark installation.

Create a local `.env` with the IOMETE connection, LLM connection, and (when
needed) `IOMETE_CERT_FILE`. See [ENV_QUICK_START.md](../ENV_QUICK_START.md)
for the environment variables. Install the runtime dependencies:

```bash
python -m pip install -r requirements.txt
```

## Investigation contract

Every run collects Iceberg metadata, profiles every primitive column with exact
aggregate batches, and starts ten initial LLM hypotheses. Core evidence starts
the investigation immediately while the required full profile continues beside
it. The UI shows evidence-backed findings and profile progress until both work
streams finish. Non-primitive, empty-table, failed, and skipped columns remain
explicit in the evidence.

## Run from the CLI

Run the full investigation:

```bash
python scripts/run_investigation.py --table catalog.schema.table
```

Useful optional inputs are `--snapshot <id>` to pin an Iceberg snapshot,
`--query-metrics-table catalog.schema.query_log` for workload metadata,
`--db path/to/investigation.db` for a separate local store, and `--output
reports/my-run.md` for a specific report path. The standard report path is
`reports/`; its JSON sidecar is written alongside the Markdown report.

## Run the dashboard

```bash
streamlit run app.py
```

Enter a fully qualified `catalog.schema.table`, optionally provide a snapshot
or query-metrics table, and start the analysis. The dashboard and CLI use the
same full-investigation pipeline. The dashboard reuses its Spark Connect session and reads prior runs from
`data/investigation.db`.

## Read the result safely

The report starts with the lifecycle and assessment. Treat only
`action_required` recommendations as evidence-backed actions. A `clean` result
means all completed checks returned validated clean evidence; it is not a claim
that an unavailable area was inspected.

Use the **Deterministic coverage** section (or the dashboard **Evidence** page)
to see what was actually collected:

- `completed` — the collection Module recorded deterministic evidence.
- `skipped` / **Not assessed** — the Module was deliberately outside the run
  contract or is waiting for its staged full-profile evidence.
- `unavailable` — source metadata was not available.
- `failed` — collection attempted the Module but could not complete it. A Deep
  run with a failed required Module is assessed as `needs_review`.

Evidence IDs connect each finding to immutable collected facts. The LLM can
reason over these persisted records, request bounded evidence payloads, and
produce the human-readable explanation; it does not create the underlying
measurements. The **Whole-run review** then flags inconsistency, unsupported
certainty, duplicate recommendations, missing justification, and coverage gaps.

## Verify a checkout

```bash
python -m pytest
python -m pip install -r requirements-dev.txt
python -m ruff check src app.py ui_metadata.py ui_render.py
python -m mypy
git diff --check
```

The test suite is hermetic. It does not require live IOMETE or LLM credentials;
running an investigation does.
