# Running investigations

This guide covers the current Fast/Deep investigation workflow. It applies to
any Apache Iceberg table; a table DDL is not required as input.

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

## Choose an analysis depth

| Mode | Deterministic collection contract | Use when |
|---|---|---|
| `fast` | Iceberg metadata, layout, properties, and available workload metadata. It does not read base-table rows for column profiling. | You need a quick layout/configuration assessment. |
| `deep` | Everything in Fast, plus exact aggregate null counts and cardinalities for every primitive column, in bounded batches. Numeric and temporal columns also have min/max ranges. | You need evidence for schema/data-quality or partition-candidate reasoning. |

Deep is intentionally more expensive because it scans table data. It does not
invent distribution statistics, and non-primitive, empty-table, failed, and
skipped columns remain explicit in the evidence.

`--max-checks` limits initial LLM hypotheses after deterministic collection. It
does not reduce the Deep column-profile contract and can lead to follow-up
checks when the evidence warrants them.

## Run from the CLI

Run Fast explicitly:

```bash
python scripts/run_investigation.py --table catalog.schema.table --metadata-profile fast
```

Run Deep with a bounded initial investigation plan:

```bash
python scripts/run_investigation.py --table catalog.schema.table --metadata-profile deep --max-checks 5
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

Enter a fully qualified `catalog.schema.table`, select Fast or Deep, optionally
provide a snapshot or query-metrics table, set the maximum planned checks, and
start the analysis. The dashboard and CLI use the same pipeline. The dashboard
reuses its Spark Connect session and reads prior runs from
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
  contract, such as column profiling in Fast.
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
