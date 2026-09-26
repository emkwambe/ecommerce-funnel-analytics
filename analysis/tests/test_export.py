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
    assert linked["D1"] == []
    # Sprint 2 (Changes 2026-09-26, Sections 4, 7, 10): the revenue-difference entry is D4's first link.
    sprint2 = next(c["title"] for c in entries if "Sprint 2 investigations" in c["title"])
    assert linked["D4"] == [sprint2]


def test_correction_log_titles_safe_for_export():
    """Any log entry whose title would fail the naming guard must carry a Public title that passes it."""
    from funnel.export import CORRECTION_LOG, ENTRY_HEADING
    from funnel.naming_guard import naming_findings

    text = CORRECTION_LOG.read_text(encoding="utf-8")
    headings = list(ENTRY_HEADING.finditer(text))
    assert headings
    for i, h in enumerate(headings):
        body = text[h.end(): headings[i + 1].start() if i + 1 < len(headings) else len(text)]
        public = re.search(r"^- \*\*Public title:\*\* (.+)$", body, re.MULTILINE)
        if naming_findings(h.group(3)):
            assert public, f"entry {h.group(3)!r} needs a '- **Public title:**' line for the site"
        if public:
            assert naming_findings(public.group(1)) == [], public.group(1)


def test_export_uses_public_title_when_present():
    from funnel.export import parse_correction_log

    log = (
        "**2026-01-01 · Sprint 9 · Original title**\n"
        "- **Origin:** Claude Code\n- **How it was caught:** the pytest commit gate\n"
        "- **Public title:** Title for the site\n\n"
        "**2026-01-02 · Sprint 9 · Plain title**\n"
        "- **Origin:** Claude Chat\n- **How it was caught:** human review\n"
    )
    titles = [e["title"] for e in parse_correction_log(log)["entries"]]
    assert titles == ["Title for the site", "Plain title"]


def test_every_correction_log_entry_is_classified():
    from funnel.export import CORRECTION_LOG, parse_correction_log

    log = parse_correction_log(CORRECTION_LOG.read_text(encoding="utf-8"))
    assert "Other" not in log["by_caught"], [e["title"] for e in log["entries"] if e["caught_by"] == "Other"]
    assert "Other" not in log["by_origin"]


def test_caught_categories_are_the_trio_template_categories():
    """v1.1.2 (owner decision): "how caught" uses exactly the trio correction-log template's categories, and an
    entry caught by CI (the README link error in PR #7) is classified as CI."""
    from funnel.export import CAUGHT_CATEGORIES, CAUGHT_RULES, CORRECTION_LOG, caught_category, parse_correction_log

    assert CAUGHT_CATEGORIES == ("Local test", "CI", "Copilot review", "Human review", "Smoke",
                                 "Executor self-review", "Planner review")
    assert {label for label, _ in CAUGHT_RULES} == set(CAUGHT_CATEGORIES)
    log = parse_correction_log(CORRECTION_LOG.read_text(encoding="utf-8"))
    assert set(log["by_caught"]) <= set(CAUGHT_CATEGORIES)
    by_title = {e["title"]: e["caught_by"] for e in log["entries"]}
    assert by_title["README linked to a production page before it was deployed"] == "CI"
    assert caught_category("CI `docs-checks` (lychee) on PR #7") == "CI"
    assert caught_category("the pytest commit gate (1 failed)") == "Local test"
    assert caught_category("human review by the project owner") == "Human review"
    assert caught_category("Claude Code's harness stopped the run; the human reviewed it") == "Executor self-review"


def test_metrics_index_maps_legend_labels_to_full_labels(metrics_text):
    """Changes 2026-09-26 (third entry): chart legends use short labels; tables and tooltips use the full ones."""
    index = parse_metrics_index(metrics_text)
    # The third entry's '(legend label: "...")' format; numbered Sprint 2 items are checked below.
    legend = {e["short_label"]: e["display_label"] for e in index if e["short_label"] and "_item_" not in e["key"]}
    items = {e["key"]: (e["short_label"], e["display_label"]) for e in index if "_item_" in e["key"]}
    assert items["2026-09-26_item_9"][0] == "Purchased later by the same user, 7 days (%)"
    assert items["2026-09-26_item_9"][1].startswith("Carted products with no observed purchase in the session")
    assert set(items) >= {f"2026-09-26_item_{n}" for n in (1, 2, 4, 9, 10, 12, 13)}
    assert legend == {
        "Purchase of a carted product":
            "Sessions with an observed purchase of a product with an observed same-session cart event",
        "Purchases only of products not carted in the session":
            "Sessions with observed purchases only of products with no observed same-session cart event",
    }
    names = {e["name"] for e in index}
    assert "Sessions with an observed cart event and an observed purchase, none of a carted product" in names
    assert all(e["definition"] for e in index)
