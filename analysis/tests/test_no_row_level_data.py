"""No committed file under web/, docs/, or ai-workflow/evidence/ may hold row-level event data."""

from __future__ import annotations

import pytest

from funnel.common import REPO_ROOT
from funnel.row_guard import committable_files, row_level_findings, scan


def test_committable_files_have_no_row_level_data():
    files = committable_files()
    assert files, "expected committable files under the guarded directories"
    assert scan(files) == {}


@pytest.mark.parametrize("sample", [
    "2019-10-01 00:00:00 UTC,view,44600062,2103807459595387724,,shiseido,35.79,541312140,"
    "72d76fde-8bb3-4e00-8c23-a032dfb62e6e",
    "2019-10-01 00:00:00 UTC,purchase,3900821,2053013552326770905,appliances.environment.water_heater,aqua,33.2",
    "session 72d76fde-8bb3-4e00-8c23-a032dfb62e6e converted",
    '[{"event_time": "2019-10-01", "event_type": "cart", "user_id": 541312140}]',
])
def test_detector_catches_injected_rows(sample):
    assert row_level_findings(sample)


@pytest.mark.parametrize("sample", [
    "| `event_time` | `TIMESTAMP WITH TIME ZONE` |\n| `user_session` | `VARCHAR` |",
    '{"event_types": {"counts": {"view": 100, "cart": 5}}}',
    "- **SHA-256:** `" + "a" * 64 + "`",
    "Min: 2019-10-01 00:00:00+00; max: 2019-10-31 23:59:59+00.",
])
def test_detector_passes_aggregate_text(sample):
    assert row_level_findings(sample) == []


def test_injected_row_in_a_guarded_file_is_caught(tmp_path, monkeypatch):
    leak = tmp_path / "leak.md"
    leak.write_text("2019-10-01 00:00:00 UTC,view,1,2,,brand,1.0,3,s\n", encoding="utf-8")
    monkeypatch.setattr("funnel.row_guard.REPO_ROOT", tmp_path)
    assert scan([leak]) == {"leak.md": ["raw CSV event row"]}


def test_readme_carries_both_attribution_links():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store" in readme
    assert "https://rees46.com" in readme
