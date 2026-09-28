"""Closing report and /questions export (owner closing decision, 2026-09-27; funnel.closing)."""

from __future__ import annotations

import copy
import json
import re

import pytest

from funnel import closing as c
from funnel.common import REPO_ROOT, recorded_dataset_sha256

APP = REPO_ROOT / "web" / "app"
LF, CRLF = chr(10), chr(13) + chr(10)


@pytest.fixture(scope="module")
def inputs():
    return c.load_exports(), c.CONTENT.read_text(encoding="utf-8"), c.TEMPLATE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def committed():
    return json.loads(c.OUT.read_text(encoding="utf-8"))


def test_committed_report_and_export_equal_a_fresh_build(inputs, committed):
    report, export = c.build(*inputs)
    # Line endings are normalized: git's autocrlf may check the committed report out with CRLF on Windows.
    on_disk = c.REPORT.read_bytes().decode("utf-8").replace(CRLF, LF)
    assert on_disk == report.replace(CRLF, LF), "docs/closing-report.md is stale; run python -m funnel.closing"
    assert {k: v for k, v in committed.items() if k != "manifest"} == json.loads(json.dumps(export))


def test_manifest_names_the_script_and_the_current_dataset(committed):
    # Like funnel.export's outputs, closing.json is regenerated from a clean tree in its own commit; the flag is
    # recorded as found (a gate on it would fail every commit that changes the generator's inputs).
    m = committed["manifest"]
    assert m["script"] == "funnel.closing"
    assert m["dataset_sha256"] == recorded_dataset_sha256()
    assert isinstance(m["git_worktree_dirty"], bool)


def test_every_figure_equals_its_export_field(inputs, committed):
    fresh = c.resolve_figures(inputs[0])
    assert committed["figures"] == json.loads(json.dumps(fresh))
    assert {"no_cart_revenue_share", "later_value_share", "revenue_gap", "later_population"} <= set(fresh)


def test_a_figure_that_differs_from_its_export_stops_the_build(inputs):
    exports, content, template = inputs
    changed = copy.deepcopy(exports)
    row = next(r for r in changed["purchase_paths.json"]["rows"] if r["purchase_path"] == c.NO_CART_PATH)
    row["revenue_share"] = 0.49  # the content says 48%
    with pytest.raises(c.ClosingError, match="differs from its export"):
        c.build(changed, content, template)


def test_an_unbound_number_stops_the_build(inputs):
    exports, content, template = inputs
    edited = content.replace("Everything so far is descriptive", "Everything in 12 sessions is descriptive", 1)
    assert edited != content
    with pytest.raises(c.ClosingError, match="not bound"):
        c.build(exports, edited, template)


def test_a_naming_rule_violation_stops_the_build(inputs):
    exports, content, template = inputs
    edited = content.replace("Everything so far is descriptive", "Everything about carts is descriptive", 1)
    with pytest.raises(c.ClosingError, match="naming rules"):
        c.build(exports, edited, template)


def test_groups_and_start_here_follow_the_owner_mapping(committed):
    groups = {g["label"]: g["questions"] for g in committed["groups"]}
    assert groups == {"Product and engineering": [1, 2, 3], "More data": [4, 5, 9], "Better methods": [6, 7],
                      "Only an experiment": [8]}
    assert [q["n"] for q in committed["questions"] if q["start_here"]] == [1]
    assert "what should the team test first?" in committed["question_1"]["lead"]


def test_every_evidence_anchor_exists_on_its_page(committed):
    for q in committed["questions"]:
        href = q["evidence"]["href"]
        if q["evidence"]["external"]:
            assert href.endswith(c.ESCALATION_BRIEF) and (REPO_ROOT / c.ESCALATION_BRIEF).exists()
            continue
        path, _, anchor = href.partition("#")
        page = APP / path.strip("/") / "page.tsx"
        assert page.exists(), href
        if anchor:
            assert f'id="{anchor}"' in page.read_text(encoding="utf-8"), href


def _code(page) -> str:
    """Page source without comments: a comment that names a figure isn't rendered text."""
    source = page.read_text(encoding="utf-8")
    source = re.sub(r"\{/\*.*?\*/\}", "", source, flags=re.DOTALL)
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", source)  # whole-line // comments


def test_pages_render_closing_content_from_the_export_never_typed(committed):
    texts = [f["text"] for f in committed["findings"]] + [committed["question_1"]["text"]]
    texts += [q[k] for q in committed["questions"] for k in ("question", "card_line", "why", "who")]
    rendered = [c.render(t, committed["figures"]) for t in texts]
    for page in APP.rglob("*.tsx"):
        source = _code(page)
        for text in rendered:
            # A long fragment of any closing text, typed into a page, would bypass the export.
            fragment = re.split(r"[\"'&{]", text)[0][:60]
            if len(fragment) >= 30:
                assert fragment not in source, f"{page.relative_to(REPO_ROOT)} types closing text: {fragment!r}"
    for figure in committed["figures"].values():
        for page in (APP / "page.tsx", APP / "questions" / "page.tsx"):
            assert figure["formatted"] not in _code(page), (page, figure["formatted"])


def test_evidence_labels_are_readable_not_raw_paths(committed):
    """Owner decision (v1.1.4): labels like "See the evidence: purchase paths", generated in the export."""
    for q in committed["questions"]:
        label = q["evidence"]["label"]
        assert label.startswith(c.EVIDENCE_PREFIX), label
        assert "/" not in label and "#" not in label, label
    labels = {q["n"]: q["evidence"]["label"] for q in committed["questions"]}
    assert labels[1] == "See the evidence: purchase paths"
    assert labels[2] == "See the evidence: revenue figures investigation"
