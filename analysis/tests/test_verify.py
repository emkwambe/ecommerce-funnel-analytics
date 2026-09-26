"""Independent verification SQL on a small hand-counted event log."""

from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from funnel import verify
from conftest import make_events

D = "2019-10-01 "
# (event_time UTC, event_type, product_id, category_id, category_code, brand, price, user_id, user_session)
ROWS = [
    # V1: view -> cart -> purchase of p1, with one exact duplicate purchase row.
    (D + "10:00:00", "view", 1, 1, "a.b", "x", 10.0, 1, "V1"),
    (D + "10:01:00", "cart", 1, 1, "a.b", "x", 10.0, 1, "V1"),
    (D + "10:02:00", "purchase", 1, 1, "a.b", "x", 10.0, 1, "V1"),
    (D + "10:02:00", "purchase", 1, 1, "a.b", "x", 10.0, 1, "V1"),
    # V2: p2 carted at 0, 5, then 7; no purchase. Carted value 7 (latest non-zero).
    (D + "11:00:00", "view", 2, 2, "c.d", "y", 7.0, 2, "V2"),
    (D + "11:01:00", "cart", 2, 2, "c.d", "y", 0.0, 2, "V2"),
    (D + "11:02:00", "cart", 2, 2, "c.d", "y", 5.0, 2, "V2"),
    (D + "11:03:00", "cart", 2, 2, "c.d", "y", 7.0, 2, "V2"),
    # V2: p8 carted before its only view, no purchase: a cart event with no view at or before it.
    (D + "11:10:00", "cart", 8, 2, "c.d", "y", 3.0, 2, "V2"),
    (D + "11:20:00", "view", 8, 2, "c.d", "y", 3.0, 2, "V2"),
    # V3: p3 bought twice with no cart event; secondary revenue keeps the earliest price (20).
    (D + "12:00:00", "purchase", 3, 3, None, None, 20.0, 3, "V3"),
    (D + "12:05:00", "purchase", 3, 3, None, None, 25.0, 3, "V3"),
    # M: two user_ids, excluded.
    (D + "13:00:00", "view", 4, 4, "e.f", "z", 3.0, 4, "M"),
    (D + "13:01:00", "view", 4, 4, "e.f", "z", 3.0, 5, "M"),
    # Null session, excluded.
    (D + "14:00:00", "view", 5, 5, "g.h", "w", 4.0, 6, None),
    # V6: only a zero-price cart event: a carted pair counted, excluded from value.
    (D + "15:00:00", "cart", 6, 6, "i.j", "v", 0.0, 7, "V6"),
    # V6 also buys p11, which it never carted: a cart session with a purchase of no carted product.
    (D + "15:05:00", "purchase", 11, 6, "i.j", "v", 4.0, 7, "V6"),
]


@pytest.fixture()
def vcon() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    make_events(c, ROWS, name="synthetic")
    verify.build_independent_tables(c, "synthetic")
    yield c
    c.close()


def test_independent_headline(vcon):
    h = verify.independent_headline(vcon)
    assert h["valid_sessions"] == 4                      # V1, V2, V3, V6
    assert h["orders"] == 3                              # V1, V3, V6
    assert h["revenue"] == Decimal("59.00")              # 10 + 20 + 25 + 4
    assert h["revenue_repeat_collapsed"] == Decimal("34.00")  # 10 + 20 + 4
    assert h["session_purchase_rate"] == pytest.approx(3 / 4)
    assert h["view_to_cart_session_rate"] == pytest.approx(2 / 2)   # V1, V2 view; both cart
    assert h["cart_session_purchase_rate"] == pytest.approx(1 / 3)  # V1 of V1, V2, V6
    assert h["purchase_events_by_path"] == {
        "Purchase with an observed same-session cart event": 1,
        "Purchase with no observed same-session cart event": 3,
    }
    assert h["revenue_share_by_path"]["Purchase with an observed same-session cart event"] == Decimal(10) / Decimal(59)
    assert h["carted_value_with_no_observed_purchase"] == Decimal("10.00")  # V2 p2 at 7 + V2 p8 at 3
    # Changes 2026-09-26 (third entry): V3 and V6 buy only products they did not cart; V6 also carted.
    assert h["sessions_with_purchases_only_of_uncarted_products"] == 2
    assert h["cart_sessions_with_purchase_of_no_carted_product"] == 1


def test_independent_data_quality_both_bases(vcon):
    dq = verify.independent_data_quality(vcon)
    # Cart events with no view at or before: V2 p8 (view comes later) and V6 p6 (no view).
    assert dq["raw_basis"] == {
        "exact_duplicate_rows_removed": 1, "zero_price_events": 2,
        "null_session_events": 1, "multi_user_sessions": 1,
        "cart_events_with_no_view_at_or_before": 2,
    }
    assert dq["contract_basis"] == {
        "exact_duplicate_rows_removed": 1, "null_session_events_excluded": 1,
        "multi_user_sessions_excluded": 1, "zero_price_events": 2,
        "cart_events_with_no_view_at_or_before": 2,
    }


def test_rates_compare_within_tolerance_and_amounts_exactly():
    assert verify._match(0.1 + 0.2, 0.3)
    assert not verify._match(0.3, 0.3 + 1e-6)
    assert verify._match(Decimal("55.00"), Decimal("55.0"))
    assert not verify._match(Decimal("55.00"), Decimal("55.01"))
