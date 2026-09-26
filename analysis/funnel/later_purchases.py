"""Analysis B intervals, Kaplan-Meier (R3), seed stability, and the pre-committed stop rules.

Run: python -m funnel.later_purchases   (after python -m funnel.build)

metrics.md Changes 2026-09-26 (Sprint 2 investigations), B items 9-16 and the common rules:
- intervals: 95% percentile intervals from a cluster bootstrap at the user_id level (each resample draws
  user_id values with replacement and keeps all of a drawn user's pairs), 2,000 resamples, seed 20260926;
- Kaplan-Meier (item 12): 1 - S(t) daily for t = 1..30 days over every carted pair with no purchase in the
  session, censored at 2019-10-31 23:59:59 UTC, count-based and value-weighted, with bootstrap bands. S(t)
  uses events strictly before t, matching item 8 condition 4 (t < session start + N days);
- seed stability: the primary intervals (items 9, 10, 12 at 7 days) with seeds 20260927-20260929;
- stop rules (method record B, owner decisions B-D4 and B-D6): identity checks; the B1 count share outside
  the all-pairs KM 7-day interval (then the cohort diagnostic is computed and the run stops); the B1 count
  share not above the comparison baseline (B5). The dominance rule is reported, not a stop.

Reads data/warehouse.duckdb read-only behind the dataset-hash and available-memory gates. Writes
later_purchases.json to the current sprint's evidence folder, and exits 3 if a stop rule fired.
"""

from __future__ import annotations

import sys
import time
from typing import Any

import numpy as np

from funnel.common import (
    CURRENT_EVIDENCE_DIR,
    DATA_DIR,
    DUCKDB_TMP_DIR,
    manifest,
    require_available_ram,
    require_dataset_hash_match,
    write_json,
)

SCRIPT = "funnel.later_purchases"
OUT = CURRENT_EVIDENCE_DIR / "later_purchases.json"
RESAMPLES = 2000
SEED = 20260926
STABILITY_SEEDS = (20260927, 20260928, 20260929)
DAY = 86400
GRID_DAYS = tuple(range(1, 31))
SPECS = ("B1", "B2", "B3", "B5", "B6", "B7", "B8")
DOMINANCE_LIMIT = 0.10


# ---------- pure functions (tested on hand-counted data) ----------

def user_weights(rng: np.random.Generator, n_users: int) -> np.ndarray:
    """One cluster-bootstrap resample: how many times each user is drawn (sums to n_users)."""
    return np.bincount(rng.integers(0, n_users, size=n_users), minlength=n_users).astype(float)


def share_intervals(eligible: np.ndarray, followed: np.ndarray, eligible_value: np.ndarray,
                    followed_value: np.ndarray, seed: int, resamples: int = RESAMPLES) -> dict[str, Any]:
    """Count and value shares with user-level cluster bootstrap percentile intervals (per-user sums in)."""
    rng = np.random.default_rng(seed)
    counts, values = np.empty(resamples), np.empty(resamples)
    for b in range(resamples):
        w = user_weights(rng, len(eligible))
        counts[b] = (w @ followed) / (w @ eligible)
        denominator = w @ eligible_value
        values[b] = (w @ followed_value) / denominator if denominator > 0 else np.nan
    return {
        "count_share": float(followed.sum() / eligible.sum()),
        "count_interval": [float(x) for x in np.percentile(counts, [2.5, 97.5])],
        "value_share": float(followed_value.sum() / eligible_value.sum()) if eligible_value.sum() > 0 else None,
        "value_interval": [float(x) for x in np.nanpercentile(values, [2.5, 97.5])],
        "resamples": resamples,
        "seed": seed,
    }


def km_cdf(durations: np.ndarray, events: np.ndarray, weights: np.ndarray, grid_seconds: np.ndarray,
           distinct: tuple[np.ndarray, np.ndarray] | None = None) -> np.ndarray:
    """Weighted Kaplan-Meier 1 - S(t) at each grid time, from events strictly before t.

    durations must be sorted ascending (events and weights aligned with them). At each distinct time, the
    weighted number at risk is every pair whose duration is at or after that time. `distinct` optionally
    passes np.unique(durations, return_index=True), which does not change between bootstrap resamples."""
    total = weights.sum()
    cum = np.concatenate(([0.0], np.cumsum(weights)))
    times, first = distinct if distinct is not None else np.unique(durations, return_index=True)
    at_risk = total - cum[first]
    d = np.add.reduceat(weights * events, first)
    with np.errstate(divide="ignore", invalid="ignore"):
        factor = np.where(at_risk > 0, 1.0 - d / at_risk, 1.0)
    survival = np.cumprod(factor)
    last_before = np.searchsorted(times, grid_seconds, side="left") - 1
    s = np.where(last_before >= 0, survival[np.clip(last_before, 0, None)], 1.0)
    return 1.0 - s


