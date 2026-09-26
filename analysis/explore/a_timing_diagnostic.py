"""EXPLORATORY AND UNPUBLISHED. Analysis A timing diagnostic (Sprint 2 Step 4).

Status:
- Exploratory only. Run under the project owner's H4 decision of 2026-09-26, recorded in
  ai-workflow/sprint-2-verification.md as an explicit, scoped exception to CLAUDE.md rule 3 for
  unpublished diagnostics. The quantities below are NOT defined metrics (docs/metrics.md); nothing
  from them may be published without a dated Changes entry.
- Referenced by ai-workflow/search-log.md rows 12-16. It generates hypotheses, not findings.
- Its outputs are reported to the project owner only and must NEVER be committed. The script
  refuses any output path inside the repository, and analysis/tests/test_explore_outputs.py fails
  if anything other than Python source is committable under analysis/explore/.

Run (after python -m funnel.build; the output path must be outside the repository):
    python analysis/explore/a_timing_diagnostic.py --out C:/path/outside/repo/a_timing.json

Reads data/warehouse.duckdb read-only, behind the dataset-hash and available-memory gates.

D1  per-second distribution of time since the pair's previous purchase event, 1..300 s (+ >300 s)
D2  31-60 s band: price vs first purchase, top-level category (value shares)
D3  concentration: share of band events/value held by the top 1% of users and of sessions
    (with the same statistic over all repeat purchase events as a reference)
D4  band share by UTC day of the repeat event and by UTC hour
D5  comparison baseline: per-second gaps between consecutive same-type events of the same
    (session, product) for views and cart events (and purchases, as a cross-check with D1), 0..300 s
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from funnel.common import DATA_DIR, REPO_ROOT, require_available_ram, require_dataset_hash_match
from funnel.ingest import connect

BAND = (31, 60)


def q(con, sql):
    return con.execute(sql).fetchall()


def output_path(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description="Exploratory, unpublished analysis A timing diagnostic.")
    parser.add_argument("--out", required=True, type=Path, help="JSON output path, outside the repository")
    out = parser.parse_args(argv).out.resolve()
    if out.is_relative_to(REPO_ROOT.resolve()):
        sys.exit(f"HALT: {out} is inside the repository; exploratory outputs must never be committed.")
    return out


def main() -> None:
    out_path = output_path()
    started = time.perf_counter()
    available = require_available_ram()
    sha = require_dataset_hash_match()
    con = connect()
    con.execute(f"ATTACH '{(DATA_DIR / 'warehouse.duckdb').as_posix()}' AS wh (READ_ONLY)")
    con.execute(f"""
        CREATE TEMP TABLE rp AS
        SELECT r.*, s.user_id, cast(r.event_time AS DATE) AS day_utc, hour(r.event_time) AS hour_utc,
               r.seconds_since_previous_purchase BETWEEN {BAND[0]} AND {BAND[1]} AS in_band
        FROM wh.main_intermediate.int_repeat_purchase_events AS r
        JOIN wh.main_intermediate.int_sessions AS s USING (user_session)
    """)
    out: dict = {"label": "EXPLORATORY, UNPUBLISHED; owner decision H4 2026-09-26; never commit",
                 "dataset_sha256": sha, "available_ram_gb_before_run": available}

    # D1
    out["D1_per_second"] = {int(s): [int(n), float(v)] for s, n, v in q(con, """
        SELECT least(seconds_since_previous_purchase, 301), count(*), sum(price)
        FROM rp GROUP BY 1 ORDER BY 1""")}

    # D2
    out["D2_band_price"] = q(con, """
        SELECT price_group, count(*), sum(price), sum(price) / (SELECT sum(price) FROM rp WHERE in_band)
        FROM rp WHERE in_band GROUP BY 1 ORDER BY 1""")
    out["D2_band_category"] = q(con, """
        SELECT category_top, count(*), sum(price) / (SELECT sum(price) FROM rp WHERE in_band) AS band_share,
               (SELECT sum(price) FROM rp AS a WHERE a.category_top = b.category_top) / (SELECT sum(price) FROM rp) AS all_share
        FROM rp AS b WHERE in_band GROUP BY 1 ORDER BY 3 DESC LIMIT 8""")

    # D3
    def top_share(unit: str, where: str) -> dict:
        n_units, top_n, ev_share, val_share = q(con, f"""
            WITH per AS (SELECT {unit} AS u, count(*) AS n, sum(price) AS v FROM rp WHERE {where} GROUP BY 1),
            ranked AS (SELECT *, row_number() OVER (ORDER BY n DESC, v DESC, u) AS k, count(*) OVER () AS units FROM per)
            SELECT any_value(units), ceil(any_value(units) * 0.01),
                   sum(n) FILTER (WHERE k <= ceil(units * 0.01)) / sum(n),
                   sum(v) FILTER (WHERE k <= ceil(units * 0.01)) / sum(v)
            FROM ranked""")[0]
        return {"units": int(n_units), "top_1pct_units": int(top_n),
                "top_1pct_event_share": float(ev_share), "top_1pct_value_share": float(val_share)}
    out["D3_concentration"] = {
        "band_by_user": top_share("user_id", "in_band"),
        "band_by_session": top_share("user_session", "in_band"),
        "all_repeats_by_user": top_share("user_id", "true"),
        "all_repeats_by_session": top_share("user_session", "true"),
        "band_max_events_single_user": int(q(con, "SELECT max(n) FROM (SELECT count(*) n FROM rp WHERE in_band GROUP BY user_id)")[0][0]),
    }

    # D4
    out["D4_by_day"] = [(str(d), int(n), int(b), float(sv)) for d, n, b, sv in q(con, """
        SELECT day_utc, count(*), count(*) FILTER (WHERE in_band),
               coalesce(sum(price) FILTER (WHERE in_band), 0) / sum(price)
        FROM rp GROUP BY 1 ORDER BY 1""")]
    out["D4_by_hour"] = [(int(h), int(n), int(b), float(sv)) for h, n, b, sv in q(con, """
        SELECT hour_utc, count(*), count(*) FILTER (WHERE in_band),
               coalesce(sum(price) FILTER (WHERE in_band), 0) / sum(price)
        FROM rp GROUP BY 1 ORDER BY 1""")]

    # D5: consecutive same-type gaps within (session, product), deduplicated events in valid sessions
    con.execute("""
        CREATE TEMP TABLE gaps AS
        -- least() ignores NULL, so the first event of each pair (no previous event) is dropped
        -- before capping, not counted as a >300 s gap (correction log, Sprint 2 Step 4).
        SELECT event_type, least(raw_gap, 301) AS gap
        FROM (
            SELECT event_type,
                   date_diff('second', lag(event_time) OVER (PARTITION BY event_type, user_session, product_id ORDER BY event_time), event_time) AS raw_gap
            FROM wh.main_staging.stg_events AS e
            WHERE e.user_session IN (SELECT user_session FROM wh.main_intermediate.int_sessions)
        )
        WHERE raw_gap IS NOT NULL
    """)
    out["D5_consecutive_gaps"] = {}
    for et in ("view", "cart", "purchase"):
        rows = q(con, f"SELECT gap, count(*) FROM gaps WHERE event_type = '{et}' GROUP BY 1 ORDER BY 1")
        out["D5_consecutive_gaps"][et] = {int(g): int(n) for g, n in rows}
    # Cross-check: purchase gaps must equal D1 per second (independent gap computations).
    d1 = {s: v[0] for s, v in out["D1_per_second"].items()}
    out["D5_purchase_equals_D1"] = out["D5_consecutive_gaps"]["purchase"] == d1

    out["elapsed_seconds"] = round(time.perf_counter() - started, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(f"wrote {out_path} in {out['elapsed_seconds']} s; D5 purchase equals D1: {out['D5_purchase_equals_D1']}")


if __name__ == "__main__":
    main()
