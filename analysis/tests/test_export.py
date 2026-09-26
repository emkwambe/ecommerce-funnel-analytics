"""JSON exports: metrics.md parsing and decision links (the written files: test_export_files.py)."""

from __future__ import annotations

import re

import pytest

from funnel.export import DECISIONS, METRICS_MD, _sections, changes_entries, parse_metrics_index


@pytest.fixture(scope="module")
def metrics_text() -> str:
    return METRICS_MD.read_text(encoding="utf-8")


def test_metrics_index_covers_section_6_and_skips_section_1(metrics_text):
    index = parse_metrics_index(metrics_text)
    names = {e["name"] for e in index}
    for metric in ("Sessions", "Session purchase rate", "View-to-cart session rate", "Cart-session purchase rate",
                   "Average order value", "Revenue per session", "Order"):
        assert metric in names, metric
    assert all(e["section"] != "1" for e in index)
    assert all(e["definition"] for e in index)
    labels = {e["name"]: e["display_label"] for e in index}
    assert labels["Session purchase rate"] == "Sessions with an observed purchase (%)"


def test_changes_entries_are_indexed_with_their_sections(metrics_text):
    entries = changes_entries(metrics_text)
    assert len(entries) == len(re.findall(r"^### ", _sections(metrics_text)["Changes"], re.MULTILINE)) >= 2
    assert entries[0]["sections"] == ["6", "9", "10"]
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["date"]) for e in entries)


def test_every_decision_links_to_the_section_that_records_it(metrics_text):
    sections = _sections(metrics_text)
    assert [d[0] for d in DECISIONS] == [f"D{i}" for i in range(1, 11)]
    for did, _, summary, section in DECISIONS:
        heading_and_body = next(h for h in re.findall(r"^## .*$", metrics_text, re.MULTILINE)
                                if h.startswith(f"## {section}."))
        assert re.search(rf"\b{did}\b", heading_and_body + sections[section]), (did, section)
        assert not re.search(r"\d", summary), f"{did} summary must carry no figures"


def test_decisions_link_to_the_changes_entries_that_apply(metrics_text):
    from funnel.export import RELATED_SECTIONS

    entries = changes_entries(metrics_text)
    linked = {did: [c["title"] for c in entries if {section, *RELATED_SECTIONS.get(did, ())} & set(c["sections"])]
              for did, _, _, section in DECISIONS}
    first = entries[0]["title"]  # Sections 6, 9, 10
    assert first in linked["D5"] and first in linked["D7"] and first in linked["D8"]
    assert linked["D1"] == [] and linked["D4"] == []
