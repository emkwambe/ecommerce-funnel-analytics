"""The closing report and the /questions export (owner closing decision, 2026-09-27).

Run: python -m funnel.closing   (reads committed files only; no analysis, no data access)

Inputs:
- ai-workflow/closing-content.md: the owner-approved content (four headline findings, the nine questions with their
  card lines, reasons, who can answer, and evidence links, and question 1's statement);
- ai-workflow/closing-report-template.md: the report's prose, with {{findings}} and {{questions}} slots;
- the committed exports under web/public/data/, for every figure.

Number binding (closing-content.md's rule): every figure in the content is bound to a named export field. The typed
figure must equal the value formatted from the export; if any differs, the run stops and reports it. A digit left in
any text after binding is an unbound figure and also stops the run. The export stores texts with {figure} tokens and
a figures table (value, formatted text, source file and field), so pages render figures from the export, never typed.
Every text is checked with the naming guard (docs/metrics.md Section 1) before anything is written.

Outputs: docs/closing-report.md and web/public/data/closing.json (with the provenance manifest, CLAUDE.md rule 5).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from funnel.common import REPO_ROOT, recorded_dataset_sha256, utc_now_iso, git_commit_sha, git_worktree_dirty, write_json
from funnel.naming_guard import naming_findings

SCRIPT = "funnel.closing"
CONTENT = REPO_ROOT / "ai-workflow" / "closing-content.md"
TEMPLATE = REPO_ROOT / "ai-workflow" / "closing-report-template.md"
REPORT = REPO_ROOT / "docs" / "closing-report.md"
WEB_DATA = REPO_ROOT / "web" / "public" / "data"
OUT = WEB_DATA / "closing.json"
ESCALATION_BRIEF = "ai-workflow/escalations/2026-09-27-C-rankings-stop-rules.md"
REPO_URL = "https://github.com/emkwambe/ecommerce-funnel-analytics"
NO_CART_PATH = "Purchase with no observed same-session cart event"

GROUPS = (  # card-grid order; labels as in closing-content.md
    ("product_engineering", "Product and engineering"),
    ("more_data", "More data"),
    ("better_methods", "Better methods"),
    ("experiment", "Only an experiment"),
)
# Evidence links: the content names a page and, in parentheses, a section; sections map to anchors on the pages.
ANCHORS = {"purchase paths section": "purchase-paths", "identity checks": "identity-checks",
           "late-October finding": "late-october", "limitations": "limitations"}


class ClosingError(Exception):
    pass


# ---------- figures bound to export fields ----------

@dataclass(frozen=True)
class Figure:
    key: str
    source: str   # export file under web/public/data
    field: str    # field path, as the Sources lines name it
    read: Callable[[dict[str, dict[str, Any]]], Any]
    fmt: Callable[[Any], str]


def _later_7(ex: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """B1, the primary 7-day estimate (metrics.md Changes 2026-09-26, Sprint 2 investigations, items 9 and 10)."""
    rows = [e for e in ex["investigation_later_purchases.json"]["estimates"] if e["spec_key"] == "B1"]
    if len(rows) != 1 or rows[0]["window_days"] != 7:
        raise ClosingError("investigation_later_purchases.json: expected exactly one B1 estimate, with a 7-day window")
    return rows[0]


def _no_cart(ex: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = [r for r in ex["purchase_paths.json"]["rows"] if r["purchase_path"] == NO_CART_PATH]
    if len(rows) != 1:
        raise ClosingError(f'purchase_paths.json: expected one row "{NO_CART_PATH}"')
    return rows[0]


def _population_dates(label: str) -> str:
    m = re.fullmatch(r"sessions starting (.+) UTC", label)
    if not m:
        raise ClosingError(f"unexpected population label: {label!r}")
    return f"{m.group(1)} (UTC)"


def _month_year(iso_date: str) -> str:
    months = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December")
    return f"{months[int(iso_date[5:7]) - 1]} {iso_date[:4]}"


# Longer texts first, so "October 1–24, 2019 (UTC)" is bound before "October 2019" could match anything.
FIGURES = (
    Figure("later_population", "investigation_later_purchases.json",
           "estimates[spec_key=B1].population", lambda ex: _later_7(ex)["population"], _population_dates),
    Figure("revenue_gap", "investigation_revenue_gap.json", "totals.revenue_difference",
           lambda ex: ex["investigation_revenue_gap.json"]["totals"]["revenue_difference"],
           lambda v: f"${v / 1e6:.1f}M"),
    Figure("later_value_share", "investigation_later_purchases.json", "estimates[spec_key=B1].value_share",
           lambda ex: _later_7(ex)["value_share"], lambda v: f"{v * 100:.1f}%"),
    Figure("later_window", "investigation_later_purchases.json", "estimates[spec_key=B1].window_days",
           lambda ex: _later_7(ex)["window_days"], lambda v: f"{v} days"),
    Figure("later_window_adjective", "investigation_later_purchases.json", "estimates[spec_key=B1].window_days",
           lambda ex: _later_7(ex)["window_days"], lambda v: f"{v}-day"),
    Figure("no_cart_revenue_share", "purchase_paths.json", f'rows["{NO_CART_PATH}"].revenue_share',
           lambda ex: _no_cart(ex)["revenue_share"], lambda v: f"{v * 100:.0f}%"),
    Figure("month", "kpis.json", "month.period_start", lambda ex: ex["kpis.json"]["month"]["period_start"],
           _month_year),
)


def resolve_figures(exports: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f.key: {"value": (value := f.read(exports)), "formatted": f.fmt(value), "source": f.source,
                    "field": f.field} for f in FIGURES}


def bind(text: str, figures: dict[str, dict[str, Any]], where: str) -> str:
    """Replace each typed figure with its {token}. The content's rule is checked where it can fail: a typed figure
    that differs from the export value is either caught here (a near miss of a bound figure) or left as a digit."""
    bound = text
    for f in FIGURES:
        bound = bound.replace(figures[f.key]["formatted"], "{" + f.key + "}")
    leftover = re.sub(r"\{[a-z_]+\}", "", bound)
    if re.search(r"\d", leftover):
        near = [f"{f.key}: the export gives {figures[f.key]['formatted']!r}" for f in FIGURES]
        raise ClosingError(f"{where}: a figure is not bound to an export field, or differs from its export "
                           f"value. Text: {text!r}. Bound figures: {'; '.join(near)}")
    return bound


def render(text: str, figures: dict[str, dict[str, Any]]) -> str:
    return re.sub(r"\{([a-z_]+)\}", lambda m: figures[m.group(1)]["formatted"], text)


# ---------- parsing the approved content ----------

def _table(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] in ("#",) or set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        raise ClosingError(f"closing-content.md has no section '## {heading}'")
    return m.group(1)


def _evidence(cell: str) -> dict[str, str]:
    if cell.startswith("The escalation brief on GitHub"):
        return {"href": f"{REPO_URL}/blob/main/{ESCALATION_BRIEF}", "label": "The escalation brief (GitHub)",
                "external": True}
    m = re.fullmatch(r"`(/[a-z/-]*)`(?: \((.+)\))?", cell)
    if not m:
        raise ClosingError(f"unrecognized evidence link: {cell!r}")
    path, section = m.group(1), m.group(2)
    if section is None:
        return {"href": path, "label": path, "external": False}
    if section not in ANCHORS:
        raise ClosingError(f"no anchor for evidence section {section!r}")
    return {"href": f"{path}#{ANCHORS[section]}", "label": f"{path} ({section})", "external": False}


def parse_content(text: str) -> dict[str, Any]:
    findings = [{"id": r[0], "text": r[1], "tier": r[2]} for r in _table(_section(text, "Four headline findings (home page)"))]
    if [f["id"] for f in findings] != ["F1", "F2", "F3", "F4"]:
        raise ClosingError("expected findings F1-F4")
    qsection = _section(text, "Nine questions worth asking next")
    membership: dict[int, str] = {}
    for key, label in GROUPS:
        m = re.search(rf"^- \*\*{re.escape(label)}:\*\* questions? (.+?)\.$", qsection, re.MULTILINE)
        if not m:
            raise ClosingError(f"no group line for {label!r}")
        for n in re.findall(r"\d+", m.group(1)):
            if int(n) in membership:
                raise ClosingError(f"question {n} is in two groups")
            membership[int(n)] = key
    statement = re.search(r"^\*\*Question 1 is (.+?)\*\* (.+)$", qsection, re.MULTILINE)
    if not statement:
        raise ClosingError("no question 1 statement")
    questions = []
    for r in _table(qsection):
        n = int(r[0])
        questions.append({"n": n, "question": r[1], "card_line": r[2], "why": r[3], "who": r[4],
                          "group": membership.get(n), "evidence": _evidence(r[5]), "start_here": n == 1})
    if [q["n"] for q in questions] != list(range(1, 10)) or sorted(membership) != list(range(1, 10)):
        raise ClosingError("expected questions 1-9, each in exactly one group")
    return {"findings": findings, "questions": questions,
            "question_1": {"lead": f"Question 1 is {statement.group(1)}", "text": statement.group(2)}}


def bind_content(content: dict[str, Any], figures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = json.loads(json.dumps(content))
    for f in out["findings"]:
        f["text"] = bind(f["text"], figures, f"finding {f['id']}")
    for q in out["questions"]:
        for key in ("question", "card_line", "why", "who"):
            q[key] = bind(q[key], figures, f"question {q['n']} ({key})")
    out["question_1"]["text"] = bind(out["question_1"]["text"], figures, "question 1 statement")
    return out


def naming_check(bound: dict[str, Any], figures: dict[str, dict[str, Any]]) -> None:
    texts = [f["text"] for f in bound["findings"]] + [bound["question_1"]["lead"], bound["question_1"]["text"]]
    texts += [q[k] for q in bound["questions"] for k in ("question", "card_line", "why", "who")]
    hits = sorted({h for t in texts for h in naming_findings(render(t, figures))})
    if hits:
        raise ClosingError(f"the closing content breaks the naming rules (docs/metrics.md Section 1): {hits}")


# ---------- the report ----------

def _md_cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_report(template: str, bound: dict[str, Any], figures: dict[str, dict[str, Any]]) -> str:
    findings = ["| # | Finding | Tier |", "|---|---|---|"]
    findings += [f"| {f['id']} | {_md_cell(render(f['text'], figures))} | {f['tier']} |" for f in bound["findings"]]
    questions = [f"**{bound['question_1']['lead']}** {render(bound['question_1']['text'], figures)}", ""]
    for key, label in GROUPS:
        numbers = [str(q["n"]) for q in bound["questions"] if q["group"] == key]
        listed = f"questions {', '.join(numbers[:-1])} and {numbers[-1]}" if len(numbers) > 1 else f"question {numbers[0]}"
        questions.append(f"- **{label}:** {listed}.")
    questions += ["", "| # | Question | Why it matters | Who can answer | Evidence |", "|---|---|---|---|---|"]
    for q in bound["questions"]:
        ev = q["evidence"]
        href = ev["href"] if ev["external"] else f"https://ecommercefunnel-analytics.vercel.app{ev['href']}"
        questions.append(f"| {q['n']} | {_md_cell(render(q['question'], figures))} | "
                         f"{_md_cell(render(q['why'], figures))} | {_md_cell(q['who'])} | "
                         f"[{ev['label']}]({href}) |")
    sources = sorted({f"`{v['source']}`: `{v['field']}`" for v in figures.values()})
    return (template.replace("{{findings}}", "\n".join(findings)).replace("{{questions}}", "\n".join(questions))
            .replace("{{sources}}", "; ".join(sources)))


# ---------- the run ----------

def load_exports() -> dict[str, dict[str, Any]]:
    names = sorted({f.source for f in FIGURES})
    return {n: json.loads((WEB_DATA / n).read_text(encoding="utf-8")) for n in names}


def dataset_sha(exports: dict[str, dict[str, Any]]) -> str:
    shas = {e["manifest"]["dataset_sha256"] for e in exports.values()}
    recorded = recorded_dataset_sha256()
    if shas != {recorded}:
        raise ClosingError(f"source exports' dataset SHA-256 {sorted(shas)} differ from docs/data-source.md {recorded}")
    return recorded


def build(exports: dict[str, dict[str, Any]], content_text: str, template: str) -> tuple[str, dict[str, Any]]:
    figures = resolve_figures(exports)
    bound = bind_content(parse_content(content_text), figures)
    naming_check(bound, figures)
    report = render_report(template, bound, figures)
    export = {
        "source": {"content": "ai-workflow/closing-content.md",
                   "content_sha256": hashlib.sha256(content_text.encode("utf-8")).hexdigest(),
                   "report": "docs/closing-report.md",
                   "escalation_brief": ESCALATION_BRIEF},
        "status": "closed",
        "figures": figures,
        "findings": bound["findings"],
        "question_1": bound["question_1"],
        "groups": [{"key": k, "label": label, "questions": [q["n"] for q in bound["questions"] if q["group"] == k]}
                   for k, label in GROUPS],
        "questions": bound["questions"],
    }
    return report, export


def main() -> None:
    try:
        exports = load_exports()
        sha = dataset_sha(exports)
        report, export = build(exports, CONTENT.read_text(encoding="utf-8"), TEMPLATE.read_text(encoding="utf-8"))
    except ClosingError as err:
        sys.exit(f"HALT: {err}")
    REPORT.write_bytes(report.encode("utf-8"))
    write_json(OUT, {"manifest": {"git_commit_sha": git_commit_sha(), "git_worktree_dirty": git_worktree_dirty(),
                                  "dataset_sha256": sha, "generated_at_utc": utc_now_iso(), "script": SCRIPT},
                     **export})
    print(f"Wrote {REPORT.relative_to(REPO_ROOT)} and {OUT.relative_to(REPO_ROOT)}; "
          f"{len(export['figures'])} figures bound, {len(export['questions'])} questions, "
          f"{len(export['findings'])} findings.")


if __name__ == "__main__":
    main()
