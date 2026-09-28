"""Tech stack on /how-its-built and in the README (owner decision, v1.1.5): versions come from their source files."""

from __future__ import annotations

import json

from funnel import tech_stack as ts
from funnel.export import WEB_DATA

# Owner decision for PR #21 (v1.1.5): seven layers, starting with the AI workflow.
OWNER_GROUPS = ["AI workflow", "Languages", "Data and storage", "Transformation and quality",
                "Analysis and verification", "Web and delivery", "Engineering practice"]


def _committed() -> dict:
    return json.loads((WEB_DATA / "workflow.json").read_text(encoding="utf-8"))["tech_stack"]


def test_every_listed_version_equals_its_source():
    sources = {"analysis/requirements.txt": ts.requirement_versions(), "web/package.json": ts.package_versions(),
               "ai-workflow/tools.md": ts.tools_versions()}
    listed = [i for g in _committed()["groups"] for i in g["items"]]
    versioned = [i for i in listed if i["version_source"]]
    assert versioned, "expected versioned items"
    for item in versioned:
        src = item["version_source"]
        key = src["key"].lower() if src["file"] == "analysis/requirements.txt" else src["key"]
        assert item["version"] == sources[src["file"]].get(key), (item["name"], item["version"], src)
    assert all(i["version"] is None for i in listed if not i["version_source"])


def test_committed_stack_is_the_current_resolution_in_the_owner_groups():
    committed = _committed()
    assert committed == json.loads(json.dumps(ts.resolve())), "refresh: python -m funnel.export --only workflow.json"
    assert [g["group"] for g in committed["groups"]] == OWNER_GROUPS
    names = {i["name"] for g in committed["groups"] for i in g["items"]}
    assert {"Claude Chat", "Claude Code", "Human checkpoints", "Python", "SQL", "TypeScript", "HTML/CSS", "Kaggle CLI",
            "Parquet", "DuckDB", "dbt-core", "dbt-duckdb", "dbt tests", "pandas", "pyarrow", "pytest",
            "Independent verifier", "Next.js", "React", "Tailwind CSS", "Vercel CLI", "Git", "GitHub",
            "GitHub Actions CI", "Branch protection", "GitGuardian", "Playwright"} == names
    assert all(i["role"] for g in committed["groups"] for i in g["items"])


def test_readme_section_matches_the_exported_stack():
    readme = ts.README.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert ts.readme_with_stack(readme, _committed()) == readme, "refresh: python -m funnel.export --only workflow.json"
    assert "## Tech stack" in readme


def test_version_parsers_read_the_expected_formats(tmp_path, monkeypatch):
    tools = tmp_path / "tools.md"
    tools.write_text("| Tool | Version | Purpose |\n|---|---|---|\n| Python | 3.12.10 (`venv`) | x |\n"
                     "| Node / npm | 22.18.0 / 11.7.0 | y |\n| git | 2.53.0.windows.2 | z |\n", encoding="utf-8")
    monkeypatch.setattr(ts, "TOOLS_MD", tools)
    assert ts.tools_versions() == {"Python": "3.12.10", "Node / npm": "22.18.0", "git": "2.53.0"}
    req = tmp_path / "requirements.txt"
    req.write_text("duckdb==1.5.5\n# comment\ndbt-core==1.12.5\n", encoding="utf-8")
    monkeypatch.setattr(ts, "REQUIREMENTS", req)
    assert ts.requirement_versions() == {"duckdb": "1.5.5", "dbt-core": "1.12.5"}
