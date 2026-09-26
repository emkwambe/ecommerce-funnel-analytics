"""Owner decision H4 (2026-09-26), item 2: no page or ledger row applies a B value share to the total carted value
with no observed purchase in the session. B's shares describe their scoped populations (carted products from
sessions starting October 1-N, 2019 UTC); the Section 7 total covers all of October.

Two checks, on the claim ledger, the /investigations pages and exports, the README, and the contract and its
/metrics copy:
1. wording: one line (or ledger row) that references a B value share together with the published total;
2. numbers: any guarded text containing a B value share multiplied by the Section 7 total (computed here from
   the committed exports, in the usual money formats).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from funnel.common import REPO_ROOT
from funnel.naming_guard import METRICS_MD, WEB_METRICS_MD, strip_naming_rules_section

WEB_DATA = REPO_ROOT / "web" / "public" / "data"
LEDGER = REPO_ROOT / "ai-workflow" / "claim-ledger.md"
INVESTIGATIONS = REPO_ROOT / "web" / "app" / "investigations"

VALUE_SHARE = re.compile(r"value_share|value share|value-weighted share", re.IGNORECASE)
TOTAL = re.compile(r"funnel_category\.json|carted_value_with_no_observed_purchase"
                   r"|\b(?:total|all|entire|whole|overall)\b[^.|\n]{0,40}\bcarted value", re.IGNORECASE)


def guarded_texts() -> dict[str, str]:
    texts = {
        "ai-workflow/claim-ledger.md": LEDGER.read_text(encoding="utf-8"),
        "README.md": (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        "docs/metrics.md": strip_naming_rules_section(METRICS_MD.read_text(encoding="utf-8")),
        "web/content/metrics.md": strip_naming_rules_section(WEB_METRICS_MD.read_text(encoding="utf-8")),
    }
    for path in sorted(WEB_DATA.glob("investigation*.json")):
        texts[path.relative_to(REPO_ROOT).as_posix()] = path.read_text(encoding="utf-8")
    if INVESTIGATIONS.exists():
        for page in sorted(p for p in INVESTIGATIONS.rglob("*") if p.is_file()):
            texts[page.relative_to(REPO_ROOT).as_posix()] = page.read_text(encoding="utf-8")
    return texts


def wording_findings(text: str) -> list[str]:
    return [line.strip()[:160] for line in text.splitlines() if VALUE_SHARE.search(line) and TOTAL.search(line)]


def extrapolated_amounts() -> list[str]:
    """Each B value share times the Section 7 total, in the formats a page or document would show."""
    later = WEB_DATA / "investigation_later_purchases.json"
    if not later.exists():
        return []
    shares = [r["value_share"] for r in json.loads(later.read_text(encoding="utf-8"))["estimates"]]
    category = json.loads((WEB_DATA / "funnel_category.json").read_text(encoding="utf-8"))["category_top"]
    total = sum(r["carted_value_with_no_observed_purchase"] for r in category)
    amounts = []
    for share in shares:
        x = share * total
        amounts += [f"{x:,.0f}", f"{x:,.2f}", f"{x / 1e6:.1f}M", f"{x / 1e6:.2f}M", f"{x / 1e6:.1f} million",
                    f"{x / 1e6:.2f} million"]
    return amounts


def number_findings(text: str, amounts: list[str]) -> list[str]:
    return [a for a in amounts if re.search(rf"(?<![\d.,]){re.escape(a)}(?![\d])", text)]


def test_no_b_value_share_is_applied_to_the_total_carted_value():
    amounts = extrapolated_amounts()
    hits = {}
    for name, text in guarded_texts().items():
        found = wording_findings(text) + number_findings(text, amounts)
        if found:
            hits[name] = found
    assert not hits, f"B value share applied to the total carted value (owner decision H4, item 2): {hits}"


def test_guard_catches_wording_and_numbers_and_passes_scoped_claims():
    assert wording_findings("| C99 | value share x total carted value = recovered amount |")
    assert wording_findings("value_share applied to funnel_category.json totals")
    assert wording_findings("the value share of all carted value with no observed purchase")
    # A scoped B claim that cites its own population's values is allowed.
    assert not wording_findings("| C8 | value share: followed_value / eligible_value (sessions starting "
                                "October 1-24, 2019 UTC) |")
    assert number_findings("about 14,458,000 of it", ["14,458,000"]) == ["14,458,000"]
    assert number_findings("id 114,458,0001", ["14,458,000"]) == []


def test_guard_scans_the_ledger_and_every_investigation_export():
    names = set(guarded_texts())
    assert "ai-workflow/claim-ledger.md" in names
    assert {p.name for p in WEB_DATA.glob("investigation*.json")} <= {Path(n).name for n in names}