def km_with_bands(durations: np.ndarray, events: np.ndarray, user_index: np.ndarray, value: np.ndarray,
                  seed: int, grid_days: tuple[int, ...] = GRID_DAYS, resamples: int = RESAMPLES) -> dict[str, Any]:
    """Count-based and value-weighted KM curves with user-level cluster bootstrap 95% bands."""
    order = np.argsort(durations, kind="stable")
    d, e, u, v = durations[order], events[order].astype(float), user_index[order], value[order]
    grid = np.array(grid_days, dtype=float) * DAY
    n_users = int(user_index.max()) + 1 if len(user_index) else 0
    distinct = np.unique(d, return_index=True)
    point_count = km_cdf(d, e, np.ones_like(d, dtype=float), grid, distinct)
    point_value = km_cdf(d, e, v, grid, distinct)
    rng = np.random.default_rng(seed)
    boot_count, boot_value = np.empty((resamples, len(grid))), np.empty((resamples, len(grid)))
    for b in range(resamples):
        w = user_weights(rng, n_users)[u]
        boot_count[b] = km_cdf(d, e, w, grid, distinct)
        boot_value[b] = km_cdf(d, e, w * v, grid, distinct)
    lo_c, hi_c = np.percentile(boot_count, [2.5, 97.5], axis=0)
    lo_v, hi_v = np.percentile(boot_value, [2.5, 97.5], axis=0)
    rows = [{"days": int(t), "count": float(pc), "count_interval": [float(a), float(b)],
             "value_weighted": float(pv), "value_weighted_interval": [float(c), float(f)]}
            for t, pc, a, b, pv, c, f in zip(grid_days, point_count, lo_c, hi_c, point_value, lo_v, hi_v)]
    return {"curve": rows, "pairs": int(len(d)), "events": int(e.sum()), "users": n_users,
            "resamples": resamples, "seed": seed}


def km_at(curve: dict[str, Any], days: int) -> dict[str, Any]:
    return next(r for r in curve["curve"] if r["days"] == days)


def stop_rules(estimates: dict[str, dict[str, Any]], km7: dict[str, Any], checks: dict[str, float]) -> list[dict[str, Any]]:
    """The pre-committed stop rules; each entry says whether it fired."""
    b1 = estimates["B1"]["count_share"]
    lo, hi = km7["count_interval"]
    identity_ok = (checks["user_id_check:events_in_eligible_sessions_with_null_user_id"] == 0
                   and checks["user_id_check:eligible_sessions_with_more_than_one_user_id"] == 0
                   and checks["user_id_check:share_of_eligible_pairs_with_non_null_user_id"] == 1.0)
    return [
        {"rule": "identity: user_id checks 1-2 are zero and check 3 is 100%", "fired": not identity_ok},
        {"rule": "R3 agreement: the B1 7-day count share lies inside the all-pairs KM 7-day 95% interval",
         "fired": not (lo <= b1 <= hi), "b1_count_share": b1, "km_7_day_interval": [lo, hi]},
        {"rule": "comparison baseline: the B1 count share is above the B5 count share",
         "fired": not (b1 > estimates["B5"]["count_share"]), "b1_count_share": b1,
         "b5_count_share": estimates["B5"]["count_share"]},
    ]


# ---------- data access and the run ----------

def _load(con, sql: str) -> dict[str, np.ndarray]:
    return con.execute(sql).fetchnumpy()


