"""Exploratory code may be committed; its outputs never (owner decision, Sprint 2 Step 4)."""

from __future__ import annotations

import sys

import pytest

from funnel.common import REPO_ROOT
from funnel.row_guard import committable_files

EXPLORE = REPO_ROOT / "analysis" / "explore"


def test_only_python_source_is_committable_under_explore():
    files = committable_files(("analysis/explore",))
    assert files, "analysis/explore/ should hold the exploratory scripts referenced by the search log"
    others = [p.relative_to(REPO_ROOT).as_posix() for p in files if p.suffix != ".py"]
    assert not others, f"exploratory outputs must never be committed: {others}"


def test_every_exploratory_script_declares_its_status():
    for path in EXPLORE.glob("*.py"):
        header = path.read_text(encoding="utf-8")[:600]
        assert "EXPLORATORY AND UNPUBLISHED" in header, path.name
        assert "search-log.md rows" in path.read_text(encoding="utf-8"), path.name


def test_timing_diagnostic_refuses_an_output_path_inside_the_repo():
    sys.path.insert(0, str(EXPLORE))
    try:
        import a_timing_diagnostic as diag
    finally:
        sys.path.remove(str(EXPLORE))
    with pytest.raises(SystemExit, match="inside the repository"):
        diag.output_path(["--out", str(REPO_ROOT / "analysis" / "explore" / "out.json")])
    assert not diag.output_path(["--out", str(REPO_ROOT.parent / "elsewhere.json")]).is_relative_to(REPO_ROOT)
