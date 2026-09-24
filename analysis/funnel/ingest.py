"""Fetch the October 2019 file, hash it, convert it to Parquet, write data-source.md.

Run: python -m funnel.ingest [--force-download]

This is a provenance event and is run rarely. The Kaggle file is the only
source. The publisher's alternate archive on data.rees46.com is not used.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import duckdb

from funnel.common import (
    DATA_SOURCE_MD,
    DUCKDB_MEMORY_LIMIT,
    DUCKDB_THREADS,
    DUCKDB_TMP_DIR,
    EVIDENCE_DIR,
    KAGGLE_SLUG,
    KAGGLE_URL,
    PARQUET_FILE,
    RAW_CSV,
    RAW_DIR,
    RAW_FILE_NAME,
    load_kaggle_token_into_env,
    manifest,
    require_dataset_hash_match,
    sha256_file,
    utc_now_iso,
    write_json,
    write_text,
)

SCRIPT = "funnel.ingest"
RETRIEVAL_SIDECAR = RAW_DIR / f"{RAW_FILE_NAME}.retrieval.json"

KAGGLE_LICENSE_FIELD = "copyright-authors"
PUBLISHER_USAGE_STATEMENT = (
    "You can use this dataset for free. Just mention the source of it: "
    "link to this page and link to [REES46 Marketing Platform](https://rees46.com)."
)
REES46_URL = "https://rees46.com"

# Raw event_time text format expected from the publisher's column description ("in UTC").
RAW_EVENT_TIME_REGEX = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$"


def _kaggle_api() -> Any:
    load_kaggle_token_into_env()
    from kaggle.api.kaggle_api_extended import KaggleApi  # import after the token is in env

    api = KaggleApi()
    api.authenticate()
    return api


def kaggle_file_size(api: Any) -> int:
    response = api.dataset_list_files(KAGGLE_SLUG, page_size=50)
    for item in response.files:
        if item.name == RAW_FILE_NAME:
            return int(item.total_bytes)
    sys.exit(f"HALT: {RAW_FILE_NAME} not listed in {KAGGLE_SLUG}.")


def download(api: Any) -> dict[str, Any]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    retrieved_at = utc_now_iso()
    api.dataset_download_file(KAGGLE_SLUG, RAW_FILE_NAME, path=str(RAW_DIR), force=True, quiet=False)
    archive = RAW_DIR / f"{RAW_FILE_NAME}.zip"
    archive_sha256: str | None = None
    if archive.exists():
        archive_sha256 = sha256_file(archive)
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            if names != [RAW_FILE_NAME]:
                sys.exit(f"HALT: unexpected archive contents: {names}")
            zf.extract(RAW_FILE_NAME, RAW_DIR)
    if not RAW_CSV.exists():
        sys.exit(f"HALT: download finished but {RAW_CSV} is missing.")
    record = {
        "retrieved_at_utc": retrieved_at,
        "download_artifact": archive.name if archive_sha256 else RAW_FILE_NAME,
        "download_artifact_sha256": archive_sha256,
    }
    write_json(RETRIEVAL_SIDECAR, record)
    return record


def count_csv_data_lines(path: Path, chunk_size: int = 1 << 24) -> int:
    """Newline count minus the header, independent of any CSV parser."""
    newlines = 0
    last_byte = b""
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            newlines += chunk.count(b"\n")
            last_byte = chunk[-1:]
    lines = newlines + (1 if last_byte not in (b"\n", b"") else 0)
    return lines - 1


def connect() -> duckdb.DuckDBPyConnection:
    """DuckDB connection sized for the project machine (see common.DUCKDB_MEMORY_LIMIT)."""
    DUCKDB_TMP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"SET temp_directory = '{DUCKDB_TMP_DIR.as_posix()}'")
    con.execute(f"SET memory_limit = '{DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"SET threads = {DUCKDB_THREADS}")
    con.execute("SET preserve_insertion_order = false")
    return con


def csv_relation_sql(path: Path) -> str:
    return f"read_csv('{path.as_posix()}', header = true, sample_size = -1)"


def convert_to_parquet(
    con: duckdb.DuckDBPyConnection, csv_path: Path = RAW_CSV, parquet_path: Path = PARQUET_FILE
) -> dict[str, Any]:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    src = csv_relation_sql(csv_path)
    csv_schema = con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()
    csv_rows = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    con.execute(
        f"COPY (SELECT * FROM {src}) TO '{parquet_path.as_posix()}' "
        "(FORMAT parquet, COMPRESSION zstd)"
    )
    pq = f"read_parquet('{parquet_path.as_posix()}')"
    parquet_schema = con.execute(f"DESCRIBE SELECT * FROM {pq}").fetchall()
    parquet_rows = con.execute(f"SELECT count(*) FROM {pq}").fetchone()[0]
    return {
        "csv_columns": [{"name": r[0], "type": r[1]} for r in csv_schema],
        "parquet_columns": [{"name": r[0], "type": r[1]} for r in parquet_schema],
        "csv_rows_duckdb": int(csv_rows),
        "parquet_rows": int(parquet_rows),
    }


def raw_event_time_format(con: duckdb.DuckDBPyConnection, csv_path: Path = RAW_CSV) -> dict[str, Any]:
    """How event_time is written in the raw text, before any type inference."""
    src = f"read_csv('{csv_path.as_posix()}', header = true, all_varchar = true)"
    nonmatching, null_count = con.execute(
        f"SELECT count(*) FILTER (WHERE event_time IS NOT NULL "
        f"AND NOT regexp_full_match(event_time, '{RAW_EVENT_TIME_REGEX[1:-1]}')), "
        f"count(*) FILTER (WHERE event_time IS NULL) FROM {src}"
    ).fetchone()
    suffixes = con.execute(
        f"SELECT regexp_extract(event_time, '\\d{{2}}:\\d{{2}}:\\d{{2}}(.*)$', 1) AS suffix, count(*) "
        f"FROM {src} GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
    ).fetchall()
    return {
        "expected_regex": RAW_EVENT_TIME_REGEX,
        "rows_not_matching": int(nonmatching),
        "null_rows": int(null_count),
        "suffixes_after_time": [{"suffix": s, "rows": int(n)} for s, n in suffixes],
    }


def utc_round_trip(con: duckdb.DuckDBPyConnection, csv_path: Path = RAW_CSV) -> dict[str, Any]:
    """Check that parsing event_time to TIMESTAMP keeps the logged UTC clock time.

    Each raw text value is cast to TIMESTAMP (the cast DuckDB's reader applies),
    formatted back as 'YYYY-MM-DD HH:MM:SS UTC', and compared with the raw text.
    A changed row means the parse shifted or altered the value.
    """
    src = f"read_csv('{csv_path.as_posix()}', header = true, all_varchar = true)"
    checked, changed, raw_min, raw_max, parsed_min, parsed_max = con.execute(
        f"""
        SELECT count(*),
               count(*) FILTER (WHERE strftime(CAST(event_time AS TIMESTAMP), '%Y-%m-%d %H:%M:%S') || ' UTC'
                                <> event_time),
               min(event_time), max(event_time),
               CAST(min(CAST(event_time AS TIMESTAMP)) AS VARCHAR),
               CAST(max(CAST(event_time AS TIMESTAMP)) AS VARCHAR)
        FROM {src} WHERE event_time IS NOT NULL
        """
    ).fetchone()
    return {
        "rows_checked": int(checked),
        "rows_changed_by_round_trip": int(changed),
        "raw_text_min": raw_min,
        "raw_text_max": raw_max,
        "parsed_min": parsed_min,
        "parsed_max": parsed_max,
    }


def render_data_source_md(ingest: dict[str, Any]) -> str:
    cols = "\n".join(
        f"| `{c['name']}` | `{c['type']}` |" for c in ingest["conversion"]["parquet_columns"]
    )
    conv = ingest["conversion"]
    raw = ingest["raw_file"]
    fmt = ingest["raw_event_time_format"]
    suffixes = ", ".join(f"`{s['suffix']!r}`: {s['rows']}" for s in fmt["suffixes_after_time"])
    archive = (
        f"- **Download artifact:** `{raw['download_artifact']}`, SHA-256 `{raw['download_artifact_sha256']}`\n"
        if raw["download_artifact_sha256"]
        else ""
    )
    return f"""# Data source

> Generated by `python -m funnel.ingest`. Do not edit by hand; rerun the script.
> Stage commands halt unless the raw file's SHA-256 equals the value recorded here.

## Source

- **Title:** eCommerce behavior data from multi category store
- **Publisher:** REES46 (Kaggle owner `mkechinov`); data collected by the Open CDP project (https://rees46.com/en/open-cdp)
- **Kaggle slug:** `{KAGGLE_SLUG}`
- **URL:** {KAGGLE_URL}
- **Source used:** the Kaggle file only. The publisher also links an alternate archive on data.rees46.com, but this project does not use it.

## License and basis for use

- **Kaggle license field:** `{KAGGLE_LICENSE_FIELD}` (displayed by Kaggle as "Data files © Original Authors"). Rights are reserved; the field grants no open license.
- **Publisher's usage statement** (verbatim, from the dataset description at {KAGGLE_URL}):

  > {PUBLISHER_USAGE_STATEMENT}

- **Basis for this project's use:** this project relies on that statement. It publishes only aggregates and findings: never the raw data and never row-level extracts. A test (`analysis/tests/test_no_row_level_data.py`) fails if any committed file under `web/`, `docs/`, or `ai-workflow/evidence/` contains row-level event data.
- **Decision record:** the project owner chose to rely on the publisher's statement on 2026-09-24, after Sprint 0 stopped at the license check.

## Attribution required

Both links appear in the README and in the site footer:

- Kaggle dataset page: {KAGGLE_URL}
- REES46 Marketing Platform: {REES46_URL}

## File

- **File name:** `{RAW_FILE_NAME}`
- **Retrieved (UTC):** {raw['retrieved_at_utc']}
- **Size (bytes):** {raw['size_bytes']} (Kaggle-listed size: {raw['kaggle_listed_size_bytes']})
- **SHA-256:** `{raw['sha256']}`
{archive}
## Row counts

| Method | Rows |
|---|---|
| Newline count minus header (no CSV parser) | {conv['csv_rows_newline_count']} |
| DuckDB `read_csv` | {conv['csv_rows_duckdb']} |
| Parquet (`{PARQUET_FILE.name}`) | {conv['parquet_rows']} |

All three counts match: **{ingest['checks']['row_counts_match']}**. Parquet types equal the CSV-inferred types: **{ingest['checks']['types_preserved']}**.

## Columns (DuckDB-inferred types, full-file sample)

| Column | Type |
|---|---|
{cols}

## Raw `event_time` text format

Checked on the raw CSV as text, before type inference. Rows not matching `{fmt['expected_regex']}`: {fmt['rows_not_matching']}. Null rows: {fmt['null_rows']}. Text after `HH:MM:SS`, with row counts: {suffixes}.
{_render_utc_round_trip(ingest.get("utc_round_trip"))}"""


def _render_utc_round_trip(rt: dict[str, Any] | None) -> str:
    if not rt:
        return ""
    return f"""
## UTC round trip (`funnel.ingest.utc_round_trip`)

`event_time` is stored as `TIMESTAMP` without a zone. Each raw value was cast to `TIMESTAMP`, formatted back as
`YYYY-MM-DD HH:MM:SS UTC`, and compared with the raw text. Rows checked: {rt['rows_checked']}; rows changed:
{rt['rows_changed_by_round_trip']}. Raw text range {rt['raw_text_min']} to {rt['raw_text_max']}; parsed range
{rt['parsed_min']} to {rt['parsed_max']}. Stored values are the logged UTC clock time when no rows change.
"""


def run(force_download: bool) -> dict[str, Any]:
    api = _kaggle_api()
    listed_size = kaggle_file_size(api)
    if force_download or not RAW_CSV.exists() or not RETRIEVAL_SIDECAR.exists():
        retrieval = download(api)
    else:
        retrieval = json.loads(RETRIEVAL_SIDECAR.read_text(encoding="utf-8"))
        print(f"Reusing existing {RAW_CSV.name} retrieved at {retrieval['retrieved_at_utc']}")

    size = RAW_CSV.stat().st_size
    print("Hashing raw file ...", flush=True)
    sha = sha256_file(RAW_CSV)
    print("Counting raw lines ...", flush=True)
    newline_rows = count_csv_data_lines(RAW_CSV)
    con = connect()
    print("Converting to Parquet ...", flush=True)
    conversion = convert_to_parquet(con)
    conversion["csv_rows_newline_count"] = newline_rows
    print("Checking raw event_time format ...", flush=True)
    fmt = raw_event_time_format(con)

    checks = {
        "size_matches_kaggle_listing": size == listed_size,
        "row_counts_match": newline_rows == conversion["csv_rows_duckdb"] == conversion["parquet_rows"],
        "types_preserved": conversion["csv_columns"] == conversion["parquet_columns"],
    }
    ingest = {
        "manifest": manifest(SCRIPT, sha),
        "source": {"kaggle_slug": KAGGLE_SLUG, "url": KAGGLE_URL},
        "raw_file": {
            "name": RAW_FILE_NAME,
            "size_bytes": size,
            "kaggle_listed_size_bytes": listed_size,
            "sha256": sha,
            **retrieval,
        },
        "conversion": conversion,
        "raw_event_time_format": fmt,
        "checks": checks,
    }
    write_json(EVIDENCE_DIR / "ingest.json", ingest)
    if not all(checks.values()):
        print(json.dumps(checks, indent=2))
        sys.exit("HALT: an ingest check failed; data-source.md not written.")
    write_text(DATA_SOURCE_MD, render_data_source_md(ingest))
    return ingest


def recheck() -> dict[str, Any]:
    """Rerun the raw-file checks on the existing CSV without downloading or converting.

    Halts unless the CSV hash equals docs/data-source.md, then adds the UTC
    round trip to ingest.json and regenerates data-source.md.
    """
    sha = require_dataset_hash_match()
    ingest_path = EVIDENCE_DIR / "ingest.json"
    ingest = json.loads(ingest_path.read_text(encoding="utf-8"))
    if ingest["raw_file"]["sha256"] != sha:
        sys.exit("HALT: ingest.json does not describe the current raw file.")
    con = connect()
    print("Running UTC round trip on the raw CSV ...", flush=True)
    rt = utc_round_trip(con)
    ingest["utc_round_trip"] = rt
    ingest["checks"]["utc_round_trip_exact"] = rt["rows_changed_by_round_trip"] == 0
    ingest["checks"]["utc_round_trip_covers_all_rows"] = rt["rows_checked"] == ingest["conversion"]["parquet_rows"]
    ingest["manifest"] = manifest(f"{SCRIPT} --recheck", sha)
    write_json(ingest_path, ingest)
    if not all(ingest["checks"].values()):
        print(json.dumps(ingest["checks"], indent=2))
        sys.exit("HALT: a recheck failed; data-source.md not written.")
    write_text(DATA_SOURCE_MD, render_data_source_md(ingest))
    return ingest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--recheck", action="store_true",
                        help="rerun raw-file checks on the existing CSV; no download or conversion")
    args = parser.parse_args()
    if args.recheck:
        ingest = recheck()
        print(json.dumps({"utc_round_trip": ingest["utc_round_trip"], "checks": ingest["checks"]}, indent=2))
        return
    ingest = run(args.force_download)
    print(json.dumps({k: ingest[k] for k in ("raw_file", "checks")}, indent=2))
    c = ingest["conversion"]
    print(
        f"rows: newline={c['csv_rows_newline_count']} duckdb_csv={c['csv_rows_duckdb']} "
        f"parquet={c['parquet_rows']}"
    )


if __name__ == "__main__":
    main()
