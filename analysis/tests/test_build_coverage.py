"""funnel.build test-coverage guard: expected tests that did not run are reported."""

from __future__ import annotations

from funnel.build import test_coverage as coverage_of

MODEL_STG = "model.funnel.stg_events"
MODEL_INT = "model.funnel.int_sessions"
NODES = {
    MODEL_STG: {},
    MODEL_INT: {"depends_on": {"nodes": [MODEL_STG]}},
    "test.funnel.not_null_int_sessions_user_session": {"depends_on": {"nodes": [MODEL_INT]}},
    # Depends on a built model and an unselected one: the case cautious selection dropped.
    "test.funnel.assert_no_tied_latest_cart_category": {"depends_on": {"nodes": [MODEL_STG, MODEL_INT]}},
    "test.funnel.not_null_stg_events_event_id": {"depends_on": {"nodes": [MODEL_STG]}},
}


def result(uid: str, status: str) -> dict:
    return {"unique_id": uid, "status": status}


def test_skipped_selection_is_reported():
    results = [result(MODEL_INT, "success"), result("test.funnel.not_null_int_sessions_user_session", "pass")]
    cov = coverage_of(NODES, results)
    assert cov["models_built"] == 1
    assert cov["tests_expected"] == 2
    assert cov["tests_run"] == 1
    assert cov["tests_expected_not_run"] == ["assert_no_tied_latest_cart_category"]


def test_full_coverage_passes():
    results = [
        result(MODEL_INT, "success"),
        result("test.funnel.not_null_int_sessions_user_session", "pass"),
        result("test.funnel.assert_no_tied_latest_cart_category", "pass"),
    ]
    assert coverage_of(NODES, results)["tests_expected_not_run"] == []


def test_skipped_test_counts_as_not_run():
    results = [
        result(MODEL_INT, "success"),
        result("test.funnel.not_null_int_sessions_user_session", "skipped"),
        result("test.funnel.assert_no_tied_latest_cart_category", "pass"),
    ]
    assert coverage_of(NODES, results)["tests_expected_not_run"] == ["not_null_int_sessions_user_session"]


def test_failed_model_expects_no_tests():
    results = [result(MODEL_INT, "error")]
    assert coverage_of(NODES, results)["tests_expected"] == 0
