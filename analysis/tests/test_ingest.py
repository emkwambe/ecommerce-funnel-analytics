"""Ingest: row-count agreement on a small CSV, the real ingest record, and the hash gate."""

from __future__ import annotations

import json

import duckdb
import pytest

from funnel import common
from funnel.common import EVIDENCE_DIR
from funnel.ingest import convert_to_parquet, count_csv_data_lines, raw_event_time_format

CSV = (
    "event_time,event_type,product_id,category_id,category_code,brand,price,user_id,user_session\n"
    "2019-10-01 00:00:00 UTC,view,1,10,a.b,x,1.5,100,s1\n"
    "2019-10-01 00:00:01 UTC,cart,1,10,a.b,x,1.5,100,s1\n"
    "2019-10-01 00:00:02 UTC,purchase,1,10,,,1.5,100,\n"
)


def test_parquet_row_count_equals_csv_row_count_on_small_file(tmp_path):
    csv = tmp_path / "small.csv"
    csv.write_bytes(CSV.encode("utf-8"))
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    result = convert_to_parquet(con, csv, tmp_path / "small.parquet")
    assert count_csv_data_lines(csv) == result["csv_rows_duckdb"] == result["parquet_rows"] == 3
    assert result["csv_columns"] == result["parquet_columns"]
    fmt = raw_event_time_format(con, csv)
    assert fmt["rows_not_matching"] == 0
    assert fmt["suffixes_after_time"] == [{"suffix": " UTC", "rows": 3}]


def test_count_csv_data_lines_without_trailing_newline(tmp_path):
    csv = tmp_path / "no_trailing.csv"
    csv.write_bytes(CSV.rstrip("\n").encode("utf-8"))
    assert count_csv_data_lines(csv) == 3


def test_real_ingest_parquet_row_count_equals_csv_row_count():
    ingest = json.loads((EVIDENCE_DIR / "ingest.json").read_text(encoding="utf-8"))
    conv = ingest["conversion"]
    assert conv["csv_rows_newline_count"] == conv["csv_rows_duckdb"] == conv["parquet_rows"]
    assert conv["csv_columns"] == conv["parquet_columns"]
    assert ingest["checks"] == {
        "size_matches_kaggle_listing": True, "row_counts_match": True, "types_preserved": True,
    }
    assert ingest["raw_file"]["sha256"] == common.recorded_dataset_sha256()


def test_hash_gate_halts_on_mismatch(tmp_path, monkeypatch):
    raw = tmp_path / "raw.csv"
    raw.write_bytes(b"a,b\n1,2\n")
    doc = tmp_path / "data-source.md"
    doc.write_text("- **SHA-256:** `" + "0" * 64 + "`\n", encoding="utf-8")
    monkeypatch.setattr(common, "DATA_SOURCE_MD", doc)
    with pytest.raises(SystemExit, match="hash mismatch"):
        common.require_dataset_hash_match(raw)
    doc.write_text(f"- **SHA-256:** `{common.sha256_file(raw)}`\n", encoding="utf-8")
    assert common.require_dataset_hash_match(raw) == common.sha256_file(raw)
