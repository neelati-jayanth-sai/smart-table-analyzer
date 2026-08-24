"""Initialize investigation database and seed the knowledge index.

This script is kept for backward compatibility. It now delegates to the unified
investigation database initializer.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "init_investigation_db.py"
    subprocess.run([sys.executable, str(script), "--db", "data/investigation.db"], check=True)


if __name__ == "__main__":
    main()
