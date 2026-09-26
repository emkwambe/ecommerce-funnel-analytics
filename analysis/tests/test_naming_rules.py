"""Naming rules (docs/metrics.md Section 1): committed wording passes; injected terms are caught."""

from __future__ import annotations

import json
import re

import pytest

from funnel.common import DOCS_DIR, REPO_ROOT
from funnel.naming_guard import (
    CART_COUNT_LABELS,
    METRICS_MD,
    PROHIBITED_TERMS,
    guarded_files,
    naming_findings,
    scan,
    strip_naming_rules_section,
)

ALL_TERMS = (*PROHIBITED_TERMS, *CART_COUNT_LABELS)


def test_committable_web_docs_and_exports_follow_naming_rules():
    files = guarded_files()
    assert METRICS_MD in files, "docs/metrics.md must be in scope"
    assert scan(files) == {}


def test_guard_list_matches_contract_rule_3():
    section_1 = METRICS_MD.read_text(encoding="utf-8")
    rule_3 = next(line for line in section_1.splitlines() if line.startswith("3. **No inferred loss.**"))
    listed = re.findall(r'"([^"]+)"', rule_3.split(" as a statement")[0])
    assert tuple(listed) == PROHIBITED_TERMS


@pytest.mark.parametrize("term", ALL_TERMS)
def test_injected_term_in_a_docs_copy_is_caught(tmp_path, term):
    copy = tmp_path / "data-profile.md"
    original = (DOCS_DIR / "data-profile.md").read_text(encoding="utf-8")
    assert naming_findings(original) == []
    copy.write_text(original + f"\nSessions show {term.upper()} here.\n", encoding="utf-8")
    assert term in scan([copy])[copy.as_posix()]


@pytest.mark.parametrize("term", ALL_TERMS)
def test_injected_term_in_metrics_md_outside_section_1_is_caught(tmp_path, term):
    copy = tmp_path / "metrics.md"
    text = METRICS_MD.read_text(encoding="utf-8")
    # Inserted before the Section 3 heading, so it lands in the body of Section 2.
    injected = text.replace("## 3. Session rules", f"The {term} figure.\n\n## 3. Session rules", 1)
    assert injected != text
    copy.write_text(injected, encoding="utf-8")
    assert term in scan([copy], metrics_md=copy)[copy.as_posix()]


def test_terms_inside_metrics_md_section_1_are_allowed(tmp_path):
    copy = tmp_path / "metrics.md"
    copy.write_text(METRICS_MD.read_text(encoding="utf-8"), encoding="utf-8")
    assert scan([copy], metrics_md=copy) == {}
    # The same text scanned as an ordinary doc fails, so the exclusion is doing the work.
    assert scan([copy], metrics_md=tmp_path / "other.md")


@pytest.mark.parametrize("term", ALL_TERMS)
def test_injected_term_in_a_json_export_is_caught(tmp_path, term):
    export = tmp_path / "web" / "public" / "data" / "funnel_category.json"
    export.parent.mkdir(parents=True)
    export.write_text(json.dumps({"rows": [{"label": term.title(), "value": 1}]}), encoding="utf-8")
    assert term in scan([export])[export.as_posix()]


@pytest.mark.parametrize("text", [
    "Sessions with an observed cart event",
    "carted value with no observed purchase in this session",
    "observed cart events; cart-session purchase rate",
])
def test_contract_labels_pass(text):
    assert naming_findings(text) == []


def test_missing_section_1_halts():
    with pytest.raises(ValueError):
        strip_naming_rules_section("# Metric Definitions\n\n## 2. Event rules\n")


def test_scope_is_web_and_docs():
    for path in guarded_files():
        assert path.relative_to(REPO_ROOT).parts[0] in ("web", "docs")
