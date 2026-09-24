"""Shared paths, hashing, provenance manifest, and dataset-hash gate."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PARQUET_DIR = DATA_DIR / "parquet"
DUCKDB_TMP_DIR = DATA_DIR / "duckdb_tmp"
DOCS_DIR = REPO_ROOT / "docs"
EVIDENCE_DIR = REPO_ROOT / "ai-workflow" / "evidence" / "sprint-0"
DATA_SOURCE_MD = DOCS_DIR / "data-source.md"

KAGGLE_SLUG = "mkechinov/ecommerce-behavior-data-from-multi-category-store"
KAGGLE_URL = f"https://www.kaggle.com/datasets/{KAGGLE_SLUG}"
RAW_FILE_NAME = "2019-Oct.csv"
RAW_CSV = RAW_DIR / RAW_FILE_NAME
PARQUET_FILE = PARQUET_DIR / "2019-Oct.parquet"

# DuckDB resource limits: a fixed ceiling, not a share of total RAM. The project
# machine has 15.78 GB of RAM but was observed with ~3.8 GB free while other
# applications ran; an 8 GB limit got a profile run killed under memory pressure
# (see ai-workflow/correction-log.md). Heavy queries spill to DUCKDB_TMP_DIR instead.
DUCKDB_MEMORY_LIMIT = "4GB"
DUCKDB_THREADS = 4

# The line in data-source.md that the stage-command hash gate reads.
SHA_LINE_PATTERN = re.compile(r"^- \*\*SHA-256:\*\* `([0-9a-f]{64})`", re.MULTILINE)


def sha256_file(path: Path, chunk_size: int = 1 << 24) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def git_commit_sha() -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def git_worktree_dirty() -> bool:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())


def manifest(script: str, dataset_sha256: str) -> dict[str, Any]:
    """Provenance block required on every JSON export (CLAUDE.md rule 5)."""
    return {
        "git_commit_sha": git_commit_sha(),
        "git_worktree_dirty": git_worktree_dirty(),
        "dataset_sha256": dataset_sha256,
        "generated_at_utc": utc_now_iso(),
        "script": script,
    }


def recorded_dataset_sha256(data_source_md: Path | None = None) -> str | None:
    data_source_md = data_source_md or DATA_SOURCE_MD
    if not data_source_md.exists():
        return None
    match = SHA_LINE_PATTERN.search(data_source_md.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def require_dataset_hash_match(raw_csv: Path = RAW_CSV) -> str:
    """Halt the stage unless the raw file hash equals the one in data-source.md."""
    recorded = recorded_dataset_sha256()
    if recorded is None:
        sys.exit(f"HALT: no SHA-256 recorded in {DATA_SOURCE_MD}; run python -m funnel.ingest first.")
    if not raw_csv.exists():
        sys.exit(f"HALT: raw dataset missing at {raw_csv}.")
    actual = sha256_file(raw_csv)
    if actual != recorded:
        sys.exit(f"HALT: dataset hash mismatch. recorded={recorded} actual={actual}")
    return actual


def free_ram_gb() -> float | None:
    """Free physical memory, reported before heavy runs (None if unavailable)."""
    if sys.platform != "win32":
        return None
    import ctypes

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return round(status.ullAvailPhys / 1024**3, 2)


def dir_size_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.glob("*") if f.is_file()) if path.exists() else 0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """UTF-8 without BOM, LF line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def load_kaggle_token_into_env() -> None:
    """Copy KAGGLE_API_TOKEN from the Windows user environment into this process.

    The value is never printed or logged. A process that already has the
    variable (for example, one started after it was set) keeps its own value.
    """
    if os.environ.get("KAGGLE_API_TOKEN"):
        return
    token: str | None = None
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                token, _ = winreg.QueryValueEx(key, "KAGGLE_API_TOKEN")
        except FileNotFoundError:
            token = None
    if not token:
        sys.exit("HALT: KAGGLE_API_TOKEN is not set in the process or the user environment.")
    os.environ["KAGGLE_API_TOKEN"] = token
