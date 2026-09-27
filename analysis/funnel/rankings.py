"""Sprint 3 category rankings: empirical-Bayes session conversion with user-clustered rank intervals.

Run: python -m funnel.rankings   (after python -m funnel.build)

metrics.md Changes 2026-09-26 (Sprint 3 ranking) and method record C (ai-workflow/method-selection/
C-category-rankings.md), both approved at H3 on 2026-09-26:
- estimate (item 6): beta-binomial posterior mean (x + a) / (n + a + b), with the prior Beta(a, b) fitted by
  maximum likelihood over the ranked categories (C-D3); method of moments as sensitivity C4;
- ranks (item 7): 1 = highest estimate; 90% percentile intervals of each category's rank and estimate from a
  user_id cluster bootstrap (each resample draws users with replacement and keeps all their category-sessions),
  the prior refitted in every resample; 2,000 resamples, seed 20260926; stability seeds 20260927-29;
- separability (item 8): two categories are separable when their 90% rank intervals don't overlap;
- minimum reporting size (item 9, C-D2): 1,000 category-sessions; smaller categories are neither ranked nor used
  in the prior fit; "unknown" is never ranked (item 3);
- both levels (item 10, C-D1); revenue per category-session, both U1 figures, never ranked (item 11, C-D8);
- robustness plan C1-C11: seed stability (C2), Wilson lower bound ranking as R3 (C3), method-of-moments prior
  (C4), minimum size 500 and 2,000 (C5), sensitivities C6-C8, the label-permutation negative control (C9, C-D6),
  design effect and leave-one-out prior diagnostics (C10), revenue (C11);
- stop rules and slow-down triggers F1-F9 (method record, "Failure conditions"), evaluated after every
  specification has run; the run exits 3 if any fired.

Reads data/warehouse.duckdb read-only behind the dataset-hash and available-memory gates. Writes rankings.json to
the current sprint's evidence folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
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

SCRIPT = "funnel.rankings"
OUT = CURRENT_EVIDENCE_DIR / "rankings.json"
PARTIAL_DIR = DATA_DIR / "rankings_partial"
LEVELS = ("category_top", "category_code")
RESAMPLES = 2000
SEED = 20260926
STABILITY_SEEDS = (20260927, 20260928, 20260929)
PERMUTATION_SEEDS = (20261001, 20261002, 20261003, 20261004, 20261005)
MIN_SIZE = 1000
SENSITIVITY_MIN_SIZES = (500, 2000)
INTERVAL = (0.05, 0.95)  # 90%
WILSON_Z = 1.959963984540054  # two-sided 95%: the Wilson lower bound (95%) of method record C, candidate C
S_MAX = 1e10  # cap on the prior precision a + b: at the cap the prior is the pooled rate (no overdispersion)
S_MIN = 1e-6
MAX_STEP = 2.0  # largest Newton step in each coordinate of theta = (logit mu, log s)
# Operational thresholds fixed before the real-data run (search log, Sprint 3 rows).
DESIGN_EFFECT_LIMIT = 2.0          # F3: the median design effect over ranked categories
B_C_DISAGREEMENT_LIMIT = 2         # F5: categories whose separable partners differ between B and C
RANK_MOVE_LIMIT = 2                # F8: rank change among common categories
TIGHT_PRIOR_MIN_WEIGHT = 0.99      # F2: every ranked category is shrunk at least 99% of the way to the prior
LOOSE_PRIOR_MAX_WEIGHT = 0.001     # F2: no ranked category is shrunk even 0.1% of the way


# ---------- special functions (numpy has no digamma or vectorized lgamma; scipy is not a dependency) ----------

def digamma(x: np.ndarray) -> np.ndarray:
    """psi(x) for x > 0: recurrence psi(x) = psi(x + 1) - 1/x up to x >= 10, then the asymptotic series."""
    x = np.array(x, dtype=float)
    out = np.zeros_like(x)
    small = x < 10
    while small.any():
        out[small] -= 1.0 / x[small]
        x[small] += 1.0
        small = x < 10
    inv2 = 1.0 / (x * x)
    return out + np.log(x) - 0.5 / x - inv2 * (1 / 12 - inv2 * (1 / 120 - inv2 * (1 / 252 - inv2 * (1 / 240 - inv2 / 132))))


def lgamma(x: np.ndarray) -> np.ndarray:
    """log Gamma(x) for x > 0: recurrence up to x >= 10, then Stirling's series."""
    x = np.array(x, dtype=float)
    out = np.zeros_like(x)
    small = x < 10
    while small.any():
        out[small] -= np.log(x[small])
        x[small] += 1.0
        small = x < 10
    inv2 = 1.0 / (x * x)
    series = (1 / 12 - inv2 * (1 / 360 - inv2 * (1 / 1260 - inv2 / 1680))) / x
    return out + (x - 0.5) * np.log(x) - x + 0.5 * math.log(2 * math.pi) + series


# ---------- the beta-binomial prior ----------

