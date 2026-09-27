"""Sprint 3 category ranking (metrics.md Changes 2026-09-26, Sprint 3 ranking; method record C): the numerics in
funnel.rankings, the independent R2 path in funnel.verify, and their agreement, on hand-counted or exactly known data.

Synthetic log (ROWS), top level / full code:
  S1 (U1): views phone p1 and kettle p2; buys p1 twice (100 at 10:01, 100 at 10:02: a repeat purchase event)
  S2 (U1): views phone p1; no purchase
  S3 (U2): views a product with no code (p3) and buys it (50); views tv p4; buys kettle p2 (30) without viewing
           appliances, so appliances is not entered in S3
  S4 (U3): views and carts shoes p5; no purchase
  S5 (U4 and U5): a multi-user session viewing phone p1: excluded (Section 3)
  S6 (U6): views phone p1 and buys it (100)
Expected (category-sessions, with purchase, revenue, repeat-collapsed revenue):
  electronics (4, 2, 300, 200) = phone (3, 2, 300, 200) + tv (1, 0, 0, 0); appliances = kettle (1, 0, 0, 0);
  apparel = shoes (1, 0, 0, 0); unknown (1, 1, 50, 50) at both levels.
"""

from __future__ import annotations

import math
from decimal import Decimal

import duckdb
import numpy as np
import pytest

from conftest import make_events
from funnel import rankings as rk
from funnel import verify


def _e(t: str, kind: str, product: int, code: str | None, price: float, user: int, session: str) -> tuple:
    return ("2019-10-01 " + t, kind, product, product, code, "b", price, user, session)


ROWS = [
    _e("10:00:00", "view", 1, "electronics.phone", 100.0, 1, "S1"),
    _e("10:00:30", "view", 2, "appliances.kettle", 30.0, 1, "S1"),
    _e("10:01:00", "purchase", 1, "electronics.phone", 100.0, 1, "S1"),
    _e("10:02:00", "purchase", 1, "electronics.phone", 100.0, 1, "S1"),
    _e("11:00:00", "view", 1, "electronics.phone", 100.0, 1, "S2"),
    _e("12:00:00", "view", 3, None, 50.0, 2, "S3"),
    _e("12:01:00", "purchase", 3, None, 50.0, 2, "S3"),
    _e("12:02:00", "view", 4, "electronics.tv", 400.0, 2, "S3"),
    _e("12:03:00", "purchase", 2, "appliances.kettle", 30.0, 2, "S3"),
    _e("13:00:00", "view", 5, "apparel.shoes", 20.0, 3, "S4"),
    _e("13:01:00", "cart", 5, "apparel.shoes", 20.0, 3, "S4"),
    _e("14:00:00", "view", 1, "electronics.phone", 100.0, 4, "S5"),
    _e("14:00:30", "view", 1, "electronics.phone", 100.0, 5, "S5"),
    _e("15:00:00", "view", 1, "electronics.phone", 100.0, 6, "S6"),
    _e("15:01:00", "purchase", 1, "electronics.phone", 100.0, 6, "S6"),
]


def test_independent_ranking_counts_match_hand_counts():
    c = duckdb.connect()
    make_events(c, ROWS, name="synthetic")
    verify.build_independent_tables(c, "synthetic")
    got = verify.independent_ranking_counts(c)
    c.close()
    d = Decimal
    zero = (d("0.00"), d("0.00"))
    assert got["category_top"] == {"electronics": (4, 2, d("300.00"), d("200.00")), "appliances": (1, 0, *zero),
                                   "apparel": (1, 0, *zero), "unknown": (1, 1, d("50.00"), d("50.00"))}
    assert got["category_code"] == {"electronics.phone": (3, 2, d("300.00"), d("200.00")),
                                    "electronics.tv": (1, 0, *zero), "appliances.kettle": (1, 0, *zero),
                                    "apparel.shoes": (1, 0, *zero), "unknown": (1, 1, d("50.00"), d("50.00"))}


# ---------- special functions ----------

EULER_GAMMA = 0.5772156649015329


