"""The Sprint 2 verification file: the owner decisions stay as written; the evidence part is generated."""

from __future__ import annotations

from funnel import verification_sprint2 as v2


def test_verification_file_keeps_the_owner_decisions_and_one_marker():
    text = v2.OUT.read_text(encoding="utf-8")
    assert text.count(v2.MARKER) == 1
    head = text.split(v2.MARKER, 1)[0]
    assert "## Owner decisions" in head and "| H4 |" in head and "| H8 |" in head


def test_generated_part_renders_from_committed_evidence(tmp_path, monkeypatch):
    out = tmp_path / "sprint-2-verification.md"
    out.write_text("# Sprint 2 verification\n\n## Owner decisions\n\nkept as written\n\n" + v2.MARKER + " old -->\nstale\n",
                   encoding="utf-8")
    monkeypatch.setattr(v2, "OUT", out)
    v2.main()
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Sprint 2 verification\n\n## Owner decisions\n\nkept as written\n\n")
    assert "stale" not in text and text.count(v2.MARKER) == 1
    for heading in ("## Full dbt builds", "## Independent verification", "## Analysis A", "## Analysis B",
                    "### Seed-stability check", "## Correction log", "## Sprint 2 commits"):
        assert heading in text, heading
