"""Write the site's JSON exports from the dbt marts, each with a provenance manifest.

Run: python -m funnel.export

Reads data/warehouse.duckdb (read-only) after a passing `python -m funnel.build`, and writes
web/public/data/: kpis.json, funnel_category.json, purchase_paths.json, data_quality.json,
metrics_index.json (parsed from docs/metrics.md), data_story.json (the /data page), and, from
Sprint 2, investigation_revenue_gap.json (analysis A) and investigation_later_purchases.json
(analysis B; halts if a B stop rule fired).
Halts if the dataset hash differs from docs/data-source.md, if the last full dbt build did not
pass on this dataset, if the reconciliation chain in data_story.json does not sum, or if the
independent verification of analysis A is missing, on another dataset, or has a mismatch.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from funnel.common import (
    CURRENT_EVIDENCE_DIR,
    DATA_DIR,
    DOCS_DIR,
    EVIDENCE_DIR,
    KAGGLE_URL,
    REPO_ROOT,
    manifest,
    require_dataset_hash_match,
    write_json,
)
from funnel.ingest import KAGGLE_LICENSE_FIELD, PUBLISHER_USAGE_STATEMENT, REES46_URL, connect

SCRIPT = "funnel.export"
WAREHOUSE = DATA_DIR / "warehouse.duckdb"
WEB_DATA = REPO_ROOT / "web" / "public" / "data"
METRICS_MD = DOCS_DIR / "metrics.md"
BUILD_RUNS = CURRENT_EVIDENCE_DIR / "dbt_build_runs.json"
VERIFY_JSON = CURRENT_EVIDENCE_DIR / "verify.json"
REQUIREMENTS = REPO_ROOT / "analysis" / "requirements.txt"

# Sections, beyond its home section, whose Changes entries apply to a decision: D5's same-session
# cart reading is applied in the Section 6 cart-session purchase rate, and D8's exclusions are
# counted under Section 10.
RELATED_SECTIONS = {"D5": ("6",), "D8": ("10",)}

# One line per decision (no figures: figures come from the exports). Each links to the
# metrics.md section that records it; test_export checks the section names the decision.
DECISIONS = (
    ("D1", "Deduplication", "Exact duplicate rows are removed; rows that differ in any column are kept.", "2"),
    ("D2", "Zero prices", "Zero-price events count as events but are excluded from every value.", "2"),
    ("D3", "Price", "Revenue uses the purchase price; carted value uses each pair's latest non-zero cart price.", "2"),
    ("D4", "Order and revenue", "One order is one valid session with an observed purchase.", "4"),
    ("D5", "Purchase paths", "Purchases are split by whether the product has a cart event in the same session.", "5"),
    ("D6", "Cart event order", "Cart events count whether or not a view preceded them.", "2"),
    ("D7", "Breakdowns", "Missing category and brand form an explicit unknown level, with its share stated.", "9"),
    ("D8", "Session rules", "Sessions as logged; null-session events and multi-user sessions are excluded.", "3"),
    ("D9", "Event types", "Only view, cart, and purchase exist, and all three are used.", "2"),
    ("D10", "Time", "Timestamps are UTC as logged; the store's local time zone is unknown.", "2"),
)

# Data limitations, each citing the exported fields that support it (CLAUDE.md rule 2).
LIMITATIONS = (
    ("There is no order or transaction ID, so an order is defined as a session with an observed purchase.",
     ["contents.order_or_transaction_id_exists", "reconciliation.orders"]),
    ("Repeated purchase events of one product in a session may be extra units or repeated logging; both "
     "revenue figures are shown where the difference matters.",
     ["kpis.month.revenue", "kpis.month.revenue_repeat_collapsed"]),
    ("A session is the logged user_session. Purchases in other sessions or on other devices are not linked, "
     "so no observed purchase in a session does not mean no purchase.",
     ["reconciliation.valid_sessions"]),
    ("Most purchase events have no cart event for that product in the same session.",
     ["purchase_paths.rows"]),
    ("Category and brand are missing on part of the log and form an explicit unknown level.",
     ["data_quality.unknown_category_event_share", "data_quality.unknown_brand_event_share"]),
    ("Times are UTC. The store's local time zone is unknown, so no hour-of-day result describes local behavior.",
     ["contents.min_event_time_utc", "contents.max_event_time_utc"]),
    ("The log covers one month, so results say nothing about seasonality or longer-term trends.",
     ["contents.min_event_time_utc", "contents.max_event_time_utc"]),
    ("Observed means logged: an event absent from this log is not evidence that it did not happen.",
     ["contents.raw_rows"]),
)

PRE_ANALYSIS_FINDINGS = (
    ("Exact duplicate rows (surplus)", ("duplicates", "exact_duplicate_rows", "surplus_rows")),
    ("Zero-price events", ("price", "zero_price_events")),
    ("Products with more than one distinct price", ("price", "products_with_more_than_one_distinct_price")),
    ("Events with no category code", ("category_brand", "category_code", "null_or_empty_count")),
    ("Events with no brand", ("category_brand", "brand", "null_or_empty_count")),
    ("Category codes mapping to more than one category_id",
     ("category_brand", "category_codes_mapping_to_more_than_one_category_id")),
    ("Events with a null session", ("sessions_users", "null_user_session_events")),
    ("Sessions with more than one user_id", ("sessions_users", "sessions_with_more_than_one_user_id")),
    ("Sessions spanning more than 24 hours", ("sessions_users", "sessions_spanning_more_than_24_hours")),
    ("Purchase events with no cart event of the product in the session",
     ("ordering_anomalies", "purchase_events_with_no_cart_of_product_in_session")),
    ("Cart events with no view at or before them in the session",
     ("ordering_anomalies", "cart_events_with_no_view_at_or_before_in_session")),
    ("Sessions with more than one purchase event", ("order_reconstruction", "sessions_with_more_than_one_purchase_event")),
    ("(session, product) pairs with repeated purchase events",
     ("order_reconstruction", "session_product_pairs_with_more_than_one_purchase_event")),
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [{n: _jsonable(v) for n, v in zip(names, r)} for r in cur.fetchall()]


# ---------- metrics.md parsing ----------

def _sections(text: str) -> dict[str, str]:
    """Level-2 sections keyed by number ('1'..'10') or 'Changes'."""
    out: dict[str, str] = {}
    parts = re.split(r"^(## .*)$", text, flags=re.MULTILINE)
    for heading, body in zip(parts[1::2], parts[2::2]):
        number = re.match(r"## (\d+)\.", heading)
        out[number.group(1) if number else heading[3:].strip()] = body
    return out


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def parse_metrics_index(text: str) -> list[dict[str, str]]:
    """Metric definitions from Sections 4, 6, and 7, and the dated Changes entries.

    Section 1 (naming rules) is never exported: it quotes the prohibited terms."""
    sections = _sections(text)
    entries: list[dict[str, str]] = []
    for number in ("4", "7"):
        for name, definition in re.findall(r"^- \*\*(.+?)\.\*\* (.+)$", sections[number], re.MULTILINE):
            entries.append({"key": _slug(name), "name": name, "definition": definition.strip(),
                            "display_label": name, "section": number})
    for line in sections["6"].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] not in ("Metric", "---") and not set(cells[0]) <= {"-"}:
            entries.append({"key": _slug(cells[0]), "name": cells[0], "definition": cells[1],
                            "display_label": cells[2], "section": "6"})
    for heading, body in re.findall(r"^### (.+?)\n(.*?)(?=^### |\Z)", sections.get("Changes", ""),
                                    re.MULTILINE | re.DOTALL):
        entries.append({"key": "changes_" + _slug(heading), "name": heading.strip(),
                        "definition": " ".join(body.split()), "display_label": heading.strip(),
                        "section": "Changes"})
        # Metrics a Changes entry defines: - "Full label" (legend label: "Short"): definition
        #                                 - "Full label" (display label): definition
        for full, short, definition in re.findall(
            r'^\s*- "([^"]+)" \((?:legend label: "([^"]+)"|display label)\): (.+)$', body, re.MULTILINE
        ):
            first, _, rest = definition.strip().partition(". ")
            entries.append({"key": _slug(full), "name": full,
                            "definition": first[:1].upper() + first[1:] + ("." if rest else ""),
                            "note": rest.strip() or None, "display_label": full, "section": "Changes",
                            "short_label": short or None})
    for e in entries:
        e.setdefault("short_label", None)
        e.setdefault("note", None)
    return entries


def changes_entries(text: str) -> list[dict[str, Any]]:
    """Dated Changes entries with the metrics.md sections each one touches."""
    out = []
    for heading in re.findall(r"^### (.+)$", _sections(text).get("Changes", ""), re.MULTILINE):
        touched = re.search(r"\(Sections? ([\d, ]+)\)", heading)
        out.append({"title": heading.strip(),
                    "date": heading.split(" ")[0],
                    "sections": [s.strip() for s in touched.group(1).split(",")] if touched else []})
    return out


# ---------- exports ----------

def last_full_build(dataset_sha: str) -> dict[str, Any]:
    runs = json.loads(BUILD_RUNS.read_text(encoding="utf-8"))["runs"]
    full = [r for r in runs if r["dbt_args"] == ["build"]]
    if not full or full[-1]["dbt_exit_code"] != 0 or full[-1]["manifest"]["dataset_sha256"] != dataset_sha:
        sys.exit("HALT: the last full dbt build did not pass on this dataset; run python -m funnel.build.")
    last = full[-1]
    return {"git_commit_sha": last["manifest"]["git_commit_sha"],
            "generated_at_utc": last["manifest"]["generated_at_utc"],
            "dbt_done_counts": last.get("dbt_done_counts"),
            "test_coverage": last.get("test_coverage")}


def reconciliation(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    raw_rows, removed = con.execute(
        "SELECT raw_rows, exact_duplicate_rows_removed FROM wh.main_staging.stg_dedup_audit").fetchone()
    dedup, null_events, multi_user_events, valid_events = con.execute("""
        SELECT count(*),
               count(*) FILTER (WHERE e.user_session IS NULL),
               count(*) FILTER (WHERE e.user_session IS NOT NULL AND s.user_session IS NULL),
               count(*) FILTER (WHERE s.user_session IS NOT NULL)
        FROM wh.main_staging.stg_events AS e
        LEFT JOIN wh.main_intermediate.int_sessions AS s USING (user_session)
    """).fetchone()
    multi_user_sessions = con.execute(
        "SELECT value FROM wh.main_marts.mart_data_quality WHERE metric_key = 'multi_user_sessions_excluded'"
    ).fetchone()[0]
    sessions, orders = con.execute(
        "SELECT sessions, orders FROM wh.main_marts.mart_kpis_daily WHERE period_type = 'month'").fetchone()
    chain = {
        "raw_rows": int(raw_rows),
        "exact_duplicate_rows_removed": int(removed),
        "deduplicated_events": int(dedup),
        "null_session_events_excluded": int(null_events),
        "multi_user_sessions_excluded": int(multi_user_sessions),
        "events_in_multi_user_sessions_excluded": int(multi_user_events),
        "valid_session_events": int(valid_events),
        "valid_sessions": int(sessions),
        "orders": int(orders),
    }
    if chain["raw_rows"] - chain["exact_duplicate_rows_removed"] != chain["deduplicated_events"] or (
        chain["deduplicated_events"] - chain["null_session_events_excluded"]
        - chain["events_in_multi_user_sessions_excluded"] != chain["valid_session_events"]
    ):
        sys.exit(f"HALT: reconciliation chain does not sum: {chain}")
    return chain


def data_story(con: duckdb.DuckDBPyConnection, metrics_text: str, dq: dict[str, Any]) -> dict[str, Any]:
    ingest = json.loads((EVIDENCE_DIR / "ingest.json").read_text(encoding="utf-8"))
    profile = json.loads((EVIDENCE_DIR / "profile.json").read_text(encoding="utf-8"))
    kaggle_pin = next((line.strip() for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
                       if line.startswith("kaggle==")), None)
    raw = ingest["raw_file"]

    def dig(path: tuple[str, ...]) -> Any:
        node: Any = profile
        for key in path:
            node = node[key]
        return node

    changes = changes_entries(metrics_text)
    return {
        "source": {
            "title": "eCommerce behavior data from multi category store",
            "publisher": "REES46 (Kaggle owner mkechinov), collected by the Open CDP project",
            "kaggle_slug": ingest["source"]["kaggle_slug"],
            "kaggle_url": KAGGLE_URL,
            "rees46_url": REES46_URL,
            "obtained_with": f"Kaggle API through the kaggle Python package ({kaggle_pin}), "
                             "October 2019 file only (python -m funnel.ingest)",
            "file_name": raw["name"],
            "size_bytes": raw["size_bytes"],
            "retrieved_at_utc": raw["retrieved_at_utc"],
            "sha256": raw["sha256"],
            "license_field": KAGGLE_LICENSE_FIELD,
            "publisher_usage_statement": PUBLISHER_USAGE_STATEMENT,
            "attribution_links": [KAGGLE_URL, REES46_URL],
        },
        "contents": {
            "grain": "One row is one logged event.",
            "raw_rows": profile["schema"]["row_count"],
            "columns": [c["name"] for c in profile["schema"]["columns"]],
            "event_type_counts": profile["event_types"]["counts"],
            "min_event_time_utc": profile["time"]["min_event_time"],
            "max_event_time_utc": profile["time"]["max_event_time"],
            "distinct_counts": profile["schema"]["distinct_counts"],
            "order_or_transaction_id_exists": profile["order_reconstruction"]["order_or_transaction_id_exists"],
        },
        "pre_analysis_findings": [
            {"finding": label, "count": dig(path), "profile_field": ".".join(path)}
            for label, path in PRE_ANALYSIS_FINDINGS
        ],
        "decisions": [
            {"id": did, "title": title, "summary": summary, "metrics_section": section,
             "related_sections": list(RELATED_SECTIONS.get(did, ())),
             "changes": [c["title"] for c in changes
                         if {section, *RELATED_SECTIONS.get(did, ())} & set(c["sections"])]}
            for did, title, summary, section in DECISIONS
        ],
        "changes_entries": changes,
        "reconciliation": reconciliation(con),
        "data_quality_shares": {k: dq[k]["value"] for k in (
            "unknown_category_event_share", "unknown_category_revenue_share",
            "unknown_brand_event_share", "unknown_brand_revenue_share")},
        "limitations": [{"text": text, "supporting_fields": fields} for text, fields in LIMITATIONS],
    }


# ---------- workflow record (/how-its-built) ----------

CORRECTION_LOG = REPO_ROOT / "ai-workflow" / "correction-log.md"
ENTRY_HEADING = re.compile(r"^\*\*(\d{4}-\d{2}-\d{2}) · (.+?) · (.+)\*\*$", re.MULTILINE)
# First matching rule wins; exported with the counts so the classification is visible.
# Sprint 2 Step 4: "Project owner" added for errors in the owner's own specifications caught by a check.
ORIGINS = ("Claude Code", "Claude Chat", "Project owner")

CAUGHT_RULES = (
    ("Harness or shell", ("harness", "timeout", "shell error", "command error")),
    ("Human review", ("human review",)),
    ("Test or commit gate", ("pytest", "commit gate")),
    ("Pipeline run or generated output", ("dbt exit code", "generated column types")),
    ("Screenshot or smoke check", ("screenshot", "smoke")),
    ("Claude Code's own review", ("review", "check")),
)
MILESTONES = (
    ("conventions", "Conventions and preflight spec committed before data access",
     "project conventions and data preflight spec"),
    ("sprint0", "Sprint 0: ingest and structural profile", "Sprint 0: ingest"),
    ("contract", "Metric contract committed before any business metric", "metric contract (before any business metric"),
    ("changes", "Metric contract Changes entry", "metrics.md Changes"),
    ("build", "Full dbt build from a clean tree", "Sprint 1 Step 3 evidence"),
    ("verify", "Independent verification against the marts", "Sprint 1 Step 4 evidence"),
    ("exports", "JSON exports with manifests", "Sprint 1 Step 5: JSON exports"),
)
WORKFLOW_FILES_DIRS = ("ai-workflow",)


def caught_category(text: str) -> str:
    lowered = text.lower()
    return next((label for label, words in CAUGHT_RULES if any(w in lowered for w in words)), "Other")


def parse_correction_log(text: str) -> dict[str, Any]:
    entries = []
    headings = list(ENTRY_HEADING.finditer(text))
    for i, h in enumerate(headings):
        body = text[h.end(): headings[i + 1].start() if i + 1 < len(headings) else len(text)]
        origin = re.search(r"^- \*\*Origin:\*\* (.+)$", body, re.MULTILINE)
        caught = re.search(r"^- \*\*How it was caught:\*\* (.+)$", body, re.MULTILINE)
        # An entry may carry a Public title for the site when its own title quotes a prohibited
        # term; the log itself stays as written (test_correction_log_titles_safe_for_export).
        public_title = re.search(r"^- \*\*Public title:\*\* (.+)$", body, re.MULTILINE)
        origin_text = origin.group(1) if origin else "n/a"
        if origin_text.startswith("n/a"):
            continue  # the "checks run with no error found" record is not an error
        origin_label = next((o for o in ORIGINS if origin_text.startswith(o)), "Other")
        title = public_title.group(1).strip() if public_title else h.group(3).strip()
        entries.append({"date": h.group(1), "phase": h.group(2), "title": title,
                        "origin": origin_label, "caught_by": caught_category(caught.group(1) if caught else "")})

    def count(key: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in entries:
            out[e[key]] = out.get(e[key], 0) + 1
        return out

    return {
        "source": "ai-workflow/correction-log.md",
        "n_entries": len(entries),
        "by_origin": count("origin"),
        "by_caught": count("caught_by"),
        "by_phase": count("phase"),
        "origin_rule": "origin is the entry's Origin line (Claude Code, Claude Chat, or Project owner)",
        "caught_rules": [{"category": label, "keywords": list(words)} for label, words in CAUGHT_RULES],
        "entries": entries,
    }


def git_timeline() -> list[dict[str, str]]:
    log = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "log", "--reverse", "--date=format-local:%Y-%m-%d %H:%M UTC",
         "--format=%H%x09%ad%x09%s"],
        capture_output=True, text=True, check=True, env={**os.environ, "TZ": "UTC"},
    ).stdout.splitlines()
    events = []
    for line in log:
        sha, date, subject = line.split("\t", 2)
        for event, label, prefix in MILESTONES:
            if subject.startswith(prefix):
                events.append({"event": event, "label": label, "sha": sha, "short_sha": sha[:7],
                               "date_utc": date, "subject": subject})
                break
    return events


def workflow_record() -> dict[str, Any]:
    files = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "--", *WORKFLOW_FILES_DIRS],
                           capture_output=True, text=True, check=True).stdout.split()
    return {
        "timeline": git_timeline(),
        "correction_log": parse_correction_log(CORRECTION_LOG.read_text(encoding="utf-8")),
        "workflow_files": [f for f in files if f.endswith(".md")],
    }


A_DIMENSION_ORDER = ("time_since_previous_purchase", "price_vs_first_purchase", "purchase_events_in_pair",
                     "time_by_price", "category_top")
# Groups the Changes entry defines (A item 3), with its labels and order. An empty group is exported as
# a zero row, so a page shows it as 0 rather than omitting it (for example "Same second", which D1 empties).
A_TIME_GROUPS = (("same_second", "Same second"), ("under_a_minute", "1 to 59 seconds later"),
                 ("a_minute_or_more", "1 minute or more later"))
A_PRICE_GROUPS = (("same_price", "Same price as the first purchase event"),
                  ("different_price", "Different price from the first purchase event"))
A_DEFINED_GROUPS = {
    "time_since_previous_purchase": [(k, label, i + 1) for i, (k, label) in enumerate(A_TIME_GROUPS)],
    "price_vs_first_purchase": [(k, label, i + 1) for i, (k, label) in enumerate(A_PRICE_GROUPS)],
    "purchase_events_in_pair": [("2", "2", 1), ("3", "3", 2), ("4_or_more", "4 or more", 3)],
    "time_by_price": [(f"{tk}|{pk}", f"{tl} · {pl}", 10 * (ti + 1) + pi + 1)
                      for ti, (tk, tl) in enumerate(A_TIME_GROUPS) for pi, (pk, pl) in enumerate(A_PRICE_GROUPS)],
}


def verification_summary(dataset_sha: str, prefixes: tuple[str, ...]) -> dict[str, Any]:
    """The R2 checks for one analysis from verify.json; halts unless all of them ran and matched."""
    if not VERIFY_JSON.exists():
        sys.exit(f"HALT: {VERIFY_JSON} missing; run python -m funnel.verify.")
    record = json.loads(VERIFY_JSON.read_text(encoding="utf-8"))
    if record["manifest"]["dataset_sha256"] != dataset_sha:
        sys.exit("HALT: verify.json was produced on a different dataset; rerun python -m funnel.verify.")
    checks = [c for c in record["checks"] if c["check"].startswith(prefixes)]
    if not checks or not all(c["match"] for c in checks):
        sys.exit(f"HALT: independent verification for {prefixes} is missing or has a mismatch.")
    return {"checks": len(checks), "all_match": True, "verify_git_commit_sha": record["manifest"]["git_commit_sha"],
            "verify_generated_at_utc": record["manifest"]["generated_at_utc"]}


def investigation_revenue_gap(con: duckdb.DuckDBPyConnection, dataset_sha: str) -> dict[str, Any]:
    """Analysis A (metrics.md Changes 2026-09-26, Sprint 2 investigations, A items 1-6)."""
    decomposition = rows(con, "SELECT * FROM wh.main_marts.mart_revenue_gap_decomposition")
    total = next(r for r in decomposition if r["dimension"] == "total")

    def dimension(name: str) -> list[dict[str, Any]]:
        cells = [r for r in decomposition if r["dimension"] == name]
        if name == "category_top":  # categories by value, largest first; others in the entry's order
            return sorted(cells, key=lambda r: (-float(r["repeat_purchase_value"]), r["group_key"]))
        present = {r["group_key"]: r for r in cells}
        unknown = set(present) - {k for k, _, _ in A_DEFINED_GROUPS[name]}
        if unknown:
            sys.exit(f"HALT: {name} has groups the Changes entry does not define: {sorted(unknown)}")
        return [present.get(key) or {
            "row_key": f"{name}:{key}", "dimension": name, "group_key": key, "group_label": label,
            "sort_order": order, "repeat_purchase_events": 0, "pairs": 0, "repeat_purchase_value": 0.0,
            "share_of_difference": 0.0, "top_10_pair_share": None,
            **{k: total[k] for k in ("revenue", "revenue_repeat_collapsed", "revenue_difference")},
        } for key, label, order in A_DEFINED_GROUPS[name]]

    return {
        "question": "Why are there two revenue figures?",
        "method_record": "ai-workflow/method-selection/A-revenue-gap.md",
        "contract": "docs/metrics.md, Changes 2026-09-26 (Sprint 2 investigations), A items 1-6",
        "totals": {k: total[k] for k in ("revenue", "revenue_repeat_collapsed", "revenue_difference",
                                          "repeat_purchase_events", "pairs", "repeat_purchase_value")},
        "dimensions": {name: dimension(name) for name in A_DIMENSION_ORDER},
        "thresholds": rows(con, "SELECT * FROM wh.main_marts.mart_revenue_gap_thresholds ORDER BY threshold_seconds"),
        "secondary_cases": {
            "exact_duplicate_rows": rows(con, """
                SELECT * FROM wh.main_marts.mart_duplicate_rows_breakdown ORDER BY event_type, group_size
            """),
            "cart_no_view_reconciliation": rows(con, "SELECT * FROM wh.main_marts.mart_cart_no_view_reconciliation")[0],
        },
        "independent_verification": verification_summary(dataset_sha, ("A:", "A-S1:", "A-S2:")),
    }


LATER_PURCHASES_JSON = CURRENT_EVIDENCE_DIR / "later_purchases.json"
# A fired stop rule blocks the export unless the owner resolved it; each resolution names its record.
RESOLVED_STOP_RULES = {
    "R3 agreement: the B1 7-day count share lies inside the all-pairs KM 7-day 95% interval": (
        "Owner decision H4, 2026-09-26 (option A): B1 kept at 'shows', scoped to its population; the "
        "disagreement is disclosed and the late-October cohort difference reported as a finding. Records: "
        "ai-workflow/escalations/2026-09-26-B-R3-agreement.md, ai-workflow/sprint-2-verification.md."),
}


def population_label(cutoff: str) -> str:
    """'sessions starting October 1-D, 2019 UTC' from a specification's ISO cutoff (owner decision H4, item 1)."""
    from datetime import datetime

    day = datetime.fromisoformat(cutoff)
    if (day.year, day.month) != (2019, 10):
        sys.exit(f"HALT: cutoff {cutoff} is outside October 2019.")
    return f"sessions starting October 1–{day.day}, 2019 UTC"


