"""Analysis B (metrics.md Changes 2026-09-26, Sprint 2 investigations, B items 7-16) on a hand-counted event log:
the independent B1 recomputation in funnel.verify and the statistics in funnel.later_purchases. Every expected
value is counted by hand from ROWS; the same rows drive a scratch dbt build of the B marts.

Pairs (cart session start -> first later purchase):
  p1@SA  10-01 10:00 -> SB 10-03 09:05 (1d 23h05m)        followed at 3, 7, 14 days; value 100
  p2@SC  10-02 12:00 -> SD 10-06 12:30 (4d 00h30m)        7 and 14 days; value 50 (latest non-zero; the latest
                                                         cart event, 12:00:20, is zero-price and is the anchor)
  p2@SC2 10-04 12:00 -> SD 10-06 12:30 (2d 00h30m)        3, 7, 14 days; value 50; same user and product as p2@SC
  p3@SE  10-05 08:00 -> SF 10-15 08:10 (10d 00h10m)       14 days only; value 30; SE lasts 25 h (long session)
  p4@SG  10-07 10:00; SH (starts 09:00, before SG) buys p4 at 10:20, after the 10:10 cart: fails condition 2
         (overlap diagnostic only); value 20
  p5@SI  10-08 10:00; SJ (starts 10:05) buys p5 at 10:20, before the 10:30 cart: fails condition 3; value 40
  p6@SK  10-26 10:00 -> SL 10-27 10:30 (1d 00h30m)        after the 7- and 14-day cutoffs; 3 days; value 60
  p7@SM  10-04 10:00, zero-price cart only: counts, no value; never bought
  p8@SN  bought in its own session: not eligible
Viewed-only pairs in sessions with an eligible carted pair (B5): p9@SA (bought in SB at 10-03 09:10: followed;
value 15), p10@SC (25), p99@SE (5), p12@SG (8). p11@SO is in a session with no carted pair: excluded.
"""

from __future__ import annotations

from decimal import Decimal

import duckdb
import numpy as np
import pytest

from funnel import later_purchases as lp
from funnel import verify
from conftest import make_events

# (event_time UTC, event_type, product_id, category_id, category_code, brand, price, user_id, user_session)
def _e(t: str, kind: str, product: int, price: float, user: int, session: str) -> tuple:
    return ("2019-" + t, kind, product, product, "c.d", "b", price, user, session)


ROWS = [
    _e("10-01 10:00:00", "view", 1, 100.0, 101, "SA"), _e("10-01 10:01:00", "cart", 1, 100.0, 101, "SA"),
    _e("10-01 10:02:00", "view", 9, 15.0, 101, "SA"),
    _e("10-03 09:00:00", "view", 1, 100.0, 101, "SB"), _e("10-03 09:05:00", "purchase", 1, 100.0, 101, "SB"),
    _e("10-03 09:10:00", "purchase", 9, 15.0, 101, "SB"),
    _e("10-02 12:00:00", "view", 2, 50.0, 102, "SC"), _e("10-02 12:00:10", "cart", 2, 50.0, 102, "SC"),
    _e("10-02 12:00:20", "cart", 2, 0.0, 102, "SC"), _e("10-02 12:05:00", "view", 10, 25.0, 102, "SC"),
    _e("10-04 12:00:00", "cart", 2, 50.0, 102, "SC2"),
    _e("10-06 12:00:00", "view", 2, 50.0, 102, "SD"), _e("10-06 12:30:00", "purchase", 2, 50.0, 102, "SD"),
    _e("10-05 08:00:00", "view", 3, 30.0, 103, "SE"), _e("10-05 08:00:30", "cart", 3, 30.0, 103, "SE"),
    _e("10-06 09:00:00", "view", 99, 5.0, 103, "SE"),
    _e("10-15 08:00:00", "view", 3, 30.0, 103, "SF"), _e("10-15 08:10:00", "purchase", 3, 30.0, 103, "SF"),
    _e("10-07 09:00:00", "view", 4, 20.0, 104, "SH"), _e("10-07 10:20:00", "purchase", 4, 20.0, 104, "SH"),
    _e("10-07 10:00:00", "view", 4, 20.0, 104, "SG"), _e("10-07 10:05:00", "view", 12, 8.0, 104, "SG"),
    _e("10-07 10:10:00", "cart", 4, 20.0, 104, "SG"),
    _e("10-08 10:00:00", "view", 5, 40.0, 105, "SI"), _e("10-08 10:30:00", "cart", 5, 40.0, 105, "SI"),
    _e("10-08 10:05:00", "view", 5, 40.0, 105, "SJ"), _e("10-08 10:20:00", "purchase", 5, 40.0, 105, "SJ"),
    _e("10-26 10:00:00", "cart", 6, 60.0, 106, "SK"),
    _e("10-27 10:00:00", "view", 6, 60.0, 106, "SL"), _e("10-27 10:30:00", "purchase", 6, 60.0, 106, "SL"),
    _e("10-04 10:00:00", "cart", 7, 0.0, 107, "SM"),
    _e("10-09 10:00:00", "cart", 8, 10.0, 108, "SN"), _e("10-09 10:05:00", "purchase", 8, 10.0, 108, "SN"),
    _e("10-10 10:00:00", "view", 11, 9.0, 110, "SO"), _e("10-11 10:00:00", "purchase", 11, 9.0, 110, "SP"),
]

