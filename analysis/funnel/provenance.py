"""Run guards against unrecorded changes (owner decision H4, 2026-09-27).

On 2026-09-27 an unattributed second actor edited the staging models and the metric contract, rebuilt the marts with
dbt directly (outside funnel.build), and ran funnel.rankings on them (ai-workflow/escalations/
2026-09-27-C-rankings-stop-rules.md). These guards make that impossible to do silently:

- require_clean_worktree: funnel.build and funnel.rankings refuse to start while `git status --porcelain` shows any
  tracked change or untracked, non-ignored file, so every run corresponds to a commit;
- marts_fingerprint: a SHA-256 over mart_category_ranking_counts (every row) and a hash sum over
  mart_category_sessions, recorded by funnel.build after a successful gated build;
- gated_build_record: funnel.rankings refuses marts whose fingerprint has no gated build record (clean tree, dbt exit
  code 0, every expected test run) in the current sprint's dbt_build_runs.json.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from funnel.common import CURRENT_EVIDENCE_DIR, git_worktree_dirty

BUILD_RUNS = CURRENT_EVIDENCE_DIR / "dbt_build_runs.json"


def require_clean_worktree(script: str) -> None:
    if git_worktree_dirty():
        sys.exit(f"HALT: {script} refuses to start on a dirty working tree (git status --porcelain is not empty). "
                 "Commit or remove every change first, so the run corresponds to a commit.")


def marts_fingerprint(con, catalog: str | None = None) -> str | None:
    """Fingerprint of the two ranking marts, or None if they don't exist. `catalog` is the attached database name
    (for example "wh"); None means the connection's own database."""
    prefix = f"{catalog}.main_marts" if catalog else "main_marts"
    try:
        counts = con.execute(f"""
            SELECT row_key, category_sessions, category_sessions_with_purchase, CAST(revenue AS VARCHAR),
                   CAST(revenue_collapsed AS VARCHAR)
            FROM {prefix}.mart_category_ranking_counts ORDER BY row_key""").fetchall()
        sessions = con.execute(f"""
            SELECT count(*), sum(hash(category_level, category, user_session, user_id, has_purchase, revenue,
                                      revenue_collapsed, is_long_session, is_most_active_user,
                                      has_missing_code_event))
            FROM {prefix}.mart_category_sessions""").fetchone()
    except Exception as exc:  # noqa: BLE001 - a missing table means there is nothing to fingerprint
        if "does not exist" in str(exc) or "Catalog Error" in str(exc):
            return None
        raise
    return hashlib.sha256(repr((counts, sessions)).encode("utf-8")).hexdigest()


def is_gated(run: dict[str, Any]) -> bool:
    coverage = run.get("test_coverage") or {}
    return (run.get("dbt_exit_code") == 0
            and run.get("manifest", {}).get("git_worktree_dirty") is False
            and run.get("worktree_clean_at_start") is True
            and coverage.get("tests_expected_not_run") == []
            and bool(run.get("marts_fingerprint")))


def gated_build_record(fingerprint: str, runs_path: Path = BUILD_RUNS) -> dict[str, Any] | None:
    """The latest gated build run whose recorded marts fingerprint equals `fingerprint`, or None."""
    if not runs_path.exists():
        return None
    runs = json.loads(runs_path.read_text(encoding="utf-8")).get("runs", [])
    matches = [r for r in runs if is_gated(r) and r.get("marts_fingerprint") == fingerprint]
    return matches[-1] if matches else None


def require_gated_marts(fingerprint: str | None, script: str, runs_path: Path = BUILD_RUNS) -> dict[str, Any]:
    if fingerprint is None:
        sys.exit(f"HALT: {script}: the ranking marts don't exist; run python -m funnel.build first.")
    record = gated_build_record(fingerprint, runs_path)
    if record is None:
        sys.exit(f"HALT: {script} refuses marts with fingerprint {fingerprint[:12]}: no gated build record "
                 f"(clean tree, dbt exit 0, every expected test run) in {runs_path.name} has that fingerprint. "
                 "Rebuild through python -m funnel.build from a clean, committed tree.")
    return record
