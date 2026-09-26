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


def test_revenue_gap_export_shows_every_defined_group_with_contract_labels():
    """Empty groups (for example "Same second" after D1) are exported as zero rows, labeled as in the
    Changes entry."""
    from funnel.export import A_DEFINED_GROUPS
    from funnel.naming_guard import METRICS_MD

    contract = METRICS_MD.read_text(encoding="utf-8")
    gap = json.loads((WEB_DATA / "investigation_revenue_gap.json").read_text(encoding="utf-8"))
    for name, defined in A_DEFINED_GROUPS.items():
        assert [c["group_key"] for c in gap["dimensions"][name]] == [k for k, _, _ in defined], name
        if name != "time_by_price":  # two-way labels join two contract labels
            for cell in gap["dimensions"][name]:
                assert f'"{cell["group_label"]}"' in contract, cell["group_label"]


def test_revenue_gap_secondary_cases_match_sprint0_and_sprint1_on_their_bases():
    """Sprint 2 Step 4 item 2: the secondary-case counts match the Sprint 0 profile (raw basis) and the
    Sprint 1 data-quality export (contract basis)."""
    profile = json.loads((common.EVIDENCE_DIR / "profile.json").read_text(encoding="utf-8"))
    dq = {r["metric_key"]: r for r in json.loads((WEB_DATA / "data_quality.json").read_text(encoding="utf-8"))["rows"]}
    gap = json.loads((WEB_DATA / "investigation_revenue_gap.json").read_text(encoding="utf-8"))
    duplicates = gap["secondary_cases"]["exact_duplicate_rows"]
    removed = sum(d["rows_removed"] for d in duplicates)
    assert removed == dq["exact_duplicate_rows_removed"]["value"]
    assert removed == profile["duplicates"]["exact_duplicate_rows"]["surplus_rows"]
    cart = gap["secondary_cases"]["cart_no_view_reconciliation"]
    assert cart["raw_basis_count"] == profile["ordering_anomalies"]["cart_events_with_no_view_at_or_before_in_session"]
    assert cart["contract_basis_count"] == dq["cart_events_with_no_view_at_or_before"]["value"]
    assert (cart["in_null_session_events"] + cart["in_multi_user_sessions"] + cart["removed_as_exact_duplicates"]
            + cart["contract_basis_count"]) == cart["raw_basis_count"]


def test_repeat_purchase_events_reconcile_with_the_sprint0_raw_basis():
    """Method record A, robustness plan: the Sprint 0 raw-basis surplus purchase events exceed the contract
    basis by exactly the exact-duplicate purchase rows removed by D1 (observed; other components are zero)."""
    profile = json.loads((common.EVIDENCE_DIR / "profile.json").read_text(encoding="utf-8"))
    gap = json.loads((WEB_DATA / "investigation_revenue_gap.json").read_text(encoding="utf-8"))
    raw_surplus = profile["order_reconstruction"]["surplus_purchase_events_in_repeated_pairs"]
    purchase_rows_removed = sum(d["rows_removed"] for d in gap["secondary_cases"]["exact_duplicate_rows"]
                                if d["event_type"] == "purchase")
    assert raw_surplus - gap["totals"]["repeat_purchase_events"] == purchase_rows_removed


def test_exports_share_one_clean_manifest():
    manifests = [json.loads((WEB_DATA / name).read_text(encoding="utf-8"))["manifest"] for name in EXPORTS]
    assert all(m == manifests[0] for m in manifests), "all exports come from one run"
    assert manifests[0]["git_worktree_dirty"] is False
