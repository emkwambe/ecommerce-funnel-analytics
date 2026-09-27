"""Run guards (owner decision H4, 2026-09-27; funnel.provenance): funnel.build and funnel.rankings refuse a dirty
working tree, and funnel.rankings refuses marts whose fingerprint has no gated build record."""

from __future__ import annotations

import json

import duckdb
import pytest

from funnel import provenance as pv


def _marts(con: duckdb.DuckDBPyConnection, schema: str = "main_marts") -> None:
    con.execute(f"CREATE SCHEMA {schema}")
    con.execute(f"""CREATE TABLE {schema}.mart_category_ranking_counts AS SELECT * FROM (VALUES
        ('C1:category_top:a', 10, 2, 5.00, 5.00), ('C1:category_top:b', 20, 1, 3.00, 2.00))
        AS t(row_key, category_sessions, category_sessions_with_purchase, revenue, revenue_collapsed)""")
    con.execute(f"""CREATE TABLE {schema}.mart_category_sessions AS SELECT * FROM (VALUES
        ('category_top', 'a', 's1', 1, true, 5.00, 5.00, false, false, false),
        ('category_top', 'b', 's2', 2, false, 0.00, 0.00, false, false, true))
        AS t(category_level, category, user_session, user_id, has_purchase, revenue, revenue_collapsed,
             is_long_session, is_most_active_user, has_missing_code_event)""")


def _run(fp: str, **over) -> dict:
    run = {"manifest": {"git_commit_sha": "abc1234", "git_worktree_dirty": False,
                        "generated_at_utc": "2026-09-27T00:00:00+00:00"},
           "dbt_args": ["build"], "dbt_exit_code": 0, "worktree_clean_at_start": True,
           "test_coverage": {"tests_expected_not_run": []}, "marts_fingerprint": fp}
    for key, value in over.items():
        if key == "dirty":
            run["manifest"]["git_worktree_dirty"] = value
        else:
            run[key] = value
    return run


def test_dirty_tree_halts(monkeypatch):
    monkeypatch.setattr(pv, "git_worktree_dirty", lambda: True)
    with pytest.raises(SystemExit, match="dirty working tree"):
        pv.require_clean_worktree("funnel.rankings")
    monkeypatch.setattr(pv, "git_worktree_dirty", lambda: False)
    pv.require_clean_worktree("funnel.rankings")  # no exit


def test_fingerprint_is_stable_and_changes_with_any_row():
    one, two = duckdb.connect(), duckdb.connect()
    _marts(one)
    _marts(two)
    assert pv.marts_fingerprint(one) == pv.marts_fingerprint(two)
    two.execute("UPDATE main_marts.mart_category_sessions SET has_purchase = true WHERE user_session = 's2'")
    assert pv.marts_fingerprint(one) != pv.marts_fingerprint(two)
    one.execute("ATTACH ':memory:' AS wh")
    _marts(one, "wh.main_marts")
    assert pv.marts_fingerprint(one, "wh") == pv.marts_fingerprint(one)
    assert pv.marts_fingerprint(duckdb.connect()) is None  # no marts at all


def test_only_a_gated_record_with_the_same_fingerprint_counts(tmp_path):
    runs = tmp_path / "dbt_build_runs.json"
    cases = {
        "gated": (_run("fp"), True),
        "dirty at the end": (_run("fp", dirty=True), False),
        "no clean-start flag (a record from before the guard)": (_run("fp", worktree_clean_at_start=None), False),
        "dbt failed": (_run("fp", dbt_exit_code=1), False),
        "an expected test did not run": (_run("fp", test_coverage={"tests_expected_not_run": ["t"]}), False),
        "another fingerprint": (_run("other"), False),
    }
    for label, (run, expected) in cases.items():
        runs.write_text(json.dumps({"runs": [run]}), encoding="utf-8")
        assert (pv.gated_build_record("fp", runs) is not None) is expected, label
    assert pv.gated_build_record("fp", tmp_path / "missing.json") is None


def test_require_gated_marts_halts_without_a_record(tmp_path):
    runs = tmp_path / "dbt_build_runs.json"
    runs.write_text(json.dumps({"runs": [_run("fp")]}), encoding="utf-8")
    assert pv.require_gated_marts("fp", "funnel.rankings", runs)["marts_fingerprint"] == "fp"
    with pytest.raises(SystemExit, match="no gated build record"):
        pv.require_gated_marts("unrecorded", "funnel.rankings", runs)
    with pytest.raises(SystemExit, match="don't exist"):
        pv.require_gated_marts(None, "funnel.rankings", runs)


def test_build_and_rankings_refuse_a_dirty_tree_before_doing_anything(monkeypatch):
    from funnel import build, rankings

    monkeypatch.setattr(pv, "git_worktree_dirty", lambda: True)

    def must_not_run(*args, **kwargs):
        raise AssertionError("ran past the dirty-tree guard")

    monkeypatch.setattr(build, "require_available_ram", must_not_run)
    monkeypatch.setattr(build.subprocess, "Popen", must_not_run)
    monkeypatch.setattr(build.sys, "argv", ["funnel.build"])
    with pytest.raises(SystemExit, match="dirty working tree"):
        build.main()
    monkeypatch.setattr(rankings, "require_available_ram", must_not_run)
    with pytest.raises(SystemExit, match="dirty working tree"):
        rankings.main()
