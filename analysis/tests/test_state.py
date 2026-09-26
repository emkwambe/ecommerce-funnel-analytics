"""ai-workflow/STATE.md generator (trio-sprint-workflow v2.4.0 state sync): the git-free parts, offline."""

from __future__ import annotations

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
        assert "(material; open" in item or "(critical; open" in item, item


def test_waiting_argument_needs_three_parts(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(state, "OUT", tmp_path / "STATE.md")
    with pytest.raises(SystemExit, match="H\\|question\\|link"):
        state.main(["--now", "x", "--next", "y", "--waiting", "H8 merge"])
