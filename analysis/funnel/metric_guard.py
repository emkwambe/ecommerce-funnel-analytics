"""Metric-lock guard for the structural profile (CLAUDE.md rule 3).

Until docs/metrics.md is committed, profile.json may contain no rate, ratio, or
revenue sum, and nothing grouped by category, brand, product, time bucket, or
user segment. The guard enforces three rules:

1. Allow-list: every JSON path must match a known structural field.
2. Tokens: no key may name a business metric or a grouping ("by_brand").
3. Floats: fractional values may appear only in null shares and price quantiles.
"""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from typing import Any

METRIC_TOKENS = frozenset({
    "rate", "rates", "ratio", "ratios", "conversion", "conversions", "cvr", "ctr",
    "revenue", "gmv", "aov", "sales", "funnel", "arpu", "arppu", "ltv",
    "pct", "percent", "percentage", "proportion", "fraction", "share",
    "sum", "avg", "mean", "average",
})
GROUPING_TOKENS = frozenset({
    "category", "categories", "brand", "brands", "product", "products", "day", "days",
    "date", "dates", "hour", "hours", "week", "weeks", "weekday", "month", "months",
    "segment", "segments", "cohort", "cohorts", "user", "users", "session", "sessions",
    "time", "period",
})
GROUPING_PREFIXES = frozenset({"by", "per", "each", "top"})
ALLOWED_SHARE_KEYS = frozenset({"null_share", "null_or_empty_share"})

_TIME = ("event_time_type", "session_timezone_for_display", "min_event_time", "max_event_time",
         "events_before_2019_10_01_utc", "events_on_or_after_2019_11_01_utc",
         "events_outside_october_2019_utc", "null_event_time", "events_with_sub_second_precision")
_PRICE = ("zero_price_events", "negative_price_events", "null_price_events", "zero_price_purchase_events",
          "negative_price_purchase_events", "products_with_more_than_one_distinct_price",
          "max_distinct_prices_for_one_product")
_CB = ("category_ids_mapping_to_more_than_one_category_code", "category_ids_with_both_null_and_non_null_code",
       "category_codes_mapping_to_more_than_one_category_id")
_SU = ("null_user_session_events", "sessions_non_null", "sessions_with_more_than_one_user_id",
       "sessions_spanning_more_than_24_hours")
_OA = ("purchase_events_evaluated", "purchase_events_with_no_view_of_product_in_session",
       "purchase_events_with_no_cart_of_product_in_session", "cart_events_evaluated",
       "cart_events_with_no_view_at_or_before_in_session", "cart_events_with_no_view_strictly_before_in_session",
       "purchase_or_cart_events_not_evaluable_null_session_or_product")
_ORC = ("order_or_transaction_id_exists", "sessions_with_at_least_one_purchase_event",
        "sessions_with_more_than_one_purchase_event", "session_product_pairs_with_more_than_one_purchase_event",
        "surplus_purchase_events_in_repeated_pairs", "session_product_pairs_with_repeated_purchase_in_same_second",
        "publisher_statement_multiple_purchases")