def test_digamma_matches_exact_values_and_the_recurrence():
    # Nine recurrence steps from x = 1 accumulate rounding of about 2e-14.
    assert rk.digamma(np.array([1.0]))[0] == pytest.approx(-EULER_GAMMA, abs=5e-14)
    assert rk.digamma(np.array([0.5]))[0] == pytest.approx(-EULER_GAMMA - 2 * math.log(2), abs=5e-14)
    x = np.array([1e-3, 0.3, 2.5, 9.99, 10.0, 37.2, 1e4, 4e6])
    assert rk.digamma(x + 1) - rk.digamma(x) == pytest.approx(1 / x, rel=1e-12)
    assert verify._psi(1.0) == pytest.approx(-EULER_GAMMA, abs=5e-14)
    assert [verify._psi(v) for v in x] == pytest.approx(list(rk.digamma(x)), rel=1e-13, abs=1e-13)


def test_lgamma_matches_math_lgamma():
    x = np.array([1e-3, 0.5, 1.0, 3.7, 9.99, 10.0, 123.4, 5e5, 1.2e7])
    assert rk.lgamma(x) == pytest.approx([math.lgamma(v) for v in x], rel=1e-13, abs=1e-12)


# ---------- the prior ----------

X = np.array([30, 55, 12, 400, 90, 7, 260, 33], dtype=float)
N = np.array([1000, 1500, 1200, 9000, 2100, 1100, 5000, 1300], dtype=float)


def _grid_best(x: np.ndarray, n: np.ndarray) -> float:
    best = -math.inf
    for mu in np.linspace(0.005, 0.08, 151):
        for log_s in np.linspace(math.log(5), math.log(5e4), 151):
            s = math.exp(log_s)
            best = max(best, rk.loglik(mu * s, (1 - mu) * s, x, n))
    return best


def test_mle_is_a_stationary_point_at_least_as_good_as_a_grid():
    prior = rk.fit_prior_mle(X, N)
    assert not prior["at_cap"]
    assert np.abs(rk._score_theta(rk._theta(prior["mu"], prior["s"]), X, N)) == pytest.approx([0, 0], abs=1e-6)
    assert prior["loglik"] >= _grid_best(X, N) - 1e-9


def test_mle_hits_the_cap_when_rates_are_identical():
    prior = rk.fit_prior_mle(np.array([10.0, 20.0, 40.0]), np.array([1000.0, 2000.0, 4000.0]))
    assert prior["at_cap"] and prior["s"] == pytest.approx(rk.S_MAX)
    assert prior["mu"] == pytest.approx(0.01, rel=1e-9)


def test_moments_fit_follows_its_formula():
    x, n = np.array([10.0, 60.0]), np.array([100.0, 200.0])
    mu = 70 / 300
    spread = 100 * (0.1 - mu) ** 2 + 200 * (0.3 - mu) ** 2
    rho = (spread / (mu * (1 - mu)) - 1) / (300 - (100**2 + 200**2) / 300)
    prior = rk.fit_prior_mom(x, n)
    assert prior["mu"] == pytest.approx(mu) and prior["s"] == pytest.approx(1 / rho - 1)


def test_independent_posterior_agrees_with_rankings_within_the_r2_tolerance():
    prior = rk.fit_prior_mle(X, N)
    ours = rk.posterior_mean(X, N, prior)
    names = [f"c{i}" for i in range(len(X))]
    theirs = verify.independent_posterior({c: (int(n), int(x)) for c, x, n in zip(names, X, N)})
    assert [theirs["posterior_mean"][c] for c in names] == pytest.approx(list(ours), rel=verify.POSTERIOR_TOLERANCE)
    assert [theirs["rank"][c] for c in names] == list(rk.ranks_desc(ours))


def test_independent_posterior_skips_small_and_unknown_categories():
    got = verify.independent_posterior({"a": (999, 10), "unknown": (5000, 50), "b": (1000, 10), "c": (3000, 90)})
    assert sorted(got["posterior_mean"]) == ["b", "c"]


# ---------- estimates, ranks, and separability ----------

