"""ai-workflow/STATE.md generator (trio-sprint-workflow v2.4.0 state sync): the git-free parts, offline."""

from __future__ import annotations

import re

from funnel import state


def test_mode_and_tier_are_declared_in_claude_md():
    assert state.mode_and_tier() == ("Transparent", "Governed")


def test_open_uncertainties_exclude_resolved_items():
    items = state.open_uncertainties()
    ids = [i.split(":")[0] for i in items]
    assert "U3" not in ids  # resolved by owner decision H4
    assert {"U1", "U2"} <= set(ids)


def test_recent_decisions_come_from_the_owner_decision_tables():
    rows = state.recent_decisions()
    assert 1 <= len(rows) <= 5
    assert all(r[3].startswith("ai-workflow/sprint-") for r in rows)


def test_one_line_trims_markup_and_length():
    assert state._one_line("**Bold** `code`. Second sentence.") == "Bold code."
    assert len(state._one_line("x" * 500, 50)) == 50


def test_one_line_keeps_colons_and_semicolons():
    """First STATE.md draft cut 'Add "Mode: Transparent" ...' at the colon; only sentence ends split."""
    assert state._one_line('Add "Mode: Transparent" to CLAUDE.md. More.') == 'Add "Mode: Transparent" to CLAUDE.md.'
    assert state._one_line("On the owner's instruction: deploy; smoke. Then tag.") == \
        "On the owner's instruction: deploy; smoke."


def test_uncertainty_lines_are_whole():
    for item in state.open_uncertainties():
        assert not item.rstrip(")").endswith(":"), item
        # Accepted limitations (H5) stay listed, under their own status, never shown as "open".
        assert re.search(r"\((material|critical); (open|accepted limitation)\)$", item), item


def test_open_prs_become_waiting_rows():
    rows = state.waiting_from_open_prs([{"number": 14, "title": "Sprint 3 Step 0", "url": "https://x/pull/14"}])
    assert rows == ["H8|Merge PR #14 (Sprint 3 Step 0)|https://x/pull/14"]


def test_stale_snapshot_is_reported_only_for_prs_no_longer_open():
    snapshot = ("## Waiting on the owner\n| H | Question | Link |\n|---|---|---|\n"
                "| H8 | Merge PR #13 (records) | https://x/13 |\n| H8 | Merge PR #14 | https://x/14 |\n\n## Open")
    found = state.snapshot_discrepancies(snapshot, {13: "MERGED", 14: "OPEN"})
    assert len(found) == 1 and "PR #13" in found[0] and "MERGED" in found[0]


def test_print_mode_writes_nothing(tmp_path, monkeypatch, capsys):
    """trio v2.4.1 §2a: the live state is printed, never written or committed."""
    out = tmp_path / "STATE.md"
    out.write_text("committed snapshot\n", encoding="utf-8")
    monkeypatch.setattr(state, "OUT", out)
    monkeypatch.setattr(state, "live_inputs", lambda now, w, nxt, d: ("now", [], "next", []))
    monkeypatch.setattr(state, "live_release", lambda: "https://site at v9 (abc)")
    monkeypatch.setattr(state, "repo_line", lambda: "Last merged: PR #1")
    state.main(["--print"])
    assert out.read_text(encoding="utf-8") == "committed snapshot\n"
    printed = capsys.readouterr().out
    assert "live state" in printed and "nothing was written or committed" in printed


def test_writing_the_snapshot_still_needs_now_and_next(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(state, "OUT", tmp_path / "STATE.md")
    with pytest.raises(SystemExit, match="required when writing"):
        state.main(["--now", "x"])


def test_waiting_argument_needs_three_parts(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(state, "OUT", tmp_path / "STATE.md")
    with pytest.raises(SystemExit, match="H\\|question\\|link"):
        state.main(["--now", "x", "--next", "y", "--waiting", "H8 merge"])
