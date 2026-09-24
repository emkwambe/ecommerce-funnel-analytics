"""Metric-lock guard: the real profile passes; injected leaks are caught."""

from __future__ import annotations

import copy
import json

import pytest

from funnel import profile as pf
from funnel.common import EVIDENCE_DIR
from funnel.metric_guard import find_metric_leaks

PROFILE_JSON = EVIDENCE_DIR / "profile.json"


@pytest.fixture()
def synthetic_profile(con) -> dict:
    p = {"manifest": {"git_commit_sha": "x", "git_worktree_dirty": False, "dataset_sha256": "y",
                      "generated_at_utc": "z", "script": "funnel.profile"},
         **pf.run_profile(con, "events")}
    p["decisions_needed"] = pf.decisions_needed(p)
    return p


def test_synthetic_profile_passes(synthetic_profile):
    assert find_metric_leaks(synthetic_profile) == []


def test_committed_profile_json_passes():
    assert PROFILE_JSON.exists(), f"{PROFILE_JSON} missing; run python -m funnel.profile"
    assert find_metric_leaks(json.loads(PROFILE_JSON.read_text(encoding="utf-8"))) == []


INJECTIONS = {
    "conversion rate by category": lambda p: p.update(
        {"conversion_rate_by_category": {"electronics.phone": 0.12}}),
    "revenue sum by day": lambda p: p["price"].update(
        {"revenue_sum_by_day": {"2019-10-01": 1234.5}}),
    "grouped counts hidden under event_types": lambda p: p["event_types"]["counts"].update(
        {"purchase": {"brand_a": 3}}),
    "innocuous name, grouped ratios": lambda p: p["sessions_users"].update(
        {"segments": {"new": 0.4, "returning": 0.6}}),
    "ratio smuggled into an allowed count": lambda p: p["ordering_anomalies"].update(
        {"cart_events_evaluated": 0.25}),
    "per-product purchase share": lambda p: p.update(
        {"top_products": [{"product_id": 1, "purchase_share": 0.3}]}),
}


@pytest.mark.parametrize("name", list(INJECTIONS))
def test_injected_leak_is_caught(synthetic_profile, name):
    leaked = copy.deepcopy(synthetic_profile)
    INJECTIONS[name](leaked)
    assert find_metric_leaks(leaked), f"guard missed injected leak: {name}"


@pytest.mark.parametrize("name", list(INJECTIONS))
def test_injected_leak_into_committed_profile_copy_is_caught(name):
    leaked = json.loads(PROFILE_JSON.read_text(encoding="utf-8"))
    INJECTIONS[name](leaked)
    assert find_metric_leaks(leaked), f"guard missed injected leak: {name}"
