"""Synthetic event log with known, hand-counted anomalies."""

from __future__ import annotations

import duckdb
import pytest

COLUMNS = (
    "event_time TIMESTAMP, event_type VARCHAR, product_id BIGINT, category_id BIGINT, "
    "category_code VARCHAR, brand VARCHAR, price DOUBLE, user_id BIGINT, user_session VARCHAR"
)

D = "2019-10-01 "
# (event_time UTC, event_type, product_id, category_id, category_code, brand, price, user_id, user_session)
ROWS = [
    # S1: clean view -> cart -> purchase, plus one exact duplicate view and a remove_from_cart.
    (D + "10:00:00", "view", 100, 1, "electronics.phone", "a", 10.0, 1, "S1"),               # 1
    (D + "10:00:00", "view", 100, 1, "electronics.phone", "a", 10.0, 1, "S1"),               # 2 exact dup of 1
    (D + "10:01:00", "cart", 100, 1, "electronics.phone", "a", 10.0, 1, "S1"),               # 3
    (D + "10:02:00", "purchase", 100, 1, "electronics.phone", "a", 10.0, 1, "S1"),           # 4
    (D + "10:03:00", "remove_from_cart", 100, 1, "electronics.phone", "a", 10.0, 1, "S1"),   # 5
    # S2: zero-price purchase with no view and no cart; null category_code and brand.
    (D + "11:00:00", "purchase", 200, 2, None, None, 0.0, 2, "S2"),                          # 6
    # S3: cart before any view (view comes later); empty-string brand.
    (D + "12:00:00", "cart", 300, 3, "home.lamp", "", 5.0, 3, "S3"),                         # 7
    (D + "12:05:00", "view", 300, 3, "home.lamp", "", 5.0, 3, "S3"),                         # 8
    (D + "12:06:00", "purchase", 300, 3, "home.lamp", "", 5.0, 3, "S3"),                     # 9
    # S4: one session, two user_ids; category_id 4 maps to two codes.
    (D + "13:00:00", "view", 400, 4, "x.y", "b", 7.0, 4, "S4"),                              # 10
    (D + "13:00:30", "view", 400, 4, "x.z", "b", 7.0, 5, "S4"),                              # 11
    # S5: session longer than 24 hours; negative price; product 500 has two prices.
    ("2019-10-02 00:00:00", "view", 500, 5, "x.w", "c", -1.0, 6, "S5"),                      # 12
    ("2019-10-03 06:00:00", "view", 500, 5, "x.w", "c", 20.0, 6, "S5"),                      # 13
    # S6: repeated purchase of 600 in the same second at different prices (near-dup, not exact);
    # cart of 601 in the same second as its view; two views of 602 within one second.
    (D + "13:58:00", "view", 600, 6, "e.f", "d", 30.0, 7, "S6"),                             # 14
    (D + "13:59:00", "cart", 600, 6, "e.f", "d", 30.0, 7, "S6"),                             # 15
    (D + "14:00:00", "purchase", 600, 6, "e.f", "d", 30.0, 7, "S6"),                         # 16
    (D + "14:00:00", "purchase", 600, 6, "e.f", "d", 31.0, 7, "S6"),                         # 17
    (D + "14:09:00", "view", 601, 6, "e.f", "d", 8.0, 7, "S6"),                              # 18
    (D + "14:09:00", "cart", 601, 6, "e.f", "d", 8.0, 7, "S6"),                              # 19
    (D + "14:10:00", "purchase", 601, 6, "e.f", "d", 8.0, 7, "S6"),                          # 20
    (D + "14:20:00.300", "view", 602, 6, "e.f", "d", 9.0, 7, "S6"),                          # 21
    (D + "14:20:00.700", "view", 602, 6, "e.f", "d", 9.0, 7, "S6"),                          # 22
    # Null session.
    (D + "15:00:00", "view", 700, 7, "g.h", "e", 3.0, 8, None),                              # 23
    # S7: two events outside October 2019 (so S7 also spans > 24h); one null price.
    ("2019-11-01 00:00:00", "view", 800, 8, "i.j", "f", 4.0, 9, "S7"),                       # 24
    ("2019-09-30 23:59:59", "view", 801, 8, "i.j", "f", 4.0, 9, "S7"),                       # 25
    ("2019-10-15 00:00:00", "view", 802, 8, "i.j", "f", None, 9, "S7"),                      # 26
]


def make_events(con: duckdb.DuckDBPyConnection, rows: list[tuple] = ROWS, name: str = "events") -> str:
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"CREATE OR REPLACE TABLE {name} ({COLUMNS})")
    con.executemany(
        f"INSERT INTO {name} VALUES (CAST(? AS TIMESTAMP), ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    return name


@pytest.fixture()
def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    make_events(c)
    yield c
    c.close()