def investigation_later_purchases(con: duckdb.DuckDBPyConnection, dataset_sha: str) -> dict[str, Any]:
    """Analysis B (metrics.md Changes 2026-09-26, Sprint 2 investigations, B items 7-16). Point estimates and
    counts from the marts; intervals, Kaplan-Meier, and seed stability from funnel.later_purchases."""
    if not LATER_PURCHASES_JSON.exists():
        sys.exit(f"HALT: {LATER_PURCHASES_JSON} missing; run python -m funnel.later_purchases.")
    stats = json.loads(LATER_PURCHASES_JSON.read_text(encoding="utf-8"))
    if stats["manifest"]["dataset_sha256"] != dataset_sha:
        sys.exit("HALT: later_purchases.json was produced on a different dataset; rerun python -m funnel.later_purchases.")
    unresolved = [r["rule"] for r in stats["stop_rules"] if r["fired"] and r["rule"] not in RESOLVED_STOP_RULES]
    if unresolved:
        sys.exit(f"HALT: analysis B stop rules fired without an owner resolution {unresolved}; escalate first.")
    stop_rules = [{**r, "owner_resolution": RESOLVED_STOP_RULES.get(r["rule"]) if r["fired"] else None}
                  for r in stats["stop_rules"]]
    estimates = rows(con, "SELECT * FROM wh.main_marts.mart_later_purchase_estimates ORDER BY spec_key")
    for row in estimates:
        interval = stats["estimates"][row["spec_key"]]
        if abs(interval["count_share"] - float(row["count_share"])) > 1e-12:
            sys.exit(f"HALT: {row['spec_key']} intervals were computed on different point estimates.")
        row.update({k: interval[k] for k in ("count_interval", "value_interval", "resamples", "seed")})
        row["population"] = population_label(row["cutoff"])
    checks = rows(con, "SELECT * FROM wh.main_marts.mart_later_purchase_checks ORDER BY sort_order")
    check = {r["row_key"]: r["value"] for r in checks}
    b1 = next(r for r in estimates if r["spec_key"] == "B1")
    cohort = stats["cohort_diagnostic"]
    return {
        "question": "Were carted products purchased in a later session?",
        "method_record": "ai-workflow/method-selection/B-later-purchases.md",
        "contract": "docs/metrics.md, Changes 2026-09-26 (Sprint 2 investigations), B items 7-16",
        "estimates": estimates,
        "kaplan_meier": stats["kaplan_meier"],
        "kaplan_meier_population": "every carted pair with no purchase in the session, all of October 2019 UTC "
                                   "(no cutoff); censored at 2019-10-31 23:59:59 UTC",
        # Owner decision H4, item 1: the late-October cohort difference, reported as a finding in its own right.
        "cohort_difference": {
            "b1_population": b1["population"],
            "b1_count_share": b1["count_share"],
            "b1_count_interval": b1["count_interval"],
            "later_population": population_label(b1["cutoff"]).replace("October 1–", "after October "),
            "later_km_7_day": cohort["after_7_day_cutoff"]["count"],
            "later_km_7_day_interval": cohort["after_7_day_cutoff"]["count_interval"],
            "matched_km_7_day": cohort["by_7_day_cutoff"]["count"],
        },
        # Owner decision H4, item 3: disclosed beside the estimate; may reflect technical session splits.
        "within_1_hour_disclosure": {
            "share_of_followed_pairs": check[
                "diagnostic:share_of_followed_pairs_with_first_later_purchase_within_1_hour_of_latest_cart_event"],
            "population": b1["population"],
        },
        "seed_stability": stats["seed_stability"],
        "stop_rules": stop_rules,
        "dominance": stats["dominance"],
        "checks": checks,
        "statistics_run": {"git_commit_sha": stats["manifest"]["git_commit_sha"],
                           "generated_at_utc": stats["manifest"]["generated_at_utc"]},
        "independent_verification": verification_summary(dataset_sha, ("B1:", "B-all:")),
    }


