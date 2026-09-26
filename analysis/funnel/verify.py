"""Independent verification of the dbt marts (Sprint 1 Step 4).

Run: python -m funnel.verify

Recomputes the headline metrics directly from the Parquet file with separately written DuckDB
SQL that does not read any dbt model, then compares each with the marts in
data/warehouse.duckdb: integers and DECIMAL sums exactly, rates to 1e-9. Data-quality overlaps
with Sprint 0 are compared like with like: raw-basis figures recomputed here against Sprint 0's
profile.json, and the contract-basis figures recomputed here against mart_data_quality.
Sprint 2 adds R2 for analysis A (the revenue difference, its breakdown and thresholds, and the two
secondary cases) and for analysis B (the B1 7-day count and value shares, with their counts and sums). Writes verify.json under the current sprint's evidence folder (CURRENT_EVIDENCE_DIR
in funnel.common) and exits non-zero on any mismatch.
"""

from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from typing import Any

import duckdb

from funnel.common import (
    CURRENT_EVIDENCE_DIR,
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
OUT = CURRENT_EVIDENCE_DIR / "verify.json"
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
    # Changes 2026-09-26 (third entry): per purchasing session, whether any purchased product has a
    # cart event in the session; recomputed here from events, not from the mart's pair rollup.
    only_uncarted, cart_sessions_no_carted_purchase = _one(con, """
        WITH carted AS (SELECT DISTINCT user_session, product_id FROM vev WHERE event_type = 'cart'),
        purchasing AS (
            SELECT p.user_session, max(CASE WHEN c.user_session IS NULL THEN 0 ELSE 1 END) AS any_carted
            FROM vev AS p LEFT JOIN carted AS c USING (user_session, product_id)
            WHERE p.event_type = 'purchase'
            GROUP BY p.user_session
        ),
        carting AS (SELECT DISTINCT user_session FROM vev WHERE event_type = 'cart')
        SELECT count(*) FILTER (WHERE any_carted = 0),
               count(*) FILTER (WHERE any_carted = 0 AND user_session IN (SELECT user_session FROM carting))
        FROM purchasing
    """)
    return {
        "sessions_with_purchases_only_of_uncarted_products": int(only_uncarted),
        "cart_sessions_with_purchase_of_no_carted_product": int(cart_sessions_no_carted_purchase),
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


# Sprint 2, analysis A (metrics.md Changes 2026-09-26, Sprint 2 investigations, A items 1-6).
A_DIMENSIONS = ("time_since_previous_purchase", "price_vs_first_purchase", "category_top",
                "purchase_events_in_pair", "time_by_price")
A_THRESHOLDS_SECONDS = (0, 1, 5, 10, 30, 60, 300, 1800, 3600)


def independent_revenue_gap(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Repeat purchase events and their breakdown, recomputed from vev without the dbt models.

    The previous purchase time comes from a window frame over earlier timestamps plus a tie count,
    not from the self-join int_repeat_purchase_events uses."""
    con.execute("""
        CREATE OR REPLACE TEMP TABLE repeat_purchases AS
        WITH p AS (
            SELECT
                user_session, product_id, event_time,
                CAST(price AS DECIMAL(18, 2)) AS amount,
                CASE WHEN category_code IS NULL OR trim(category_code) = '' THEN 'unknown'
                     ELSE split_part(trim(category_code), '.', 1) END AS top,
                count(*) OVER (PARTITION BY user_session, product_id) AS n_in_pair,
                count(*) OVER (PARTITION BY user_session, product_id, event_time) AS n_same_time,
                max(event_time) OVER (
                    PARTITION BY user_session, product_id ORDER BY event_time
                    RANGE BETWEEN UNBOUNDED PRECEDING AND INTERVAL 1 SECOND PRECEDING
                ) AS earlier_time,
                min(event_time) OVER (PARTITION BY user_session, product_id) AS first_time,
                row_number() OVER (PARTITION BY user_session, product_id ORDER BY event_time) AS k
            FROM vev
            WHERE event_type = 'purchase'
        ),
        first_prices AS (
            SELECT DISTINCT user_session, product_id, amount AS first_amount
            FROM p WHERE event_time = first_time
        )
        SELECT p.*, f.first_amount,
               CASE WHEN p.n_same_time > 1 THEN 0
                    ELSE CAST(epoch(p.event_time) - epoch(p.earlier_time) AS BIGINT) END AS gap_seconds
        FROM p
        JOIN first_prices AS f USING (user_session, product_id)
        WHERE p.n_in_pair > 1 AND p.k > 1
    """)
    rows = con.execute("""
        SELECT
            CASE WHEN gap_seconds = 0 THEN 'same_second' WHEN gap_seconds < 60 THEN 'under_a_minute'
                 ELSE 'a_minute_or_more' END AS t,
            CASE WHEN amount = first_amount THEN 'same_price' ELSE 'different_price' END AS pr,
            top,
            CASE WHEN n_in_pair = 2 THEN '2' WHEN n_in_pair = 3 THEN '3' ELSE '4_or_more' END AS sz,
            gap_seconds,
            amount
        FROM repeat_purchases
    """).fetchall()
    by: dict[str, dict[str, list[Any]]] = {d: {} for d in A_DIMENSIONS}
    for t, pr, top, sz, _, amount in rows:
        for dim, key in zip(A_DIMENSIONS, (t, pr, top, sz, f"{t}|{pr}")):
            cell = by[dim].setdefault(key, [0, Decimal(0)])
            cell[0] += 1
            cell[1] += amount
    return {
        "repeat_purchase_events": len(rows),
        "repeat_purchase_value": sum((r[5] for r in rows), Decimal(0)),
        "by_dimension": {d: {k: (n, v) for k, (n, v) in cells.items()} for d, cells in by.items()},
        "thresholds": {s: sum((r[5] for r in rows if r[4] <= s), Decimal(0)) for s in A_THRESHOLDS_SECONDS},
    }


def independent_duplicate_breakdown(con: duckdb.DuckDBPyConnection) -> dict[str, tuple[int, int]]:
    """A-S1: identical raw rows by event type and group size -> (groups, rows removed)."""
    rows = con.execute("""
        SELECT event_type,
               CASE WHEN n = 2 THEN '2' WHEN n = 3 THEN '3' ELSE '4_or_more' END AS size,
               count(*), sum(n - 1)
        FROM (SELECT event_type, count(*) AS n FROM raw_events
              GROUP BY event_time, event_type, product_id, category_id, category_code, brand, price,
                       user_id, user_session)
        WHERE n > 1
        GROUP BY 1, 2
    """).fetchall()
    return {f"{event_type}:{size}": (int(groups), int(removed)) for event_type, size, groups, removed in rows}


def independent_cart_no_view_attribution(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """A-S2: raw-basis cart events with no view at or before them (first-view comparison, as in
    independent_data_quality), attributed to null sessions, multi-user sessions, and duplicates."""
    con.execute("""
        CREATE OR REPLACE TEMP TABLE raw_basis_carts AS
        WITH first_view AS (
            SELECT user_session, product_id, min(event_time) AS first_view_time
            FROM raw_events WHERE event_type = 'view' AND user_session IS NOT NULL
            GROUP BY user_session, product_id
        )
        SELECT c.*
        FROM raw_events AS c
        LEFT JOIN first_view AS f USING (user_session, product_id)
        WHERE c.event_type = 'cart' AND c.user_session IS NOT NULL AND c.product_id IS NOT NULL
          AND (f.first_view_time IS NULL OR f.first_view_time > c.event_time)
    """)
    total, null_session, multi_user, in_valid, distinct_in_valid = _one(con, """
        SELECT
            count(*),
            count(*) FILTER (WHERE user_session IS NULL),
            count(*) FILTER (WHERE user_session IS NOT NULL
                             AND user_session NOT IN (SELECT user_session FROM good_sessions)),
            count(*) FILTER (WHERE user_session IN (SELECT user_session FROM good_sessions)),
            (SELECT count(*) FROM (SELECT DISTINCT * FROM raw_basis_carts
                                   WHERE user_session IN (SELECT user_session FROM good_sessions)))
        FROM raw_basis_carts
    """)
    return {
        "raw_basis_count": int(total),
        "in_null_session_events": int(null_session),
        "in_multi_user_sessions": int(multi_user),
        "removed_as_exact_duplicates": int(in_valid - distinct_in_valid),
        "remaining_after_attribution": int(distinct_in_valid),
    }


def mart_values_investigation_a(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Analysis A marts; call after mart_values has attached the warehouse."""
    decomposition = con.execute("""
        SELECT dimension, group_key, repeat_purchase_events, repeat_purchase_value, revenue_difference
        FROM wh.main_marts.mart_revenue_gap_decomposition
    """).fetchall()
    thresholds = dict(con.execute("""
        SELECT threshold_seconds, repeat_purchase_value_within FROM wh.main_marts.mart_revenue_gap_thresholds
    """).fetchall())
    duplicates = {k: (int(g), int(r)) for k, g, r in con.execute("""
        SELECT row_key, duplicate_groups, rows_removed FROM wh.main_marts.mart_duplicate_rows_breakdown
    """).fetchall()}
    cart = con.execute("SELECT * FROM wh.main_marts.mart_cart_no_view_reconciliation").fetchdf().iloc[0].to_dict()
    total = next(r for r in decomposition if r[0] == "total")
    return {
        "repeat_purchase_events": int(total[2]),
        "repeat_purchase_value": Decimal(total[3]),
        "revenue_difference": Decimal(total[4]),
        "by_dimension": {d: {k: (int(n), Decimal(v)) for dim, k, n, v, _ in decomposition if dim == d}
                         for d in A_DIMENSIONS},
        "thresholds": {int(s): Decimal(v) for s, v in thresholds.items()},
        "duplicates": duplicates,
        "cart_no_view": {k: int(cart[k]) for k in ("raw_basis_count", "in_null_session_events",
                                                   "in_multi_user_sessions", "removed_as_exact_duplicates",
                                                   "contract_basis_count", "remainder")},
    }


def compare_investigation_a(independent: dict[str, Any], headline: dict[str, Any],
                            mart: dict[str, Any]) -> list[dict[str, Any]]:
    """R2 checks for analysis A; every count and DECIMAL sum must match exactly."""
    checks: list[dict[str, Any]] = []

    def add(name: str, ind: Any, other: Any, against: str) -> None:
        checks.append({"check": name, "against": against, "independent": str(ind), "compared": str(other),
                       "match": _match(ind, other)})

    gap = independent["revenue_gap"]
    add("A:revenue_difference (revenue - repeat collapsed, independent)",
        headline["revenue"] - headline["revenue_repeat_collapsed"], mart["revenue_difference"],
        "mart_revenue_gap_decomposition")
    add("A:repeat_purchase_value equals the independent difference", gap["repeat_purchase_value"],
        headline["revenue"] - headline["revenue_repeat_collapsed"], "independent headline")
    add("A:repeat_purchase_value", gap["repeat_purchase_value"], mart["repeat_purchase_value"],
        "mart_revenue_gap_decomposition")
    add("A:repeat_purchase_events", gap["repeat_purchase_events"], mart["repeat_purchase_events"],
        "mart_revenue_gap_decomposition")
    for dim in A_DIMENSIONS:
        keys = sorted(set(gap["by_dimension"][dim]) | set(mart["by_dimension"][dim]))
        for key in keys:
            ind = gap["by_dimension"][dim].get(key, (0, Decimal(0)))
            mrt = mart["by_dimension"][dim].get(key, (0, Decimal(0)))
            add(f"A:{dim}:{key}:events", ind[0], mrt[0], "mart_revenue_gap_decomposition")
            add(f"A:{dim}:{key}:value", ind[1], mrt[1], "mart_revenue_gap_decomposition")
    for seconds in A_THRESHOLDS_SECONDS:
        add(f"A:threshold_{seconds}s:value", gap["thresholds"][seconds], mart["thresholds"].get(seconds),
            "mart_revenue_gap_thresholds")
    dups = independent["duplicates"]
    for key in sorted(set(dups) | set(mart["duplicates"])):
        ind, mrt = dups.get(key, (0, 0)), mart["duplicates"].get(key, (0, 0))
        add(f"A-S1:{key}:groups", ind[0], mrt[0], "mart_duplicate_rows_breakdown")
        add(f"A-S1:{key}:rows_removed", ind[1], mrt[1], "mart_duplicate_rows_breakdown")
    cart = independent["cart_no_view"]
    for key in ("raw_basis_count", "in_null_session_events", "in_multi_user_sessions",
                "removed_as_exact_duplicates"):
        add(f"A-S2:{key}", cart[key], mart["cart_no_view"][key], "mart_cart_no_view_reconciliation")
    add("A-S2:remaining_after_attribution equals the contract-basis count", cart["remaining_after_attribution"],
        mart["cart_no_view"]["contract_basis_count"], "mart_cart_no_view_reconciliation")
    add("A-S2:remainder", 0, mart["cart_no_view"]["remainder"], "mart_cart_no_view_reconciliation")
    return checks


# Sprint 2, analysis B (metrics.md Changes 2026-09-26, Sprint 2 investigations, B items 7-10).
B1_CUTOFF = "2019-10-24 23:59:59"
B1_WINDOW_DAYS = 7


def independent_later_purchases_b1(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """B1 (7 days) recomputed from vev without the dbt models: all four later-purchase conditions tested in
    one correlated EXISTS per eligible pair, rather than a first-purchase minimum followed by a window."""
    eligible, followed, eligible_value, followed_value = _one(con, f"""
        WITH sess AS (
            SELECT user_session, min(user_id) AS user_id, min(event_time) AS session_start
            FROM vev GROUP BY user_session
        ),
        carts AS (
            SELECT user_session, product_id, max(event_time) AS latest_cart_time
            FROM vev WHERE event_type = 'cart' GROUP BY user_session, product_id
        ),
        bought AS (SELECT DISTINCT user_session, product_id FROM vev WHERE event_type = 'purchase'),
        latest_nonzero AS (
            SELECT user_session, product_id, CAST(price AS DECIMAL(18, 2)) AS value,
                   row_number() OVER (PARTITION BY user_session, product_id ORDER BY event_time DESC) AS rn
            FROM vev WHERE event_type = 'cart' AND price > 0
        ),
        eligible AS (
            SELECT c.user_session, c.product_id, c.latest_cart_time, s.user_id, s.session_start, l.value
            FROM carts AS c
            JOIN sess AS s USING (user_session)
            LEFT JOIN bought AS b USING (user_session, product_id)
            LEFT JOIN (SELECT * FROM latest_nonzero WHERE rn = 1) AS l USING (user_session, product_id)
            WHERE b.user_session IS NULL AND s.session_start <= TIMESTAMP '{B1_CUTOFF}'
        ),
        purchases AS (
            SELECT p.user_session, p.product_id, p.event_time, s.user_id, s.session_start AS purchase_session_start
            FROM vev AS p JOIN sess AS s USING (user_session)
            WHERE p.event_type = 'purchase'
        ),
        flagged AS (
            SELECT e.*, EXISTS (
                SELECT 1 FROM purchases AS p
                WHERE p.user_id = e.user_id AND p.product_id = e.product_id
                  AND p.user_session <> e.user_session
                  AND p.purchase_session_start > e.session_start
                  AND p.event_time > e.latest_cart_time
                  AND p.event_time >= e.session_start
                  AND p.event_time < e.session_start + INTERVAL {B1_WINDOW_DAYS} DAY
            ) AS is_followed
            FROM eligible AS e
        )
        SELECT count(*), count(*) FILTER (WHERE is_followed),
               coalesce(sum(value), 0), coalesce(sum(value) FILTER (WHERE is_followed), 0)
        FROM flagged
    """)
    return {
        "eligible_pairs": int(eligible),
        "followed_pairs": int(followed),
        "eligible_value": Decimal(eligible_value),
        "followed_value": Decimal(followed_value),
        "count_share": followed / eligible,
        "value_share": float(Decimal(followed_value) / Decimal(eligible_value)),
    }


def mart_values_investigation_b(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """B1 from the marts; call after mart_values has attached the warehouse."""
    row = con.execute("""
        SELECT eligible_pairs, followed_pairs, eligible_value, followed_value, count_share, value_share
        FROM wh.main_marts.mart_later_purchase_estimates WHERE spec_key = 'B1'
    """).fetchone()
    return {"eligible_pairs": int(row[0]), "followed_pairs": int(row[1]), "eligible_value": Decimal(row[2]),
            "followed_value": Decimal(row[3]), "count_share": row[4], "value_share": row[5]}


def compare_investigation_b(independent: dict[str, Any], mart: dict[str, Any]) -> list[dict[str, Any]]:
    """R2 checks for B1: counts and DECIMAL sums exactly, shares within RATE_TOLERANCE."""
    return [{"check": f"B1:{key}", "against": "mart_later_purchase_estimates", "independent": str(independent[key]),
             "compared": str(mart[key]), "match": _match(independent[key], mart[key])}
            for key in ("eligible_pairs", "followed_pairs", "eligible_value", "followed_value",
                        "count_share", "value_share")]


def mart_values(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    con.execute(f"ATTACH '{WAREHOUSE.as_posix()}' AS wh (READ_ONLY)")
    m = con.execute("""
        SELECT sessions, orders, revenue, revenue_repeat_collapsed, session_purchase_rate,
               view_to_cart_session_rate, cart_session_purchase_rate,
               sessions_with_purchases_only_of_uncarted_products, cart_sessions_with_purchase_of_no_carted_product
        FROM wh.main_marts.mart_kpis_daily WHERE period_type = 'month'
    """).fetchone()
    paths = con.execute("SELECT purchase_path, purchase_events, revenue_share FROM wh.main_marts.mart_purchase_paths").fetchall()
    carted_value = _one(con, """
        SELECT sum(carted_value_with_no_observed_purchase) FROM wh.main_marts.mart_funnel_category
        WHERE category_level = 'category_top'
    """)[0]
    dq = dict(con.execute("SELECT metric_key, value FROM wh.main_marts.mart_data_quality").fetchall())
    return {
        "sessions_with_purchases_only_of_uncarted_products": int(m[7]),
        "cart_sessions_with_purchase_of_no_carted_product": int(m[8]),
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
                "carted_value_with_no_observed_purchase", "sessions_with_purchases_only_of_uncarted_products",
                "cart_sessions_with_purchase_of_no_carted_product"):
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
        print("Recomputing analysis A (revenue difference, secondary cases) ...", flush=True)
        investigation_a = {"revenue_gap": independent_revenue_gap(con),
                           "duplicates": independent_duplicate_breakdown(con),
                           "cart_no_view": independent_cart_no_view_attribution(con)}
        print("Recomputing analysis B (B1, 7 days) ...", flush=True)
        investigation_b = independent_later_purchases_b1(con)
        mart = mart_values(con)
        mart_a = mart_values_investigation_a(con)
        mart_b = mart_values_investigation_b(con)
    finally:
        peak_spill = sampler.stop()
    sprint0 = json.loads((EVIDENCE_DIR / "profile.json").read_text(encoding="utf-8"))
    checks = (compare(independent, mart, dq, sprint0) + compare_investigation_a(investigation_a, independent, mart_a)
              + compare_investigation_b(investigation_b, mart_b))
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
