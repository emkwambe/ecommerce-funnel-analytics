import type { Metadata } from "next";
import { getWorkflow } from "@/lib/data";
import { COMMITS_URL, blobUrl, commitUrl, fmtInt, treeUrl } from "@/lib/format";
import { InlineText, PageHeader, Sources } from "../ui";

export const metadata: Metadata = { title: "How it's built · E-commerce Funnel Analytics" };

const ROLES = [
  {
    title: "Planning in chat",
    body: "The business question, the sprint briefs, and the metric contract were drafted in conversation with Claude and committed as files. Every decision the structural profile forced, and every gap Claude Code found in the contract, was settled by the human owner in writing before the affected metric was computed.",
  },
  {
    title: "Execution in Claude Code",
    body: "Claude Code carried out each sprint brief inside the repository under binding rules: no hand-typed numbers, a metric lock until the contract was committed, a memory gate before heavy runs, and a manifest on every export. It stopped and asked whenever the contract was unclear or a check failed.",
  },
  {
    title: "Verification by tests and human review",
    body: "The dbt pipeline carries schema, reconciliation, and tie tests, and every build must run all expected tests. A separate script recomputes the headline metrics from the raw file without dbt and matches them exactly. Guard tests enforce the naming rules and the no-row-level-data rule, and every catch is logged. The project owner reviewed the results and signed off each published claim.",
  },
];

function Bars({ counts, total }: { counts: Record<string, number>; total: number }) {
  return (
    <ul className="space-y-2">
      {Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .map(([label, n]) => (
          <li key={label} className="text-sm">
            <div className="flex justify-between gap-3">
              <span>{label}</span>
              <span className="num text-muted">{fmtInt(n)}</span>
            </div>
            <div className="mt-1 h-2 rounded bg-grid" aria-hidden>
              <div className="h-2 rounded bg-series-1" style={{ width: `${(n / total) * 100}%` }} />
            </div>
          </li>
        ))}
    </ul>
  );
}

export default function HowItsBuiltPage() {
  const record = getWorkflow();
  const log = record.correction_log;
  const sprintFiles = record.workflow_files.filter((f) => /sprint-\d+\.md$/.test(f));
  const verificationFiles = record.workflow_files.filter((f) => /verification\.md$/.test(f));

  return (
    <div className="space-y-12">
      <PageHeader title="How it's built">
        <p>
          A case study in using an AI coding agent for analysis that can be checked. The order in which things happened is
          the evidence, so the timeline below is read from the repository&apos;s git history rather than written by hand.
        </p>
      </PageHeader>

      {/* Owner decision v1.1.5: timeline left and tech stack right (sticky) on wide screens; on narrow screens one
          column, the stack first as a compact summary. Every item and version comes from workflow.json. */}
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,19rem)] lg:gap-8">
      <aside id="tech-stack" className="space-y-3 lg:sticky lg:top-6 lg:order-last lg:self-start" aria-labelledby="tech-stack-heading">
        <h2 id="tech-stack-heading" className="text-xl font-semibold tracking-tight">Tech stack</h2>
        {/* Owner decision (PR #21, option (b)): one compact column at every width. Each layer lists its tools with
            versions; each tool's role is available on demand. */}
        <div className="space-y-2 text-sm">
          {record.tech_stack.groups.map((g) => (
            <details key={g.group} className="rounded-lg border border-line bg-surface px-3 py-2">
              <summary className="cursor-pointer [overflow-wrap:anywhere]">
                <span className="font-medium">{g.group}:</span>{" "}
                <span className="text-muted">
                  {g.items.map((i) => (i.version ? `${i.name} ${i.version}` : i.name)).join(" · ")}
                </span>
              </summary>
              <ul className="mt-2 space-y-1 text-xs text-muted">
                {g.items.map((i) => (
                  <li key={i.name}><span className="text-ink">{i.name}</span>: <InlineText text={i.role} /></li>
                ))}
              </ul>
            </details>
          ))}
        </div>
        <Sources fields={[`workflow.json: tech_stack (versions read from ${record.tech_stack.sources.join(", ")})`]} />
      </aside>

      <section className="min-w-0 space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">Timeline from git</h2>
        <p className="text-sm">
          <a className="text-accent underline" href={COMMITS_URL} data-testid="full-history-link">
            View the full history on GitHub →
          </a>
        </p>
        <ol className="relative space-y-4 border-l border-line pl-5">
          {record.timeline.map((e) => (
            <li key={e.sha} className="relative">
              <span aria-hidden className="absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full bg-series-1 ring-2 ring-bg" />
              <div className="text-sm font-medium">{e.label}</div>
              <div className="num text-xs text-muted">
                <a className="font-mono text-accent underline" href={commitUrl(e.sha)}>{e.short_sha}</a> · {e.date_utc}
              </div>
              <div className="text-xs text-muted">{e.subject}</div>
            </li>
          ))}
        </ol>
      </section>
      </div>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">Division of labor</h2>
        <ol className="grid gap-4 sm:grid-cols-3">
          {ROLES.map((r) => (
            <li key={r.title} className="rounded-lg border border-line bg-surface p-5">
              <h3 className="font-semibold">{r.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{r.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">The correction log, by the numbers</h2>
        <p className="max-w-2xl text-muted">
          {fmtInt(log.n_entries)} errors were caught and recorded, each committed together with its fix. The counts below
          are parsed from <a className="text-accent underline" href={blobUrl(log.source)}>{log.source}</a> by code, not
          typed.
        </p>
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-3 rounded-lg border border-line bg-surface p-4">
            <h3 className="text-sm font-semibold">Where the error came from</h3>
            <Bars counts={log.by_origin} total={log.n_entries} />
          </div>
          <div className="space-y-3 rounded-lg border border-line bg-surface p-4">
            <h3 className="text-sm font-semibold">How it was caught</h3>
            <Bars counts={log.by_caught} total={log.n_entries} />
          </div>
        </div>
        <ul className="space-y-1 text-sm">
          {log.entries.map((e) => (
            <li key={`${e.date}-${e.title}`}>
              <span className="num text-muted">{e.phase}</span> · {e.title}{" "}
              <span className="text-xs text-muted">({e.origin} · {e.caught_by})</span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">
          Classification: {log.origin_rule}. How-caught categories are keyword rules, first match wins:{" "}
          {log.caught_rules.map((r) => `${r.category} (${r.keywords.join(", ")})`).join("; ")}.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold tracking-tight">Read the record</h2>
        <ul className="space-y-1 text-sm">
          {sprintFiles.map((f) => (
            <li key={f}><a className="text-accent underline" href={blobUrl(f)}>Sprint brief: {f.split("/").pop()}</a></li>
          ))}
          {verificationFiles.map((f) => (
            <li key={f}><a className="text-accent underline" href={blobUrl(f)}>Verification evidence: {f.split("/").pop()}</a></li>
          ))}
          <li><a className="text-accent underline" href={blobUrl("ai-workflow/correction-log.md")}>The full correction log</a></li>
          <li><a className="text-accent underline" href={blobUrl("docs/metrics.md")}>docs/metrics.md: the metric contract</a></li>
          <li><a className="text-accent underline" href={blobUrl("CLAUDE.md")}>CLAUDE.md: the rules Claude Code works under</a></li>
          <li><a className="text-accent underline" href={treeUrl("ai-workflow")}>Everything in ai-workflow/, including build and verification evidence</a></li>
        </ul>
      </section>
    </div>
  );
}
