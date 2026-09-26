import Link from "next/link";
import { getRevenueGap, metricByKey, type GapCell } from "@/lib/data";
import { blobUrl, fmtDollars, fmtDollarsCompact, fmtInt, fmtPct, shortSha } from "@/lib/format";
import { PageHeader, Section, Sources, tableWrap, td, th } from "../../ui";
import { ShareBars, type ShareRow } from "../charts";

export const metadata = { title: "Why are there two revenue figures? · E-commerce Funnel Analytics" };

// Claim-ledger rows C3–C7 (ai-workflow/claim-ledger.md). Every figure is read from investigation_revenue_gap.json;
// every label from docs/metrics.md (Changes 2026-09-26, Sprint 2 investigations) through metrics_index.json.
const cell = (cells: GapCell[], key: string) => cells.find((c) => c.group_key === key);

function shareRows(cells: GapCell[]): ShareRow[] {
  return cells.map((c) => ({
    key: c.group_key,
    label: c.group_label,
    share: c.share_of_difference,
    detail: `${fmtDollarsCompact(c.repeat_purchase_value)} · ${fmtInt(c.repeat_purchase_events)} repeat purchase events in ${fmtInt(c.pairs)} (session, product) pairs`,
  }));
}

export default function RevenueFiguresPage() {
  const g = getRevenueGap();
  const t = g.totals;
  const differenceLabel = metricByKey("2026-09-26_item_2");
  const repeatLabel = metricByKey("2026-09-26_item_1");
  const thresholdLabel = metricByKey("2026-09-26_item_4");
  const d = g.dimensions;
  const samePrice = cell(d.price_vs_first_purchase, "same_price");
  const sameSecond = cell(d.time_since_previous_purchase, "same_second");
  const within = (s: number) => g.thresholds.find((x) => x.threshold_seconds === s);
  const [w60, w300, w3600] = [within(60), within(300), within(3600)];
  const categories = d.category_top;
  const unknown = cell(categories, "unknown");
  const dup = g.secondary_cases.exact_duplicate_rows;
  const removedBy = (type: string) => dup.filter((r) => r.event_type === type).reduce((a, r) => a + r.rows_removed, 0);
  const removed = dup.reduce((a, r) => a + r.rows_removed, 0);
  const cart = g.secondary_cases.cart_no_view_reconciliation;
  const cartAllDuplicates = cart.remainder === 0 && cart.in_null_session_events === 0 && cart.in_multi_user_sessions === 0
    && cart.removed_as_exact_duplicates === cart.difference;

  return (
    <div className="space-y-12">
      <PageHeader title={g.question}>
        <p>
          The site shows revenue ({fmtDollars(t.revenue)}) and revenue with repeat purchase events collapsed (
          {fmtDollars(t.revenue_repeat_collapsed)}). This page answers why they differ, as far as the data allows.
        </p>
        <p className="text-sm">
          Part of the <Link href="/investigations" className="text-accent underline">investigations</Link>.
        </p>
      </PageHeader>

      <Section n={1} title="The answer">
        <p>
          The two figures differ by <strong className="num">{fmtDollars(t.revenue_difference)}</strong>. That difference is
          exactly the value of <span className="num">{fmtInt(t.repeat_purchase_events)}</span> purchase events after the first
          of the same product in a session, in <span className="num">{fmtInt(t.pairs)}</span> (session, product) pairs.
          Revenue counts every purchase event; the collapsed figure keeps only the first of each product in each session.
        </p>
        <p className="rounded-lg border border-line bg-flag-bg p-3 text-sm">
          The data cannot tell whether these repeat events are extra units or the same purchase logged again: the file has
          no quantity column and no order or transaction ID. This page shows where the difference sits, not which
          explanation is true. Both revenue figures are always shown together.
        </p>
        <Sources fields={["investigation_revenue_gap.json: totals.revenue, .revenue_repeat_collapsed, .revenue_difference, .repeat_purchase_events, .pairs"]} />
        <p className="text-xs text-muted">
          {differenceLabel.display_label}: {fmtDollars(t.revenue_difference)}. {repeatLabel.display_label}:{" "}
          {fmtInt(t.repeat_purchase_events)}.
        </p>
      </Section>

      <Section n={2} title="Where the difference sits">
        <div className="space-y-3">
          <h3 className="font-medium">By price compared with the first purchase event</h3>
          {samePrice && (
            <p>
              {fmtPct(samePrice.share_of_difference, 1)} of the difference comes from repeat purchase events at the same price as
              the first purchase event of that product in the session. A repeat at the same price is consistent with both an
              extra unit and a repeated log entry, so this does not separate the two.
            </p>
          )}
          <ShareBars rows={shareRows(d.price_vs_first_purchase)} caption="Share of the revenue difference, by price compared with the pair's first purchase event." />
          <Sources fields={["investigation_revenue_gap.json: dimensions.price_vs_first_purchase[].share_of_difference, .repeat_purchase_value, .repeat_purchase_events, .pairs"]} />
        </div>

        <div className="space-y-3">
          <h3 className="font-medium">By time since the previous purchase event of the same product</h3>
          {w60 && w300 && w3600 && (
            <p>
              {fmtPct(w60.share_of_difference, 1)} of the difference comes from repeat purchase events within 60 seconds of the
              previous purchase event of that product in the session, {fmtPct(w300.share_of_difference, 1)} within 5 minutes,
              and {fmtPct(w3600.share_of_difference, 1)} within 1 hour.
              {sameSecond && sameSecond.repeat_purchase_events === 0 && (
                <> None is in the same second: identical duplicate rows are removed before revenue is counted (decision D1).</>
              )}
            </p>
          )}
          <ShareBars
            rows={g.thresholds.map((x) => ({
              key: String(x.threshold_seconds),
              label: `Within ${x.threshold_label}`,
              share: x.share_of_difference,
              detail: `${fmtDollarsCompact(x.repeat_purchase_value_within)} · ${fmtInt(x.repeat_purchase_events_within)} repeat purchase events`,
            }))}
            caption={`${thresholdLabel.display_label}, for each threshold T. The thresholds were fixed before the data was seen.`}
          />
          <p className="text-xs text-muted">
            The repeat purchase events are not split into timing groups here: a fixed cut-off falls inside a large mass of
            events, so the cumulative shares above are the reliable view.
          </p>
          <Sources fields={["investigation_revenue_gap.json: thresholds[].threshold_label, .share_of_difference, .repeat_purchase_value_within, .repeat_purchase_events_within", "dimensions.time_since_previous_purchase[group_key=same_second].repeat_purchase_events", "secondary_cases.exact_duplicate_rows"]} />
        </div>

        <div className="space-y-3">
          <h3 className="font-medium">By purchase events in the pair</h3>
          <ShareBars rows={shareRows(d.purchase_events_in_pair).map((r) => ({ ...r, label: `${r.label} purchase events` }))}
            caption="Share of the revenue difference, by how many purchase events the (session, product) pair has." />
          <Sources fields={["investigation_revenue_gap.json: dimensions.purchase_events_in_pair[].share_of_difference, .repeat_purchase_value, .pairs"]} />
        </div>

        <div className="space-y-3">
          <h3 className="font-medium">By top-level category</h3>
          {categories[0] && unknown && (
            <p>
              {categories[0].group_label} accounts for {fmtPct(categories[0].share_of_difference, 1)} of the difference, and
              the unknown category for {fmtPct(unknown.share_of_difference, 1)}. A category&apos;s share partly reflects its
              share of revenue; no comparison across categories is made here.
            </p>
          )}
          <ShareBars rows={shareRows(categories.slice(0, 5))} caption="The five top-level categories with the largest share of the revenue difference." />
          <details className="text-sm">
            <summary className="cursor-pointer select-none text-muted hover:text-ink">All {categories.length} categories</summary>
            <div className={`${tableWrap} mt-2`}>
              <table className="w-full text-sm">
                <thead><tr><th className={th}>Category</th><th className={`${th} text-right`}>Share</th><th className={`${th} text-right`}>Value</th></tr></thead>
                <tbody>
                  {categories.map((c) => (
                    <tr key={c.group_key} className="border-t border-line">
                      <td className={`${td} break-all`}>{c.group_label}</td>
                      <td className={`${td} num text-right`}>{fmtPct(c.share_of_difference, 1)}</td>
                      <td className={`${td} num text-right`}>{fmtDollarsCompact(c.repeat_purchase_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <Sources fields={["investigation_revenue_gap.json: dimensions.category_top[].group_label, .share_of_difference, .repeat_purchase_value"]} />
        </div>
      </Section>

      <Section n={3} title="Two related cleaning cases">
        <p>
          Of the {fmtInt(removed)} exact duplicate rows removed before any metric is computed (decision D1),{" "}
          {fmtInt(removedBy("cart"))} are cart events, {fmtInt(removedBy("view"))} views, and {fmtInt(removedBy("purchase"))}{" "}
          purchase events.
        </p>
        <p>
          The data profile counted {fmtInt(cart.raw_basis_count)} cart events with no view at or before them in the session on
          raw rows; the published count is {fmtInt(cart.contract_basis_count)}.
          {cartAllDuplicates
            ? ` The difference of ${fmtInt(cart.difference)} is entirely rows removed as exact duplicates; none is in excluded sessions.`
            : ` Of the difference of ${fmtInt(cart.difference)}, ${fmtInt(cart.removed_as_exact_duplicates)} are rows removed as exact duplicates, ${fmtInt(cart.in_multi_user_sessions)} are in sessions with more than one user_id, and ${fmtInt(cart.remainder)} are unexplained.`}
        </p>
        <Sources fields={["investigation_revenue_gap.json: secondary_cases.exact_duplicate_rows[].event_type, .rows_removed", "secondary_cases.cart_no_view_reconciliation (raw_basis_count, contract_basis_count, removed_as_exact_duplicates, in_null_session_events, in_multi_user_sessions, remainder)"]} />
      </Section>

      <Section n={4} title="How this was checked">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            Every breakdown adds up exactly to the difference; pipeline tests fail otherwise, and the difference itself must equal
            the two published revenue figures&apos; gap.
          </li>
          <li>
            An independent recomputation from the source data, written separately from the pipeline, matched all{" "}
            {fmtInt(g.independent_verification.checks)} checks (verification at commit{" "}
            <code>{shortSha(g.independent_verification.verify_git_commit_sha)}</code>).
          </li>
          <li>
            The method, the breakdowns, and the thresholds were approved and written into the metric contract before any of
            them was computed: <a className="text-accent underline" href={blobUrl(g.method_record)}>method record</a>,{" "}
            <Link className="text-accent underline" href="/metrics">metric contract</Link> (Changes, 2026-09-26).
          </li>
        </ul>
        <Sources fields={["investigation_revenue_gap.json: independent_verification.checks, .all_match, .verify_git_commit_sha; method_record; contract"]} />
      </Section>

      <Section n={5} title="What this cannot show">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Whether a repeat purchase event is an extra unit or a repeated log entry: there is no quantity or order column.</li>
          <li>Which revenue figure is &quot;right&quot;: they answer different questions, so both stay on the site together.</li>
          <li>Anything beyond this store and October 2019.</li>
        </ul>
      </Section>
    </div>
  );
}
