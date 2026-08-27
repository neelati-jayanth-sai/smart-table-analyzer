# Smart Table Analyzer

An AI-powered investigation system for analyzing Apache Iceberg tables on the IOMETE platform. The system uses LLM-driven analysis to identify table health issues, partitioning problems, file sizing inefficiencies, and other optimization opportunities.

## Quick Start

### Prerequisites

- Python 3.11+
- IOMETE platform access
- Dell AIA Gateway credentials (or compatible LLM provider)
- PySpark with Spark Connect

### Installation

1. Clone the repository
2. Create a local `.env` file. There is no checked-in template because it would
   encourage committing environment-specific credentials and certificate paths.
   Configure IOMETE access (`IOMETE_HOST`, `IOMETE_LAKEHOUSE`,
   `IOMETE_DATA_PLANE`, `IOMETE_USER_ID`, `IOMETE_API_TOKEN`,
   `IOMETE_CATALOG`, `IOMETE_NAMESPACE`), the LLM adapter, and
   `IOMETE_CERT_FILE` when your environment requires a private CA.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running an Investigation

```bash
python scripts/run_investigation.py --table eds_it_dev.elh_comn.your_table
```

## Documentation

- **[Architecture](Architecture.md)** - System architecture and design decisions
- **[AGENTS.md](AGENTS.md)** - Coding standards and development guidelines
- **[CONTEXT.md](CONTEXT.md)** - Domain context and terminology
- **[Running investigations](docs/RUNNING_INVESTIGATIONS.md)** - Full Deep + Thorough workflow and report interpretation
- **[Enterprise Network Setup](docs/ENTERPRISE_NETWORK_SETUP.md)** - Network connectivity and service configuration

## Key Features

- **Multi-Agent Investigation Pipeline**: Analyst-Critic pattern with quality gates
- **Parallel Data Extraction**: Optimized metadata collection with thread-safe Spark execution
- **Knowledge-Driven Analysis**: LLM uses curated runbooks for Iceberg and IOMETE best practices
- **Actionable Recommendations**: SQL remediation queries directly in findings
- **Streamlit UI**: Interactive investigation viewer and results dashboard

## Testing

### Running Tests

```bash
# Hermetic test suite; scripts/ contains opt-in live smoke programs and is excluded.
python -m pytest

# Install developer tools, then run static checks.
python -m pip install -r requirements-dev.txt
python -m ruff check src app.py ui_metadata.py ui_render.py
python -m mypy
```

## Project Structure

```
smart-table-analyzer-demo/
├── src/                    # Source code
│   ├── connectors/         # LLM and IOMETE adapters
│   ├── database/          # SQLite database layer
│   ├── investigator/      # Investigation pipeline
│   ├── query/             # Query execution and hooks
│   └── reporting/         # Report generation
├── knowledge/             # Curated runbooks and documentation
├── scripts/               # CLI scripts and utilities
├── tests/                 # Test suites
└── app.py                 # Streamlit UI
```

## Configuration

Create a local `.env` with the required connection settings. Key settings:

- `IOMETE_HOST`, `IOMETE_USER_ID`, `IOMETE_API_TOKEN` - IOMETE connection
- `LLM_BASE_URL`, `LLM_CLIENT_ID`, `LLM_CLIENT_SECRET` - LLM provider
- `IOMETE_CERT_FILE` - repository-relative certificate path, when required
- `QUERY_TIMEOUT_SECONDS` - Query execution timeout

## Development

### Code Standards

See [AGENTS.md](AGENTS.md) for:
- Modular architecture principles
- Deep module design patterns
- File size limits (200 lines max)
- Skill usage guidelines

### Adding New Knowledge

Knowledge entries are added to `knowledge/runbooks/`, `knowledge/iceberg/`, or `knowledge/iomete/`. Each entry should:
- Be 50-200 lines
- Focus on a single topic
- Include source citations
- Be reviewable as plain markdown

## Support

For issues or questions:
- Check [Architecture.md](Architecture.md) for design decisions
- Review [CONTEXT.md](CONTEXT.md) for domain terminology
- Run `python -m pytest` for the hermetic verification suite

# smart-table-analyzer
