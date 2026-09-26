"""Detect wording the metric contract prohibits (docs/metrics.md Section 1).

A file fails if it contains:

- a term from Section 1 rule 3, which states an inferred loss;
- the word "carts" (rule 1: cart events are not carts), which also covers
  "unique carts".

Scope: committable files under web/ (including the JSON exports in
web/public/data/) and docs/. In docs/metrics.md, Section 1 itself is excluded,
because it quotes the prohibited terms.
"""

from __future__ import annotations

import re
from pathlib import Path

from funnel.common import REPO_ROOT
from funnel.row_guard import committable_files

NAMING_GUARDED_DIRS = ("web", "docs")
METRICS_MD = REPO_ROOT / "docs" / "metrics.md"

# Section 1 rule 3, in the order the contract lists them.
PROHIBITED_TERMS = (
    "abandoned", "abandonment", "lost revenue", "lost sales", "recoverable revenue",
    "leak", "drop-off", "lost cart", "lost carts",
)
# Rule 1 ("never say carts"): the whole word "carts" anywhere outside Section 1,
# which also covers "unique carts".
CART_COUNT_LABELS = ("carts", "unique carts")

_PATTERNS = {
    term: re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", re.IGNORECASE)
    for term in (*PROHIBITED_TERMS, *CART_COUNT_LABELS)
}
_SECTION_1 = re.compile(r"^## 1\. Naming rules\b.*?(?=^## )", re.MULTILINE | re.DOTALL)


def strip_naming_rules_section(text: str) -> str:
    """Remove metrics.md Section 1, up to the next level-2 heading."""
    stripped, n = _SECTION_1.subn("", text, count=1)
    if n != 1:
        raise ValueError("metrics.md Section 1 ('## 1. Naming rules') not found")
    return stripped


def naming_findings(text: str) -> list[str]:
    return [term for term, pattern in _PATTERNS.items() if pattern.search(text)]


def scan(paths: list[Path], metrics_md: Path | None = None) -> dict[str, list[str]]:
    metrics_md = metrics_md or METRICS_MD
    hits: dict[str, list[str]] = {}
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        if path.resolve() == metrics_md.resolve():
            text = strip_naming_rules_section(text)
        found = naming_findings(text)
        if found:
            hits[path.as_posix()] = found
    return hits


def guarded_files() -> list[Path]:
    return committable_files(NAMING_GUARDED_DIRS)
