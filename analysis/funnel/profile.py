"""Structural profile of the October 2019 event log (metric lock applies).

Run: python -m funnel.profile

Profiles structure and data quality only: schema, nulls, duplicates, value
ranges, overall event-type counts, time range, ordering anomalies. It computes
no conversion rate, revenue, or anything broken down by category, brand,
product, time period, or user segment.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import duckdb

from funnel.common import (
    DOCS_DIR,
    DUCKDB_MEMORY_LIMIT,
    DUCKDB_THREADS,
    DUCKDB_TMP_DIR,
    EVIDENCE_DIR,
    PARQUET_FILE,
    dir_size_bytes,
    require_available_ram,
    manifest,
    require_dataset_hash_match,
    write_json,
    write_text,
)
from funnel.ingest import connect

SCRIPT = "funnel.profile"
ID_LIKE_COLUMNS = ("product_id", "category_id", "user_id", "user_session")
TEXT_DIMENSION_COLUMNS = ("category_code", "brand")
ORDER_ID_NAME_PATTERN = re.compile(r"order|transaction|txn|invoice|basket|checkout|receipt", re.IGNORECASE)
PRICE_QUANTILES = {"min": 0.0, "p01": 0.01, "p50": 0.5, "p99": 0.99, "max": 1.0}
SESSION_SIZE_QUANTILES = {"min": 0.0, "p25": 0.25, "p50": 0.5, "p75": 0.75, "p90": 0.9, "p99": 0.99, "max": 1.0}

PUBLISHER_MULTIPLE_PURCHASES_QUOTE = (
    "### Multiple purchases per session\n\n"
    "A session can have multiple **purchase** events. It's ok, because it's a single order."
)


def _one(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[Any, ...]:
    return con.execute(sql).fetchone()


def _int(value: Any) -> int:
    return int(value) if value is not None else 0


def _column_list(con: duckdb.DuckDBPyConnection, t: str) -> str:
    return ", ".join(f'"{r[0]}"' for r in con.execute(f"DESCRIBE SELECT * FROM {t}").fetchall())


def _surplus_and_groups(
    con: duckdb.DuckDBPyConnection, t: str, keys: str, count_non_identical: bool = True
) -> dict[str, int]:
    """Rows beyond the first in each key group and the number of such groups.

    Optionally, in a separate query, how many key groups contain rows that are
    not exact copies (key groups with more than one distinct full row).
    """
    surplus, groups = _one(
        con,
        f"""
        SELECT sum(n - 1) FILTER (WHERE n > 1), count(*) FILTER (WHERE n > 1)
        FROM (SELECT count(*) AS n FROM {t} GROUP BY {keys})
        """,
    )
    out = {"surplus_rows": _int(surplus), "duplicate_groups": _int(groups)}
    if count_non_identical:
        out["groups_with_non_identical_rows"] = _int(_one(
            con,
            f"""
            SELECT count(*) FROM (
                SELECT 1 FROM (SELECT DISTINCT * FROM {t}) GROUP BY {keys} HAVING count(*) > 1
            )
            """,
        )[0])
    return out


def schema_and_completeness(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    described = con.execute(f"DESCRIBE SELECT * FROM {t}").fetchall()
    total = _one(con, f"SELECT count(*) FROM {t}")[0]
    columns = []
    for name, col_type, *_ in described:
        nulls = _one(con, f'SELECT count(*) FILTER (WHERE "{name}" IS NULL) FROM {t}')[0]
        columns.append({
            "name": name,
            "type": col_type,
            "null_count": int(nulls),
            "null_share": round(nulls / total, 6) if total else 0.0,
        })
    present = {c["name"] for c in columns}
    distinct = {
        col: int(_one(con, f'SELECT count(DISTINCT "{col}") FROM {t}')[0])
        for col in ID_LIKE_COLUMNS if col in present
    }
    return {"row_count": int(total), "columns": columns, "distinct_counts": distinct}


def time_checks(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    col_type = con.execute(f"SELECT typeof(event_time) FROM {t} LIMIT 1").fetchone()[0]
    start = f"CAST('2019-10-01 00:00:00' AS {col_type})"
    end = f"CAST('2019-11-01 00:00:00' AS {col_type})"
    min_t, max_t, before, after, nulls = _one(
        con,
        f"""
        SELECT CAST(min(event_time) AS VARCHAR), CAST(max(event_time) AS VARCHAR),
               count(*) FILTER (WHERE event_time < {start}),
               count(*) FILTER (WHERE event_time >= {end}),
               count(*) FILTER (WHERE event_time IS NULL)
        FROM {t}
        """,
    )
    sub_second = _one(
        con, f"SELECT count(*) FILTER (WHERE event_time <> date_trunc('second', event_time)) FROM {t}"
    )[0]
    return {
        "event_time_type": col_type,
        "session_timezone_for_display": "UTC",
        "min_event_time": min_t,
        "max_event_time": max_t,
        "events_before_2019_10_01_utc": int(before),
        "events_on_or_after_2019_11_01_utc": int(after),
        "events_outside_october_2019_utc": int(before) + int(after),
        "null_event_time": int(nulls),
        "events_with_sub_second_precision": int(sub_second),
    }


def event_types(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    rows = con.execute(
        f"SELECT event_type, count(*) FROM {t} GROUP BY 1 ORDER BY 2 DESC, 1"
    ).fetchall()
    return {
        "levels": [r[0] for r in rows],
        "counts": {("<NULL>" if r[0] is None else r[0]): int(r[1]) for r in rows},
    }


def duplicates(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    """Each check runs as its own sequential query."""
    return {
        "exact_duplicate_rows": _surplus_and_groups(
            con, t, _column_list(con, t), count_non_identical=False
        ),
        "near_duplicates_session_product_type_time": _surplus_and_groups(
            con, t, "user_session, product_id, event_type, event_time"
        ),
        "near_duplicates_session_product_type_same_second": _surplus_and_groups(
            con, t, "user_session, product_id, event_type, date_trunc('second', event_time)"
        ),
    }


def price_checks(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    zero, negative, nulls, zero_purchase, nonpos_purchase = _one(
        con,
        f"""
        SELECT count(*) FILTER (WHERE price = 0),
               count(*) FILTER (WHERE price < 0),
               count(*) FILTER (WHERE price IS NULL),
               count(*) FILTER (WHERE price = 0 AND event_type = 'purchase'),
               count(*) FILTER (WHERE price < 0 AND event_type = 'purchase')
        FROM {t}
        """,
    )
    qs = list(PRICE_QUANTILES.values())
    values = _one(con, f"SELECT quantile_disc(price, {qs}) FROM {t}")[0]
    multi_price_products, max_prices = _one(
        con,
        f"""
        SELECT count(*) FILTER (WHERE n_prices > 1), max(n_prices)
        FROM (SELECT product_id, count(DISTINCT price) AS n_prices FROM {t} GROUP BY product_id)
        """,
    )
    return {
        "zero_price_events": int(zero),
        "negative_price_events": int(negative),
        "null_price_events": int(nulls),
        "zero_price_purchase_events": int(zero_purchase),
        "negative_price_purchase_events": int(nonpos_purchase),
        "quantiles": {k: (float(v) if v is not None else None) for k, v in zip(PRICE_QUANTILES, values)},
        "products_with_more_than_one_distinct_price": _int(multi_price_products),
        "max_distinct_prices_for_one_product": _int(max_prices),
    }


def category_brand(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    total = _one(con, f"SELECT count(*) FROM {t}")[0]
    out: dict[str, Any] = {}
    for col in TEXT_DIMENSION_COLUMNS:
        nulls, empty = _one(
            con,
            f"SELECT count(*) FILTER (WHERE {col} IS NULL), "
            f"count(*) FILTER (WHERE trim({col}) = '') FROM {t}",
        )
        out[col] = {
            "null_count": int(nulls),
            "empty_string_count": int(empty),
            "null_or_empty_count": int(nulls) + int(empty),
            "null_or_empty_share": round((nulls + empty) / total, 6) if total else 0.0,
        }
    multi_code, mixed_null = _one(
        con,
        f"""
        SELECT count(*) FILTER (WHERE n_codes > 1), count(*) FILTER (WHERE n_codes >= 1 AND has_null)
        FROM (
            SELECT category_id, count(DISTINCT category_code) AS n_codes,
                   bool_or(category_code IS NULL) AS has_null
            FROM {t} GROUP BY category_id
        )
        """,
    )
    multi_id = _one(
        con,
        f"""
        SELECT count(*) FROM (
            SELECT category_code FROM {t} WHERE category_code IS NOT NULL
            GROUP BY category_code HAVING count(DISTINCT category_id) > 1
        )
        """,
    )[0]
    out["category_ids_mapping_to_more_than_one_category_code"] = _int(multi_code)
    out["category_ids_with_both_null_and_non_null_code"] = _int(mixed_null)
    out["category_codes_mapping_to_more_than_one_category_id"] = _int(multi_id)
    return out


def sessions_users(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    """Each check runs as its own sequential query. More than one user_id is
    detected as min(user_id) <> max(user_id), which equals count(DISTINCT
    user_id) > 1 (both ignore nulls) without a per-group distinct set."""
    null_sessions = _one(con, f"SELECT count(*) FILTER (WHERE user_session IS NULL) FROM {t}")[0]
    n_sessions = _one(con, f"SELECT count(DISTINCT user_session) FROM {t}")[0]
    multi_user = _one(
        con,
        f"""
        SELECT count(*) FROM (
            SELECT user_session FROM {t} WHERE user_session IS NOT NULL
            GROUP BY user_session HAVING min(user_id) <> max(user_id)
        )
        """,
    )[0]
    over_24h = _one(
        con,
        f"""
        SELECT count(*) FROM (
            SELECT user_session FROM {t} WHERE user_session IS NOT NULL
            GROUP BY user_session HAVING max(event_time) - min(event_time) > INTERVAL 24 HOUR
        )
        """,
    )[0]
    qs = list(SESSION_SIZE_QUANTILES.values())
    values = _one(
        con,
        f"""
        SELECT quantile_disc(n, {qs}) FROM (
            SELECT count(*) AS n FROM {t} WHERE user_session IS NOT NULL GROUP BY user_session
        )
        """,
    )[0]
    return {
        "null_user_session_events": int(null_sessions),
        "sessions_non_null": int(n_sessions),
        "sessions_with_more_than_one_user_id": int(multi_user),
        "sessions_spanning_more_than_24_hours": int(over_24h),
        "events_in_session_quantiles": {
            k: (int(v) if v is not None else None) for k, v in zip(SESSION_SIZE_QUANTILES, values)
        },
    }


def ordering_anomalies(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    """Counts only. Evaluated within (user_session, product_id); rows with a null
    session or product cannot be matched and are counted separately.

    Each check runs as its own sequential query, and each looks up earlier steps
    only for the (session, product) pairs of the events being checked."""

    def evaluated(event_type: str) -> int:
        return _int(_one(
            con,
            f"SELECT count(*) FROM {t} WHERE event_type = '{event_type}' "
            "AND user_session IS NOT NULL AND product_id IS NOT NULL",
        )[0])

    def without_step(event_type: str, step: str, time_op: str | None) -> int:
        """Events of event_type with no `step` event for the pair in the session.
        With time_op, only step events at time_op relative to the event count."""
        time_cond = f"AND s.event_time {time_op} e.event_time" if time_op else ""
        return _int(_one(
            con,
            f"""
            WITH e AS (
                SELECT user_session, product_id, event_time FROM {t}
                WHERE event_type = '{event_type}' AND user_session IS NOT NULL AND product_id IS NOT NULL
            ),
            s AS (
                SELECT user_session, product_id, event_time FROM {t}
                WHERE event_type = '{step}'
                  AND (user_session, product_id) IN (SELECT (user_session, product_id) FROM e)
            )
            SELECT count(*) FROM e
            WHERE NOT EXISTS (
                SELECT 1 FROM s
                WHERE s.user_session = e.user_session AND s.product_id = e.product_id {time_cond}
            )
            """,
        )[0])

    row = (
        evaluated("purchase"),
        without_step("purchase", "view", None),
        without_step("purchase", "cart", None),
        evaluated("cart"),
        without_step("cart", "view", "<="),
        without_step("cart", "view", "<"),
    )
    excluded = _one(
        con,
        f"""
        SELECT count(*) FROM {t}
        WHERE event_type IN ('purchase', 'cart') AND (user_session IS NULL OR product_id IS NULL)
        """,
    )[0]
    return {
        "purchase_events_evaluated": _int(row[0]),
        "purchase_events_with_no_view_of_product_in_session": _int(row[1]),
        "purchase_events_with_no_cart_of_product_in_session": _int(row[2]),
        "cart_events_evaluated": _int(row[3]),
        "cart_events_with_no_view_at_or_before_in_session": _int(row[4]),
        "cart_events_with_no_view_strictly_before_in_session": _int(row[5]),
        "purchase_or_cart_events_not_evaluable_null_session_or_product": int(excluded),
    }


def order_reconstruction(con: duckdb.DuckDBPyConnection, t: str) -> dict[str, Any]:
    names = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {t}").fetchall()]
    order_like = [n for n in names if ORDER_ID_NAME_PATTERN.search(n)]
    with_purchase, multi_purchase = _one(
        con,
        f"""
        SELECT count(*), count(*) FILTER (WHERE n > 1)
        FROM (SELECT user_session, count(*) AS n FROM {t}
              WHERE event_type = 'purchase' AND user_session IS NOT NULL GROUP BY 1)
        """,
    )
    pairs, surplus, same_second_pairs = _one(
        con,
        f"""
        SELECT count(*) FILTER (WHERE n > 1),
               sum(n - 1) FILTER (WHERE n > 1),
               count(*) FILTER (WHERE max_same_second > 1)
        FROM (
            SELECT user_session, product_id, count(*) AS n,
                   max(n_in_second) AS max_same_second
            FROM (
                SELECT user_session, product_id,
                       count(*) OVER (PARTITION BY user_session, product_id,
                                      date_trunc('second', event_time)) AS n_in_second
                FROM {t} WHERE event_type = 'purchase' AND user_session IS NOT NULL
            )
            GROUP BY 1, 2
        )
        """,
    )
    return {
        "order_or_transaction_id_columns": order_like,
        "order_or_transaction_id_exists": bool(order_like),
        "sessions_with_at_least_one_purchase_event": _int(with_purchase),
        "sessions_with_more_than_one_purchase_event": _int(multi_purchase),
        "session_product_pairs_with_more_than_one_purchase_event": _int(pairs),
        "surplus_purchase_events_in_repeated_pairs": _int(surplus),
        "session_product_pairs_with_repeated_purchase_in_same_second": _int(same_second_pairs),
        "publisher_statement_multiple_purchases": PUBLISHER_MULTIPLE_PURCHASES_QUOTE,
    }


REQUIRED_EVENT_LEVELS = ("view", "cart", "purchase")


def run_profile(
    con: duckdb.DuckDBPyConnection, t: str, timings: dict[str, float] | None = None
) -> dict[str, Any]:
    levels = {r[0] for r in con.execute(f"SELECT DISTINCT event_type FROM {t}").fetchall()}
    missing = [lvl for lvl in REQUIRED_EVENT_LEVELS if lvl not in levels]
    if missing:
        # The ordering checks filter on these literal levels; absent levels would
        # silently yield zero counts, so halt instead.
        raise SystemExit(f"HALT: event_type levels {missing} not found; observed {sorted(map(str, levels))}.")
    checks = (
        ("schema", schema_and_completeness), ("time", time_checks), ("event_types", event_types),
        ("duplicates", duplicates), ("price", price_checks), ("category_brand", category_brand),
        ("sessions_users", sessions_users), ("ordering_anomalies", ordering_anomalies),
        ("order_reconstruction", order_reconstruction),
    )
    out: dict[str, Any] = {}
    for name, check in checks:  # sequential; one check's queries finish before the next starts
        started = time.perf_counter()
        out[name] = check(con, t)
        if timings is not None:
            timings[name] = round(time.perf_counter() - started, 1)
            print(f"  {name}: {timings[name]} s", flush=True)
    return out


def _decision(did: str, title: str, evidence: list[str], choice: str, options: list[str],
              observed: bool) -> dict[str, Any]:
    return {
        "id": did, "title": title, "observed": observed, "evidence": evidence,
        "choice_forced": choice, "options": options,
    }


def decisions_needed(p: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the neutral decision list from computed counts only."""
    d, pr, cb = p["duplicates"], p["price"], p["category_brand"]
    su, oa, orc, tm, et = (p["sessions_users"], p["ordering_anomalies"],
                           p["order_reconstruction"], p["time"], p["event_types"])
    exact, near, sec = (d["exact_duplicate_rows"], d["near_duplicates_session_product_type_time"],
                        d["near_duplicates_session_product_type_same_second"])
    out = [
        _decision(
            "D1", "Deduplication",
            [f"Exact duplicate rows: {exact['surplus_rows']} surplus rows in {exact['duplicate_groups']} groups.",
             f"Same (user_session, product_id, event_type, event_time): {near['surplus_rows']} surplus rows in "
             f"{near['duplicate_groups']} groups; {near['groups_with_non_identical_rows']} of those groups contain "
             "rows that differ in another column.",
             f"Same (user_session, product_id, event_type) within one second: {sec['surplus_rows']} surplus rows in "
             f"{sec['duplicate_groups']} groups; {sec['groups_with_non_identical_rows']} contain non-identical rows."],
            "Which rows count as one event before any funnel count.",
            ["Keep all rows as logged.",
             "Drop exact duplicate rows only.",
             "Collapse on (user_session, product_id, event_type, event_time).",
             "Collapse on (user_session, product_id, event_type) within the same second.",
             "Apply different rules per event type (for example, collapse purchases only)."],
            exact["surplus_rows"] + near["surplus_rows"] + sec["surplus_rows"] > 0,
        ),
        _decision(
            "D2", "Zero, negative, and null prices",
            [f"Zero-price events: {pr['zero_price_events']} (of which purchase events: {pr['zero_price_purchase_events']}).",
             f"Negative-price events: {pr['negative_price_events']} (of which purchase events: "
             f"{pr['negative_price_purchase_events']}).",
             f"Null-price events: {pr['null_price_events']}."],
            "Whether zero, negative, or null priced purchases count toward revenue and toward purchase counts.",
            ["Count them as purchases and as revenue at their logged price.",
             "Count them as purchases but exclude them from revenue.",
             "Exclude them from both purchases and revenue.",
             "Flag them in a separate data-quality metric only."],
            pr["zero_price_events"] + pr["negative_price_events"] + pr["null_price_events"] > 0,
        ),
        _decision(
            "D3", "Price varies for the same product",
            [f"Products with more than one distinct price: {pr['products_with_more_than_one_distinct_price']}; "
             f"maximum distinct prices for one product: {pr['max_distinct_prices_for_one_product']}."],
            "Which price is the value of a purchase or of a lost cart.",
            ["Use the price logged on each event.",
             "Use the price on the purchase event for purchases and on the cart event for cart events.",
             "Use a per-product reference price (for example, the median across the month)."],
            pr["products_with_more_than_one_distinct_price"] > 0,
        ),
        _decision(
            "D4", "Order definition without an order ID",
            [f"Order or transaction ID columns found: {orc['order_or_transaction_id_columns'] or 'none'}.",
             f"Sessions with at least one purchase event: {orc['sessions_with_at_least_one_purchase_event']}; "
             f"with more than one: {orc['sessions_with_more_than_one_purchase_event']}.",
             f"(user_session, product_id) pairs with more than one purchase event: "
             f"{orc['session_product_pairs_with_more_than_one_purchase_event']} "
             f"({orc['surplus_purchase_events_in_repeated_pairs']} surplus events); pairs with repeats in the same "
             f"second: {orc['session_product_pairs_with_repeated_purchase_in_same_second']}.",
             "Publisher statement (evidence only, not a decision), verbatim from the Kaggle dataset page: "
             "\"A session can have multiple **purchase** events. It's ok, because it's a single order.\""],
            "What one order is, which determines order counts and order value.",
            ["One order per session that has at least one purchase event.",
             "One order per (session, product) purchase pair.",
             "One order per purchase event.",
             "Purchase events grouped by user_id within a time window."],
            not orc["order_or_transaction_id_exists"],
        ),
        _decision(
            "D5", "Purchases without a view or cart of that product in the session",
            [f"Purchase events evaluated: {oa['purchase_events_evaluated']}.",
             f"With no view of the product in the session: {oa['purchase_events_with_no_view_of_product_in_session']}.",
             f"With no cart of the product in the session: {oa['purchase_events_with_no_cart_of_product_in_session']}."],
            "Whether the funnel requires the preceding steps in the same session.",
            ["Count them in the purchase step regardless of earlier steps.",
             "Exclude them from step-to-step funnel counts but keep them in totals.",
             "Attribute earlier steps across sessions by user_id.",
             "Treat purchases without a cart as a separate path (for example, direct buy)."],
            oa["purchase_events_with_no_view_of_product_in_session"]
            + oa["purchase_events_with_no_cart_of_product_in_session"] > 0,
        ),
        _decision(
            "D6", "Cart events with no prior view",
            [f"Cart events evaluated: {oa['cart_events_evaluated']}.",
             f"No view at or before the cart time in the session: "
             f"{oa['cart_events_with_no_view_at_or_before_in_session']}.",
             f"No view strictly before the cart time (same-second views excluded): "
             f"{oa['cart_events_with_no_view_strictly_before_in_session']}."],
            "Whether view-before-cart is required, and whether a same-second view counts as prior.",
            ["Require no ordering; count any cart.",
             "Require a view at or before the cart in the same session.",
             "Require a view strictly before the cart.",
             "Look for the view across sessions by user_id."],
            oa["cart_events_with_no_view_at_or_before_in_session"] > 0,
        ),
        _decision(
            "D7", "Missing or inconsistent category and brand",
            [f"category_code null or empty: {cb['category_code']['null_or_empty_count']} events.",
             f"brand null or empty: {cb['brand']['null_or_empty_count']} events.",
             f"category_id values mapping to more than one category_code: "
             f"{cb['category_ids_mapping_to_more_than_one_category_code']}; with both null and non-null codes: "
             f"{cb['category_ids_with_both_null_and_non_null_code']}.",
             f"category_code values mapping to more than one category_id: "
             f"{cb['category_codes_mapping_to_more_than_one_category_id']}."],
            "How category and brand breakdowns treat missing and inconsistent labels.",
            ["Group missing labels as an explicit 'unknown' level.",
             "Break down by category_id instead of category_code.",
             "Exclude missing labels from category or brand breakdowns only.",
             "Map each category_id to one code by a stated rule."],
            cb["category_code"]["null_or_empty_count"] + cb["brand"]["null_or_empty_count"]
            + cb["category_ids_mapping_to_more_than_one_category_code"] > 0,
        ),
        _decision(
            "D8", "Session anomalies",
            [f"Events with null user_session: {su['null_user_session_events']}.",
             f"Sessions with more than one user_id: {su['sessions_with_more_than_one_user_id']}.",
             f"Sessions spanning more than 24 hours: {su['sessions_spanning_more_than_24_hours']}."],
            "Whether the session is a valid funnel unit as logged.",
            ["Use user_session as logged.",
             "Exclude null, multi-user, or over-24-hour sessions.",
             "Split sessions by user_id, or re-sessionize by an inactivity gap.",
             "Use user_id with a time window instead of sessions."],
            su["null_user_session_events"] + su["sessions_with_more_than_one_user_id"]
            + su["sessions_spanning_more_than_24_hours"] > 0,
        ),
        _decision(
            "D9", "Event types beyond view, cart, purchase",
            [f"Event type levels observed: {', '.join(map(str, et['levels']))}.",
             "Counts per level: " + ", ".join(f"{k} {v}" for k, v in et["counts"].items()) + "."],
            "Which event types enter the funnel.",
            ["Use view, cart, and purchase only; ignore other levels.",
             "Use other levels (for example, remove_from_cart) as a separate cart-removal signal.",
             "Net cart events against removals before counting cart."],
            any(lvl not in ("view", "cart", "purchase") for lvl in et["levels"]),
        ),
        _decision(
            "D10", "Time zone and month boundary",
            [f"event_time type: {tm['event_time_type']}; range {tm['min_event_time']} to {tm['max_event_time']} "
             "(displayed in UTC).",
             f"Events outside October 2019 in UTC: {tm['events_outside_october_2019_utc']}.",
             "The store's local time zone is not stated in the data."],
            "Which clock defines days and hours for time breakdowns, and how boundary events are handled.",
            ["Use UTC as logged.",
             "Convert to a stated store-local time zone.",
             "Drop or keep events outside October 2019 in UTC."],
            True,
        ),
    ]
    return out


