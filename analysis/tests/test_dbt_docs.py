"""Every dbt model is documented and tested (CLAUDE.md, Style: "every model documented and tested")."""

from __future__ import annotations

import yaml

from funnel.common import REPO_ROOT

MODELS = REPO_ROOT / "pipeline" / "models"


def documented_models() -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for path in MODELS.rglob("*.yml"):
        for model in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("models", []) or []:
            docs[model["name"]] = model
    return docs


def test_every_model_file_is_documented_with_a_tested_column():
    docs = documented_models()
    model_files = sorted(p.stem for p in MODELS.rglob("*.sql"))
    assert model_files, "no dbt models found"
    problems = []
    for name in model_files:
        model = docs.get(name)
        if model is None:
            problems.append(f"{name}: no YAML entry")
            continue
        if not str(model.get("description", "")).strip():
            problems.append(f"{name}: no description")
        columns = model.get("columns") or []
        if not any(c.get("data_tests") for c in columns):
            problems.append(f"{name}: no column has a data test")
        if any(not str(c.get("description", "")).strip() for c in columns):
            problems.append(f"{name}: a column has no description")
    assert not problems, problems


def test_no_yaml_entry_without_a_model_file():
    model_files = {p.stem for p in MODELS.rglob("*.sql")}
    assert not set(documented_models()) - model_files
