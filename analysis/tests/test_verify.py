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
    assert h["orders"] == 2                              # V1, V3
    assert h["revenue"] == Decimal("55.00")              # 10 + 20 + 25
    assert h["revenue_repeat_collapsed"] == Decimal("30.00")  # 10 + 20
    assert h["session_purchase_rate"] == pytest.approx(2 / 4)
    assert h["view_to_cart_session_rate"] == pytest.approx(2 / 2)   # V1, V2 view; both cart
    assert h["cart_session_purchase_rate"] == pytest.approx(1 / 3)  # V1 of V1, V2, V6
    assert h["purchase_events_by_path"] == {
        "Purchase with an observed same-session cart event": 1,
        "Purchase with no observed same-session cart event": 2,
    }
    assert h["revenue_share_by_path"]["Purchase with an observed same-session cart event"] == Decimal(10) / Decimal(55)
    assert h["carted_value_with_no_observed_purchase"] == Decimal("7.00")


def test_independent_data_quality_both_bases(vcon):
    dq = verify.independent_data_quality(vcon)
    assert dq["raw_basis"] == {
        "exact_duplicate_rows_removed": 1, "zero_price_events": 2,
        "null_session_events": 1, "multi_user_sessions": 1,
    }
    assert dq["contract_basis"] == {
        "exact_duplicate_rows_removed": 1, "null_session_events_excluded": 1,
        "multi_user_sessions_excluded": 1, "zero_price_events": 2,
    }


def test_rates_compare_within_tolerance_and_amounts_exactly():
    assert verify._match(0.1 + 0.2, 0.3)
    assert not verify._match(0.3, 0.3 + 1e-6)
    assert verify._match(Decimal("55.00"), Decimal("55.0"))
    assert not verify._match(Decimal("55.00"), Decimal("55.01"))