H = 3600
D = 86400
# Kaplan-Meier over every carted pair with no purchase in the session (no cutoff), in the order p1, p2@SC,
# p2@SC2, p3, p4, p5, p6, p7; censored pairs run to 2019-10-31 23:59:59.
KM_DURATIONS = np.array([D + 23 * H + 300, 4 * D + 1800, 2 * D + 1800, 10 * D + 600,
                         24 * D + 13 * H + 3599, 23 * D + 13 * H + 3599, D + 1800, 27 * D + 13 * H + 3599], dtype=float)
KM_EVENTS = np.array([1, 1, 1, 1, 0, 0, 1, 0], dtype=float)
KM_VALUES = np.array([100, 50, 50, 30, 20, 40, 60, 0], dtype=float)
KM_USERS = np.array([0, 1, 1, 2, 3, 4, 5, 6])


@pytest.fixture()
def bcon() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    make_events(c, ROWS, name="synthetic")
    verify.build_independent_tables(c, "synthetic")
    yield c
    c.close()


def test_independent_b1_matches_hand_counts(bcon):
    b1 = verify.independent_later_purchases_b1(bcon)
    # Eligible: p1, p2@SC, p2@SC2, p3, p4, p5, p7. Followed within 7 days: p1, p2@SC, p2@SC2.
    assert (b1["eligible_pairs"], b1["followed_pairs"]) == (7, 3)
    assert (b1["eligible_value"], b1["followed_value"]) == (Decimal("290.00"), Decimal("200.00"))
    assert b1["count_share"] == pytest.approx(3 / 7)
    assert b1["value_share"] == pytest.approx(200 / 290)


def _km(weights: np.ndarray, days: tuple[int, ...]) -> np.ndarray:
    order = np.argsort(KM_DURATIONS, kind="stable")
    return lp.km_cdf(KM_DURATIONS[order], KM_EVENTS[order], weights[order], np.array(days, dtype=float) * D)


def test_kaplan_meier_matches_hand_counts():
    # No censoring precedes the last event, so 1 - S(t) = events before t / 8.
    assert _km(np.ones(8), (1, 2, 3, 7, 14, 30)) == pytest.approx([0, 2 / 8, 3 / 8, 4 / 8, 5 / 8, 5 / 8])
    # Value-weighted: 60 + 100 + 50 by 3 days, + 50 by 7, + 30 by 14, of 350.
    assert _km(KM_VALUES, (3, 7, 14)) == pytest.approx([210 / 350, 260 / 350, 290 / 350])


