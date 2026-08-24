# Production Knowledge Base

## Architecture (per Architecture.md §5)

The knowledge base uses a **SQLite index** + **file-backed content** approach:
- **Index:** `investigation.db` (SQLite) holds lightweight index (topic path → current version)
- **Content:** Authored markdown files in `knowledge/<source>/*.md` (one per topic, 50-200 lines)
- **Retrieval:** `scripts/retrieve_knowledge.py` CLI or `scripts/knowledge_retrieval.py` module

## Authored Knowledge

Production knowledge lives in three source trees:

### `knowledge/iceberg/`
Curated Apache Iceberg knowledge (6 entries):
- `partition-transforms.md` - Partition transforms, pitfalls, best practices
- `file-sizing-best-practices.md` - Target file sizes, compaction triggers
- `snapshot-management.md` - Time travel, retention, expiry
- `manifest-file-structure.md` - Manifest/manifest-list architecture
- `sort-order-optimization.md` - Sort order benefits and usage
- `data-skew-detection.md` - Detecting and fixing skew
- `metadata-tables.md` - System tables for diagnostics

### `knowledge/iomete/`
Platform-specific IOMETE knowledge (4 entries):
- `compaction-job-behavior.md` - How compaction works on IOMETE
- `snapshot-retention-defaults.md` - Platform retention policies
- `partition-evolution-limitations.md` - IOMETE-specific constraints
- `query-planning-quirks.md` - Platform query planner behaviors

### `knowledge/runbooks/`
Team operational guidelines (3 entries):
- `partition-strategy-guidelines.md` - Team conventions for partitioning
- `target-file-size-standards.md` - Team file size standards
- `maintenance-schedule.md` - Compaction and maintenance schedules

## Usage

### List knowledge paths

```bash
python scripts/retrieve_knowledge.py list --tree iceberg
python scripts/retrieve_knowledge.py list --tree iomete
python scripts/retrieve_knowledge.py list --tree runbooks
```

### Fetch specific entry

```bash
python scripts/retrieve_knowledge.py fetch --tree iceberg --path partition-transforms
```

## Maintenance

### Rebuild knowledge index
After authoring new entries or updating existing ones:

```bash
python scripts/init_knowledge_db.py
```

This scans `knowledge/<source>/*.md` files and rebuilds the SQLite index.

## Clean Structure

The knowledge folder contains **only production files** - no intermediate artifacts:
- `knowledge/<source>/*.md` - Hand-authored knowledge entries (16 total)
- `knowledge/<source>/README.md` - Source-level documentation
- `investigation.db` - SQLite index (root level)

All intermediate authoring artifacts (entries/, tree/, manifest/) have been removed.

## Provenance

Authored entries cite source material in footer:
- Apache Iceberg entries reference official spec and docs
- IOMETE entries reference platform documentation (internal)
- Runbooks reference team operational experience

Original sources:
- Apache Iceberg: `https://github.com/apache/iceberg.git`
- IOMETE docs: `https://github.com/iomete/iom-docs.git` (sync via `scripts/sync_official_docs.py`)
