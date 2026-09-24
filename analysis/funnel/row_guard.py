"""Detect row-level event data in files that are or would be committed.

The project publishes aggregates and findings only (docs/data-source.md). A
file fails if it holds any of:

- a user_session value (UUID format);
- a raw CSV event row (timestamp, event_type, product_id, ...);
- a JSON event record (an event_type value alongside a user_id value).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from funnel.common import REPO_ROOT

GUARDED_DIRS = ("web", "docs", "ai-workflow/evidence")
EVENT_LEVELS = r"(?:view|cart|remove_from_cart|purchase)"

UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
CSV_EVENT_ROW = re.compile(
    rf"\d{{4}}-\d{{2}}-\d{{2}}[ T]\d{{2}}:\d{{2}}:\d{{2}}(?: UTC|[+-]\d{{2}}(?::?\d{{2}})?|Z)?\s*,\s*{EVENT_LEVELS}\s*,\s*\d+"
)
JSON_EVENT_TYPE_VALUE = re.compile(rf'"event_type"\s*:\s*"{EVENT_LEVELS}"')
JSON_USER_ID_VALUE = re.compile(r'"user_(?:id|session)"\s*:\s*"?[0-9a-f-]{6,}')


def row_level_findings(text: str) -> list[str]:
    findings = []
    if UUID.search(text):
        findings.append("user_session-like UUID value")
    if CSV_EVENT_ROW.search(text):
        findings.append("raw CSV event row")
    if JSON_EVENT_TYPE_VALUE.search(text) and JSON_USER_ID_VALUE.search(text):
        findings.append("JSON event record (event_type with user id or session value)")
    return findings


def committable_files(dirs: tuple[str, ...] = GUARDED_DIRS) -> list[Path]:
    """Tracked files plus untracked files not ignored: what a commit could include."""
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "--", *dirs],
        capture_output=True, text=True, check=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line.strip()]


def scan(paths: list[Path]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        found = row_level_findings(text)
        if found:
            hits[str(path.relative_to(REPO_ROOT))] = found
    return hits
