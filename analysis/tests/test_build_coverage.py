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


def test_summary_lines_strip_colour_codes_and_timestamps():
    from funnel.build import done_counts, summary_lines

    output = (
        "\x1b[0m05:56:11  Finished running 10 table models, 78 data tests in 0 hours 17 minutes.\n"
        "\x1b[0m05:56:11  \x1b[32mCompleted successfully\x1b[0m\n"
        "\x1b[0m05:56:11  Done. PASS=88 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=88\n"
    )
    lines = summary_lines(output)
    assert lines == [
        "Finished running 10 table models, 78 data tests in 0 hours 17 minutes.",
        "Completed successfully",
        "Done. PASS=88 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=88",
    ]
    assert done_counts(lines) == {"pass": 88, "warn": 0, "error": 0, "skip": 0, "no_op": 0, "reused": 0,
                                  "total": 88}
    assert done_counts([]) is None
