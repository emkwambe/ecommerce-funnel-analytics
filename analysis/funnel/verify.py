"""Independent verification of the dbt marts (Sprint 1 Step 4).

Run: python -m funnel.verify

Recomputes the headline metrics directly from the Parquet file with separately written DuckDB
SQL that does not read any dbt model, then compares each with the marts in
data/warehouse.duckdb: integers and DECIMAL sums exactly, rates to 1e-9. Data-quality overlaps
with Sprint 0 are compared like with like: raw-basis figures recomputed here against Sprint 0's
profile.json, and the contract-basis figures recomputed here against mart_data_quality.
Writes ai-workflow/evidence/sprint-1/verify.json and exits non-zero on any mismatch.
"""

from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from typing import Any

import duckdb

from funnel.common import (
    DATA_DIR,
    DUCKDB_TMP_DIR,
    EVIDENCE_DIR,
    PARQUET_FILE,
    REPO_ROOT,
    manifest,
    require_available_ram,
    require_dataset_hash_match,
    write_json,
)
from funnel.ingest import connect
from funnel.profile import SpillSampler

SCRIPT = "funnel.verify"
WAREHOUSE = DATA_DIR / "warehouse.duckdb"
OUT = REPO_ROOT / "ai-workflow" / "evidence" / "sprint-1" / "verify.json"
RATE_TOLERANCE = 1e-9