def loglik(a: float, b: float, x: np.ndarray, n: np.ndarray) -> float:
    """Beta-binomial log-likelihood over categories, without the binomial coefficients (constant in a, b).
    -inf outside the parameter space (a or b not positive and finite), so a line search rejects such points."""
    if not (0 < a < math.inf and 0 < b < math.inf):
        return -math.inf
    return float(np.sum(lgamma(x + a) + lgamma(n - x + b) - lgamma(n + a + b))
                 + len(x) * (lgamma(np.array([a + b]))[0] - lgamma(np.array([a]))[0] - lgamma(np.array([b]))[0]))


def _score_ab(a: float, b: float, x: np.ndarray, n: np.ndarray) -> tuple[float, float]:
    common = len(x) * digamma(np.array([a + b]))[0] - np.sum(digamma(n + a + b))
    ga = float(np.sum(digamma(x + a)) - len(x) * digamma(np.array([a]))[0] + common)
    gb = float(np.sum(digamma(n - x + b)) - len(x) * digamma(np.array([b]))[0] + common)
    return ga, gb


def _theta(mu: float, s: float) -> np.ndarray:
    return np.array([math.log(mu / (1 - mu)), math.log(s)])


LOGIT_BOUND = 40.0  # |logit mu| <= 40, so mu stays within about 4e-18 of 0 and 1 and exp() cannot overflow


def _ab(theta: np.ndarray) -> tuple[float, float, float, float]:
    u = min(max(float(theta[0]), -LOGIT_BOUND), LOGIT_BOUND)
    e = math.exp(-abs(u))
    mu, one_minus_mu = (1.0 / (1.0 + e), e / (1.0 + e)) if u >= 0 else (e / (1.0 + e), 1.0 / (1.0 + e))
    s = math.exp(theta[1])
    return mu * s, one_minus_mu * s, mu, s


