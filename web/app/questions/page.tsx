import type { Metadata } from "next";
import Link from "next/link";
import { type ClosingQuestion, closingSources, closingText, getClosing } from "@/lib/data";
import { PageHeader, Sources, td, th } from "../ui";

export const metadata: Metadata = { title: "Questions worth asking next · E-commerce Funnel Analytics" };

// Every text on this page comes from closing.json (python -m funnel.closing, generated from the closing report);
// figures are resolved from the export's figures table, never typed.

function Evidence({ q }: { q: ClosingQuestion }) {
  const { href, label, external } = q.evidence;
  const cls = "text-sm text-accent underline [overflow-wrap:anywhere]";
  return external ? (
    <a className={cls} href={href}>
      Evidence: {label}
    </a>
  ) : (
    <Link className={cls} href={href}>
      Evidence: {label}
    </Link>
  );
}

export default function QuestionsPage() {
  const c = getClosing();
  const f = c.figures;
  const byNumber = new Map(c.questions.map((q) => [q.n, q]));
  const groupLabel = new Map(c.groups.map((g) => [g.key, g.label]));
  const texts = [c.question_1.text, ...c.questions.flatMap((q) => [q.question, q.card_line, q.why, q.who])];

  return (
    <div className="space-y-12">
      <PageHeader title="Questions worth asking next">
        <p>
          The project is closed. These are the questions its data can&apos;t answer, grouped by who can answer them.
          Each card links to the page that holds its evidence.
        </p>
      </PageHeader>

      <section className="space-y-2 rounded-lg border border-accent/40 bg-accent/10 p-4" aria-label="Start here">
        <p className="font-semibold">{c.question_1.lead}</p>
        <p>{closingText(c.question_1.text, f)}</p>
      </section>

      {c.groups.map((g) => (
        <section key={g.key} id={`group-${g.key.replaceAll("_", "-")}`} className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">{g.label}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {g.questions.map((n) => {
              const q = byNumber.get(n);
              if (!q) throw new Error(`closing.json: group ${g.key} lists a missing question ${n}`);
              return (
                <article
                  key={q.n}
                  className={`flex flex-col gap-2 rounded-lg border bg-surface p-4 ${q.start_here ? "border-accent" : "border-line"}`}
                >
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                    <span>Question {q.n}</span>
                    {q.start_here && (
                      <span className="rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 font-medium text-accent">
                        Start here
                      </span>
                    )}
                  </div>
                  <h3 className="font-medium leading-snug">{closingText(q.question, f)}</h3>
                  <p className="text-sm text-muted">{closingText(q.card_line, f)}</p>
                  <div className="mt-auto pt-1">
                    <Evidence q={q} />
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ))}

      <section id="all-questions" className="space-y-3">
        <h2 className="text-xl font-semibold tracking-tight">All {c.questions.length} questions</h2>
        {/* Wider screens: a fixed-layout table that wraps inside its columns. Phones: one block per question. Neither
            scrolls sideways at 390 px. */}
        <div className="hidden rounded-lg border border-line bg-surface sm:block">
          <table className="w-full table-fixed text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className={`${th} w-10`}>#</th>
                <th className={th}>Question</th>
                <th className={th}>Why it matters</th>
                <th className={th}>Who can answer</th>
              </tr>
            </thead>
            <tbody>
              {c.questions.map((q) => (
                <tr key={q.n} className="border-b border-line align-top last:border-0">
                  <td className={`${td} num`}>{q.n}</td>
                  <td className={`${td} [overflow-wrap:anywhere]`}>{closingText(q.question, f)}</td>
                  <td className={`${td} [overflow-wrap:anywhere]`}>{closingText(q.why, f)}</td>
                  <td className={`${td} [overflow-wrap:anywhere]`}>
                    {closingText(q.who, f)} <span className="text-muted">({groupLabel.get(q.group)})</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ol className="space-y-3 sm:hidden">
          {c.questions.map((q) => (
            <li key={q.n} className="space-y-1 rounded-lg border border-line bg-surface p-3 text-sm">
              <p className="font-medium">
                {q.n}. {closingText(q.question, f)}
              </p>
              <p>
                <span className="text-muted">Why it matters: </span>
                {closingText(q.why, f)}
              </p>
              <p>
                <span className="text-muted">Who can answer: </span>
                {closingText(q.who, f)} ({groupLabel.get(q.group)})
              </p>
            </li>
          ))}
        </ol>
      </section>

      <Sources
        fields={[
          ...closingSources(texts, f),
          "closing.json: question_1, groups[], questions[] (generated from docs/closing-report.md and the owner-approved ai-workflow/closing-content.md)",
        ]}
      />
    </div>
  );
}