def test_posterior_mean_wilson_and_ranks():
    assert rk.posterior_mean(np.array([3.0]), np.array([10.0]), {"a": 1.0, "b": 4.0})[0] == pytest.approx(4 / 15)
    assert rk.wilson_lower(np.array([5.0]), np.array([10.0]))[0] == pytest.approx(0.2365930905, abs=1e-9)
    assert list(rk.ranks_desc(np.array([0.2, 0.5, 0.2, 0.1]))) == [2, 1, 2, 4]


def test_separable_pairs_and_partner_sets():
    lo, hi = np.array([1, 1, 3, 5]), np.array([2, 3, 4, 5])
    pairs = rk.separable_pairs(lo, hi)
    assert pairs == [(0, 2), (0, 3), (1, 3), (2, 3)]
    assert rk.partner_sets(pairs, 4) == [{2, 3}, {3}, {0, 3}, {0, 1, 2}]


def test_rank_intervals_use_observed_ranks():
    draws = np.array([[1, 2], [1, 2], [2, 1], [1, 2]] * 5, dtype=float)
    lo, hi = rk.quantile_interval(draws, integer=True)
    assert list(lo) == [1, 1] and list(hi) == [2, 2]


def test_user_category_sums_and_weighted_totals():
    user = np.array([0, 0, 1, 1, 1, 2])
    cat = np.array([0, 0, 0, 1, 1, 1])
    sums = rk.user_category_sums(user, cat, 2, {"x": np.array([1, 0, 1, 0, 1, 1])})
    assert list(zip(sums["user"], sums["cat"], sums["n"], sums["x"])) == [(0, 0, 2, 1), (1, 0, 1, 1), (1, 1, 2, 1),
                                                                         (2, 1, 1, 1)]
    totals = rk.category_totals(sums, 2, weights=np.array([2.0, 0.0, 1.0]))
    assert list(totals["n"]) == [4, 1] and list(totals["x"]) == [2, 1]


def _users(rates: list[float], sessions_per_cat: int, seed: int) -> tuple[dict[str, np.ndarray], int]:
    """Each user has five category-sessions in one category; purchase flags drawn at the category's rate."""
    rng = np.random.default_rng(seed)
    per_user = 5
    cats = np.repeat(np.arange(len(rates)), sessions_per_cat)
    x = (rng.random(len(cats)) < np.array(rates)[cats]).astype(float)
    user = np.arange(len(cats)) // per_user
    sums = rk.user_category_sums(user, cats, len(rates), {"x": x, "revenue": 10 * x, "revenue_collapsed": 5 * x})
    return sums, int(user.max()) + 1


def test_bootstrap_separates_distinct_rates_and_not_identical_ones():
    distinct, n_users = _users([0.02, 0.05, 0.10, 0.20], 4000, seed=1)
    ranked = np.arange(4)
    run = rk.rank_run(distinct, n_users, 4, ranked, seed=rk.SEED, resamples=200)
    names = ["a", "b", "c", "d"]
    totals = rk.category_totals(distinct, 4)
    out = rk.summarize(run, names, totals, ranked)
    assert out["separable_pair_count"] == 6
    assert [r["rank"] for r in out["rows"]] == [4, 3, 2, 1]
    assert all(r["estimate_interval"][0] <= r["estimate"] <= r["estimate_interval"][1] for r in out["rows"])
    assert out["r3"]["spearman_b_vs_wilson"] == pytest.approx(1.0)
    assert all(r["revenue_per_category_session"] == pytest.approx(10 * r["raw_rate"]) for r in out["rows"])


def test_identical_rates_rarely_separate():
    """Calibration, not a guarantee: with four equal-rate categories, a chance extreme can separate (seed 2 gives a
    category at z = 2.59 and three separable pairs), so the rule is checked as a false-separation rate. Before the
    real-data run, 1 of 40 such datasets (seeds 100-139, 200 resamples) showed any separable pair."""
    hits = 0
    for s in range(20):
        same, n_users = _users([0.05] * 4, 4000, seed=100 + s)
        run = rk.rank_run(same, n_users, 4, np.arange(4), seed=rk.SEED, resamples=100, extras=False)
        hits += rk.summarize(run, list("abcd"), rk.category_totals(same, 4), np.arange(4))["separable_pair_count"] > 0
    assert hits <= 3


