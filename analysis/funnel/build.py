"""Run the dbt pipeline behind the RAM and dataset-hash gates, and record the run.

Run: python -m funnel.build [extra dbt build arguments, e.g. --select staging]

Halts below the available-memory gate or if the raw file hash differs from
docs/data-source.md. Records available memory, elapsed time, peak spill, and
the dbt result in ai-workflow/evidence/sprint-1/dbt_build_runs.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from funnel.common import (
    DUCKDB_MEMORY_LIMIT,
    DUCKDB_THREADS,
    DUCKDB_TMP_DIR,
    REPO_ROOT,
    manifest,
    require_available_ram,
    require_dataset_hash_match,
    write_json,
)
from funnel.profile import SpillSampler

SCRIPT = "funnel.build"
PIPELINE_DIR = REPO_ROOT / "pipeline"
DBT_EXE = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")
RUNS_JSON = REPO_ROOT / "ai-workflow" / "evidence" / "sprint-1" / "dbt_build_runs.json"
SUMMARY_PREFIXES = ("Done. PASS=", "Finished running", "Completed with", "Completed successfully")


def dbt_command(extra_args: list[str]) -> list[str]:
    return [str(DBT_EXE), "build", "--project-dir", str(PIPELINE_DIR), "--profiles-dir", str(PIPELINE_DIR),
            *extra_args]


def summary_lines(output: str) -> list[str]:
    """dbt's own result lines, with the log timestamp prefix removed."""
    lines = []
    for raw in output.splitlines():
        text = raw.split("  ", 1)[-1].strip() if raw[:2].isdigit() else raw.strip()
        if text.startswith(SUMMARY_PREFIXES):
            lines.append(text)
    return lines


def append_run(record: dict[str, Any], path: Path = RUNS_JSON) -> None:
    runs = json.loads(path.read_text(encoding="utf-8"))["runs"] if path.exists() else []
    write_json(path, {"runs": [*runs, record]})


def main() -> None:
    extra = sys.argv[1:]
    available = require_available_ram()
    sha = require_dataset_hash_match()
    DUCKDB_TMP_DIR.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "FUNNEL_REPO_ROOT": REPO_ROOT.as_posix()}
    print(f"dbt threads 1; DuckDB memory_limit {DUCKDB_MEMORY_LIMIT}, threads {DUCKDB_THREADS}", flush=True)
    sampler = SpillSampler(DUCKDB_TMP_DIR)
    sampler.start()
    started = time.perf_counter()
    try:
        proc = subprocess.Popen(dbt_command(extra), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env=env)
        chunks = []
        for line in proc.stdout:  # stream so progress is visible
            print(line, end="", flush=True)
            chunks.append(line)
        exit_code = proc.wait()
    finally:
        peak_spill = sampler.stop()
    elapsed = round(time.perf_counter() - started, 1)
    record = {
        "manifest": manifest(SCRIPT, sha),
        "dbt_args": ["build", *extra],
        "available_ram_gb_before_run": available,
        "duckdb_memory_limit": DUCKDB_MEMORY_LIMIT,
        "duckdb_threads": DUCKDB_THREADS,
        "dbt_threads": 1,
        "elapsed_seconds": elapsed,
        "peak_spill_bytes": peak_spill,
        "spill_sample_interval_seconds": 1.0,
        "dbt_exit_code": exit_code,
        "dbt_summary": summary_lines("".join(chunks)),
    }
    append_run(record)
    print(f"Elapsed: {elapsed} s; peak spill: {peak_spill} bytes ({round(peak_spill / 1024**3, 2)} GiB); "
          f"dbt_exit_code={exit_code}", flush=True)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
