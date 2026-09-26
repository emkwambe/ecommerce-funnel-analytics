"""Analysis A (metrics.md Changes 2026-09-26, Sprint 2 investigations, A items 1-6): the independent
recomputation in funnel.verify on a small hand-counted event log. Every expected value below is counted
by hand from ROWS."""

from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from funnel import verify
from conftest import make_events

D = "2019-10-01 "
# (event_time UTC, event_type, product_id, category_id, category_code, brand, price, user_id, user_session)
ROWS = [
    # R1: p20 bought four times. Two at 10:00:00 differ only in brand (not exact duplicates) at the same
    # price; repeats: the tie (0 s, same price, 10), 10:00:30 (30 s, different price, 12), 10:02:30
    # (120 s after 10:00:30, same price, 10). Pair of 4 events.
    (D + "09:59:00", "view", 20, 20, "electronics.phone", "a", 10.0, 10, "R1"),
    (D + "10:00:00", "purchase", 20, 20, "electronics.phone", "a", 10.0, 10, "R1"),
    (D + "10:00:00", "purchase", 20, 20, "electronics.phone", "b", 10.0, 10, "R1"),
    (D + "10:00:30", "purchase", 20, 20, "electronics.phone", "a", 12.0, 10, "R1"),
    (D + "10:02:30", "purchase", 20, 20, "electronics.phone", "a", 10.0, 10, "R1"),
    # R2: p21 bought twice, 5 s apart, same price 5. Pair of 2.
    (D + "11:00:00", "purchase", 21, 21, "appliances.kettle", "k", 5.0, 11, "R2"),
    (D + "11:00:05", "purchase", 21, 21, "appliances.kettle", "k", 5.0, 11, "R2"),
    # V3: p3 bought twice, 300 s apart, 20 then 25 (different price); unknown category. Pair of 2.
    (D + "12:00:00", "purchase", 3, 3, None, None, 20.0, 3, "V3"),
    (D + "12:05:00", "purchase", 3, 3, None, None, 25.0, 3, "V3"),
    # V1: an exact duplicate purchase row (removed by D1), so no repeat purchase event.
    (D + "10:00:00", "view", 1, 1, "a.b", "x", 10.0, 1, "V1"),
    (D + "10:01:00", "cart", 1, 1, "a.b", "x", 10.0, 1, "V1"),
    (D + "10:02:00", "purchase", 1, 1, "a.b", "x", 10.0, 1, "V1"),
    (D + "10:02:00", "purchase", 1, 1, "a.b", "x", 10.0, 1, "V1"),
    # R3: three identical view rows of p31 (a group of 3: 2 rows removed), and two identical cart rows
    # of p30 with no view of p30 (a group of 2: 1 row removed; both raw rows are in the raw basis).
    (D + "13:00:00", "view", 31, 31, "c.d", "y", 2.0, 12, "R3"),
    (D + "13:00:00", "view", 31, 31, "c.d", "y", 2.0, 12, "R3"),
    (D + "13:00:00", "view", 31, 31, "c.d", "y", 2.0, 12, "R3"),
    (D + "14:00:00", "cart", 30, 30, "c.d", "y", 6.0, 12, "R3"),
    (D + "14:00:00", "cart", 30, 30, "c.d", "y", 6.0, 12, "R3"),
    # V2: p2 viewed before its carts; p8 carted before its only view (in the raw basis).
    (D + "11:00:00", "view", 2, 2, "c.d", "y", 7.0, 2, "V2"),
    (D + "11:01:00", "cart", 2, 2, "c.d", "y", 0.0, 2, "V2"),
    (D + "11:02:00", "cart", 2, 2, "c.d", "y", 5.0, 2, "V2"),
    (D + "11:10:00", "cart", 8, 2, "c.d", "y", 3.0, 2, "V2"),
    (D + "11:20:00", "view", 8, 2, "c.d", "y", 3.0, 2, "V2"),
    # M: two user_ids (excluded); its cart of p9 has no view, so it is in the raw basis, multi-user part.
    (D + "13:00:00", "view", 4, 4, "e.f", "z", 3.0, 4, "M"),
    (D + "13:01:00", "view", 4, 4, "e.f", "z", 3.0, 5, "M"),
    (D + "13:02:00", "cart", 9, 4, "e.f", "z", 3.0, 4, "M"),
    # Null session: outside the raw basis by its definition.
    (D + "14:00:00", "view", 5, 5, "g.h", "w", 4.0, 6, None),
    (D + "14:01:00", "cart", 5, 5, "g.h", "w", 4.0, 6, None),
    # V6: a zero-price cart of p6 with no view (in the raw basis); a purchase of p11, bought once.
    (D + "15:00:00", "cart", 6, 6, "i.j", "v", 0.0, 7, "V6"),
    (D + "15:05:00", "purchase", 11, 6, "i.j", "v", 4.0, 7, "V6"),
]