def main() -> None:
    from funnel.ingest import connect
    from funnel.profile import SpillSampler

    started = time.perf_counter()
    available = require_available_ram()
    sha = require_dataset_hash_match()
    con = connect()
    con.execute(f"ATTACH '{(DATA_DIR / 'warehouse.duckdb').as_posix()}' AS wh (READ_ONLY)")
    sampler = SpillSampler(DUCKDB_TMP_DIR)
    sampler.start()
    try:
        point = {r[0]: dict(zip(("eligible_pairs", "followed_pairs", "count_share", "eligible_value",
                                  "followed_value", "value_share"), r[1:]))
                 for r in con.execute("""
                     SELECT spec_key, eligible_pairs, followed_pairs, count_share, eligible_value, followed_value,
                            value_share FROM wh.main_marts.mart_later_purchase_estimates""").fetchall()}
        checks = dict(con.execute("SELECT row_key, value FROM wh.main_marts.mart_later_purchase_checks").fetchall())
        estimates: dict[str, dict[str, Any]] = {}
        user_sums: dict[str, dict[str, np.ndarray]] = {}
        for spec in SPECS:
            s = _load(con, f"""
                SELECT eligible_pairs, followed_pairs, CAST(eligible_value AS DOUBLE) AS eligible_value,
                       CAST(followed_value AS DOUBLE) AS followed_value
                FROM wh.main_marts.mart_later_purchase_user_sums WHERE spec_key = '{spec}' ORDER BY user_id""")
            user_sums[spec] = {k: s[k].astype(float) for k in s}
            print(f"Bootstrap {spec} ({len(s['eligible_pairs'])} users) ...", flush=True)
            estimates[spec] = share_intervals(user_sums[spec]["eligible_pairs"], user_sums[spec]["followed_pairs"],
                                              user_sums[spec]["eligible_value"], user_sums[spec]["followed_value"], SEED)
            if abs(estimates[spec]["count_share"] - float(point[spec]["count_share"])) > 1e-12:
                sys.exit(f"HALT: {spec} bootstrap point differs from the mart.")
        km_pairs = _load(con, """
            SELECT duration_seconds, is_event, dense_rank() OVER (ORDER BY user_id) - 1 AS user_index,
                   coalesce(CAST(value AS DOUBLE), 0) AS value, cohort
            FROM wh.main_marts.mart_later_purchase_km_pairs""")
        durations = km_pairs["duration_seconds"].astype(float)
        events = km_pairs["is_event"].astype(bool)
        user_index = km_pairs["user_index"].astype(np.int64)
        value = km_pairs["value"].astype(float)
        print(f"Kaplan-Meier with bands ({len(durations)} pairs) ...", flush=True)
        km = km_with_bands(durations, events, user_index, value, SEED)
        km7 = km_at(km, 7)

        print("Seed stability ...", flush=True)
        stability = []
        for seed in (SEED, *STABILITY_SEEDS):
            b1 = share_intervals(user_sums["B1"]["eligible_pairs"], user_sums["B1"]["followed_pairs"],
                                 user_sums["B1"]["eligible_value"], user_sums["B1"]["followed_value"], seed)
            k7 = km_at(km if seed == SEED else km_with_bands(durations, events, user_index, value, seed,
                                                              grid_days=(7,)), 7)
            stability.append({"seed": seed, "b1_count_interval": b1["count_interval"],
                              "b1_value_interval": b1["value_interval"], "km_7_day_count_interval": k7["count_interval"]})

        rules = stop_rules(estimates, km7, checks)
        cohort = None
        if rules[1]["fired"]:  # owner decision B-D6: escalate with the cohort diagnostic
            cohort = {}
            for name in ("by_7_day_cutoff", "after_7_day_cutoff"):
                mask = km_pairs["cohort"] == name
                cohort[name] = km_at(km_with_bands(durations[mask], events[mask],
                                                   np.unique(user_index[mask], return_inverse=True)[1],
                                                   value[mask], SEED, grid_days=(3, 7)), 7)
    finally:
        peak_spill = sampler.stop()

    top_share = checks["diagnostic:share_of_followed_pairs_held_by_top_0_1_pct_users_by_eligible_pairs"]
    fired = [r["rule"] for r in rules if r["fired"]]
    elapsed = round(time.perf_counter() - started, 1)
    write_json(OUT, {
        "manifest": manifest(SCRIPT, sha),
        "available_ram_gb_before_run": available,
        "elapsed_seconds": elapsed,
        "peak_spill_bytes": peak_spill,
        "estimates": {k: {**v, "eligible_pairs": int(point[k]["eligible_pairs"]),
                          "followed_pairs": int(point[k]["followed_pairs"])} for k, v in estimates.items()},
        "kaplan_meier": km,
        "seed_stability": stability,
        "stop_rules": rules,
        "cohort_diagnostic": cohort,
        "dominance": {"share_of_followed_pairs_held_by_top_0_1_pct_users": top_share,
                      "exceeds_limit": top_share > DOMINANCE_LIMIT, "limit": DOMINANCE_LIMIT},
        "checks": checks,
    })
    print(f"Elapsed: {elapsed} s; peak spill: {peak_spill} bytes ({round(peak_spill / 1024**3, 2)} GiB); "
          f"stop rules fired: {fired or 'none'}", flush=True)
    sys.exit(3 if fired else 0)


if __name__ == "__main__":
    main()
