"""Generate ai-workflow/STATE.md (trio-sprint-workflow v2.4.0, `assets/templates/STATE.md`, `references/state-sync.md`).

Run at every stop, merge, deploy, and tag:

    python -m funnel.state --now "Sprint 2 closed" --waiting "H8|Merge PR #13|https://..." --next "owner: merge PR #13"

Derived from code and git: mode and tier (CLAUDE.md), live release (latest tag and the production URL in the
latest smoke evidence), last merged and open PRs (`gh`), working tree (`git status`), open uncertainties
(`ai-workflow/uncertainty-register.md`), and the last five owner decisions (the owner-decisions table of the latest
`ai-workflow/sprint-*-verification.md`). The working-context fields that only the executor knows at a stop (--now,
--waiting, --next, --discrepancy) are passed in explicitly, never guessed. The repo wins over this file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

from funnel.common import CURRENT_EVIDENCE_DIR, REPO_ROOT, write_text

OUT = REPO_ROOT / "ai-workflow" / "STATE.md"
REPO = "emkwambe/ecommerce-funnel-analytics"


def _run(*args: str) -> str:
    return subprocess.run(list(args), capture_output=True, text=True, check=True, encoding="utf-8").stdout.strip()


def _one_line(text: str, limit: int = 160) -> str:
    text = re.sub(r"\*\*|`", "", text).strip()
    first = re.split(r"(?<=[.;:])\s", text, maxsplit=1)[0]
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def mode_and_tier() -> tuple[str, str]:
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    mode = re.search(r"^Mode:\s*(\w+)", text, re.MULTILINE)
    tier = re.search(r"^Tier:\s*(\w+)", text, re.MULTILINE)
    return (mode.group(1) if mode else "undeclared"), (tier.group(1) if tier else "undeclared")


def live_release() -> str:
    tag = _run("git", "-C", str(REPO_ROOT), "describe", "--tags", "--abbrev=0", "origin/main")
    sha = _run("git", "-C", str(REPO_ROOT), "rev-list", "-n", "1", "--abbrev-commit", tag)
    smokes = sorted(CURRENT_EVIDENCE_DIR.glob("smoke_production*.txt"), key=lambda p: p.stat().st_mtime)
    url = "unknown"
    if smokes:
        m = re.search(r"Smoke test against (\S+)", smokes[-1].read_text(encoding="utf-8"))
        url = m.group(1) if m else url
    return f"{url} at {tag} ({sha})"


def repo_line() -> str:
    merged = json.loads(_run("gh", "pr", "list", "-R", REPO, "--state", "merged", "--limit", "1",
                             "--json", "number,mergeCommit,mergedAt"))
    open_prs = json.loads(_run("gh", "pr", "list", "-R", REPO, "--state", "open", "--json", "number,title"))
    dirty = bool(_run("git", "-C", str(REPO_ROOT), "status", "--porcelain"))
    last = (f"PR #{merged[0]['number']} ({merged[0]['mergeCommit']['oid'][:7]}, {merged[0]['mergedAt']})"
            if merged else "none")
    opened = ", ".join(f"#{p['number']} {p['title']}" for p in open_prs) or "none"
    return f"Last merged: {last} · Open PRs: {opened} · Working tree: {'dirty' if dirty else 'clean'}"


def open_uncertainties() -> list[str]:
    text = (REPO_ROOT / "ai-workflow" / "uncertainty-register.md").read_text(encoding="utf-8").split("## Resolved")[0]
    out = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 9 and re.fullmatch(r"U\d+", cells[0]) and not cells[8].lower().startswith("resolved"):
            out.append(f"{cells[0]}: {_one_line(cells[2], 140)} ({cells[4]}; {_one_line(cells[8], 60)})")
    return out


def recent_decisions(n: int = 5) -> list[list[str]]:
    files = sorted((REPO_ROOT / "ai-workflow").glob("sprint-*-verification.md"))
    rows = []
    for path in files:
        head = path.read_text(encoding="utf-8").split("<!-- GENERATED BELOW", 1)[0]
        for line in head.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 4 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]):
                rows.append([cells[0], _one_line(cells[1], 40), _one_line(cells[2]),
                             f"{path.relative_to(REPO_ROOT).as_posix()}"])
    return rows[-n:]


def render(now: str, waiting: list[str], next_action: str, discrepancies: list[str]) -> str:
    mode, tier = mode_and_tier()
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    waiting_rows = [w.split("|", 2) for w in waiting]
    lines = [
        "# STATE — ecommerce-funnel-analytics",
        "",
        f"Generated {generated} by Claude Code (`python -m funnel.state`) from git, gh, and the working context."
        " The repo wins over this file if they disagree. Regenerate it; don't hand-edit.",
        "",
        f"**Mode:** {mode} · **Tier:** {tier} · **Live:** {live_release()}",
        "",
        "## Now",
        now,
        "",
        "## Waiting on the owner",
        "| H | Question (one line) | Link |",
        "|---|---|---|",
        *([f"| {h} | {q} | {link} |" for h, q, link in waiting_rows] or ["| — | nothing waiting | — |"]),
        "",
        "## Open uncertainties (material or critical)",
        *([f"- {u}" for u in open_uncertainties()] or ["- none"]),
        "",
        "## Recent owner decisions",
        "| Date | H | Decision | Recorded in |",
        "|---|---|---|---|",
        *[f"| {d} | {h} | {text} | `{where}` |" for d, h, text, where in recent_decisions()],
        "",
        "## Repo",
        repo_line(),
        "",
        "## Next action",
        next_action,
        "",
        "## Known chat/repo discrepancies",
        *([f"- {d}" for d in discrepancies] or ["none"]),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Regenerate ai-workflow/STATE.md")
    p.add_argument("--now", required=True, help="Sprint and step, with a one-line goal")
    p.add_argument("--waiting", action="append", default=[], help='"H|question|link", repeatable')
    p.add_argument("--next", required=True, dest="next_action", help='"who: what"')
    p.add_argument("--discrepancy", action="append", default=[], help="a known chat/repo discrepancy, repeatable")
    a = p.parse_args(argv)
    for w in a.waiting:
        if w.count("|") != 2:
            raise SystemExit(f'--waiting must be "H|question|link": {w!r}')
    write_text(OUT, render(a.now, a.waiting, a.next_action, a.discrepancy))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
