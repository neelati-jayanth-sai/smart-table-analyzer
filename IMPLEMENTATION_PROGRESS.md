# Implementation progress

## Completed

- Added an allowlisted deterministic-skill catalog with checked-in SQL templates.
- Removed the Investigator's free-form SQL prompt and raw `run_query` tool.
- Kept `LegacyAnalyzer` as the deterministic baseline sensor and persisted its evidence before LLM investigation.
- Removed the planner package; the Investigator now selects and runs one registered check at a time.
- Centralised check preparation, removed mock SQL generation, and removed the invalid manifest check.

## Current work

- Root-cause corrections are implemented and validated with a real local UI rerun.

## Architectural decisions

- `LegacyAnalyzer` owns baseline facts and threshold signals, never LLM reasoning or recommendations.
- The Investigator owns adaptive selection, knowledge retrieval, explanation, and prioritisation.
- A deterministic skill owns its template, expected result, interpretation contract, and failure policy.
- The evidence ledger/cache is the shared source of truth for UI, background work, and investigation reasoning.

## Verification

- Full non-live suite: 300 passed in 41.64s.
- Local Iceberg/dashboard validation: passed.
- Live Ollama Cloud `gpt-oss:120b-cloud` small-file E2E: passed in 38.92s.
- Browser UI judgment (`local.e2e.small_files_orders`): corrected run completed in 17s with one verified proof entry; see `reports/UI_JUDGMENT_LOCAL.md`.

## Next priority

- Maintain the skill catalog and add only independently tested deterministic checks.
