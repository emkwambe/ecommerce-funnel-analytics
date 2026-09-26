import type { Metadata } from "next";
import { getDataQuality, type QualityRow } from "@/lib/data";
import { fmtDollars, fmtFixed, fmtInt, fmtPct } from "@/lib/format";
import { PageHeader, Section, Sources, tableWrap, td, th } from "../ui";

export const metadata: Metadata = { title: "Data quality · E-commerce Funnel Analytics" };

const isShare = (r: QualityRow) => r.metric_key.endsWith("_share");
const isMoney = (key: string) => key.endsWith("revenue_per_session") || key.endsWith("average_order_value");
const isRate = (key: string) => key.endsWith("_rate");

function value(r: QualityRow, v: number) {
  if (isShare(r) || isRate(r.metric_key)) return fmtPct(v, 2);
  if (isMoney(r.metric_key)) return fmtDollars(v);
  return fmtInt(v);
}

function change(r: QualityRow) {
  const all = r.value;
  const excl = r.value_excluding_long_sessions!;
  if (isRate(r.metric_key)) {
    const pp = (excl - all) * 100;
    return `${pp < 0 ? "−" : "+"}${fmtFixed(Math.abs(pp), 3)} pp`;
  }
  const rel = (excl - all) / all;
  return `${rel < 0 ? "−" : "+"}${fmtFixed(Math.abs(rel) * 100, 2)}%`;
}

export default function DataQualityPage() {
  const rows = getDataQuality().rows;
  const quality = rows.filter((r) => r.metric_group === "data_quality");
  const sensitivity = rows.filter((r) => r.metric_group === "long_session_sensitivity");
  const bases = [...new Set(quality.map((r) => r.basis))];
  const maxShift = Math.max(
    ...sensitivity.map((r) => Math.abs((r.value_excluding_long_sessions! - r.value) / r.value)),
  );

  return (
    <div className="space-y-12">
      <PageHeader title="Data quality">
        <p>
          Every data-quality metric the contract requires (metrics.md §10), each with the basis it is counted on. Where the
          Sprint 0 structural profile published a figure for the same check on raw rows, it is shown alongside; the two
          differ only by the basis.
        </p>
      </PageHeader>

      <Section n={1} title="Data-quality metrics">
        <div className={tableWrap}>
          <table className="w-full text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className={th}>Metric</th>
                <th className={th}>Basis</th>
                <th className={`${th} text-right`}>Value</th>
                <th className={`${th} text-right`}>Sprint 0, raw rows</th>
              </tr>
            </thead>
            <tbody>
              {quality.map((r) => (
                <tr key={r.metric_key} className="border-b border-line last:border-0">
                  <td className={td}>{r.metric_label}</td>
                  <td className={`${td} text-xs text-muted`}>{r.basis}</td>
                  <td className={`${td} num text-right`}>{value(r, r.value)}</td>
                  <td className={`${td} num text-right text-muted`}>
                    {r.sprint0_raw_basis_value === null ? "—" : value(r, r.sprint0_raw_basis_value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted">
          Bases used: {bases.join("; ")}. Exact duplicate rows are counted on raw rows; null-session events and multi-user
          sessions on deduplicated events before session exclusions, since they are excluded from valid sessions by
          definition (metrics.md Changes, 2026-09-26); everything else on deduplicated events in valid sessions.
        </p>
        <Sources fields={["data_quality.json: rows[metric_group=data_quality].metric_label, .basis, .value, .sprint0_raw_basis_value"]} />
      </Section>

      <Section n={2} title="Long-session sensitivity">
        <p className="text-muted">
          Sessions longer than 24 hours are kept. As a check, the headline metrics are recomputed without them.
        </p>
        <div className={tableWrap}>
          <table className="w-full text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className={th}>Metric</th>
                <th className={`${th} text-right`}>All valid sessions</th>
                <th className={`${th} text-right`}>Excluding sessions over 24 hours</th>
                <th className={`${th} text-right`}>Change</th>
              </tr>
            </thead>
            <tbody>
              {sensitivity.map((r) => (
                <tr key={r.metric_key} className="border-b border-line last:border-0">
                  <td className={td}>{r.metric_label.replace(", long-session sensitivity", "")}</td>
                  <td className={`${td} num text-right`}>{value(r, r.value)}</td>
                  <td className={`${td} num text-right`}>{value(r, r.value_excluding_long_sessions!)}</td>
                  <td className={`${td} num text-right text-muted`}>{change(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted">
          The largest relative change across the five metrics is {fmtPct(maxShift, 2)}
          {maxShift < 0.01 ? ": every headline figure moves by less than 1% when long sessions are excluded." : "."}
        </p>
        <Sources fields={["data_quality.json: rows[metric_group=long_session_sensitivity].value, .value_excluding_long_sessions"]} />
      </Section>
    </div>
  );
}
