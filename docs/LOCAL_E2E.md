# Local End-to-End Testing

This path uses PyIceberg, PyArrow, DuckDB, and a local SQLite Iceberg catalog. It never starts Spark.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\local_e2e_data.py --reset
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\run_local_e2e.py
```

The generated tables are `e2e.healthy_orders`, `e2e.small_files_orders`,
`e2e.skewed_orders`, `e2e.tiny_partitions_orders`, `e2e.snapshot_bloat_orders`,
`e2e.evolving_orders`, `e2e.delete_files_orders`, `e2e.mixed_orders`, and
`e2e.empty_orders`. Local metadata uses a 20 KB fixture scale while production
keeps the 128 MB default.

For a real Ollama Investigator run, set `OLLAMA_API_KEY` in the shell, then:

```powershell
$env:LLM_PROVIDER = 'ollama'
.\.venv\Scripts\python.exe scripts\run_local_e2e.py --live-ollama
```

To run the dashboard over the local catalog:

```powershell
$env:STA_RUNTIME = 'local'
$env:LLM_PROVIDER = 'ollama'
$env:STA_TARGET_FILE_BYTES = '20000'
.\.venv\Scripts\streamlit.exe run app.py
```

Enter a local table as `local.e2e.small_files_orders`. The current application
surface is Streamlit; `DashboardAnalysisRunner` is its programmatic application
interface, not a separately hosted HTTP API.