ALLOWED_PATHS: tuple[str, ...] = (
    *(f"manifest.{k}" for k in ("git_commit_sha", "git_worktree_dirty", "dataset_sha256",
                                "generated_at_utc", "script")),
    "schema.row_count",
    *(f"schema.columns.[].{k}" for k in ("name", "type", "null_count", "null_share")),
    *(f"schema.distinct_counts.{k}" for k in ("product_id", "category_id", "user_id", "user_session")),
    *(f"time.{k}" for k in _TIME),
    "event_types.levels.[]",
    "event_types.counts.*",
    *(f"duplicates.exact_duplicate_rows.{k}" for k in ("surplus_rows", "duplicate_groups")),
    *(f"duplicates.near_duplicates_session_product_type_{v}.{k}"
      for v in ("time", "same_second")
      for k in ("surplus_rows", "duplicate_groups", "groups_with_non_identical_rows")),
    *(f"price.{k}" for k in _PRICE),
    *(f"price.quantiles.{k}" for k in ("min", "p01", "p50", "p99", "max")),
    *(f"category_brand.{c}.{k}" for c in ("category_code", "brand")
      for k in ("null_count", "empty_string_count", "null_or_empty_count", "null_or_empty_share")),
    *(f"category_brand.{k}" for k in _CB),
    *(f"sessions_users.{k}" for k in _SU),
    *(f"sessions_users.events_in_session_quantiles.{k}"
      for k in ("min", "p25", "p50", "p75", "p90", "p99", "max")),
    *(f"ordering_anomalies.{k}" for k in _OA),
    *(f"order_reconstruction.{k}" for k in _ORC),
    "order_reconstruction.order_or_transaction_id_columns.[]",
    *(f"raw_event_time_format.{k}" for k in ("expected_regex", "rows_not_matching", "null_rows")),
    *(f"raw_event_time_format.suffixes_after_time.[].{k}" for k in ("suffix", "rows")),
    *(f"decisions_needed.[].{k}" for k in ("id", "title", "observed", "choice_forced")),
    "decisions_needed.[].evidence.[]",
    "decisions_needed.[].options.[]",
)
FLOAT_ALLOWED_PATHS: tuple[str, ...] = (
    "schema.columns.[].null_share",
    "category_brand.*.null_or_empty_share",
    "price.quantiles.*",
)
INT_ONLY_PATHS: tuple[str, ...] = ("event_types.counts.*",)


def _match(path: list[str], pattern: str) -> bool:
    parts = pattern.split(".")
    return len(parts) == len(path) and all(fnmatchcase(seg, pat) for seg, pat in zip(path, parts))


def _tokens(key: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", key.lower()) if t]


def key_problems(key: str) -> list[str]:
    problems = []
    tokens = _tokens(key)
    if key not in ALLOWED_SHARE_KEYS:
        hits = sorted(METRIC_TOKENS.intersection(tokens))
        if hits:
            problems.append(f"metric term {hits}")
    for a, b in zip(tokens, tokens[1:]):
        if a in GROUPING_PREFIXES and b in GROUPING_TOKENS:
            problems.append(f"grouping '{a}_{b}'")
    return problems


def _walk(node: Any, path: list[str]) -> list[tuple[list[str], Any]]:
    if isinstance(node, dict):
        leaves: list[tuple[list[str], Any]] = []
        for k, v in node.items():
            leaves += _walk(v, path + [str(k)])
        return leaves
    if isinstance(node, list):
        leaves = []
        for v in node:
            leaves += _walk(v, path + ["[]"])
        return leaves
    return [(path, node)]


def _dict_keys(node: Any) -> list[str]:
    if isinstance(node, dict):
        return [str(k) for k in node] + [k for v in node.values() for k in _dict_keys(v)]
    if isinstance(node, list):
        return [k for v in node for k in _dict_keys(v)]
    return []


def find_metric_leaks(profile: dict[str, Any]) -> list[str]:
    """Return human-readable violations; empty means the profile passes."""
    leaks: list[str] = []
    for key in sorted(set(_dict_keys(profile))):
        for problem in key_problems(key):
            leaks.append(f"key '{key}': {problem}")
    for path, value in _walk(profile, []):
        dotted = ".".join(path)
        if not any(_match(path, p) for p in ALLOWED_PATHS):
            leaks.append(f"path '{dotted}' is not an allowed structural field")
        if isinstance(value, float) and not any(_match(path, p) for p in FLOAT_ALLOWED_PATHS):
            leaks.append(f"path '{dotted}' holds a fractional value outside null shares and price quantiles")
        if any(_match(path, p) for p in INT_ONLY_PATHS) and (isinstance(value, bool) or not isinstance(value, int)):
            leaks.append(f"path '{dotted}' must be an integer count")
    return leaks