def test_bootstrap_is_reproducible():
    sums, n_users = _users([0.02, 0.05], 500, seed=3)
    one = rk.rank_run(sums, n_users, 2, np.arange(2), seed=rk.SEED, resamples=50, extras=False)
    two = rk.rank_run(sums, n_users, 2, np.arange(2), seed=rk.SEED, resamples=50, extras=False)
    assert np.array_equal(one["draws"]["estimate"], two["draws"]["estimate"])


def test_permutation_keeps_category_sizes_and_leaves_other_rows():
    cat = np.array([0, 0, 1, 1, 1, 2, 2])
    eligible = np.isin(cat, [0, 1])
    out = rk.permute_labels(cat, eligible, seed=20261001)
    assert np.array_equal(np.bincount(out), np.bincount(cat))
    assert list(out[5:]) == [2, 2]


def test_sensitivity_comparisons():
    moves = rk.relative_moves(["a", "b", "c", "d"], [0.4, 0.3, 0.2, 0.1], ["a", "b", "d", "e"], [0.1, 0.3, 0.4, 0.9])
    assert moves == {"a": 2, "b": 0, "d": -2}
    a = {"rows": [{"category": c} for c in "abc"], "separable_pairs": [["a", "b"], ["a", "c"]]}
    b = {"rows": [{"category": c} for c in "abcd"], "separable_pairs": [["a", "b"], ["b", "c"]]}
    assert rk.pair_status_changes(a, b) == [["a", "c"], ["b", "c"]]


def _level(**over) -> dict:
    rows = [{"category": c, "rank": i + 1, "category_sessions": n, "shrinkage_weight": w, "design_effect": 1.2,
             "estimate": 0.1 - i / 100} for i, (c, n, w) in enumerate([("a", 5000, 0.2), ("b", 3000, 0.3),
                                                                      ("c", 1000, 0.5)])]
    c1 = {"rows": rows, "prior": {"s": 1000.0}, "separable_pairs": [],
          "r3": {"categories_with_differing_separability": []}}
    level = {"specs": {"C1": c1, "C8": {"rows": rows, "separable_pairs": []}},
             "leave_one_out": [{"category": "a", "exceeds": False}], "negative_control": [
                 {"permutation_seed": 1, "separable_pair_count": 0}],
             "min_size_sensitivity": {"500": {"same_ranked_set_as_c1": True},
                                      "2000": {"same_ranked_set_as_c1": True}}}
    level.update(over)
    return level


def test_triggers_fire_only_when_their_condition_holds():
    assert [r["fired"] for r in rk.triggers(_level())] == [False] * 7
    fired = rk.triggers(_level(negative_control=[{"permutation_seed": 9, "separable_pair_count": 1}]))
    assert [r["rule"][:2] for r in fired if r["fired"]] == ["F6"]
    level = _level()
    level["specs"]["C1"]["rows"][0]["category_sessions"] = 900  # the top-ranked category below the median
    assert [r["rule"][:2] for r in rk.triggers(level) if r["fired"]] == ["F7"]
    level = _level()
    for r in level["specs"]["C1"]["rows"]:
        r["design_effect"] = 2.5
    assert [r["rule"][:2] for r in rk.triggers(level) if r["fired"]] == ["F3"]
    level = _level()
    for r in level["specs"]["C1"]["rows"]:
        r["shrinkage_weight"] = 0.0005
    assert [r["rule"][:2] for r in rk.triggers(level) if r["fired"]] == ["F2"]


# ---------- end to end: run_level, the rules, and the JSON write on a synthetic warehouse ----------

