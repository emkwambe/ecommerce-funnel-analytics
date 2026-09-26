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


def test_changes_item_labels_are_read_from_metrics_index_not_typed():
    """Sprint 2: labels defined in numbered Changes-entry items (keys "<date>_item_<n>") are read with metricByKey(),
    never typed into a page."""
    from funnel.export import parse_metrics_index

    labels = [e["display_label"] for e in parse_metrics_index(METRICS_MD.read_text(encoding="utf-8"))
              if "_item_" in e["key"]]
    labels += [e["short_label"] for e in parse_metrics_index(METRICS_MD.read_text(encoding="utf-8"))
               if "_item_" in e["key"] and e["short_label"]]
    assert len(labels) >= 7, "expected the Sprint 2 display labels to be indexed"
    for page in (WEB / "app").rglob("*.tsx"):
        text = page.read_text(encoding="utf-8")
        for label in labels:
            assert label not in text, f"{page.relative_to(REPO_ROOT)} types the label {label!r}; use metricByKey()"


def test_investigation_pages_exist_and_are_linked():
    """Sprint 2 Step 6: both investigation pages exist, the index links them, and the home page links the index."""
    app = WEB / "app"
    for route in ("investigations", "investigations/revenue-figures", "investigations/later-purchases"):
        assert (app / route / "page.tsx").exists(), route
    index = (app / "investigations" / "page.tsx").read_text(encoding="utf-8")
    assert "/investigations/revenue-figures" in index and "/investigations/later-purchases" in index
    home = (app / "page.tsx").read_text(encoding="utf-8")
    where = re.search(r'title="Where to look next">(.*?)</Section>', home, re.DOTALL)
    assert where and 'href="/investigations"' in where.group(1)


def test_evidence_images_within_size_limit():
    """Committed evidence images are compressed WebP of at most 300 KB (full-resolution copies are gitignored)."""
    from funnel.row_guard import committable_files

    images = [p for p in committable_files(("ai-workflow/evidence",))
              if p.suffix.lower() in {".webp", ".png", ".jpg", ".jpeg"}]
    for image in images:
        assert image.suffix.lower() == ".webp", f"{image.relative_to(REPO_ROOT)}: commit WebP only"
        assert image.stat().st_size <= 300 * 1024, f"{image.relative_to(REPO_ROOT)} exceeds 300 KB"


def test_home_findings_are_descriptive_only():
    """v1.0.1: the "What the data shows" findings carry no wording of cause, loss, or priority."""
    page = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    section = re.search(r'title="What the data shows">(.*?)</Section>', page, re.DOTALL)
    assert section, "home page must have the 'What the data shows' section"
    text = re.sub(r"<Sources[^>]*/>", "", section.group(1), flags=re.DOTALL).lower()
    banned = ("because", "due to", "caused", "causes", "drives", "driven", "leads to", "results in", "lost",
              "losing", "leak", "abandon", "priorit", "should", "must", "opportunit", "biggest problem")
    found = [w for w in banned if re.search(rf"\b{re.escape(w)}", text)]
    assert found == [], f"descriptive findings use {found}"
    assert text.count("<p>") == 2, "exactly two findings, each in its own paragraph"
