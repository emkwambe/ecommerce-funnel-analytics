"""Every profile check must detect each planted anomaly with the exact count.

Expected values are hand-counted from the annotated rows in conftest.py.
"""

from __future__ import annotations

import pytest

from funnel import profile as pf


def test_schema_and_completeness(con):
    s = pf.schema_and_completeness(con, "events")
    assert s["row_count"] == 26
    nulls = {c["name"]: c["null_count"] for c in s["columns"]}
    assert nulls == {
        "event_time": 0, "event_type": 0, "product_id": 0, "category_id": 0,
        "category_code": 1, "brand": 1, "price": 1, "user_id": 0, "user_session": 1,
    }
    shares = {c["name"]: c["null_share"] for c in s["columns"]}
    assert shares["price"] == round(1 / 26, 6)
    assert s["distinct_counts"] == {"product_id": 12, "category_id": 8, "user_id": 9, "user_session": 7}


def test_time(con):
    t = pf.time_checks(con, "events")
    assert t["event_time_type"] == "TIMESTAMP"  # matches the real Parquet type
    assert t["min_event_time"].startswith("2019-09-30 23:59:59")
    assert t["max_event_time"].startswith("2019-11-01 00:00:00")
    assert t["events_before_2019_10_01_utc"] == 1
    assert t["events_on_or_after_2019_11_01_utc"] == 1
    assert t["events_outside_october_2019_utc"] == 2
    assert t["null_event_time"] == 0
    assert t["events_with_sub_second_precision"] == 2


def test_event_types_are_observed_levels_with_overall_counts(con):
    e = pf.event_types(con, "events")
    assert e["counts"] == {"view": 15, "purchase": 6, "cart": 4, "remove_from_cart": 1}
    assert set(e["levels"]) == {"view", "purchase", "cart", "remove_from_cart"}


def test_duplicates(con):
    d = pf.duplicates(con, "events")
    assert d["exact_duplicate_rows"] == {"surplus_rows": 1, "duplicate_groups": 1}
    assert d["near_duplicates_session_product_type_time"] == {
        "surplus_rows": 2, "duplicate_groups": 2, "groups_with_non_identical_rows": 1,
    }
    assert d["near_duplicates_session_product_type_same_second"] == {
        "surplus_rows": 3, "duplicate_groups": 3, "groups_with_non_identical_rows": 2,
    }


def test_price(con):
    p = pf.price_checks(con, "events")
    assert p["zero_price_events"] == 1
    assert p["negative_price_events"] == 1
    assert p["null_price_events"] == 1
    assert p["zero_price_purchase_events"] == 1
    assert p["negative_price_purchase_events"] == 0
    assert p["quantiles"]["min"] == -1.0
    assert p["quantiles"]["max"] == 31.0
    assert p["products_with_more_than_one_distinct_price"] == 2
    assert p["max_distinct_prices_for_one_product"] == 2


def test_category_brand(con):
    c = pf.category_brand(con, "events")
    assert c["category_code"] == {
        "null_count": 1, "empty_string_count": 0, "null_or_empty_count": 1,
        "null_or_empty_share": round(1 / 26, 6),
    }
    assert c["brand"] == {
        "null_count": 1, "empty_string_count": 3, "null_or_empty_count": 4,
        "null_or_empty_share": round(4 / 26, 6),
    }
    assert c["category_ids_mapping_to_more_than_one_category_code"] == 1
    assert c["category_ids_with_both_null_and_non_null_code"] == 0
    assert c["category_codes_mapping_to_more_than_one_category_id"] == 0


def test_sessions_users(con):
    s = pf.sessions_users(con, "events")
    assert s["null_user_session_events"] == 1
    assert s["sessions_non_null"] == 7
    assert s["sessions_with_more_than_one_user_id"] == 1
    assert s["sessions_spanning_more_than_24_hours"] == 2  # S5 and S7
    q = s["events_in_session_quantiles"]
    # Session sizes: S1 5, S2 1, S3 3, S4 2, S5 2, S6 9, S7 3 -> sorted 1,2,2,3,3,5,9
    assert (q["min"], q["p50"], q["max"]) == (1, 3, 9)


def test_ordering_anomalies(con):
    o = pf.ordering_anomalies(con, "events")
    assert o == {
        "purchase_events_evaluated": 6,
        "purchase_events_with_no_view_of_product_in_session": 1,
        "purchase_events_with_no_cart_of_product_in_session": 1,
        "cart_events_evaluated": 4,
        "cart_events_with_no_view_at_or_before_in_session": 1,
        "cart_events_with_no_view_strictly_before_in_session": 2,
        "purchase_or_cart_events_not_evaluable_null_session_or_product": 0,
    }


def test_order_reconstruction(con):
    o = pf.order_reconstruction(con, "events")
    assert o["order_or_transaction_id_columns"] == []
    assert o["order_or_transaction_id_exists"] is False
    assert o["sessions_with_at_least_one_purchase_event"] == 4
    assert o["sessions_with_more_than_one_purchase_event"] == 1
    assert o["session_product_pairs_with_more_than_one_purchase_event"] == 1
    assert o["surplus_purchase_events_in_repeated_pairs"] == 1
    assert o["session_product_pairs_with_repeated_purchase_in_same_second"] == 1


def test_order_id_column_is_detected(con):
    con.execute("CREATE TABLE with_order AS SELECT *, 1 AS order_id FROM events")
    assert pf.order_reconstruction(con, "with_order")["order_or_transaction_id_columns"] == ["order_id"]


def test_missing_required_event_level_halts(con):
    con.execute("CREATE TABLE no_cart AS SELECT * FROM events WHERE event_type <> 'cart'")
    with pytest.raises(SystemExit):
        pf.run_profile(con, "no_cart")


def test_decisions_list_every_anomaly_with_counts_and_publisher_quote(con):
    p = pf.run_profile(con, "events")
    decisions = pf.decisions_needed(p)
    assert [d["id"] for d in decisions] == [f"D{i}" for i in range(1, 11)]
    assert all(d["options"] and d["evidence"] and d["choice_forced"] for d in decisions)
    d4 = next(d for d in decisions if d["id"] == "D4")
    assert any("It's ok, because it's a single order." in e and "evidence only" in e for e in d4["evidence"])
    d9 = next(d for d in decisions if d["id"] == "D9")
    assert d9["observed"] is True and "remove_from_cart 1" in d9["evidence"][1]
