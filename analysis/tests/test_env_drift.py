"""Env drift: `.env.example` lists exactly the environment variables the code reads (trio documentation playbook §3)."""

from __future__ import annotations

import re

from funnel.common import REPO_ROOT
from funnel.row_guard import committable_files

ENV_EXAMPLE = REPO_ROOT / ".env.example"
CODE_DIRS = ("analysis/funnel", "pipeline", "web")
CODE_SUFFIXES = {".py", ".mjs", ".js", ".ts", ".tsx", ".sql", ".yml", ".yaml"}

READ_PATTERNS = (
    re.compile(r"""os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]*)["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]*)["']\s*\]"""),
    re.compile(r"""os\.getenv\(\s*["']([A-Z][A-Z0-9_]*)["']"""),
    re.compile(r"""process\.env\.([A-Z][A-Z0-9_]*)"""),
    re.compile(r"""process\.env\[\s*["']([A-Z][A-Z0-9_]*)["']\s*\]"""),
    re.compile(r"""env_var\(\s*["']([A-Z][A-Z0-9_]*)["']"""),
)


def env_reads(text: str) -> set[str]:
    return {m.group(1) for pattern in READ_PATTERNS for m in pattern.finditer(text)}


def names_read_by_code() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in committable_files(CODE_DIRS):
        if path.suffix not in CODE_SUFFIXES or not path.is_file():
            continue
        for name in env_reads(path.read_text(encoding="utf-8", errors="ignore")):
            found.setdefault(name, []).append(path.relative_to(REPO_ROOT).as_posix())
    return found


def names_in_env_example() -> set[str]:
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    return {m.group(1) for line in lines if (m := re.match(r"^([A-Z][A-Z0-9_]*)=", line))}


def test_env_example_is_committable_not_ignored():
    """Sprint 2 Step 0: `.env*` in .gitignore also matched .env.example, so it was left out of the commit."""
    assert ENV_EXAMPLE in committable_files((".env.example",)), ".env.example is ignored by git; it must be committed"


def test_env_example_has_names_only_no_values():
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if re.match(r"^[A-Z][A-Z0-9_]*=", line):
            assert line.endswith("="), f".env.example must not carry a value: {line.split('=')[0]}"


def test_every_env_var_read_is_listed_and_every_listed_var_is_read():
    read = names_read_by_code()
    listed = names_in_env_example()
    missing = {name: read[name] for name in sorted(set(read) - listed)}
    unused = sorted(listed - set(read))
    assert not missing, f"read by code but missing from .env.example: {missing}"
    assert not unused, f"listed in .env.example but read nowhere: {unused}"


def test_scanner_detects_each_read_form():
    sample = "\n".join((
        'os.environ.get("A_ONE")', "os.environ['A_TWO']", 'os.getenv("A_THREE")',
        "process.env.A_FOUR", 'process.env["A_FIVE"]', "{{ env_var('A_SIX', 'x') }}",
    ))
    assert env_reads(sample) == {"A_ONE", "A_TWO", "A_THREE", "A_FOUR", "A_FIVE", "A_SIX"}