def test_kaplan_meier_handles_censoring_before_events():
    durations = np.array([1, 2, 3, 4], dtype=float) * D
    events = np.array([1, 0, 1, 1], dtype=float)
    # At 3 days two pairs remain at risk: S = (1 - 1/4)(1 - 1/2) = 3/8 just after day 3; 0 after day 4.
    got = lp.km_cdf(durations, events, np.ones(4), np.array([1, 1.5, 3.5, 5]) * D)
    assert got == pytest.approx([0, 1 / 4, 5 / 8, 1])


def test_kaplan_meier_uses_events_strictly_before_t():
    # An event exactly at 7 days is not "within 7 days" (item 8, condition 4: t < start + N days).
    got = lp.km_cdf(np.array([7 * D, 8 * D]), np.array([1.0, 0.0]), np.ones(2), np.array([7, 7.00001]) * D)
    assert got == pytest.approx([0, 0.5])


def test_cluster_bootstrap_resamples_users_and_is_reproducible():
    rng = np.random.default_rng(1)
    assert lp.user_weights(rng, 6).sum() == 6
    # B1 per user (U1, U2, U3, U4, U5, U7): pairs, followed, value, followed value.
    sums = [np.array(x, dtype=float) for x in ([1, 2, 1, 1, 1, 1], [1, 2, 0, 0, 0, 0],
                                              [100, 100, 30, 20, 40, 0], [100, 100, 0, 0, 0, 0])]
    a = lp.share_intervals(*sums, seed=lp.SEED, resamples=500)
    b = lp.share_intervals(*sums, seed=lp.SEED, resamples=500)
    assert a == b
    assert a["count_share"] == pytest.approx(3 / 7) and a["value_share"] == pytest.approx(200 / 290)
    lo, hi = a["count_interval"]
    assert 0 <= lo <= a["count_share"] <= hi <= 1
    # With six users the percentile endpoints are coarse and can coincide across seeds; the resamples differ.
    draws = [lp.user_weights(np.random.default_rng(s), 6) for s in (lp.SEED, lp.SEED + 1)]
    assert not np.array_equal(draws[0], draws[1])


def test_km_bands_bracket_the_point_and_are_reproducible():
    one = lp.km_with_bands(KM_DURATIONS, KM_EVENTS.astype(bool), KM_USERS, KM_VALUES, lp.SEED,
                           grid_days=(3, 7), resamples=300)
    two = lp.km_with_bands(KM_DURATIONS, KM_EVENTS.astype(bool), KM_USERS, KM_VALUES, lp.SEED,
                           grid_days=(3, 7), resamples=300)
    assert one == two
    seven = lp.km_at(one, 7)
    assert seven["count"] == pytest.approx(0.5) and seven["value_weighted"] == pytest.approx(260 / 350)
    assert seven["count_interval"][0] <= seven["count"] <= seven["count_interval"][1]


def _checks(null_events=0, multi=0, share=1.0) -> dict[str, float]:
    return {"user_id_check:events_in_eligible_sessions_with_null_user_id": null_events,
            "user_id_check:eligible_sessions_with_more_than_one_user_id": multi,
            "user_id_check:share_of_eligible_pairs_with_non_null_user_id": share}


def test_stop_rules_fire_only_when_their_condition_holds():
    estimates = {"B1": {"count_share": 3 / 7}, "B5": {"count_share": 1 / 4}}
    inside = {"count_interval": [0.3, 0.6]}
    assert [r["fired"] for r in lp.stop_rules(estimates, inside, _checks())] == [False, False, False]
    assert [r["fired"] for r in lp.stop_rules(estimates, {"count_interval": [0.5, 0.6]}, _checks())] == [False, True, False]
    equal_baseline = {"B1": {"count_share": 0.25}, "B5": {"count_share": 0.25}}
    assert lp.stop_rules(equal_baseline, {"count_interval": [0.2, 0.3]}, _checks())[2]["fired"] is True
    assert lp.stop_rules(estimates, inside, _checks(multi=1))[0]["fired"] is True
    assert lp.stop_rules(estimates, inside, _checks(share=0.99))[0]["fired"] is True
