"""The tech stack shown on /how-its-built and in the README (owner decision, v1.1.5).

Each item names its role in this project. Versions are never typed: each comes from its source file at export time,
namely analysis/requirements.txt (exact pins), web/package.json (the declared version or range), or
ai-workflow/tools.md (versions verified at the preflight). Items without a version source (a file format, a
practice, a service) carry none. test_tech_stack.py fails if an exported version differs from its source.

Written into workflow.json by python -m funnel.export --only workflow.json, which also refreshes the README's
section between the tech-stack markers.
"""

from __future__ import annotations

import json
import re
from typing import Any

from funnel.common import REPO_ROOT

REQUIREMENTS = REPO_ROOT / "analysis" / "requirements.txt"
PACKAGE_JSON = REPO_ROOT / "web" / "package.json"
TOOLS_MD = REPO_ROOT / "ai-workflow" / "tools.md"
README = REPO_ROOT / "README.md"
README_START, README_END = "<!-- tech-stack:start -->", "<!-- tech-stack:end -->"

# (group, name, role, version source): the source is ("requirements", package), ("package.json", package), or
# ("tools.md", the tool's row name), or None.
STACK: tuple[tuple[str, str, str, tuple[str, str] | None], ...] = (
    ("Data", "Kaggle CLI", "Downloads the October 2019 event log from its Kaggle dataset page (`python -m funnel.ingest`).",
     ("requirements", "kaggle")),
    ("Data", "Parquet", "The ingested event log is stored once as a Parquet file; every stage reads it from there.", None),
    ("Data", "DuckDB", "Runs every query over the raw data and holds the warehouse the dbt models build into, with a "
                       "fixed memory limit.", ("requirements", "duckdb")),
    ("Transformation and quality", "dbt-core", "Staging, intermediate, and mart models, each documented and tested, "
                                               "built through `funnel.build` behind memory and dataset-hash gates.",
     ("requirements", "dbt-core")),
    ("Transformation and quality", "dbt-duckdb", "The dbt adapter for DuckDB.", ("requirements", "dbt-duckdb")),
    ("Transformation and quality", "dbt tests", "Schema tests (not null, unique, accepted values), singular "
                                                "reconciliation tests that tie marts to totals and to each other, and "
                                                "tie checks on earliest and latest values; every build must run every "
                                                "expected test.", None),
    ("Analysis and verification", "Python", "The `funnel` package: ingestion, profiling, builds, statistics, exports, "
                                            "and guards.", ("tools.md", "Python")),
    ("Analysis and verification", "pandas", "Small aggregates only; the raw data is too large for it.",
     ("requirements", "pandas")),
    ("Analysis and verification", "pyarrow", "Reads and writes the Parquet file.", ("requirements", "pyarrow")),
    ("Analysis and verification", "pytest", "The commit gate (pytest's own exit code), with guard tests for the naming "
                                            "rules, row-level data, and drift between exports and their sources.",
     ("requirements", "pytest")),
    ("Analysis and verification", "Independent verifier (`funnel.verify`)", "Recomputes every published figure from the "
                                                                           "Parquet file with separately written SQL, "
                                                                           "without dbt.", None),
    ("Web and delivery", "Next.js", "The site, prerendered from the JSON exports at build time.", ("package.json", "next")),
    ("Web and delivery", "TypeScript", "The site's code.", ("package.json", "typescript")),
    ("Web and delivery", "Tailwind CSS", "Layout and the light and dark themes.", ("package.json", "tailwindcss")),
    ("Web and delivery", "Vercel (CLI)", "Production hosting; deploys go through the Vercel CLI, never on merge.",
     ("tools.md", "Vercel CLI")),
    ("Engineering practice", "GitHub", "Source, pull requests, and release tags; every change reaches `main` through a "
                                       "pull request.", None),
    ("Engineering practice", "GitHub Actions CI", "Required checks on every pull request: Python tests, the web build, "
                                                  "and a documentation link check.", None),
    ("Engineering practice", "Branch protection", "On `main`: pull request required, checks required and up to date, "
                                                  "enforced for admins, no force pushes.", None),
    ("Engineering practice", "GitGuardian", "Secret scanning on every pull request.", None),
    ("Engineering practice", "Playwright", "Screenshots at phone width in both themes, failing on any horizontal "
                                           "overflow.", ("package.json", "playwright")),
    ("AI workflow", "Claude Chat", "The command center: planning, framing, and challenging the work with the project "
                                   "owner.", None),
    ("AI workflow", "Claude Code", "The executor: carries out each step in the repository under binding rules and stops "
                                   "at every checkpoint.", None),
    ("AI workflow", "Human checkpoints", "The project owner decides scope, contract changes, and merges, and signs off "
                                         "every published claim.", None),
)
GROUPS = tuple(dict.fromkeys(g for g, *_ in STACK))


def requirement_versions() -> dict[str, str]:
    out = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)==([^\s#]+)\s*", line)
        if m:
            out[m.group(1).lower()] = m.group(2)
    return out


def package_versions() -> dict[str, str]:
    pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    return {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}


def tools_versions() -> dict[str, str]:
    """Versions from the Claude Code tool table in tools.md: the first version number in the row's second cell."""
    out = {}
    for line in TOOLS_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2:
            m = re.search(r"\d+(?:\.\d+)+", cells[1])
            if m and cells[0] not in out:
                out[cells[0]] = m.group(0)
    return out


def resolve() -> dict[str, Any]:
    sources = {"requirements": requirement_versions(), "package.json": package_versions(), "tools.md": tools_versions()}
    files = {"requirements": "analysis/requirements.txt", "package.json": "web/package.json",
             "tools.md": "ai-workflow/tools.md"}
    groups = []
    for group in GROUPS:
        items = []
        for g, name, role, source in STACK:
            if g != group:
                continue
            version = None
            if source:
                kind, key = source
                version = sources[kind].get(key.lower() if kind == "requirements" else key)
                if version is None:
                    raise ValueError(f"tech stack: {name}: no version for {key!r} in {files[kind]}")
            items.append({"name": name, "role": role, "version": version,
                          "version_source": None if not source else {"file": files[source[0]], "key": source[1]}})
        groups.append({"group": group, "items": items})
    return {"groups": groups, "sources": sorted(files.values())}


def render_markdown(stack: dict[str, Any]) -> str:
    lines = ["## Tech stack", "",
             "Each tool with its role in this project. Versions are read by `python -m funnel.export --only "
             "workflow.json` from `analysis/requirements.txt`, `web/package.json`, and `ai-workflow/tools.md`; a test "
             "fails if any differs from its source. The same list is on the "
             "[How it's built](https://ecommercefunnel-analytics.vercel.app/how-its-built) page.", ""]
    for group in stack["groups"]:
        lines.append(f"**{group['group']}**")
        lines.append("")
        for item in group["items"]:
            version = f" `{item['version']}`" if item["version"] else ""
            lines.append(f"- **{item['name']}**{version}: {item['role']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def readme_with_stack(readme: str, stack: dict[str, Any]) -> str:
    block = f"{README_START}\n{render_markdown(stack)}{README_END}"
    if README_START in readme and README_END in readme:
        return re.sub(re.escape(README_START) + r".*?" + re.escape(README_END), lambda _: block, readme, flags=re.DOTALL)
    raise ValueError("README.md has no tech-stack markers")


def sync_readme(stack: dict[str, Any]) -> None:
    raw = README.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    updated = readme_with_stack(raw.replace("\r\n", "\n"), stack).replace("\n", nl)
    README.write_bytes(updated.encode("utf-8"))