def _score_theta(theta: np.ndarray, x: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Gradient of the log-likelihood in theta = (logit mu, log s), with a = mu s and b = (1 - mu) s."""
    a, b, mu, s = _ab(theta)
    one_minus_mu = b / s  # computed without cancellation in _ab
    ga, gb = _score_ab(a, b, x, n)
    return np.array([mu * one_minus_mu * s * (ga - gb), s * (mu * ga + one_minus_mu * gb)])


def fit_prior_mom(x: np.ndarray, n: np.ndarray) -> dict[str, Any]:
    """Method of moments with unequal sizes: mu is the pooled rate, and the intra-class correlation
    rho = 1 / (1 + s) solves E[S] = mu (1 - mu) [(K - 1) + rho (N - sum n^2 / N)] for S = sum n (p - mu)^2.
    rho <= 0 (no overdispersion) puts s at the cap S_MAX."""
    x, n = np.asarray(x, float), np.asarray(n, float)
    big_n, k = n.sum(), len(n)
    mu = x.sum() / big_n
    spread = float(np.sum(n * (x / n - mu) ** 2))
    rho = (spread / (mu * (1 - mu)) - (k - 1)) / (big_n - np.sum(n * n) / big_n)
    s = S_MAX if rho <= 1 / (1 + S_MAX) else min(max(1 / rho - 1, S_MIN), S_MAX)
    return {"a": mu * s, "b": (1 - mu) * s, "mu": mu, "s": s, "method": "moments", "at_cap": s >= S_MAX}


def fit_prior_mle(x: np.ndarray, n: np.ndarray, max_iter: int = 200) -> dict[str, Any]:
    """Maximum likelihood by damped Newton on the exact score in theta = (logit mu, log s), from the moments fit.

    The Hessian is a central difference of the exact score, so the optimum is found where the exact score is zero.
    log s is bounded to [log S_MIN, log S_MAX]; at the upper bound with a positive s-score, the likelihood is still
    rising towards no overdispersion, and only mu is optimized with s at the cap."""
    x, n = np.asarray(x, float), np.asarray(n, float)
    start = fit_prior_mom(x, n)
    theta = _theta(start["mu"], start["s"])
    lo, hi = math.log(S_MIN), math.log(S_MAX)
    theta[1] = min(max(theta[1], lo), hi)
    at_cap = False
    for iteration in range(max_iter):
        g = _score_theta(theta, x, n)
        at_cap = theta[1] >= hi - 1e-12 and g[1] > 0
        free = np.array([True, not at_cap])
        if np.all(np.abs(g[free]) < 1e-9 * max(1.0, float(np.sum(n)) ** 0.5 * 1e-3)):
            break
        h = 1e-5
        hess = np.empty((2, 2))
        for j in range(2):
            e = np.zeros(2)
            e[j] = h
            hess[:, j] = (_score_theta(theta + e, x, n) - _score_theta(theta - e, x, n)) / (2 * h)
        hess = 0.5 * (hess + hess.T)
        hf, gf = hess[np.ix_(free, free)], g[free]
        try:
            step_f = -np.linalg.solve(hf, gf)
            if gf @ step_f <= 0:  # not an ascent direction: fall back to the gradient
                step_f = gf / max(1.0, float(np.max(np.abs(gf))))
        except np.linalg.LinAlgError:
            step_f = gf / max(1.0, float(np.max(np.abs(gf))))
        step = np.zeros(2)
        step[free] = step_f
        step *= min(1.0, MAX_STEP / max(float(np.max(np.abs(step))), 1e-300))  # trust region in theta
        base = loglik(*_ab(theta)[:2], x, n)
        t, cand = 1.0, None
        while t > 1e-8:
            trial = theta + t * step
            trial[0] = min(max(trial[0], -LOGIT_BOUND), LOGIT_BOUND)
            trial[1] = min(max(trial[1], lo), hi)
            value = loglik(*_ab(trial)[:2], x, n)
            if math.isfinite(value) and value >= base - 1e-9 * abs(base):
                cand = trial
                break
            t *= 0.5
        if cand is None:  # no acceptable point along the step: stay at the current one
            break
        if np.max(np.abs(cand - theta)) < 1e-13:
            theta = cand
            break
        theta = cand
    a, b, mu, s = _ab(theta)
    return {"a": a, "b": b, "mu": mu, "s": s, "method": "maximum likelihood", "at_cap": bool(at_cap),
            "iterations": iteration + 1, "loglik": loglik(a, b, x, n)}


def posterior_mean(x: np.ndarray, n: np.ndarray, prior: dict[str, Any]) -> np.ndarray:
    return (np.asarray(x, float) + prior["a"]) / (np.asarray(n, float) + prior["a"] + prior["b"])


def wilson_lower(x: np.ndarray, n: np.ndarray, z: float = WILSON_Z) -> np.ndarray:
    x, n = np.asarray(x, float), np.asarray(n, float)
    p = x / n
    z2 = z * z
    return (p + z2 / (2 * n) - z * np.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / (1 + z2 / n)


def ranks_desc(values: np.ndarray) -> np.ndarray:
    """Rank 1 = highest; ties share the best rank (1 + number of strictly higher values). Works row-wise on 2-D."""
    v = np.asarray(values, float)
    return 1 + np.sum(v[..., None, :] > v[..., :, None], axis=-1)


def quantile_interval(draws: np.ndarray, integer: bool = False) -> tuple[np.ndarray, np.ndarray]:
    method = "inverted_cdf" if integer else "linear"
    lo, hi = np.quantile(draws, INTERVAL, axis=0, method=method)
    return lo, hi


def separable_pairs(rank_lo: np.ndarray, rank_hi: np.ndarray) -> list[tuple[int, int]]:
    """Index pairs (i, j), i < j, whose rank intervals don't overlap."""
    k = len(rank_lo)
    return [(i, j) for i in range(k) for j in range(i + 1, k)
            if rank_hi[i] < rank_lo[j] or rank_hi[j] < rank_lo[i]]


def partner_sets(pairs: list[tuple[int, int]], k: int) -> list[set[int]]:
    out: list[set[int]] = [set() for _ in range(k)]
    for i, j in pairs:
        out[i].add(j)
        out[j].add(i)
    return out


# ---------- user-level sums and the cluster bootstrap ----------

def user_weights(rng: np.random.Generator, n_users: int) -> np.ndarray:
    """One cluster-bootstrap resample: how many times each user is drawn (sums to n_users)."""
    return np.bincount(rng.integers(0, n_users, size=n_users), minlength=n_users).astype(float)


def user_category_sums(user: np.ndarray, cat: np.ndarray, n_cats: int, columns: dict[str, np.ndarray]
                       ) -> dict[str, np.ndarray]:
    """Collapse category-session rows to one row per (user, category): the category-session count and the sums
    of each column. The bootstrap then resamples users over these rows."""
    key = user.astype(np.int64) * n_cats + cat.astype(np.int64)
    uniq, inverse = np.unique(key, return_inverse=True)
    out = {"user": (uniq // n_cats).astype(np.int64), "cat": (uniq % n_cats).astype(np.int64),
           "n": np.bincount(inverse, minlength=len(uniq)).astype(float)}
    for name, values in columns.items():
        out[name] = np.bincount(inverse, weights=np.asarray(values, float), minlength=len(uniq))
    return out


def category_totals(sums: dict[str, np.ndarray], n_cats: int, weights: np.ndarray | None = None
                    ) -> dict[str, np.ndarray]:
    w = None if weights is None else weights[sums["user"]]
    return {name: np.bincount(sums["cat"], weights=sums[name] if w is None else w * sums[name], minlength=n_cats)
            for name in sums if name not in ("user", "cat")}


def rank_run(sums: dict[str, np.ndarray], n_users: int, n_cats: int, ranked: np.ndarray, seed: int,
             resamples: int | None = None, extras: bool = True) -> dict[str, Any]:
    """Point estimates and bootstrap draws over the ranked categories (indices in `ranked`).

    Always: the MLE prior, posterior means, and their ranks. With extras: raw rates (design effect), the Wilson
    lower bound and its ranks (R3), the method-of-moments posterior and its ranks (C4), and both revenue figures
    per category-session (C11)."""
    def evaluate(tot: dict[str, np.ndarray]) -> dict[str, Any]:
        x, n = tot["x"][ranked], tot["n"][ranked]
        prior = fit_prior_mle(x, n)
        est = posterior_mean(x, n, prior)
        row: dict[str, Any] = {"prior": prior, "estimate": est, "rank": ranks_desc(est)}
        if extras:
            mom = fit_prior_mom(x, n)
            mom_est = posterior_mean(x, n, mom)
            wl = wilson_lower(x, n)
            row.update({"raw": x / n, "wilson": wl, "wilson_rank": ranks_desc(wl), "mom_prior": mom,
                        "mom_estimate": mom_est, "mom_rank": ranks_desc(mom_est),
                        "revenue": tot["revenue"][ranked] / n, "revenue_collapsed": tot["revenue_collapsed"][ranked] / n})
        return row

    resamples = RESAMPLES if resamples is None else resamples
    point = evaluate(category_totals(sums, n_cats))
    rng = np.random.default_rng(seed)
    keys = ["estimate", "rank"] + (["raw", "wilson", "wilson_rank", "mom_estimate", "mom_rank", "revenue",
                                    "revenue_collapsed"] if extras else [])
    draws = {k: np.empty((resamples, len(ranked))) for k in keys}
    priors = np.empty((resamples, 2))
    for r in range(resamples):
        res = evaluate(category_totals(sums, n_cats, user_weights(rng, n_users)))
        for k in keys:
            draws[k][r] = res[k]
        priors[r] = (res["prior"]["mu"], res["prior"]["s"])
    return {"point": point, "draws": draws, "prior_draws": priors, "seed": seed, "resamples": resamples}


def summarize(run: dict[str, Any], names: list[str], totals: dict[str, np.ndarray], ranked: np.ndarray
              ) -> dict[str, Any]:
    """Per-category table, separable pairs, and diagnostics for one rank_run."""
    point, draws = run["point"], run["draws"]
    rank_lo, rank_hi = quantile_interval(draws["rank"], integer=True)
    est_lo, est_hi = quantile_interval(draws["estimate"])
    rows = []
    for i, c in enumerate(ranked):
        row = {"category": names[c], "category_sessions": int(totals["n"][c]),
               "category_sessions_with_purchase": int(totals["x"][c]),
               "estimate": float(point["estimate"][i]), "estimate_interval": [float(est_lo[i]), float(est_hi[i])],
               "rank": int(point["rank"][i]), "rank_interval": [int(rank_lo[i]), int(rank_hi[i])]}
        if "raw" in draws:
            raw_var = float(np.var(draws["raw"][:, i], ddof=1))
            p, n = float(point["raw"][i]), float(totals["n"][c])
            wl_lo, wl_hi = quantile_interval(draws["wilson_rank"][:, [i]], integer=True)
            rv_lo, rv_hi = quantile_interval(draws["revenue"][:, [i]])
            rc_lo, rc_hi = quantile_interval(draws["revenue_collapsed"][:, [i]])
            row.update({
                "raw_rate": p,
                "design_effect": raw_var / (p * (1 - p) / n) if 0 < p < 1 else None,
                "shrinkage_weight": point["prior"]["s"] / (n + point["prior"]["s"]),
                "wilson_lower_bound": float(point["wilson"][i]), "wilson_rank": int(point["wilson_rank"][i]),
                "wilson_rank_interval": [int(wl_lo[0]), int(wl_hi[0])],
                "mom_estimate": float(point["mom_estimate"][i]), "mom_rank": int(point["mom_rank"][i]),
                "revenue_per_category_session": float(point["revenue"][i]),
                "revenue_per_category_session_interval": [float(rv_lo[0]), float(rv_hi[0])],
                "revenue_collapsed_per_category_session": float(point["revenue_collapsed"][i]),
                "revenue_collapsed_per_category_session_interval": [float(rc_lo[0]), float(rc_hi[0])],
            })
        rows.append(row)
    pairs = separable_pairs(rank_lo, rank_hi)
    out = {"rows": rows, "prior": {k: point["prior"][k] for k in ("a", "b", "mu", "s", "at_cap")},
           "prior_draws_quantiles": {"mu": [float(q) for q in np.quantile(run["prior_draws"][:, 0], INTERVAL)],
                                     "s": [float(q) for q in np.quantile(run["prior_draws"][:, 1], INTERVAL)]},
           "separable_pairs": [[names[ranked[i]], names[ranked[j]]] for i, j in pairs],
           "separable_pair_count": len(pairs), "pair_count": len(ranked) * (len(ranked) - 1) // 2,
           "seed": run["seed"], "resamples": run["resamples"]}
    if "wilson_rank" in draws:
        w_lo, w_hi = quantile_interval(draws["wilson_rank"], integer=True)
        wpairs = separable_pairs(w_lo, w_hi)
        b_sets, c_sets = partner_sets(pairs, len(ranked)), partner_sets(wpairs, len(ranked))
        differing = [names[ranked[i]] for i in range(len(ranked)) if b_sets[i] != c_sets[i]]
        out["r3"] = {"spearman_b_vs_wilson": spearman(point["estimate"], point["wilson"]),
                     "wilson_separable_pair_count": len(wpairs),
                     "pairs_separable_in_b_only": [[names[ranked[i]], names[ranked[j]]] for i, j in sorted(set(pairs) - set(wpairs))],
                     "pairs_separable_in_wilson_only": [[names[ranked[i]], names[ranked[j]]] for i, j in sorted(set(wpairs) - set(pairs))],
                     "categories_with_differing_separability": differing}
        out["mom_prior"] = {k: point["mom_prior"][k] for k in ("a", "b", "mu", "s", "at_cap")}
        out["spearman_b_vs_mom"] = spearman(point["estimate"], point["mom_estimate"])
    return out


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = ranks_desc(a).astype(float), ranks_desc(b).astype(float)
    if np.std(ra) == 0 or np.std(rb) == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def leave_one_out(x: np.ndarray, n: np.ndarray, prior_mu: float, widths: np.ndarray, names: list[str]
                  ) -> list[dict[str, Any]]:
    """F1 diagnostic: the prior mean refitted without each category, against that category's interval width."""
    out = []
    for i in range(len(x)):
        keep = np.arange(len(x)) != i
        mu_i = fit_prior_mle(x[keep], n[keep])["mu"]
        out.append({"category": names[i], "prior_mu_without": mu_i, "shift": abs(mu_i - prior_mu),
                    "estimate_interval_width": float(widths[i]), "exceeds": abs(mu_i - prior_mu) > widths[i]})
    return out


def permute_labels(cat: np.ndarray, eligible: np.ndarray, seed: int) -> np.ndarray:
    """C9: shuffle category labels across the category-sessions of the ranked categories, keeping each category's
    number of category-sessions."""
    out = cat.copy()
    idx = np.flatnonzero(eligible)
    out[idx] = cat[idx][np.random.default_rng(seed).permutation(len(idx))]
    return out


def relative_moves(names_a: list[str], est_a: np.ndarray, names_b: list[str], est_b: np.ndarray
                   ) -> dict[str, int]:
    """F8: re-rank the categories ranked in both specifications within that common set, and report each one's
    rank change."""
    common = [c for c in names_a if c in set(names_b)]
    ia = [names_a.index(c) for c in common]
    ib = [names_b.index(c) for c in common]
    ra, rb = ranks_desc(np.asarray(est_a)[ia]), ranks_desc(np.asarray(est_b)[ib])
    return {c: int(rb[k] - ra[k]) for k, c in enumerate(common)}


def pair_status_changes(summary_a: dict[str, Any], summary_b: dict[str, Any]) -> list[list[str]]:
    """F8: pairs ranked in both specifications whose separable status differs."""
    names_a = {r["category"] for r in summary_a["rows"]}
    names_b = {r["category"] for r in summary_b["rows"]}
    common = sorted(names_a & names_b)
    sep_a = {frozenset(p) for p in summary_a["separable_pairs"]}
    sep_b = {frozenset(p) for p in summary_b["separable_pairs"]}
    return [[c, d] for i, c in enumerate(common) for d in common[i + 1:]
            if (frozenset((c, d)) in sep_a) != (frozenset((c, d)) in sep_b)]


# ---------- data access and the run ----------

def _load_level(con, level: str) -> tuple[dict[str, np.ndarray], list[str], int]:
    names = [r[0] for r in con.execute(f"""
        SELECT DISTINCT category FROM wh.main_marts.mart_category_sessions
        WHERE category_level = '{level}' AND category <> 'unknown' ORDER BY category""").fetchall()]
    rows = con.execute(f"""
        WITH c AS (SELECT category, row_number() OVER (ORDER BY category) - 1 AS cat
                   FROM (SELECT DISTINCT category FROM wh.main_marts.mart_category_sessions
                         WHERE category_level = '{level}' AND category <> 'unknown'))
        SELECT dense_rank() OVER (ORDER BY s.user_id) - 1 AS user_index, c.cat,
               CAST(s.has_purchase AS TINYINT) AS x, CAST(s.revenue AS DOUBLE) AS revenue,
               CAST(s.revenue_collapsed AS DOUBLE) AS revenue_collapsed,
               s.is_long_session, s.is_most_active_user, s.has_missing_code_event
        FROM wh.main_marts.mart_category_sessions AS s INNER JOIN c USING (category)
        WHERE s.category_level = '{level}'""").fetchnumpy()
    data = {k: np.asarray(v) for k, v in rows.items()}
    return data, names, int(data["user_index"].max()) + 1


def _mart_counts(con, spec: str, level: str) -> dict[str, tuple[int, int, float, float]]:
    return {r[0]: (int(r[1]), int(r[2]), float(r[3]), float(r[4])) for r in con.execute(f"""
        SELECT category, category_sessions, category_sessions_with_purchase, revenue, revenue_collapsed
        FROM wh.main_marts.mart_category_ranking_counts
        WHERE spec_key = '{spec}' AND category_level = '{level}'""").fetchall()}


SPEC_MASKS = {"C1": None, "C6": "is_long_session", "C7": "is_most_active_user", "C8": "has_missing_code_event"}


def _spec_sums(data: dict[str, np.ndarray], spec: str, n_cats: int, cat: np.ndarray | None = None
               ) -> dict[str, np.ndarray]:
    flag = SPEC_MASKS[spec]
    keep = np.ones(len(data["x"]), dtype=bool) if flag is None else ~data[flag].astype(bool)
    cats = data["cat"] if cat is None else cat
    return user_category_sums(data["user_index"][keep], cats[keep], n_cats,
                              {"x": data["x"][keep], "revenue": data["revenue"][keep],
                               "revenue_collapsed": data["revenue_collapsed"][keep]})


def _check_against_mart(totals: dict[str, np.ndarray], names: list[str], mart: dict[str, tuple], label: str) -> None:
    for c, name in enumerate(names):
        n, x, rev, revc = mart.get(name, (0, 0, 0.0, 0.0))
        if (int(totals["n"][c]), int(round(totals["x"][c]))) != (n, x):
            sys.exit(f"HALT: {label} {name}: bootstrap input counts differ from mart_category_ranking_counts.")
        for got, want in ((totals["revenue"][c], rev), (totals["revenue_collapsed"][c], revc)):
            if abs(got - want) > 1e-6 * max(1.0, abs(want)):
                sys.exit(f"HALT: {label} {name}: bootstrap input revenue differs from mart_category_ranking_counts.")


def plain(value: Any) -> Any:
    """numpy scalars and arrays to plain Python, recursively, so json.dumps accepts the result."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return [plain(v) for v in value.tolist()]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _cached(level: str, part: str, specification: dict[str, Any], seed: int, identity: dict[str, str],
            compute: Callable[[], Any]) -> Any:
    """Resume support (owner decision, 2026-09-27): reuse a part's partial file only if its recorded key (code
    SHA-256, dataset SHA-256, mart fingerprint, level, part, specification, and seed) equals the current run's;
    otherwise compute the part and save it with its key."""
    key = plain({**identity, "level": level, "part": part, "specification": specification, "seed": seed})
    path = PARTIAL_DIR / f"{level}__{part}.json"
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = None
        if isinstance(saved, dict) and saved.get("key") == key:
            print(f"{level} {part}: reused from {path.name} (key matches)", flush=True)
            return saved["result"]
    result = plain(compute())
    write_json(path, {"key": key, "result": result})
    return result


def run_level(con, level: str, identity: dict[str, str]) -> dict[str, Any]:
    data, names, n_users = _load_level(con, level)
    n_cats = len(names)
    out: dict[str, Any] = {"level": level, "users": n_users, "category_session_rows": int(len(data["x"]))}
    base_spec = {"resamples": RESAMPLES, "interval": list(INTERVAL), "min_size": MIN_SIZE}
    specs: dict[str, Any] = {}
    for spec in ("C1", "C6", "C7", "C8"):
        sums = _spec_sums(data, spec, n_cats)
        totals = category_totals(sums, n_cats)
        _check_against_mart(totals, names, _mart_counts(con, spec, level), f"{spec} {level}")
        ranked = np.flatnonzero(totals["n"] >= MIN_SIZE)
        print(f"{level} {spec}: {len(ranked)} ranked of {n_cats} ...", flush=True)

        def compute(sums=sums, totals=totals, ranked=ranked, spec=spec) -> dict[str, Any]:
            summary = summarize(rank_run(sums, n_users, n_cats, ranked, SEED, extras=(spec == "C1")),
                                names, totals, ranked)
            summary["insufficient_data"] = [{"category": names[c], "category_sessions": int(totals["n"][c]),
                                             "category_sessions_with_purchase": int(totals["x"][c])}
                                            for c in np.flatnonzero(totals["n"] < MIN_SIZE)]
            return summary

        specs[spec] = _cached(level, spec, {"spec": spec, **base_spec, "extras": spec == "C1"}, SEED, identity,
                              compute)
        if spec == "C1":
            c1_sums, c1_totals, c1_ranked = sums, totals, ranked
    out["specs"] = specs

    # C2 seed stability (C1).
    out["seed_stability"] = []
    base = specs["C1"]
    for seed in STABILITY_SEEDS:
        print(f"{level} C2 seed {seed} ...", flush=True)
        s = _cached(level, f"C2_{seed}", {"spec": "C2", **base_spec}, seed, identity,
                    lambda seed=seed: summarize(rank_run(c1_sums, n_users, n_cats, c1_ranked, seed, extras=False),
                                                names, c1_totals, c1_ranked))
        out["seed_stability"].append({
            "seed": seed, "separable_pair_count": s["separable_pair_count"],
            "rank_intervals_changed": [r["category"] for r, b in zip(s["rows"], base["rows"])
                                       if r["rank_interval"] != b["rank_interval"]],
            "max_estimate_bound_difference": max(max(abs(r["estimate_interval"][0] - b["estimate_interval"][0]),
                                                      abs(r["estimate_interval"][1] - b["estimate_interval"][1]))
                                                  for r, b in zip(s["rows"], base["rows"])),
            "separable_pairs_changed": sorted(map(sorted, {frozenset(p) for p in s["separable_pairs"]}
                                                  ^ {frozenset(p) for p in base["separable_pairs"]}))})

    # C5 minimum size 500 and 2,000 (C1 data).
    out["min_size_sensitivity"] = {}
    for size in SENSITIVITY_MIN_SIZES:
        ranked = np.flatnonzero(c1_totals["n"] >= size)
        if np.array_equal(ranked, c1_ranked):
            out["min_size_sensitivity"][str(size)] = {"same_ranked_set_as_c1": True}
            continue
        print(f"{level} C5 minimum size {size}: {len(ranked)} ranked ...", flush=True)
        s = _cached(level, f"C5_{size}", {"spec": "C5", **base_spec, "min_size": size}, SEED, identity,
                    lambda ranked=ranked: summarize(rank_run(c1_sums, n_users, n_cats, ranked, SEED, extras=False),
                                                    names, c1_totals, ranked))
        out["min_size_sensitivity"][str(size)] = {"same_ranked_set_as_c1": False, **s}

    # C10 diagnostics: leave-one-out prior (F1). Seconds, so never cached.
    x1, n1 = c1_totals["x"][c1_ranked], c1_totals["n"][c1_ranked]
    widths = np.array([r["estimate_interval"][1] - r["estimate_interval"][0] for r in specs["C1"]["rows"]])
    out["leave_one_out"] = plain(leave_one_out(x1, n1, specs["C1"]["prior"]["mu"], widths,
                                               [names[c] for c in c1_ranked]))

    # C9 negative control: label permutations over the C1 ranked categories' category-sessions.
    out["negative_control"] = []
    eligible = np.isin(data["cat"], c1_ranked)
    for pseed in PERMUTATION_SEEDS:
        print(f"{level} C9 permutation {pseed} ...", flush=True)

        def compute_nc(pseed=pseed) -> dict[str, Any]:
            permuted = permute_labels(data["cat"], eligible, pseed)
            sums = _spec_sums(data, "C1", n_cats, cat=permuted)
            totals = category_totals(sums, n_cats)
            if not np.array_equal(totals["n"], c1_totals["n"]):
                sys.exit("HALT: the permutation changed a category's number of category-sessions.")
            s = summarize(rank_run(sums, n_users, n_cats, c1_ranked, SEED, extras=False), names, totals, c1_ranked)
            return {"permutation_seed": pseed, "bootstrap_seed": SEED,
                    "separable_pair_count": s["separable_pair_count"],
                    "separable_pairs": s["separable_pairs"], "prior": s["prior"]}

        out["negative_control"].append(_cached(level, f"C9_{pseed}", {"spec": "C9", **base_spec,
                                                                       "bootstrap_seed": SEED}, pseed, identity,
                                               compute_nc))
    return out


def triggers(level_out: dict[str, Any]) -> list[dict[str, Any]]:
    """F1-F9 evaluated for one level (F4 and F9 are checked by funnel.verify and dbt)."""
    c1 = level_out["specs"]["C1"]
    rows = c1["rows"]
    out = []
    loo = [r for r in level_out["leave_one_out"] if r["exceeds"]]
    out.append({"rule": "F1 single prior: a leave-one-out prior mean shift exceeds that category's interval width",
                "kind": "stop (H4)", "fired": bool(loo), "categories": [r["category"] for r in loo]})
    weights = [r["shrinkage_weight"] for r in rows]
    tight, loose = min(weights) > TIGHT_PRIOR_MIN_WEIGHT, max(weights) < LOOSE_PRIOR_MAX_WEIGHT
    out.append({"rule": "F2 prior collapse: every shrinkage weight above 0.99 (tight) or all below 0.001 (loose)",
                "kind": "slow-down trigger", "fired": tight or loose, "tight": tight, "loose": loose,
                "shrinkage_weight_range": [min(weights), max(weights)], "prior_s": c1["prior"]["s"]})
    deffs = [r["design_effect"] for r in rows if r["design_effect"] is not None]
    median_deff = float(np.median(deffs))
    out.append({"rule": f"F3 clustering: median design effect over ranked categories above {DESIGN_EFFECT_LIMIT}",
                "kind": "stop (H4)", "fired": median_deff > DESIGN_EFFECT_LIMIT, "median_design_effect": median_deff})
    differing = c1["r3"]["categories_with_differing_separability"]
    out.append({"rule": f"F5 B and C disagree on separability for more than {B_C_DISAGREEMENT_LIMIT} categories",
                "kind": "slow-down trigger", "fired": len(differing) > B_C_DISAGREEMENT_LIMIT,
                "categories": differing})
    nc = [p for p in level_out["negative_control"] if p["separable_pair_count"] > 0]
    out.append({"rule": "F6 negative control: any separable pair in any permutation", "kind": "stop",
                "fired": bool(nc), "permutations_with_separation": [p["permutation_seed"] for p in nc]})
    top = min(rows, key=lambda r: (r["rank"], r["category"]))
    median_n = float(np.median([r["category_sessions"] for r in rows]))
    out.append({"rule": "F7 the top-ranked category has fewer category-sessions than the median ranked category",
                "kind": "slow-down trigger", "fired": top["category_sessions"] < median_n,
                "top_category": top["category"], "top_category_sessions": top["category_sessions"],
                "median_category_sessions": median_n})
    moves, changes = {}, {}
    for label, other in [(f"C5 minimum size {s}", level_out["min_size_sensitivity"][str(s)])
                         for s in SENSITIVITY_MIN_SIZES] + [("C8 no missing-code sessions", level_out["specs"]["C8"])]:
        if other.get("same_ranked_set_as_c1"):
            continue
        m = relative_moves([r["category"] for r in rows], [r["estimate"] for r in rows],
                           [r["category"] for r in other["rows"]], [r["estimate"] for r in other["rows"]])
        moves[label] = {c: d for c, d in m.items() if abs(d) > RANK_MOVE_LIMIT}
        changes[label] = pair_status_changes(c1, other)
    fired = any(moves.values()) or any(changes.values())
    out.append({"rule": f"F8 sensitivity movement: a rank change above {RANK_MOVE_LIMIT} places among common "
                        "categories, or a changed separable status, under C5 or C8",
                "kind": "slow-down trigger", "fired": fired, "rank_moves": moves, "separable_status_changes": changes})
    return out


def code_sha256() -> str:
    """SHA-256 of this module's source: any code change invalidates every partial file."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def main() -> None:
    from funnel.ingest import connect
    from funnel.profile import SpillSampler

    from funnel.provenance import marts_fingerprint, require_clean_worktree, require_gated_marts

    started = time.perf_counter()
    require_clean_worktree(SCRIPT)
    available = require_available_ram()
    sha = require_dataset_hash_match()
    con = connect()
    con.execute(f"ATTACH '{(DATA_DIR / 'warehouse.duckdb').as_posix()}' AS wh (READ_ONLY)")
    fingerprint = marts_fingerprint(con, "wh")
    build_record = require_gated_marts(fingerprint, SCRIPT)
    print(f"Marts fingerprint {fingerprint[:12]} matches the gated build at "
          f"{build_record['manifest']['git_commit_sha'][:7]} ({build_record['manifest']['generated_at_utc']})",
          flush=True)
    identity = {"code_sha256": code_sha256(), "dataset_sha256": sha, "mart_fingerprint": fingerprint}
    print(f"Resume key: code {identity['code_sha256'][:12]}, data {sha[:12]}, marts "
          f"{identity['mart_fingerprint'][:12]}", flush=True)
    sampler = SpillSampler(DUCKDB_TMP_DIR)
    sampler.start()
    try:
        unknown = {level: dict(zip(("category_sessions", "all_category_sessions"), con.execute(f"""
            SELECT sum(category_sessions) FILTER (WHERE category = 'unknown'), sum(category_sessions)
            FROM wh.main_marts.mart_category_ranking_counts
            WHERE spec_key = 'C1' AND category_level = '{level}'""").fetchone())) for level in LEVELS}
        threshold = con.execute("""
            SELECT value FROM wh.main_marts.mart_later_purchase_checks
            WHERE row_key = 'sensitivity_threshold:most_active_user_threshold_events'""").fetchone()[0]
        levels = {level: run_level(con, level, identity) for level in LEVELS}
    finally:
        peak_spill = sampler.stop()
    rules = {level: triggers(levels[level]) for level in LEVELS}
    fired = [f"{level}: {r['rule']}" for level in LEVELS for r in rules[level] if r["fired"]]
    elapsed = round(time.perf_counter() - started, 1)
    for u in unknown.values():
        u["share"] = u["category_sessions"] / u["all_category_sessions"]
    write_json(OUT, plain({
        "manifest": manifest(SCRIPT, sha),
        "available_ram_gb_before_run": available,
        "elapsed_seconds": elapsed,
        "peak_spill_bytes": peak_spill,
        "resume_key": identity,
        "gated_build": {"git_commit_sha": build_record["manifest"]["git_commit_sha"],
                        "generated_at_utc": build_record["manifest"]["generated_at_utc"],
                        "dbt_args": build_record["dbt_args"]},
        "settings": {"resamples": RESAMPLES, "seed": SEED, "stability_seeds": list(STABILITY_SEEDS),
                     "permutation_seeds": list(PERMUTATION_SEEDS), "min_size": MIN_SIZE,
                     "sensitivity_min_sizes": list(SENSITIVITY_MIN_SIZES), "interval": list(INTERVAL),
                     "wilson_z": WILSON_Z, "s_max": S_MAX,
                     "most_active_user_threshold_events": threshold},
        "unknown_exclusion": unknown,
        "levels": levels,
        "rules": rules,
    }))
    print(f"Elapsed: {elapsed} s; peak spill: {peak_spill} bytes; rules fired: {fired or 'none'}", flush=True)
    sys.exit(3 if fired else 0)


def run_and_record(exit_code_file: Path | None) -> int:
    """Run main() and return its real exit code. The exit-code file, if given, is removed at the start and written
    as the very last step, so its absence means the run has not finished (or was killed)."""
    if exit_code_file is not None and exit_code_file.exists():
        exit_code_file.unlink()
    try:
        main()
        code = 0
    except SystemExit as stop:
        if isinstance(stop.code, str):
            print(stop.code, file=sys.stderr, flush=True)
        code = stop.code if isinstance(stop.code, int) else (0 if stop.code is None else 1)
    except KeyboardInterrupt:
        traceback.print_exc()
        code = 130
    except Exception:
        traceback.print_exc()
        code = 1
    if exit_code_file is not None:
        exit_code_file.parent.mkdir(parents=True, exist_ok=True)
        exit_code_file.write_text(f"{code}\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint 3 category ranking (method record C).")
    parser.add_argument("--exit-code-file", type=Path, default=None,
                        help="file that receives the run's real exit code as its last step")
    sys.exit(run_and_record(parser.parse_args().exit_code_file))
