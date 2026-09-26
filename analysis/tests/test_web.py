"""Site guards: the /metrics copy, the footer attribution, and labels read from the contract."""

from __future__ import annotations

import json
import re

from funnel.common import KAGGLE_URL, REPO_ROOT
from funnel.ingest import REES46_URL
from funnel.naming_guard import METRICS_MD, WEB_METRICS_MD

WEB = REPO_ROOT / "web"


def test_metrics_page_copy_equals_committed_contract():
    assert WEB_METRICS_MD.exists(), "run npm --prefix web run build (sync-content) to create web/content/metrics.md"
    assert WEB_METRICS_MD.read_bytes() == METRICS_MD.read_bytes()


def test_footer_carries_both_attribution_links():
    story = json.loads((WEB / "public" / "data" / "data_story.json").read_text(encoding="utf-8"))
    assert story["source"]["kaggle_url"] == KAGGLE_URL
    assert story["source"]["rees46_url"] == REES46_URL
    layout = (WEB / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert "href={source.kaggle_url}" in layout and "Kaggle dataset page" in layout
    assert "href={source.rees46_url}" in layout and "REES46 Marketing Platform" in layout
    assert "An analytics case study built with Claude Code by Eddy Mkwambe" in layout


def test_section_6_display_labels_are_read_from_metrics_index_not_typed():
    table = re.search(r"^## 6\..*?(?=^## )", METRICS_MD.read_text(encoding="utf-8"), re.MULTILINE | re.DOTALL).group(0)
    labels = [cells[2].strip() for line in table.splitlines()
              if len(cells := line.strip().strip("|").split("|")) == 3 and "%" in cells[2]]
    assert labels, "expected rate display labels in Section 6"
    for page in (WEB / "app").rglob("*.tsx"):
        text = page.read_text(encoding="utf-8")
        for label in labels:
            assert label not in text, f"{page.relative_to(REPO_ROOT)} types the label {label!r}; read it from metrics_index.json"