def _fmt(v: Any) -> str:
    return "null" if v is None else str(v)


def render_markdown(p: dict[str, Any], decisions: list[dict[str, Any]]) -> str:
    s, tm, et, d, pr, cb, su, oa, orc = (
        p["schema"], p["time"], p["event_types"], p["duplicates"], p["price"],
        p["category_brand"], p["sessions_users"], p["ordering_anomalies"], p["order_reconstruction"],
    )
    m = p["manifest"]
    lines = [
        "# Data profile: October 2019 event log",
        "",
        "> Generated by `python -m funnel.profile` from `data/parquet/2019-Oct.parquet`. Do not edit by hand.",
        "> Structural profile only (metric lock, CLAUDE.md rule 3): no rates, revenue, or breakdowns.",
        f"> Dataset SHA-256 `{m['dataset_sha256']}` · git `{m['git_commit_sha']}` · generated {m['generated_at_utc']}.",
        "",
        "## 1. Schema and completeness",
        "",
        f"Rows: {s['row_count']}.",
        "",
        "| Column | Type | Null count | Null share |",
        "|---|---|---|---|",
        *[f"| `{c['name']}` | `{c['type']}` | {c['null_count']} | {c['null_share']} |" for c in s["columns"]],
        "",
        "Distinct counts (id-like columns): "
        + ", ".join(f"`{k}` {v}" for k, v in s["distinct_counts"].items()) + ".",
        "",
        "## 2. Time",
        "",
        f"- `event_time` type: `{tm['event_time_type']}`; values displayed in {tm['session_timezone_for_display']}.",
        f"- Min: {tm['min_event_time']}; max: {tm['max_event_time']}.",
        f"- Events before 2019-10-01 UTC: {tm['events_before_2019_10_01_utc']}; on or after 2019-11-01 UTC: "
        f"{tm['events_on_or_after_2019_11_01_utc']}; null: {tm['null_event_time']}.",
        f"- Events with sub-second precision: {tm['events_with_sub_second_precision']}.",
    ]
    raw_fmt = p.get("raw_event_time_format")
    if raw_fmt:
        lines.append(
            f"- Raw text format (from ingest, before type inference): rows not matching "
            f"`{raw_fmt['expected_regex']}`: {raw_fmt['rows_not_matching']}; suffixes after `HH:MM:SS`: "
            + ", ".join(f"`{x['suffix']!r}` {x['rows']}" for x in raw_fmt["suffixes_after_time"]) + "."
        )
    lines += [
        "",
        "## 3. Event types (overall counts only)",
        "",
        "| event_type | Events |",
        "|---|---|",
        *[f"| `{k}` | {v} |" for k, v in et["counts"].items()],
        "",
        "## 4. Duplicates",
        "",
        "| Check | Surplus rows | Duplicate groups | Groups with non-identical rows |",
        "|---|---|---|---|",
        f"| Exact duplicate rows | {d['exact_duplicate_rows']['surplus_rows']} | "
        f"{d['exact_duplicate_rows']['duplicate_groups']} | n/a |",
    ]
    for key, label in (("near_duplicates_session_product_type_time",
                        "Same (user_session, product_id, event_type, event_time)"),
                       ("near_duplicates_session_product_type_same_second",
                        "Same (user_session, product_id, event_type), same second")):
        x = d[key]
        lines.append(f"| {label} | {x['surplus_rows']} | {x['duplicate_groups']} | "
                     f"{x['groups_with_non_identical_rows']} |")
    lines += [
        "",
        "Surplus rows are rows beyond the first in each group. Null keys group together.",
        "",
        "## 5. Price",
        "",
        f"- Zero: {pr['zero_price_events']} (purchase events: {pr['zero_price_purchase_events']}); "
        f"negative: {pr['negative_price_events']} (purchase events: {pr['negative_price_purchase_events']}); "
        f"null: {pr['null_price_events']}.",
        "- Quantiles over all events: " + ", ".join(f"{k} {_fmt(v)}" for k, v in pr["quantiles"].items()) + ".",
        f"- Products with more than one distinct price: {pr['products_with_more_than_one_distinct_price']}; "
        f"maximum distinct prices for one product: {pr['max_distinct_prices_for_one_product']}.",
        "",
        "## 6. Categories and brands",
        "",
        "| Column | Null | Empty string | Null or empty | Null-or-empty share |",
        "|---|---|---|---|---|",
        *[f"| `{c}` | {cb[c]['null_count']} | {cb[c]['empty_string_count']} | {cb[c]['null_or_empty_count']} | "
          f"{cb[c]['null_or_empty_share']} |" for c in TEXT_DIMENSION_COLUMNS],
        "",
        f"- `category_id` values mapping to more than one `category_code`: "
        f"{cb['category_ids_mapping_to_more_than_one_category_code']}.",
        f"- `category_id` values with both null and non-null codes: {cb['category_ids_with_both_null_and_non_null_code']}.",
        f"- `category_code` values mapping to more than one `category_id`: "
        f"{cb['category_codes_mapping_to_more_than_one_category_id']}.",
        "",
        "## 7. Sessions and users",
        "",
        f"- Events with null `user_session`: {su['null_user_session_events']}.",
        f"- Non-null sessions: {su['sessions_non_null']}; with more than one `user_id`: "
        f"{su['sessions_with_more_than_one_user_id']}; spanning more than 24 hours: "
        f"{su['sessions_spanning_more_than_24_hours']}.",
        "- Events per session: " + ", ".join(f"{k} {_fmt(v)}" for k, v in su["events_in_session_quantiles"].items())
        + ".",
        "",
        "## 8. Ordering anomalies (counts only)",
        "",
        "Evaluated within (`user_session`, `product_id`).",
        "",
        f"- Purchase events evaluated: {oa['purchase_events_evaluated']}; with no view of that product in the "
        f"session: {oa['purchase_events_with_no_view_of_product_in_session']}; with no cart of that product in the "
        f"session: {oa['purchase_events_with_no_cart_of_product_in_session']}.",
        f"- Cart events evaluated: {oa['cart_events_evaluated']}; with no view at or before the cart: "
        f"{oa['cart_events_with_no_view_at_or_before_in_session']}; with no view strictly before: "
        f"{oa['cart_events_with_no_view_strictly_before_in_session']}.",
        f"- Purchase or cart events not evaluable (null session or product): "
        f"{oa['purchase_or_cart_events_not_evaluable_null_session_or_product']}.",
        "",
        "## 9. Order reconstruction",
        "",
        f"- Order or transaction ID columns: {orc['order_or_transaction_id_columns'] or 'none found'}.",
        f"- Sessions with at least one purchase event: {orc['sessions_with_at_least_one_purchase_event']}; "
        f"with more than one: {orc['sessions_with_more_than_one_purchase_event']}.",
        f"- (`user_session`, `product_id`) pairs with more than one purchase event: "
        f"{orc['session_product_pairs_with_more_than_one_purchase_event']} "
        f"({orc['surplus_purchase_events_in_repeated_pairs']} surplus events); with repeats in the same second: "
        f"{orc['session_product_pairs_with_repeated_purchase_in_same_second']}.",
        "",
        "## Decisions needed before metric definitions",
        "",
        "Generated from the counts above. Options are listed neutrally; the project owner decides.",
        "",
    ]
    for dec in decisions:
        status = "observed" if dec["observed"] else "not observed in this file"
        lines += [f"### {dec['id']}. {dec['title']} ({status})", ""]
        lines += [f"- {e}" for e in dec["evidence"]]
        lines += ["", f"**Choice forced:** {dec['choice_forced']}", "", "**Options:**", ""]
        lines += [f"{i}. {o}" for i, o in enumerate(dec["options"], 1)]
        lines.append("")
    return "\n".join(lines)


