"""Generate ai-workflow/STATE.md (trio-sprint-workflow v2.4.0, `assets/templates/STATE.md`, `references/state-sync.md`).

Two modes (trio-sprint-workflow v2.4.1, state sync §2a, Governed tier):

    python -m funnel.state --print
        Live state from the current git and gh state, printed and never written or committed. Use it for every
        session handshake. Open PRs become "waiting on the owner"; a stale committed snapshot is reported.

    python -m funnel.state --now "..." --waiting "H8|Merge PR #n|https://..." --next "owner: ..."
        Writes the committed snapshot, inside each PR (it describes the state as of that PR). Never open a PR only
        to refresh it.

Derived from code and git: mode and tier (CLAUDE.md), live release (latest tag and the production URL in the
latest smoke evidence), last merged and open PRs (`gh`), working tree (`git status`), open uncertainties
and accepted limitations (`ai-workflow/uncertainty-register.md`), and the last five owner decisions (the owner-decisions table of the latest
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
    # Split at a sentence end only; colons and semicolons often introduce the substance of the sentence.
    first = re.split(r"(?<=[.?])\s", text, maxsplit=1)[0]
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
    # STATE.md itself is ignored: regenerating it would otherwise always report a dirty tree.
    dirty = any(not line.endswith("ai-workflow/STATE.md")
                for line in _run("git", "-C", str(REPO_ROOT), "status", "--porcelain").splitlines())
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
            status = cells[8].split(" (")[0].strip()
            out.append(f"{cells[0]}: {_one_line(cells[2], 140)} ({cells[4]}; {status})")
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


def waiting_from_open_prs(open_prs: list[dict]) -> list[str]:
    """Print mode: every open PR is waiting on the owner's merge (H8)."""
    return [f"H8|Merge PR #{p['number']} ({p['title']})|{p['url']}" for p in open_prs]


def snapshot_discrepancies(snapshot: str, pr_states: dict[int, str]) -> list[str]:
    """Print mode: where the committed snapshot (a per-PR record, trio v2.4.1 state sync §2a) no longer matches
    GitHub. A PR the snapshot lists as waiting that is no longer open is expected after its merge; it is reported
    so the handshake reads the live state, not the snapshot."""
    waiting = snapshot.split("## Waiting on the owner", 1)[-1].split("\n## ", 1)[0]
    out = []
    for number in sorted({int(n) for n in re.findall(r"PR #(\d+)", waiting)}):
        state = pr_states.get(number, "UNKNOWN")
        if state != "OPEN":
            out.append(f"The committed snapshot lists PR #{number} as waiting on the owner; GitHub shows it {state}"
                       " (expected after its merge: the snapshot is a per-PR record).")
    return out


def render(now: str, waiting: list[str], next_action: str, discrepancies: list[str], live: bool = False) -> str:
    mode, tier = mode_and_tier()
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    waiting_rows = [w.split("|", 2) for w in waiting]
    kind = ("live state, printed by `python -m funnel.state --print` from the current git and gh state; nothing"
            " was written or committed. Use this, not the committed snapshot, for the session handshake."
            if live else
            "a per-PR snapshot, written by `python -m funnel.state` inside the PR that commits it. After that PR"
            " merges, its waiting line is expected to be stale; `python -m funnel.state --print` gives the live"
            " state.")
    lines = [
        "# STATE — ecommerce-funnel-analytics",
        "",
        f"Generated {generated} by Claude Code from git, gh, and the working context: {kind}"
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
        "## Open uncertainties and accepted limitations (material or critical)",
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


def committed_now() -> str:
    """The "Now" line of the committed snapshot, for print mode when --now is not given."""
    if not OUT.exists():
        return "(no committed snapshot)"
    section = OUT.read_text(encoding="utf-8").split("## Now", 1)[-1].split("\n## ", 1)[0].strip()
    return section or "(empty)"


def live_inputs(now: str | None, waiting: list[str], next_action: str | None,
                discrepancies: list[str]) -> tuple[str, list[str], str, list[str]]:
    """Print mode: fill what the working context did not give from the current git and gh state."""
    open_prs = json.loads(_run("gh", "pr", "list", "-R", REPO, "--state", "open", "--json", "number,title,url"))
    waiting = waiting + [w for w in waiting_from_open_prs(open_prs) if w not in waiting]
    if OUT.exists():
        snapshot = OUT.read_text(encoding="utf-8")
        numbers = {int(n) for n in re.findall(r"PR #(\d+)", snapshot.split("## Waiting on the owner", 1)[-1]
                                              .split("\n## ", 1)[0])}
        states = {n: _run("gh", "pr", "view", str(n), "-R", REPO, "--json", "state", "--jq", ".state")
                  for n in numbers}
        discrepancies = discrepancies + snapshot_discrepancies(snapshot, states)
    now = now or f"Not given at this handshake. The committed snapshot says: {committed_now()}"
    if not next_action:
        next_action = ("owner: " + "; ".join(f"merge PR #{p['number']}" for p in open_prs)) if open_prs \
            else "Not given at this handshake: nothing is waiting on the owner in GitHub."
    return now, waiting, next_action, discrepancies


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Regenerate ai-workflow/STATE.md, or print the live state (--print).")
    p.add_argument("--print", action="store_true", dest="print_only",
                   help="print the live state from git and gh; write and commit nothing (use for handshakes)")
    p.add_argument("--now", help="Sprint and step, with a one-line goal (required unless --print)")
    p.add_argument("--waiting", action="append", default=[], help='"H|question|link", repeatable')
    p.add_argument("--next", dest="next_action", help='"who: what" (required unless --print)')
    p.add_argument("--discrepancy", action="append", default=[], help="a known chat/repo discrepancy, repeatable")
    a = p.parse_args(argv)
    for w in a.waiting:
        if w.count("|") != 2:
            raise SystemExit(f'--waiting must be "H|question|link": {w!r}')
    if a.print_only:
        print(render(*live_inputs(a.now, a.waiting, a.next_action, a.discrepancy), live=True))
        return
    if not a.now or not a.next_action:
        raise SystemExit("--now and --next are required when writing the snapshot (omit them only with --print)")
    write_text(OUT, render(a.now, a.waiting, a.next_action, a.discrepancy))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
