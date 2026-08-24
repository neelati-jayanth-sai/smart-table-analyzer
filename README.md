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
2. Copy environment template:
   ```bash
   cp .env.example .env
   ```
3. Configure `.env` with your credentials
4. Install dependencies:
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
- **[Enterprise Network Setup](docs/ENTERPRISE_NETWORK_SETUP.md)** - Network connectivity and service configuration
- **[Sample Data](temp/sample_data/README.md)** - Sample data for component-level testing

## Key Features

- **Multi-Agent Investigation Pipeline**: Analyst-Critic pattern with quality gates
- **Parallel Data Extraction**: Optimized metadata collection with thread-safe Spark execution
- **Knowledge-Driven Analysis**: LLM uses curated runbooks for Iceberg and IOMETE best practices
- **Actionable Recommendations**: SQL remediation queries directly in findings
- **Streamlit UI**: Interactive investigation viewer and results dashboard

## Testing

### Component Testing with Sample Data

The project includes sample data extracted from real investigation runs for component-level testing:

```bash
# Extract sample data from investigation database
python scripts/extract_sample_data.py
```

**Important:** Sample data supports component-level testing but **not** end-to-end investigation runs. See [Sample Data Documentation](temp/sample_data/README.md) for detailed limitations and testing strategy.

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires IOMETE connection)
pytest tests/integration/

# E2E tests (requires IOMETE connection)
pytest tests/e2e/
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
├── temp/                  # Temporary files and sample data
└── app.py                 # Streamlit UI
```

## Configuration

See `.env.example` for all configuration options. Key settings:

- `IOMETE_HOST`, `IOMETE_USER_ID`, `IOMETE_API_TOKEN` - IOMETE connection
- `LLM_BASE_URL`, `CLIENT_ID`, `CLIENT_SECRET` - LLM provider
- `MAX_INVESTIGATION_CHECKS` - Maximum checks per investigation
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
- See [Sample Data Documentation](temp/sample_data/README.md) for testing guidance