def _one(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[Any, ...]:
    return con.execute(sql).fetchone()


def build_independent_tables(con: duckdb.DuckDBPyConnection, source: str | None = None) -> None:
    """Deduplicated events and valid sessions, written without reference to the dbt models."""
    source = source or f"read_parquet('{PARQUET_FILE.as_posix()}')"
    con.execute(f"CREATE VIEW raw_events AS SELECT * FROM {source}")
    con.execute("CREATE TEMP TABLE ev AS SELECT DISTINCT * FROM raw_events")
    con.execute("""
        CREATE TEMP TABLE good_sessions AS
        SELECT user_session
        FROM ev
        WHERE user_session IS NOT NULL
        GROUP BY user_session
        HAVING min(user_id) = max(user_id) OR min(user_id) IS NULL
    """)
    con.execute("""
        CREATE TEMP TABLE vev AS
        SELECT ev.* FROM ev WHERE user_session IN (SELECT user_session FROM good_sessions)
    """)


def independent_headline(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    sessions, orders, viewing, viewing_with_cart, carting = _one(con, """
        SELECT count(*),
               count(*) FILTER (WHERE n_purchase > 0),
               count(*) FILTER (WHERE n_view > 0),
               count(*) FILTER (WHERE n_view > 0 AND n_cart > 0),
               count(*) FILTER (WHERE n_cart > 0)
        FROM (
            SELECT user_session,
                   sum(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS n_view,
                   sum(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS n_cart,
                   sum(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS n_purchase
            FROM vev GROUP BY user_session
        )
    """)
    carting_with_carted_purchase = _one(con, """
        SELECT count(DISTINCT p.user_session)
        FROM vev AS p
        WHERE p.event_type = 'purchase'
          AND EXISTS (SELECT 1 FROM vev AS c
                      WHERE c.event_type = 'cart' AND c.user_session = p.user_session
                        AND c.product_id = p.product_id)
    """)[0]
    revenue = _one(con, """
        SELECT sum(CAST(price AS DECIMAL(18, 2))) FROM vev WHERE event_type = 'purchase'
    """)[0]
    revenue_secondary = _one(con, """
        SELECT sum(CAST(price AS DECIMAL(18, 2))) FROM (
            SELECT price, row_number() OVER (PARTITION BY user_session, product_id ORDER BY event_time) AS rn
            FROM vev WHERE event_type = 'purchase'
        ) WHERE rn = 1
    """)[0]
    path_rows = con.execute("""
        WITH carted AS (SELECT DISTINCT user_session, product_id FROM vev WHERE event_type = 'cart')
        SELECT CASE WHEN c.user_session IS NULL THEN 'Purchase with no observed same-session cart event'
                    ELSE 'Purchase with an observed same-session cart event' END AS path,
               count(*), sum(CAST(p.price AS DECIMAL(18, 2)))
        FROM vev AS p LEFT JOIN carted AS c USING (user_session, product_id)
        WHERE p.event_type = 'purchase'
        GROUP BY 1
    """).fetchall()
    carted_value = _one(con, """
        WITH carted_pairs AS (SELECT DISTINCT user_session, product_id FROM vev WHERE event_type = 'cart'),
        purchased_pairs AS (SELECT DISTINCT user_session, product_id FROM vev WHERE event_type = 'purchase'),
        latest_nonzero AS (
            SELECT user_session, product_id, price,
                   row_number() OVER (PARTITION BY user_session, product_id ORDER BY event_time DESC) AS rn
            FROM vev WHERE event_type = 'cart' AND price > 0
        )
        SELECT sum(CAST(l.price AS DECIMAL(18, 2)))
        FROM carted_pairs AS cp
        LEFT JOIN purchased_pairs AS pp USING (user_session, product_id)
        JOIN latest_nonzero AS l USING (user_session, product_id)
        WHERE pp.user_session IS NULL AND l.rn = 1
    """)[0]
    return {
        "valid_sessions": int(sessions),
        "orders": int(orders),
        "revenue": Decimal(revenue),
        "revenue_repeat_collapsed": Decimal(revenue_secondary),
        "session_purchase_rate": orders / sessions,
        "view_to_cart_session_rate": viewing_with_cart / viewing,
        "cart_session_purchase_rate": carting_with_carted_purchase / carting,
        "revenue_share_by_path": {path: Decimal(rev) / Decimal(revenue) for path, _, rev in path_rows},
        "purchase_events_by_path": {path: int(n) for path, n, _ in path_rows},
        "carted_value_with_no_observed_purchase": Decimal(carted_value),
    }


def independent_data_quality(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, int]]:
    """The four overlapping checks, on both bases."""
    raw = _one(con, """
        SELECT count(*) FILTER (WHERE price = 0), count(*) FILTER (WHERE user_session IS NULL) FROM raw_events
    """)
    raw_multi = _one(con, """
        SELECT count(*) FROM (SELECT user_session FROM raw_events WHERE user_session IS NOT NULL
                              GROUP BY user_session HAVING min(user_id) <> max(user_id))
    """)[0]
    raw_rows, dedup_rows = _one(con, "SELECT (SELECT count(*) FROM raw_events), (SELECT count(*) FROM ev)")
    dedup_null, dedup_multi = _one(con, """
        SELECT (SELECT count(*) FROM ev WHERE user_session IS NULL),
               (SELECT count(*) FROM (SELECT user_session FROM ev WHERE user_session IS NOT NULL
                                      GROUP BY user_session HAVING min(user_id) <> max(user_id)))
    """)
    valid_zero = _one(con, "SELECT count(*) FROM vev WHERE price = 0")[0]

    def cart_no_view(table: str) -> int:
        """Cart events whose (session, product) has no view at or before the cart time: compared
        with the pair's earliest view, not with a per-event NOT EXISTS as in the dbt mart."""
        return int(_one(con, f"""
            WITH first_view AS (
                SELECT user_session, product_id, min(event_time) AS first_view_time
                FROM {table} WHERE event_type = 'view' AND user_session IS NOT NULL
                GROUP BY user_session, product_id
            )
            SELECT count(*)
            FROM {table} AS c
            LEFT JOIN first_view AS f USING (user_session, product_id)
            WHERE c.event_type = 'cart' AND c.user_session IS NOT NULL
              AND (f.first_view_time IS NULL OR f.first_view_time > c.event_time)
        """)[0])
    return {
        "raw_basis": {
            "exact_duplicate_rows_removed": int(raw_rows - dedup_rows),
            "zero_price_events": int(raw[0]),
            "null_session_events": int(raw[1]),
            "multi_user_sessions": int(raw_multi),
            "cart_events_with_no_view_at_or_before": cart_no_view("raw_events"),
        },
        "contract_basis": {
            "exact_duplicate_rows_removed": int(raw_rows - dedup_rows),
            "null_session_events_excluded": int(dedup_null),
            "multi_user_sessions_excluded": int(dedup_multi),
            "zero_price_events": int(valid_zero),
            "cart_events_with_no_view_at_or_before": cart_no_view("vev"),
        },
    }


def mart_values(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    con.execute(f"ATTACH '{WAREHOUSE.as_posix()}' AS wh (READ_ONLY)")
    m = con.execute("""
        SELECT sessions, orders, revenue, revenue_repeat_collapsed, session_purchase_rate,
               view_to_cart_session_rate, cart_session_purchase_rate
        FROM wh.main_marts.mart_kpis_daily WHERE period_type = 'month'
    """).fetchone()
    paths = con.execute("SELECT purchase_path, purchase_events, revenue_share FROM wh.main_marts.mart_purchase_paths").fetchall()
    carted_value = _one(con, """
        SELECT sum(carted_value_with_no_observed_purchase) FROM wh.main_marts.mart_funnel_category
        WHERE category_level = 'category_top'
    """)[0]
    dq = dict(con.execute("SELECT metric_key, value FROM wh.main_marts.mart_data_quality").fetchall())
    return {
        "valid_sessions": int(m[0]),
        "orders": int(m[1]),
        "revenue": Decimal(m[2]),
        "revenue_repeat_collapsed": Decimal(m[3]),
        "session_purchase_rate": m[4],
        "view_to_cart_session_rate": m[5],
        "cart_session_purchase_rate": m[6],
        "revenue_share_by_path": {p: s for p, _, s in paths},
        "purchase_events_by_path": {p: int(n) for p, n, _ in paths},
        "carted_value_with_no_observed_purchase": Decimal(carted_value),
        "data_quality": {k: dq[k] for k in ("exact_duplicate_rows_removed", "null_session_events_excluded",
                                            "multi_user_sessions_excluded", "zero_price_events",
                                            "cart_events_with_no_view_at_or_before")},
    }


def _match(a: Any, b: Any) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) <= RATE_TOLERANCE
    return a == b


def compare(independent: dict[str, Any], mart: dict[str, Any], dq: dict[str, dict[str, int]],
            sprint0: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ind: Any, other: Any, against: str) -> None:
        checks.append({"check": name, "against": against, "independent": str(ind), "compared": str(other),
                       "match": _match(ind, other)})

    for key in ("valid_sessions", "orders", "revenue", "revenue_repeat_collapsed", "session_purchase_rate",
                "view_to_cart_session_rate", "cart_session_purchase_rate",
                "carted_value_with_no_observed_purchase"):
        add(key, independent[key], mart[key], "mart")
    for path, share in independent["revenue_share_by_path"].items():
        add(f"revenue_share:{path}", float(share), float(mart["revenue_share_by_path"][path]), "mart")
        add(f"purchase_events:{path}", independent["purchase_events_by_path"][path],
            mart["purchase_events_by_path"][path], "mart")
    for key, value in dq["contract_basis"].items():
        add(f"data_quality:{key}", value, int(mart["data_quality"][key]), "mart_data_quality (same basis)")
    s0 = {
        "exact_duplicate_rows_removed": sprint0["duplicates"]["exact_duplicate_rows"]["surplus_rows"],
        "zero_price_events": sprint0["price"]["zero_price_events"],
        "null_session_events": sprint0["sessions_users"]["null_user_session_events"],
        "multi_user_sessions": sprint0["sessions_users"]["sessions_with_more_than_one_user_id"],
        "cart_events_with_no_view_at_or_before":
            sprint0["ordering_anomalies"]["cart_events_with_no_view_at_or_before_in_session"],
    }
    for key, value in dq["raw_basis"].items():
        add(f"sprint0_raw_basis:{key}", value, s0[key], "Sprint 0 profile.json (raw basis)")
    return checks


def main() -> None:
    started = time.perf_counter()
    available = require_available_ram()
    sha = require_dataset_hash_match()
    if not WAREHOUSE.exists():
        sys.exit(f"HALT: {WAREHOUSE} missing; run python -m funnel.build first.")
    con = connect()
    sampler = SpillSampler(DUCKDB_TMP_DIR)
    sampler.start()
    try:
        print("Building independent deduplicated events and valid sessions ...", flush=True)
        build_independent_tables(con)
        print("Recomputing headline metrics ...", flush=True)
        independent = independent_headline(con)
        print("Recomputing data-quality overlaps ...", flush=True)
        dq = independent_data_quality(con)
        mart = mart_values(con)
    finally:
        peak_spill = sampler.stop()
    sprint0 = json.loads((EVIDENCE_DIR / "profile.json").read_text(encoding="utf-8"))
    checks = compare(independent, mart, dq, sprint0)
    elapsed = round(time.perf_counter() - started, 1)
    ok = all(c["match"] for c in checks)
    write_json(OUT, {
        "manifest": manifest(SCRIPT, sha),
        "available_ram_gb_before_run": available,
        "elapsed_seconds": elapsed,
        "peak_spill_bytes": peak_spill,
        "rate_tolerance": RATE_TOLERANCE,
        "all_match": ok,
        "checks": checks,
    })
    for c in checks:
        print(f"{'OK  ' if c['match'] else 'FAIL'} {c['check']}: independent={c['independent']} "
              f"{c['against']}={c['compared']}")
    print(f"Elapsed: {elapsed} s; peak spill: {peak_spill} bytes ({round(peak_spill / 1024**3, 2)} GiB); "
          f"all_match={ok}", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
