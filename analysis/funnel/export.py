"""Write the site's JSON exports from the dbt marts, each with a provenance manifest.

Run: python -m funnel.export

Reads data/warehouse.duckdb (read-only) after a passing `python -m funnel.build`, and writes
web/public/data/: kpis.json, funnel_category.json, purchase_paths.json, data_quality.json,
metrics_index.json (parsed from docs/metrics.md), and data_story.json (the /data page).
Halts if the dataset hash differs from docs/data-source.md, if the last full dbt build did not
pass on this dataset, or if the reconciliation chain in data_story.json does not sum.
"""

from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from funnel.common import (
    DATA_DIR,
    DOCS_DIR,
    EVIDENCE_DIR,
    KAGGLE_URL,
    REPO_ROOT,
    manifest,
    require_dataset_hash_match,
    write_json,
)
from funnel.ingest import KAGGLE_LICENSE_FIELD, PUBLISHER_USAGE_STATEMENT, REES46_URL

SCRIPT = "funnel.export"
WAREHOUSE = DATA_DIR / "warehouse.duckdb"
WEB_DATA = REPO_ROOT / "web" / "public" / "data"
METRICS_MD = DOCS_DIR / "metrics.md"
BUILD_RUNS = REPO_ROOT / "ai-workflow" / "evidence" / "sprint-1" / "dbt_build_runs.json"
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


def main() -> None:
    sha = require_dataset_hash_match()
    build = last_full_build(sha)
    if not WAREHOUSE.exists():
        sys.exit(f"HALT: {WAREHOUSE} missing; run python -m funnel.build first.")
    con = duckdb.connect()
    con.execute(f"ATTACH '{WAREHOUSE.as_posix()}' AS wh (READ_ONLY)")
    metrics_text = METRICS_MD.read_text(encoding="utf-8")

    kpi_rows = rows(con, "SELECT * FROM wh.main_marts.mart_kpis_daily ORDER BY period_type, period_start")
    dq_rows = rows(con, "SELECT * FROM wh.main_marts.mart_data_quality ORDER BY sort_order")
    dq = {r["metric_key"]: r for r in dq_rows}
    category_rows = rows(con, """
        SELECT * FROM wh.main_marts.mart_funnel_category ORDER BY category_level, carted_value_with_no_observed_purchase DESC
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
    }
    # One manifest for the whole run, taken before the first write: once a file is written the
    # tree is dirty, so a per-file manifest would misreport every file after the first.
    run_manifest = manifest(SCRIPT, sha)
    for name, payload in exports.items():
        write_json(WEB_DATA / name, {"manifest": run_manifest, "pipeline_build": build, **payload})
        print(f"Wrote {WEB_DATA / name}")


if __name__ == "__main__":
    main()
