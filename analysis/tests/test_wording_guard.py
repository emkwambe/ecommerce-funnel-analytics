"""Wording guard (metrics.md Changes 2026-09-26, Sprint 2 investigations; owner decision H3-D3).

The phrase list stays in this test, not in the docs, so the contract never has to quote it. It applies to the
/investigations pages and the exported files they render from, the /metrics page copy, docs/metrics.md outside
Section 1, and README.md. Every surface must find at least one file; the investigations surface is skipped, with
the reason stated, only while no investigations page exists.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from funnel.common import REPO_ROOT
from funnel.naming_guard import METRICS_MD, WEB_METRICS_MD, strip_naming_rules_section

# Wording that states cause or loss, or presents a later purchase as a reversal of the earlier outcome.
# Each entry is a regex matched case-insensitively at word boundaries.
CAUSE = (r"caused", r"causes", r"causing", r"led to", r"leads to", r"lead to", r"drove", r"drives",
         r"driven by", r"thanks to", r"as a result of", r"resulted in", r"results in", r"because of the cart")
LOSS = (r"lost", r"losing", r"revenue loss", r"sales loss", r"loss of", r"leak\w*", r"abandon\w*",
        r"missed (?:revenue|sales|purchases?)", r"left on the table")
REVERSAL = (r"recover\w*", r"regain\w*", r"won back", r"win back", r"winback", r"rescued", r"reclaimed",
            r"saved (?:revenue|sales|carts?|value)")
# Added in Sprint 2 Step 4 by the owner (act-and-notify under H3-D3): causal and proof wording.
# "prove" is listed by word form (owner decision under H3-D3): prove\w* also matched "provenance".
CAUSE_AND_PROOF = (r"due to", r"impact\w*", r"effect of", r"prove|proves|proved|proven|proving", r"demonstrat\w*")
PHRASES = CAUSE + LOSS + REVERSAL + CAUSE_AND_PROOF
_PATTERN = re.compile(r"\b(?:" + "|".join(PHRASES) + r")\b", re.IGNORECASE)

WEB_DATA = REPO_ROOT / "web" / "public" / "data"
INVESTIGATIONS = REPO_ROOT / "web" / "app" / "investigations"
PAGE_SUFFIXES = {".tsx", ".ts", ".md", ".mdx"}
README = REPO_ROOT / "README.md"


def wording_findings(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in _PATTERN.finditer(text)})


def _read(path: Path, strip_section_1: bool = False) -> str:
    text = path.read_text(encoding="utf-8")
    return strip_naming_rules_section(text) if strip_section_1 else text


def investigation_pages() -> list[Path]:
    if not INVESTIGATIONS.exists():
        return []
    return sorted(p for p in INVESTIGATIONS.rglob("*") if p.is_file() and p.suffix in PAGE_SUFFIXES)


def investigation_render_sources() -> list[Path]:
    """Exported files the investigations pages render from: their own exports and the metric labels."""
    return sorted(WEB_DATA.glob("investigation*.json")) + [WEB_DATA / "metrics_index.json"]


SURFACES = {
    "docs/metrics.md (outside Section 1)": lambda: [(METRICS_MD, True)],
    "/metrics page copy (outside Section 1)": lambda: [(WEB_METRICS_MD, True)],
    "README.md": lambda: [(README, False)],
    "/investigations pages and their render sources": lambda: (
        [(p, False) for p in investigation_pages()] + [(p, False) for p in investigation_render_sources()]),
}


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_surface_carries_no_cause_loss_or_reversal_wording(surface: str):
    if surface.startswith("/investigations") and not investigation_pages():
        pytest.skip("no /investigations page exists yet (web/app/investigations/); the surface is guarded once one does")
    files = SURFACES[surface]()
    existing = [(p, strip) for p, strip in files if p.is_file()]
    assert existing, f"{surface}: no guarded file found; the guard would pass on nothing"
    assert len(existing) == len(files), f"{surface}: missing files {[str(p) for p, _ in files if not p.is_file()]}"
    hits = {p.relative_to(REPO_ROOT).as_posix(): found
            for p, strip in existing if (found := wording_findings(_read(p, strip)))}
    assert not hits, f"wording guard: {hits}"


def test_guard_catches_each_phrase_family_and_ignores_legitimate_wording():
    assert wording_findings("The cart caused the purchase.") == ["caused"]
    assert wording_findings("value recovered in a later session") == ["recovered"]
    assert wording_findings("Revenue loss from carts") == ["revenue loss"]
    assert wording_findings("the page must not say it was won back") == ["won back"]
    # Legitimate wording: a bare "because", "loss" in "cause or loss", "effect", "attribution"; and words that a
    # wider "prove" pattern would catch, so any future widening fails here.
    assert wording_findings("No wording of cause or loss. Effect on published numbers: none, because of D1. "
                            "Attribution links. Each export carries a provenance manifest. "
                            "Improve the page. The owner will approve the entry.") == []


@pytest.mark.parametrize(("sentence", "expected"), [
    ("Purchases rose due to the cart.", "due to"),
    ("The impact on revenue was large.", "impact"),
    ("Carts impacted later purchases.", "impacted"),
    ("This is the effect of the cart.", "effect of"),
    ("The data prove it.", "prove"),
    ("The data proves it.", "proves"),
    ("It was proven.", "proven"),
    ("The share proved it.", "proved"),
    ("Proving intent is not possible.", "proving"),
    ("The share demonstrates intent.", "demonstrates"),
    ("A clear demonstration of intent.", "demonstration"),
])
def test_guard_catches_each_cause_and_proof_term(sentence: str, expected: str):
    """One negative test per term added in Sprint 2 Step 4."""
    assert expected in wording_findings(sentence)


def test_guard_applies_to_section_outside_1_but_not_inside():
    text = METRICS_MD.read_text(encoding="utf-8")
    outside = text.replace("## 3. Session rules", "The later purchase was recovered.\n\n## 3. Session rules", 1)
    assert outside != text, "injection outside Section 1 did not change the text"
    assert "recovered" in wording_findings(strip_naming_rules_section(outside))
    inside = text.replace("## 2. Event rules", "Never say recovered.\n\n## 2. Event rules", 1)
    assert inside != text, "injection inside Section 1 did not change the text"
    assert "recovered" in inside
    assert wording_findings(strip_naming_rules_section(inside)) == []
