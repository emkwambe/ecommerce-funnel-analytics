import type { MetricEntry } from "@/lib/data";

export const th = "px-2 py-2 text-left font-medium text-muted sm:px-3";
export const td = "px-2 py-2 sm:px-3";
export const tableWrap = "overflow-x-auto rounded-lg border border-line bg-surface";

export function Section({ n, title, id, children }: { n: number; title: string; id?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="space-y-4">
      <h2 className="text-xl font-semibold tracking-tight">
        <span className="text-muted">{n}.</span> {title}
      </h2>
      {children}
    </section>
  );
}

export function PageHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="space-y-3">
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      {children && <div className="max-w-2xl space-y-2 text-muted">{children}</div>}
    </header>
  );
}

/** Names the exported JSON fields an interpretive sentence rests on (CLAUDE.md rule 2). */
export function Sources({ fields }: { fields: string[] }) {
  return (
    <p className="text-xs text-muted">
      Sources:{" "}
      {fields.map((f, i) => (
        <span key={f}>
          {i > 0 && "; "}
          {/* Field paths can be long and have no spaces; let them wrap so they never widen a 390 px page. */}
          <code className="[overflow-wrap:anywhere]">{f}</code>
        </span>
      ))}
    </p>
  );
}

/** A headline number with its count basis and its definition from docs/metrics.md. */
export function Kpi({ entry, value, basis, label }: { entry: MetricEntry; value: string; basis?: string; label?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-line bg-surface p-4">
      <div className="text-sm text-muted">{label ?? entry.display_label}</div>
      <div className="num text-2xl font-semibold tracking-tight">{value}</div>
      {basis && <div className="num text-xs text-muted">{basis}</div>}
      <details className="mt-1 text-xs text-muted">
        <summary className="cursor-pointer select-none hover:text-ink">Definition</summary>
        <p className="mt-1 leading-relaxed">
          {entry.definition}{" "}
          <span className="whitespace-nowrap">
            (<a className="text-accent underline" href={`/metrics#section-${entry.section.toLowerCase()}`}>metrics.md §{entry.section}</a>)
          </span>
        </p>
      </details>
    </div>
  );
}
