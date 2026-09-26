import type { Metadata } from "next";
import { getDataStory } from "@/lib/data";
import { blobUrl, fmtInt } from "@/lib/format";
import { PageHeader, Section, Sources, tableWrap, td, th } from "../ui";

export const metadata: Metadata = { title: "Data · E-commerce Funnel Analytics" };

const sectionLink = (section: string) => `/metrics#section-${section.toLowerCase()}`;

export default function DataPage() {
  const s = getDataStory();
  const { source, contents, reconciliation: r } = s;
  const chain = [
    { label: "Raw rows in the file", n: r.raw_rows, kind: "total" },
    { label: "Exact duplicate rows removed", n: -r.exact_duplicate_rows_removed, kind: "step" },
    { label: "Deduplicated events", n: r.deduplicated_events, kind: "total" },
    { label: "Events with a null session, excluded", n: -r.null_session_events_excluded, kind: "step" },
    { label: `Events in the ${fmtInt(r.multi_user_sessions_excluded)} sessions with more than one user_id, excluded`, n: -r.events_in_multi_user_sessions_excluded, kind: "step" },
    { label: "Events in valid sessions", n: r.valid_session_events, kind: "total" },
  ];

  return (
    <div className="space-y-12">
      <PageHeader title="The data">
        <p>
          Where the event log comes from, what one row is, what the structural profile found before any metric was
          defined, how each finding was decided, and how raw rows reconcile to the sessions and orders on this site.
        </p>
      </PageHeader>

      <Section n={1} title="Source">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
          <dt className="text-muted">Dataset</dt>
          <dd>{source.title}; {source.publisher}.</dd>
          <dt className="text-muted">Obtained with</dt>
          <dd>{source.obtained_with}.</dd>
          <dt className="text-muted">File</dt>
          <dd><code>{source.file_name}</code>, <span className="num">{fmtInt(source.size_bytes)}</span> bytes, retrieved {source.retrieved_at_utc}.</dd>
          <dt className="text-muted">SHA-256</dt>
          <dd><code className="break-all">{source.sha256}</code></dd>
          <dt className="text-muted">License</dt>
          <dd>
            Kaggle license field <code>{source.license_field}</code> (rights reserved). The publisher states: “
            {source.publisher_usage_statement}” This project relies on that statement and publishes aggregates only.
          </dd>
          <dt className="text-muted">Attribution</dt>
          <dd>
            <a className="text-accent underline" href={source.kaggle_url}>Kaggle dataset page</a> ·{" "}
            <a className="text-accent underline" href={source.rees46_url}>REES46 Marketing Platform</a>
          </dd>
        </dl>
        <Sources fields={["data_story.json: source (from ai-workflow/evidence/sprint-0/ingest.json and docs/data-source.md)"]} />
      </Section>

      <Section n={2} title="Contents">
        <p className="text-sm">
          {contents.grain} The file holds <span className="num">{fmtInt(contents.raw_rows)}</span> rows from{" "}
          {contents.min_event_time_utc} to {contents.max_event_time_utc} UTC, with{" "}
          <span className="num">{fmtInt(contents.distinct_counts.user_id)}</span> users,{" "}
          <span className="num">{fmtInt(contents.distinct_counts.user_session)}</span> sessions, and{" "}
          <span className="num">{fmtInt(contents.distinct_counts.product_id)}</span> products.{" "}
          {contents.order_or_transaction_id_exists ? "It has an order or transaction ID column." : "It has no order or transaction ID."}
        </p>
        <div className={tableWrap}>
          <table className="w-full text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className={th}>Event type</th>
                <th className={`${th} text-right`}>Raw rows</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(contents.event_type_counts).map(([type, n]) => (
                <tr key={type} className="border-b border-line last:border-0">
                  <td className={td}><code>{type}</code></td>
                  <td className={`${td} num text-right`}>{fmtInt(n)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted">Columns: {contents.columns.map((c) => c).join(", ")}.</p>
        <Sources fields={["data_story.json: contents (from the Sprint 0 profile.json)"]} />
      </Section>

      <Section n={3} title="What the profile found first">
        <p className="text-muted">
          The Sprint 0 structural profile ran before any metric was defined, on raw rows. Each finding forced a decision.
        </p>
        <div className={tableWrap}>
          <table className="w-full text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className={th}>Finding</th>
                <th className={`${th} text-right`}>Count</th>
              </tr>
            </thead>
            <tbody>
              {s.pre_analysis_findings.map((f) => (
                <tr key={f.profile_field} className="border-b border-line last:border-0">
                  <td className={td}>{f.finding}</td>
                  <td className={`${td} num text-right`}>{fmtInt(f.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Sources fields={["data_story.json: pre_analysis_findings[].count (profile_field names the profile.json path)"]} />
      </Section>

      <Section n={4} title="Decisions">
        <ul className="space-y-2 text-sm">
          {s.decisions.map((d) => (
            <li key={d.id}>
              <span className="font-medium">{d.id}. {d.title}.</span> {d.summary}{" "}
              <a className="text-accent underline" href={sectionLink(d.metrics_section)}>metrics.md §{d.metrics_section}</a>
              {d.changes.length > 0 && (
                <span className="text-muted">
                  {" "}· clarified in{" "}
                  {d.changes.map((c, i) => (
                    <span key={c}>
                      {i > 0 && "; "}
                      <a className="text-accent underline" href={sectionLink("changes")}>Changes {c.split(" · ")[0]}</a>
                    </span>
                  ))}
                </span>
              )}
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">
          The contract was committed before any business metric was computed and changes only through dated entries:{" "}
          {s.changes_entries.map((c) => c.title).join("; ")}.
        </p>
      </Section>

      <Section n={5} title="From raw rows to orders">
        <div className={tableWrap}>
          <table className="w-full text-sm">
            <tbody>
              {chain.map((c) => (
                <tr key={c.label} className={`border-b border-line last:border-0 ${c.kind === "total" ? "font-medium" : "text-muted"}`}>
                  <td className={td}>{c.label}</td>
                  <td className={`${td} num text-right`}>{c.n < 0 ? `− ${fmtInt(-c.n)}` : fmtInt(c.n)}</td>
                </tr>
              ))}
              <tr className="border-b border-line font-medium">
                <td className={td}>Valid sessions</td>
                <td className={`${td} num text-right`}>{fmtInt(r.valid_sessions)}</td>
              </tr>
              <tr className="font-medium">
                <td className={td}>Orders (valid sessions with an observed purchase)</td>
                <td className={`${td} num text-right`}>{fmtInt(r.orders)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted">
          Each total equals the row above it minus the rows removed; the export halts if the chain does not sum, and a test
          checks it again.
        </p>
        <Sources fields={["data_story.json: reconciliation (from stg_dedup_audit, stg_events, int_sessions, mart_kpis_daily)"]} />
      </Section>

      <Section n={6} title="Limitations">
        <ul className="list-disc space-y-2 pl-5 text-sm">
          {s.limitations.map((l) => (
            <li key={l.text}>
              {l.text} <span className="text-xs text-muted">({l.supporting_fields.join("; ")})</span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">
          Provenance: <a className="text-accent underline" href={blobUrl("docs/data-source.md")}>docs/data-source.md</a> and{" "}
          <a className="text-accent underline" href={blobUrl("docs/data-profile.md")}>docs/data-profile.md</a>, both generated by code.
        </p>
      </Section>
    </div>
  );
}