def main() -> None:
    sha = require_dataset_hash_match()
    build = last_full_build(sha)
    if not WAREHOUSE.exists():
        sys.exit(f"HALT: {WAREHOUSE} missing; run python -m funnel.build first.")
    con = connect()  # the shared settings (funnel.common): memory limit, threads, insertion order, spill dir
    con.execute(f"ATTACH '{WAREHOUSE.as_posix()}' AS wh (READ_ONLY)")
    metrics_text = METRICS_MD.read_text(encoding="utf-8")

    kpi_rows = rows(con, "SELECT * FROM wh.main_marts.mart_kpis_daily ORDER BY period_type, period_start")
    dq_rows = rows(con, "SELECT * FROM wh.main_marts.mart_data_quality ORDER BY sort_order")
    dq = {r["metric_key"]: r for r in dq_rows}
    category_rows = rows(con, """
        SELECT * FROM wh.main_marts.mart_funnel_category
        ORDER BY category_level, carted_value_with_no_observed_purchase DESC, category_key
    """)
    exports = {
        "kpis.json": {
            "month": next(r for r in kpi_rows if r["period_type"] == "month"),
            "daily": [r for r in kpi_rows if r["period_type"] == "day"],
        },
        "funnel_category.json": {
            "category_top": [r for r in category_rows if r["category_level"] == "category_top"],
            "category_code": [r for r in category_rows if r["category_level"] == "category_code"],
            "unknown_shares": {k: dq[k]["value"] for k in (
                "unknown_category_event_share", "unknown_category_revenue_share")},
            "disclosures": [
                "One session can enter several category funnels, so category funnel counts do not sum to "
                "session totals.",
                "Category funnel counts cover (session, category) pairs entered by a view in the category. "
                "Category revenue covers all purchase events in the category, so category revenues sum to "
                "total revenue.",
                "Carted value with no observed purchase in this session covers all carted pairs in valid "
                "sessions, grouped by the category on each pair's latest cart event, with no view "
                "requirement, so its population differs from the category funnel's.",
                "Category codes that map to more than one category_id are merged under one code.",
            ],
        },
        "purchase_paths.json": {
            "rows": rows(con, "SELECT * FROM wh.main_marts.mart_purchase_paths ORDER BY purchase_path"),
        },
        "data_quality.json": {"rows": dq_rows},
        "metrics_index.json": {"metrics": parse_metrics_index(metrics_text)},
        "data_story.json": data_story(con, metrics_text, dq),
        "workflow.json": workflow_record(),
        "investigation_revenue_gap.json": investigation_revenue_gap(con, sha),
        "investigation_later_purchases.json": investigation_later_purchases(con, sha),
    }
    # One manifest for the whole run, taken before the first write: once a file is written the
    # tree is dirty, so a per-file manifest would misreport every file after the first.
    run_manifest = manifest(SCRIPT, sha)
    for name, payload in exports.items():
        write_json(WEB_DATA / name, {"manifest": run_manifest, "pipeline_build": build, **payload})
        print(f"Wrote {WEB_DATA / name}")


if __name__ == "__main__":
    main()