class SpillSampler(threading.Thread):
    """Samples the DuckDB spill directory size once per second; keeps the peak."""

    def __init__(self, path: Path) -> None:
        super().__init__(daemon=True)
        self.path, self.peak_bytes, self._stop_event = path, 0, threading.Event()

    def run(self) -> None:
        while not self._stop_event.wait(1.0):
            try:
                self.peak_bytes = max(self.peak_bytes, dir_size_bytes(self.path))
            except OSError:
                pass  # spill files can vanish between listing and stat

    def stop(self) -> int:
        self._stop_event.set()
        self.join()
        return self.peak_bytes


def main() -> None:
    started = time.perf_counter()
    available_before = require_available_ram()
    print(f"DuckDB memory_limit {DUCKDB_MEMORY_LIMIT}, threads {DUCKDB_THREADS}", flush=True)
    sha = require_dataset_hash_match()
    con = connect()
    con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{PARQUET_FILE.as_posix()}')")
    print("Profiling ...", flush=True)
    sampler = SpillSampler(DUCKDB_TMP_DIR)
    sampler.start()
    timings: dict[str, float] = {}
    try:
        checks = run_profile(con, "events", timings)
    finally:
        peak_spill = sampler.stop()
    profile = {"manifest": manifest(SCRIPT, sha), **checks}
    ingest_json = EVIDENCE_DIR / "ingest.json"
    if ingest_json.exists():
        profile["raw_event_time_format"] = json.loads(ingest_json.read_text(encoding="utf-8"))[
            "raw_event_time_format"
        ]
    decisions = decisions_needed(profile)
    profile["decisions_needed"] = decisions

    from funnel.metric_guard import find_metric_leaks

    leaks = find_metric_leaks(profile)
    if leaks:
        raise SystemExit("HALT: metric-lock guard failed:\n" + "\n".join(leaks))
    write_json(EVIDENCE_DIR / "profile.json", profile)
    write_text(DOCS_DIR / "data-profile.md", render_markdown(profile, decisions))
    elapsed = round(time.perf_counter() - started, 1)
    write_json(EVIDENCE_DIR / "profile_run.json", {
        "manifest": profile["manifest"],
        "available_ram_gb_before_run": available_before,
        "duckdb_memory_limit": DUCKDB_MEMORY_LIMIT,
        "duckdb_threads": DUCKDB_THREADS,
        "elapsed_seconds": elapsed,
        "check_seconds": timings,
        "peak_spill_bytes": peak_spill,
        "spill_sample_interval_seconds": 1.0,
    })
    print(f"Wrote {EVIDENCE_DIR / 'profile.json'} and {DOCS_DIR / 'data-profile.md'}")
    print(f"Elapsed: {elapsed} s; peak spill: {peak_spill} bytes ({round(peak_spill / 1024**3, 2)} GiB)")


if __name__ == "__main__":
    main()
