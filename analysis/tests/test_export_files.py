"""The committed JSON exports: manifests, current dataset, and the reconciliation chain."""

from __future__ import annotations

import json

import pytest

from funnel import common
from funnel.export import WEB_DATA

EXPORTS = ("kpis.json", "funnel_category.json", "purchase_paths.json", "data_quality.json",
           "metrics_index.json", "data_story.json", "workflow.json", "investigation_revenue_gap.json")
MANIFEST_KEYS = {"git_commit_sha", "git_worktree_dirty", "dataset_sha256", "generated_at_utc", "script"}


@pytest.mark.parametrize("name", EXPORTS)
def test_committed_export_has_manifest_and_current_dataset(name):
    path = WEB_DATA / name
    assert path.exists(), f"{path} missing; run python -m funnel.export"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert MANIFEST_KEYS <= set(payload["manifest"])
    assert payload["manifest"]["dataset_sha256"] == common.recorded_dataset_sha256()
    assert payload["manifest"]["script"] == "funnel.export"
    assert payload["pipeline_build"]["test_coverage"]["tests_expected_not_run"] == []


def test_data_story_reconciliation_chain_sums():
    story = json.loads((WEB_DATA / "data_story.json").read_text(encoding="utf-8"))
    r = story["reconciliation"]
    assert r["raw_rows"] - r["exact_duplicate_rows_removed"] == r["deduplicated_events"]
    assert (r["deduplicated_events"] - r["null_session_events_excluded"]
            - r["events_in_multi_user_sessions_excluded"]) == r["valid_session_events"]
    assert r["orders"] <= r["valid_sessions"]
    fields = {f for item in story["limitations"] for f in item["supporting_fields"]}
    assert fields, "every limitation cites exported fields"


@pytest.mark.parametrize("level", ["category_top", "category_code"])
def test_category_rows_are_in_a_fully_determined_order(level):
    """Sprint 2 Step 4: rows tied on carted value (for example at 0) must not reorder between runs."""
    rows = json.loads((WEB_DATA / "funnel_category.json").read_text(encoding="utf-8"))[level]
    keys = [(-float(r["carted_value_with_no_observed_purchase"]), r["category_key"]) for r in rows]
    assert keys == sorted(keys)
    assert len({r["category_key"] for r in rows}) == len(rows)


def test_revenue_gap_export_reconciles_and_was_independently_verified():
    """Analysis A: each dimension sums to the revenue difference, and R2 matched before export."""
    from decimal import Decimal

    gap = json.loads((WEB_DATA / "investigation_revenue_gap.json").read_text(encoding="utf-8"))
    totals = gap["totals"]
    difference = Decimal(str(totals["revenue_difference"]))
    assert Decimal(str(totals["revenue"])) - Decimal(str(totals["revenue_repeat_collapsed"])) == difference
    for name, cells in gap["dimensions"].items():
        assert sum(Decimal(str(c["repeat_purchase_value"])) for c in cells) == difference, name
        assert sum(c["repeat_purchase_events"] for c in cells) == totals["repeat_purchase_events"], name
    assert gap["secondary_cases"]["cart_no_view_reconciliation"]["remainder"] == 0
    assert gap["independent_verification"]["all_match"] is True


def test_exports_share_one_clean_manifest():
    manifests = [json.loads((WEB_DATA / name).read_text(encoding="utf-8"))["manifest"] for name in EXPORTS]
    assert all(m == manifests[0] for m in manifests), "all exports come from one run"
    assert manifests[0]["git_worktree_dirty"] is False