@pytest.fixture()
def acon() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    make_events(c, ROWS, name="synthetic")
    verify.build_independent_tables(c, "synthetic")
    yield c
    c.close()


def _cells(pairs: dict[str, tuple[int, int]]) -> dict[str, tuple[int, Decimal]]:
    return {k: (n, Decimal(v)) for k, (n, v) in pairs.items()}


def test_revenue_difference_equals_repeat_purchase_value(acon):
    headline = verify.independent_headline(acon)
    gap = verify.independent_revenue_gap(acon)
    # Revenue 42 + 10 + 45 + 10 + 4 = 111; collapsed 10 + 5 + 20 + 10 + 4 = 49.
    assert headline["revenue"] - headline["revenue_repeat_collapsed"] == Decimal("62.00")
    assert gap["repeat_purchase_value"] == Decimal("62.00")
    assert gap["repeat_purchase_events"] == 5


def test_breakdown_by_every_dimension(acon):
    by = verify.independent_revenue_gap(acon)["by_dimension"]
    assert by["time_since_previous_purchase"] == _cells(
        {"same_second": (1, 10), "under_a_minute": (2, 17), "a_minute_or_more": (2, 35)})
    assert by["price_vs_first_purchase"] == _cells({"same_price": (3, 25), "different_price": (2, 37)})
    assert by["category_top"] == _cells({"electronics": (3, 32), "appliances": (1, 5), "unknown": (1, 25)})
    assert by["purchase_events_in_pair"] == _cells({"2": (2, 30), "4_or_more": (3, 32)})
    assert by["time_by_price"] == _cells({
        "same_second|same_price": (1, 10), "under_a_minute|different_price": (1, 12),
        "under_a_minute|same_price": (1, 5), "a_minute_or_more|same_price": (1, 10),
        "a_minute_or_more|different_price": (1, 25)})
    for cells in by.values():
        assert sum(n for n, _ in cells.values()) == 5
        assert sum(v for _, v in cells.values()) == Decimal("62.00")


def test_threshold_sensitivity(acon):
    thresholds = verify.independent_revenue_gap(acon)["thresholds"]
    expected = {0: 10, 1: 10, 5: 15, 10: 15, 30: 27, 60: 27, 300: 62, 1800: 62, 3600: 62}
    assert thresholds == {s: Decimal(v) for s, v in expected.items()}


def test_duplicate_rows_by_event_type_and_group_size(acon):
    assert verify.independent_duplicate_breakdown(acon) == {
        "purchase:2": (1, 1), "view:3": (1, 2), "cart:2": (1, 1)}


def test_cart_no_view_attribution_reconciles(acon):
    parts = verify.independent_cart_no_view_attribution(acon)
    # Raw basis: V2 p8, V6 p6, M p9, and both R3 p30 rows = 5; the null-session cart is outside it.
    assert parts == {"raw_basis_count": 5, "in_null_session_events": 0, "in_multi_user_sessions": 1,
                     "removed_as_exact_duplicates": 1, "remaining_after_attribution": 3}
    contract = verify.independent_data_quality(acon)["contract_basis"]["cart_events_with_no_view_at_or_before"]
    assert parts["remaining_after_attribution"] == contract == 3


def test_compare_flags_a_single_mismatch(acon):
    gap = verify.independent_revenue_gap(acon)
    headline = verify.independent_headline(acon)
    independent = {"revenue_gap": gap, "duplicates": verify.independent_duplicate_breakdown(acon),
                   "cart_no_view": verify.independent_cart_no_view_attribution(acon)}
    mart = {
        "repeat_purchase_events": gap["repeat_purchase_events"],
        "repeat_purchase_value": gap["repeat_purchase_value"],
        "revenue_difference": gap["repeat_purchase_value"],
        "by_dimension": gap["by_dimension"],
        "thresholds": gap["thresholds"],
        "duplicates": independent["duplicates"],
        "cart_no_view": {"raw_basis_count": 5, "in_null_session_events": 0, "in_multi_user_sessions": 1,
                         "removed_as_exact_duplicates": 1, "contract_basis_count": 3, "remainder": 0},
    }
    assert all(c["match"] for c in verify.compare_investigation_a(independent, headline, mart))
    mart["by_dimension"] = {**gap["by_dimension"],
                            "category_top": {**gap["by_dimension"]["category_top"], "unknown": (1, Decimal("24.99"))}}
    failed = [c["check"] for c in verify.compare_investigation_a(independent, headline, mart) if not c["match"]]
    assert failed == ["A:category_top:unknown:value"]
