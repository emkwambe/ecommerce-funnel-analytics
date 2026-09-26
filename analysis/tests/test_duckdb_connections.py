"""Every DuckDB connection the package opens uses the shared settings in funnel.common (memory limit, threads,
insertion order, spill directory, UTC), through funnel.ingest.connect(). SQL may be independent (R2); the
connection settings may not (owner instruction, Sprint 2 Step 5)."""

from __future__ import annotations

import ast
from pathlib import Path

import duckdb

from funnel.common import DUCKDB_MEMORY_LIMIT, DUCKDB_THREADS, DUCKDB_TMP_DIR, REPO_ROOT
from funnel.ingest import connect

SOURCES = (REPO_ROOT / "analysis" / "funnel", REPO_ROOT / "analysis" / "explore")
ALLOWED = {("funnel/ingest.py", "connect")}  # the one place that opens and configures a connection


def bare_connects(source: str, rel: str) -> list[str]:
    """Calls to duckdb.connect (or an alias of it) outside the allowed function, as 'file:line'."""
    tree = ast.parse(source)
    aliases = {"duckdb"}
    direct: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases |= {a.asname or a.name for a in node.names if a.name == "duckdb"}
        if isinstance(node, ast.ImportFrom) and node.module == "duckdb":
            direct |= {a.asname or a.name for a in node.names if a.name == "connect"}
    found = []

    def visit(node: ast.AST, function: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function
            if isinstance(child, ast.Call):
                f = child.func
                is_attr = isinstance(f, ast.Attribute) and f.attr == "connect" and isinstance(f.value, ast.Name) \
                    and f.value.id in aliases
                is_direct = isinstance(f, ast.Name) and f.id in direct
                if (is_attr or is_direct) and (rel, function) not in ALLOWED:
                    found.append(f"{rel}:{child.lineno}")
            visit(child, name)

    visit(tree, None)
    return found


def test_no_package_module_opens_a_bare_duckdb_connection():
    files = [p for d in SOURCES for p in sorted(d.glob("*.py"))]
    assert len(files) > 5, "expected the funnel package and the exploratory scripts"
    hits = [hit for p in files
            for hit in bare_connects(p.read_text(encoding="utf-8"), p.relative_to(REPO_ROOT / "analysis").as_posix())]
    assert not hits, f"open DuckDB through funnel.ingest.connect(): {hits}"


def test_scanner_catches_each_bare_form():
    assert bare_connects("import duckdb\ncon = duckdb.connect()\n", "funnel/x.py") == ["funnel/x.py:2"]
    assert bare_connects("import duckdb as d\ndef f():\n    return d.connect()\n", "funnel/x.py") == ["funnel/x.py:3"]
    assert bare_connects("from duckdb import connect\nconnect()\n", "funnel/x.py") == ["funnel/x.py:2"]
    assert bare_connects("import duckdb\ndef connect():\n    return duckdb.connect()\n", "funnel/ingest.py") == []


def test_shared_connection_applies_every_setting():
    reference = duckdb.connect()
    reference.execute(f"SET memory_limit = '{DUCKDB_MEMORY_LIMIT}'")
    expected_limit = reference.execute("SELECT current_setting('memory_limit')").fetchone()[0]
    con = connect()
    setting = lambda name: con.execute(f"SELECT current_setting('{name}')").fetchone()[0]  # noqa: E731
    assert setting("memory_limit") == expected_limit
    assert int(setting("threads")) == DUCKDB_THREADS
    assert setting("preserve_insertion_order") is False
    assert Path(setting("temp_directory")).resolve() == DUCKDB_TMP_DIR.resolve()
    assert setting("TimeZone") == "UTC"
