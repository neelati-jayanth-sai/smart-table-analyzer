# Next-session handoff

## Current state

The analyzer uses deterministic registered skills for execution. The LLM selects eligible checks, reads returned evidence, and writes explanations; it cannot generate arbitrary SQL or silently run extra checks.

`LegacyAnalyzer -> evidence cache -> Investigator skill selection -> deterministic skill -> executor -> structured result -> LLM explanation -> report/UI`

## Latest fixes

- Removed free-form SQL generation and raw query access from the Investigator.
- Retained `LegacyAnalyzer` as the snapshot-scoped deterministic baseline.
- Prevented hidden Analyst `run_check` calls; Analyst tools are read-only evidence access.
- Restricted selection to registered skills justified by current signals.
- Cached checks are not retried; normal execution permits at most one retry.
- Critic performs one bounded review; it never triggers another Analyst run over unchanged evidence.
- Preserved useful evidence when prose quality needs review; no-evidence findings remain inconclusive.
- Proof displays one canonical successful execution per check.
- Human byte formatting handles fixture-scale measurements correctly.

## Latest live UI result

Fixture: `local.e2e.small_files_orders`

- Before fixes: 81 seconds, duplicate/null proof entries, and `0.0 MB against a 0 MB target`.
- After fixes: 17 seconds, one verified proof entry, and `Average data file is 3.5 KB against a 20 KB target`.
- Verified evidence: 24 data files, average size 3,542 bytes.

Detailed judgment: `reports/UI_JUDGMENT_LOCAL.md`.

## Verification

Latest non-live command:

` .\.venv\Scripts\python.exe -m pytest -q --ignore=tests\test_ollama_e2e.py `

Result: `303 passed in 41.39s`.

Also passed:

` .\.venv\Scripts\ruff.exe check src tests `

` git diff --check `

## Run the local UI

` .\.venv\Scripts\python.exe scripts\local_e2e_data.py --reset `

` $env:STA_RUNTIME = 'local' `

` $env:LLM_PROVIDER = 'ollama' `

` $env:STA_TARGET_FILE_BYTES = '20000' `

` .\.venv\Scripts\streamlit.exe run app.py `

Choose `local.e2e.small_files_orders` from the local-table picker.

## Important constraints

- Keep `OLLAMA_API_KEY` only in `.env`; never print or commit it.
- Production model is `gpt-oss:120b-cloud` through Ollama Cloud.
- Source files must remain at or below 200 lines.
- Preserve the skill/execution seam: new checks need a small skill, optional checked-in SQL template, and independent tests.
- Do not reintroduce LLM-generated SQL or Analyst-triggered execution.

## Recommended next work

1. Run live UI checks for `mixed_orders` and `healthy_orders`; assess recommendation quality and false positives.
2. Add an explicit medium-issue count so `0 high-priority` does not imply no issues.
3. Consider a fixture-scale note beside local recommendations; production-size guidance can look odd beside the 20 KB fixture target.
4. Keep `IMPLEMENTATION_PROGRESS.md` concise.