def _warehouse(rng: np.random.Generator) -> duckdb.DuckDBPyConnection:
    """An in-memory stand-in for the two marts: six categories at two levels, 400 users, random flags."""
    sizes = {"a": 40, "b": 60, "c": 100, "d": 150, "e": 200, "f": 300}
    rates = {"a": 0.05, "b": 0.30, "c": 0.10, "d": 0.20, "e": 0.08, "f": 0.15}
    rows = []
    for level in ("category_top", "category_code"):
        k = 0
        for cat, size in sizes.items():
            name = cat if level == "category_top" else f"{cat}.x"
            for _ in range(size):
                k += 1
                bought = bool(rng.random() < rates[cat])
                price = float(rng.integers(1, 100)) if bought else 0.0
                rows.append((level, name, f"s{level}{k}", int(rng.integers(0, 400)), bought, price, price / 2,
                             bool(rng.random() < 0.05), bool(rng.random() < 0.05), bool(rng.random() < 0.2)))
        rows.append((level, "unknown", f"u{level}", 1, True, 5.0, 5.0, False, False, True))
    c = duckdb.connect()
    c.execute("ATTACH ':memory:' AS wh")
    c.execute("CREATE SCHEMA wh.main_marts")
    c.execute("""CREATE TABLE wh.main_marts.mart_category_sessions (category_level VARCHAR, category VARCHAR,
                 user_session VARCHAR, user_id BIGINT, has_purchase BOOLEAN, revenue DECIMAL(18, 2),
                 revenue_collapsed DECIMAL(18, 2), is_long_session BOOLEAN, is_most_active_user BOOLEAN,
                 has_missing_code_event BOOLEAN)""")
    c.executemany("INSERT INTO wh.main_marts.mart_category_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    c.execute("""CREATE TABLE wh.main_marts.mart_category_ranking_counts AS
        WITH specs AS (
            SELECT 'C1' AS spec_key, * FROM wh.main_marts.mart_category_sessions
            UNION ALL SELECT 'C6', * FROM wh.main_marts.mart_category_sessions WHERE NOT is_long_session
            UNION ALL SELECT 'C7', * FROM wh.main_marts.mart_category_sessions WHERE NOT is_most_active_user
            UNION ALL SELECT 'C8', * FROM wh.main_marts.mart_category_sessions WHERE NOT has_missing_code_event)
        SELECT spec_key, category_level, category, count(*) AS category_sessions,
               count(*) FILTER (WHERE has_purchase) AS category_sessions_with_purchase,
               sum(revenue) AS revenue, sum(revenue_collapsed) AS revenue_collapsed
        FROM specs GROUP BY ALL""")
    return c


IDENTITY = {"code_sha256": "code-a", "dataset_sha256": "data-a", "mart_fingerprint": "marts-a"}


def test_run_level_rules_and_json_write_end_to_end(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(rk, "RESAMPLES", 30)
    monkeypatch.setattr(rk, "MIN_SIZE", 50)
    monkeypatch.setattr(rk, "SENSITIVITY_MIN_SIZES", (30, 120))
    monkeypatch.setattr(rk, "PARTIAL_DIR", tmp_path)
    c = _warehouse(np.random.default_rng(7))
    for level in rk.LEVELS:
        out = rk.run_level(c, level, IDENTITY)
        assert [r["category"] for r in out["insufficient_data"]] if "insufficient_data" in out else True
        c1 = out["specs"]["C1"]
        assert len(c1["rows"]) == 5 and [r["category"] for r in c1["insufficient_data"]] == [
            "a" if level == "category_top" else "a.x"]
        assert all(not r["category"].startswith("unknown") for r in c1["rows"])
        assert not out["min_size_sensitivity"]["30"]["same_ranked_set_as_c1"]
        assert len(out["negative_control"]) == 5 and len(out["seed_stability"]) == 3
        rules = rk.triggers(out)
        assert len(rules) == 7 and all(isinstance(r["fired"], (bool, np.bool_)) for r in rules)
        json.dumps(rk.plain({"level": out, "rules": rules}))  # the final write must not fail on numpy types
    parts = ["C1", "C6", "C7", "C8", *(f"C2_{s}" for s in rk.STABILITY_SEEDS), "C5_30", "C5_120",
             *(f"C9_{s}" for s in rk.PERMUTATION_SEEDS)]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(f"{lvl}__{part}.json" for lvl in rk.LEVELS
                                                                for part in parts)
    c.close()


def test_mle_survives_extreme_starting_points():
    # Tiny, all-zero, and all-one categories drive logit mu and log s to their bounds without overflow.
    for x, n in (([0.0, 0.0, 1.0], [500.0, 800.0, 600.0]), ([500.0, 799.0, 600.0], [500.0, 800.0, 600.0]),
                 ([0.0, 400.0], [900.0, 500.0])):
        prior = rk.fit_prior_mle(np.array(x), np.array(n))
        assert all(math.isfinite(prior[k]) for k in ("a", "b", "mu", "s", "loglik"))
    assert rk._ab(np.array([-1000.0, 0.0]))[0] > 0 and rk._ab(np.array([1000.0, 0.0]))[1] > 0  # a and b stay positive
    assert rk.loglik(0.0, 1.0, np.array([1.0]), np.array([2.0])) == -math.inf


# ---------- resume support and the exit-code file (owner decision, 2026-09-27) ----------

def _counting_rank_run(monkeypatch) -> list[int]:
    calls: list[int] = []
    original = rk.rank_run

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(rk, "rank_run", counted)
    return calls


def test_resume_reuses_only_parts_whose_key_matches(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(rk, "RESAMPLES", 10)
    monkeypatch.setattr(rk, "MIN_SIZE", 50)
    monkeypatch.setattr(rk, "SENSITIVITY_MIN_SIZES", (30, 120))
    monkeypatch.setattr(rk, "PARTIAL_DIR", tmp_path)
    calls = _counting_rank_run(monkeypatch)
    c = _warehouse(np.random.default_rng(7))
    level = "category_top"
    first = rk.run_level(c, level, IDENTITY)
    parts = len(calls)
    assert parts == 4 + 3 + 2 + 5  # C1, C6-C8; C2 x 3; C5 at 30 and 120 (both change the set); C9 x 5

    # The same key everywhere: every part is reused, and the result is identical.
    calls.clear()
    again = rk.run_level(c, level, IDENTITY)
    assert calls == [] and json.dumps(rk.plain(again), sort_keys=True) == json.dumps(rk.plain(first), sort_keys=True)

    # One part's recorded key differs (its seed): only that part is recomputed.
    path = tmp_path / f"{level}__C2_{rk.STABILITY_SEEDS[0]}.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["key"]["seed"] = 1
    path.write_text(json.dumps(saved), encoding="utf-8")
    calls.clear()
    rk.run_level(c, level, IDENTITY)
    assert len(calls) == 1

    # A different code SHA (or data hash, or mart fingerprint): every part is recomputed.
    for field in ("code_sha256", "dataset_sha256", "mart_fingerprint"):
        calls.clear()
        rk.run_level(c, level, {**IDENTITY, field: "changed"})
        assert len(calls) == parts, field
    c.close()


def test_resume_recomputes_an_unreadable_or_keyless_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(rk, "PARTIAL_DIR", tmp_path)
    (tmp_path / "category_top__C1.json").write_text("{not json", encoding="utf-8")
    assert rk._cached("category_top", "C1", {"spec": "C1"}, 1, IDENTITY, lambda: {"v": 1}) == {"v": 1}
    (tmp_path / "category_top__C1.json").write_text('{"level": "category_top", "result": {"v": 9}}', encoding="utf-8")
    assert rk._cached("category_top", "C1", {"spec": "C1"}, 1, IDENTITY, lambda: {"v": 2}) == {"v": 2}
    assert rk._cached("category_top", "C1", {"spec": "C1"}, 1, IDENTITY, lambda: {"v": 3}) == {"v": 2}


def test_exit_code_file_holds_the_real_exit_code(tmp_path, monkeypatch):
    target = tmp_path / "rankings_exit_code.txt"
    target.write_text("0\n", encoding="utf-8")  # stale, from an earlier run

    def stops_with_rule():
        assert not target.exists(), "a stale exit-code file must be removed before the run starts"
        raise SystemExit(3)

    for main, expected in ((stops_with_rule, 3), (lambda: None, 0), (lambda: 1 / 0, 1),
                           (lambda: (_ for _ in ()).throw(SystemExit("HALT: mismatch")), 1)):
        monkeypatch.setattr(rk, "main", main)
        assert rk.run_and_record(target) == expected
        assert target.read_text(encoding="utf-8") == f"{expected}\n"
