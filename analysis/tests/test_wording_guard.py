"""Wording guard (metrics.md Changes 2026-09-26, Sprint 2 investigations; owner decision H3-D3).

The phrase list stays in this test, not in the docs, so the contract never has to quote it. It applies to the
/investigations pages, the /metrics page copy, docs/metrics.md outside Section 1, and README.md.
"""

from __future__ import annotations

import re

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
PHRASES = CAUSE + LOSS + REVERSAL
_PATTERN = re.compile(r"\b(?:" + "|".join(PHRASES) + r")\b", re.IGNORECASE)

INVESTIGATIONS = REPO_ROOT / "web" / "app" / "investigations"
README = REPO_ROOT / "README.md"


def wording_findings(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in _PATTERN.finditer(text)})


def guarded_texts() -> dict[str, str]:
    texts = {
        "docs/metrics.md (outside Section 1)": strip_naming_rules_section(METRICS_MD.read_text(encoding="utf-8")),
        "web/content/metrics.md (outside Section 1)": strip_naming_rules_section(
            WEB_METRICS_MD.read_text(encoding="utf-8")),
        "README.md": README.read_text(encoding="utf-8"),
    }
    if INVESTIGATIONS.exists():
        for page in sorted(INVESTIGATIONS.rglob("*")):
            if page.is_file() and page.suffix in {".tsx", ".ts", ".md", ".mdx"}:
                texts[page.relative_to(REPO_ROOT).as_posix()] = page.read_text(encoding="utf-8")
    return texts


def test_guarded_texts_carry_no_cause_loss_or_reversal_wording():
    hits = {name: found for name, text in guarded_texts().items() if (found := wording_findings(text))}
    assert not hits, f"wording guard: {hits}"


def test_guard_catches_each_phrase_family_and_ignores_legitimate_wording():
    assert wording_findings("The cart caused the purchase.") == ["caused"]
    assert wording_findings("value recovered in a later session") == ["recovered"]
    assert wording_findings("Revenue loss from carts") == ["revenue loss"]
    assert wording_findings("the page must not say it was won back") == ["won back"]
    # Legitimate contract wording: a bare "because", "loss" in "cause or loss", "effect", "attribution".
    assert wording_findings("No wording of cause or loss. Effect on published numbers: none, because of D1. "
                            "Attribution links.") == []


def test_guard_applies_to_section_outside_1_but_not_inside():
    text = METRICS_MD.read_text(encoding="utf-8")
    injected = text.replace("## 3. Session rules", "The later purchase was recovered.\n\n## 3. Session rules", 1)
    assert "recovered" in wording_findings(strip_naming_rules_section(injected))
    inside = text.replace("## 2. Event rules", "Never say recovered.\n\n## 2. Event rules", 1)
    assert wording_findings(strip_naming_rules_section(inside)) == []
