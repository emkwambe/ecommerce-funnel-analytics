"""Generate the evidence sections of ai-workflow/sprint-2-verification.md from saved evidence and exports.

Run: python -m funnel.verification_sprint2

The file's top part (the owner decisions, written as each decision was made) is kept as written. Everything below
the GENERATED marker is regenerated from ai-workflow/evidence/sprint-2/ (dbt_build_runs.json, verify.json,
later_purchases.json, pytest.txt, and, after the deploy, smoke_production.txt and screenshots.txt), the JSON
exports in web/public/data/, the correction log, and git history, so that no figure in it is typed by hand.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from funnel.common import CURRENT_EVIDENCE_DIR, REPO_ROOT, write_text
from funnel.export import CORRECTION_LOG, WEB_DATA, parse_correction_log

OUT = REPO_ROOT / "ai-workflow" / "sprint-2-verification.md"
MARKER = "<!-- GENERATED BELOW by python -m funnel.verification_sprint2"
SPRINT_1_LAST = "afd7183"  # the last commit before Sprint 2 (H9 sign-off of C1 and C2)
EV = "ai-workflow/evidence/sprint-2"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(x: float, digits: int = 2) -> str:
    return f"{x * 100:.{digits}f}%"


def interval(x: list[float], digits: int = 2) -> str:
    return f"[{pct(x[0], digits)}, {pct(x[1], digits)}]"


def money(x: float) -> str:
    return f"${x:,.2f}"


def gib(n: int) -> str:
    return f"{n / 1024 ** 3:.2f} GiB"


def sprint_commits() -> list[tuple[str, str]]:
    out = subprocess.run(["git", "-C", str(REPO_ROOT), "log", "--reverse", "--first-parent", "--format=%h%x09%s",
                          f"{SPRINT_1_LAST}..HEAD"], capture_output=True, text=True, check=True).stdout
    return [tuple(line.split("\t", 1)) for line in out.splitlines() if line.strip()]  # type: ignore[misc]


def pytest_summary(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    summary = next((ln for ln in reversed(lines) if " passed" in ln or " failed" in ln), "no summary line found")
    exit_line = next((ln for ln in reversed(lines) if ln.startswith("pytest_exit_code=")), "pytest_exit_code=?")
    return f"{summary.strip()}  ({exit_line.strip()})"


def production_section() -> list[str]:
    smoke_file, shots_file = CURRENT_EVIDENCE_DIR / "smoke_production.txt", CURRENT_EVIDENCE_DIR / "screenshots.txt"
    if not smoke_file.exists():
        return ["## Production", "", "Pending: the Step 7 deploy, production smoke, and screenshots have not run yet.", ""]
    smoke = smoke_file.read_text(encoding="utf-8")
    url = re.search(r"Smoke test against (\S+)", smoke).group(1)
    line = re.search(r"^(\d+/\d+ checks passed)$", smoke, re.MULTILINE)
    out = ["## Production", "", f"- Live site: {url}",
           f"- Smoke test against production: `{line.group(1) if line else 'no summary line'}` (`{EV}/smoke_production.txt`)."]
    if shots_file.exists():
        shots = shots_file.read_text(encoding="utf-8")
        out.append(f"- 390 px screenshots, light and dark: {len(re.findall(r'^PASS ', shots, re.MULTILINE))} page-theme"
                   f" combinations pass, {len(re.findall(r'^FAIL ', shots, re.MULTILINE))} fail; WebP files in `{EV}/`.")
    return [*out, ""]


def render_generated() -> str:
    runs = _json(CURRENT_EVIDENCE_DIR / "dbt_build_runs.json")["runs"]
    full = [r for r in runs if r["dbt_args"] == ["build"]]
    verify = _json(CURRENT_EVIDENCE_DIR / "verify.json")
    stats = _json(CURRENT_EVIDENCE_DIR / "later_purchases.json")
    pytest_file = CURRENT_EVIDENCE_DIR / "pytest.txt"
    gap = _json(WEB_DATA / "investigation_revenue_gap.json")
    later = _json(WEB_DATA / "investigation_later_purchases.json")
    log = parse_correction_log(CORRECTION_LOG.read_text(encoding="utf-8"))
    entries = [e for e in log["entries"] if e["phase"].startswith("Sprint 2")]
    checks = verify["checks"]
    t = gap["totals"]
    est = {e["spec_key"]: e for e in later["estimates"]}
    c = later["cohort_difference"]

    lines = [
        MARKER + " from saved evidence, exports, and git history. Do not edit below this line by hand. -->",
        "",
        *production_section(),
        "## Full dbt builds (from clean trees)",
        "",
        "| Commit | Clean | dbt | Tests run / expected | Models | Available before | Elapsed | Peak spill |",
        "|---|---|---|---|---|---|---|---|",
        *[f"| `{r['manifest']['git_commit_sha'][:7]}` | {not r['manifest']['git_worktree_dirty']}"
          f" | PASS={r['dbt_done_counts']['pass']} ERROR={r['dbt_done_counts']['error']}"
          f" | {r['test_coverage']['tests_run']} / {r['test_coverage']['tests_expected']} | {r['test_coverage']['models_built']}"
          f" | {r['available_ram_gb_before_run']} GB | {r['elapsed_seconds']} s | {gib(r['peak_spill_bytes'])} |" for r in full],
        "",
        "## Independent verification (`python -m funnel.verify`, latest run)",
        "",
        f"- Commit `{verify['manifest']['git_commit_sha'][:7]}`, clean tree: {not verify['manifest']['git_worktree_dirty']}."
        f" {verify['available_ram_gb_before_run']} GB available before the run; {verify['elapsed_seconds']} s;"
        f" peak spill {gib(verify['peak_spill_bytes'])}.",
        f"- All checks match: **{verify['all_match']}** ({sum(x['match'] for x in checks)} of {len(checks)}):"
        f" {sum(x['check'].startswith('A') for x in checks)} for analysis A,"
        f" {sum(x['check'].startswith('B') for x in checks)} for analysis B, and the rest from Sprint 1."
        f" Counts and DECIMAL sums exactly, rates within {verify['rate_tolerance']}. Every check is in `{EV}/verify.json`.",
        "",
        "## Analysis A: the two revenue figures (from investigation_revenue_gap.json)",
        "",
        f"- Revenue {money(t['revenue'])}; revenue with repeat purchase events collapsed {money(t['revenue_repeat_collapsed'])};"
        f" difference {money(t['revenue_difference'])}, the value of {t['repeat_purchase_events']:,} repeat purchase events in"
        f" {t['pairs']:,} (session, product) pairs.",
        "",
        "| Dimension | Group | Share of the difference | Repeat purchase events |",
        "|---|---|---|---|",
        *[f"| {dim} | {x['group_label']} | {pct(x['share_of_difference'])} | {x['repeat_purchase_events']:,} |"
          for dim in ("price_vs_first_purchase", "purchase_events_in_pair")
          for x in gap["dimensions"][dim]],
        "",
        # Timing is reported through the cumulative thresholds only (owner decision H4 for A: the 60 s bin edge
        # splits a large mass, so the bin groups are not published as a pattern).
        "Threshold sensitivity (share of the difference within T): "
        + "; ".join(f"{x['threshold_label']} {pct(x['share_of_difference'])}" for x in gap["thresholds"]) + ".",
        "",
        "## Analysis B: later purchases (from investigation_later_purchases.json and later_purchases.json)",
        "",
        "| Spec | Population | Followed / eligible | Count share [95% CI] | Value share [95% CI] |",
        "|---|---|---|---|---|",
        *[f"| {k} | {e['population']} | {e['followed_pairs']:,} / {e['eligible_pairs']:,} | {pct(e['count_share'])}"
          f" {interval(e['count_interval'])} | {pct(e['value_share'])} {interval(e['value_interval'])} |"
          for k, e in sorted(est.items())],
        "",
        "Kaplan–Meier (all carted pairs with no purchase in the session, all of October): "
        + "; ".join(f"{r['days']} d {pct(r['count'])} {interval(r['count_interval'])}"
                    for r in later["kaplan_meier"]["curve"] if r["days"] in (1, 3, 7, 14, 30)) + ".",
        "",
        f"Cohort difference: {c['later_population']}, KM 7-day {pct(c['later_km_7_day'])} {interval(c['later_km_7_day_interval'])},"
        f" against {pct(c['b1_count_share'])} {interval(c['b1_count_interval'])} for {c['b1_population']}.",
        "",
        "Stop rules (pre-committed):",
        "",
        *[f"- {r['rule']}: **{'fired' if r['fired'] else 'did not fire'}**"
          + (f". Resolution: {r['owner_resolution']}" if r.get("owner_resolution") else "") for r in later["stop_rules"]],
        "",
        f"Statistics run: commit `{stats['manifest']['git_commit_sha'][:7]}`, {stats['available_ram_gb_before_run']} GB available,"
        f" {stats['elapsed_seconds']} s.",
        "",
        "### Seed-stability check (owner decision H3-D5)",
        "",
        "| Seed | B1 count share 95% CI | B1 value share 95% CI | KM 7-day 95% CI |",
        "|---|---|---|---|",
        *[f"| {s['seed']} | {interval(s['b1_count_interval'], 3)} | {interval(s['b1_value_interval'], 3)}"
          f" | {interval(s['km_7_day_count_interval'], 3)} |" for s in later["seed_stability"]],
        "",
        "The published intervals use the first seed. Across the four seeds, each bound moves by up to"
        f" {pct(max(max(abs(s[k][i] - later['seed_stability'][0][k][i]) for s in later['seed_stability']) for k in ('b1_count_interval', 'b1_value_interval', 'km_7_day_count_interval') for i in (0, 1)), 4)}.",
        "",
        "## Tests",
        "",
        f"`{pytest_summary(pytest_file.read_text(encoding='utf-8'))}`" if pytest_file.exists()
        else "Pending: `ai-workflow/evidence/sprint-2/pytest.txt` has not been written yet.",
        "",
        f"## Correction log: {len(entries)} Sprint 2 entries",
        "",
        *[f"- {e['phase']} · {e['title']} ({e['origin']}; {e['caught_by']})" for e in entries],
        "",
        "## Sprint 2 commits on main (first parent)",
        "",
        *[f"- `{sha}` {subject}" for sha, subject in sprint_commits()],
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    text = OUT.read_text(encoding="utf-8")
    head = text.split(MARKER, 1)[0].rstrip() + "\n\n"
    write_text(OUT, head + render_generated())
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
