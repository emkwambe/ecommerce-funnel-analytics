import Link from "next/link";
import { getLaterPurchases, metricByKey, type LaterEstimate } from "@/lib/data";
import { blobUrl, fmtDollarsCompact, fmtInt, fmtPct, shortSha } from "@/lib/format";
import { niceDomain } from "@/lib/scale";
import { LineChart } from "../../line-chart";
import { PageHeader, Section, Sources, tableWrap, td, th } from "../../ui";
import { IntervalBars } from "../charts";

export const metadata = { title: "Were carted products purchased in a later session? · E-commerce Funnel Analytics" };

// Claim-ledger rows C8–C15 (ai-workflow/claim-ledger.md), scoped per owner decision H4. Every figure is read from
// investigation_later_purchases.json; every label from docs/metrics.md through metrics_index.json.
const ESCALATION = "ai-workflow/escalations/2026-09-26-B-R3-agreement.md";
const REVIEW = "ai-workflow/adversarial-review-B.md";

const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const range = (x: [number, number]) => `[${fmtPct(x[0], 1)}, ${fmtPct(x[1], 1)}]`;

export default function LaterPurchasesPage() {
  const b = getLaterPurchases();
  const est = (k: LaterEstimate["spec_key"]) => b.estimates.find((e) => e.spec_key === k)!;
  const [b1, b5] = [est("B1"), est("B5")];
  const countLabel = metricByKey("2026-09-26_item_9");
  const valueLabel = metricByKey("2026-09-26_item_10");
  const kmLabel = metricByKey("2026-09-26_item_12");
  const baselineLabel = metricByKey("2026-09-26_item_13");
  const c = b.cohort_difference;
  const r3 = b.stop_rules.find((r) => r.rule.startsWith("R3"));
  const check = (key: string) => b.checks.find((x) => x.row_key === key)?.value;
  const threshold = check("sensitivity_threshold:most_active_user_threshold_events") ?? NaN;
  const identityOk = check("user_id_check:events_in_eligible_sessions_with_null_user_id") === 0
    && check("user_id_check:eligible_sessions_with_more_than_one_user_id") === 0
    && check("user_id_check:share_of_eligible_pairs_with_non_null_user_id") === 1;
  const withinHour = b.within_1_hour_disclosure.share_of_followed_pairs;
  const curve = b.kaplan_meier.curve;
  const y = niceDomain(curve.map((p) => p.count_interval[1]), 4);
  const seedLow = Math.min(...b.seed_stability.map((s) => s.b1_count_interval[0]));
  const seedHigh = Math.max(...b.seed_stability.map((s) => s.b1_count_interval[1]));
  const intervalsOverlap = c.later_km_7_day_interval[1] >= c.b1_count_interval[0];
  const sensitivity: { key: LaterEstimate["spec_key"]; label: string }[] = [
    { key: "B1", label: countLabel.short_label ?? countLabel.display_label },
    { key: "B2", label: "3-day window" },
    { key: "B3", label: "14-day window" },
    { key: "B6", label: "One pair per user and product" },
    { key: "B7", label: `Excluding users with more than ${fmtInt(threshold)} events in the month` },
    { key: "B8", label: "Excluding cart sessions longer than 24 hours" },
  ];

  return (
    <div className="space-y-12">
      <PageHeader title={b.question}>
        <p>
          The funnel page reports carted value with no observed purchase in the session. This page asks how much of it was
          followed by a purchase of the same product, by the same user, in a later session.
        </p>
        <p className="text-sm">
          Part of the <Link href="/investigations" className="text-accent underline">investigations</Link>.
        </p>
      </PageHeader>

      <Section n={1} title="The answer">
        <p>
          Of carted products with no observed purchase in the session, from {b1.population},{" "}
          <strong className="num">{fmtPct(b1.count_share, 1)}</strong> <span className="num text-muted">{range(b1.count_interval)}</span>{" "}
          (<span className="num">{fmtInt(b1.followed_pairs)}</span> of <span className="num">{fmtInt(b1.eligible_pairs)}</span>)
          were purchased by the same user in a later session within 7 days of the cart session&apos;s start.
        </p>
        <p>
          By value, <strong className="num">{fmtPct(b1.value_share, 1)}</strong> <span className="num text-muted">{range(b1.value_interval)}</span>{" "}
          of the carted value of those same products ({fmtDollarsCompact(b1.followed_value)} of {fmtDollarsCompact(b1.eligible_value)})
          was followed by a purchase of the same product by the same user in a later session within 7 days.
        </p>
        <p className="rounded-lg border border-line bg-flag-bg p-3 text-sm">
          These shares describe carted products from {b1.population} only, the sessions with a full 7 days of follow-up in
          the data. They are not a rate for all of October (section 2 shows why), and they are not applied to any other amount.
          They say nothing about why a product was bought later, or about purchases this log cannot see: on another device,
          in another account, by someone else in the household, or after October 2019.
        </p>
        <p className="text-xs text-muted">
          {countLabel.display_label}. {valueLabel.display_label}. Intervals are 95% intervals from resampling users, so
          users with many carted products are not treated as independent.
        </p>
        <Sources fields={["investigation_later_purchases.json: estimates[spec_key=B1].population, .count_share, .count_interval, .followed_pairs, .eligible_pairs, .value_share, .value_interval, .followed_value, .eligible_value"]} />
      </Section>

      <Section n={2} title="Late October differs">
        <p>
          For carted products from {c.later_population}, the Kaplan–Meier estimate of the share purchased by the same user in a
          later session within 7 days is {fmtPct(c.later_km_7_day, 1)} {range(c.later_km_7_day_interval)}, lower than{" "}
          {fmtPct(c.b1_count_share, 1)} {range(c.b1_count_interval)} for {c.b1_population}.
          {intervalsOverlap ? " The two intervals overlap." : " The two intervals do not overlap."}
        </p>
        <IntervalBars
          max={Math.max(c.b1_count_interval[1], c.later_km_7_day_interval[1]) * 1.25}
          caption="Share purchased by the same user in a later session within 7 days, by when the cart session started."
          rows={[
            { key: "b1", label: sentence(c.b1_population), value: c.b1_count_share, lower: c.b1_count_interval[0], upper: c.b1_count_interval[1], color: "var(--series-1)", detail: `${c.b1_population} (fixed window)` },
            { key: "later", label: sentence(c.later_population), value: c.later_km_7_day, lower: c.later_km_7_day_interval[0], upper: c.later_km_7_day_interval[1], color: "var(--series-2)", detail: `${c.later_population} (Kaplan–Meier)` },
          ]}
        />
        <p>
          The Kaplan–Meier estimate over all of October pools both groups, so its 7-day value does not contain the fixed-window
          share: the planned method check did not agree. No reason for the difference is claimed. Calendar effects, the shorter
          follow-up that can be observed near the end of the data, and changes in logging are all consistent with it.
        </p>
        {r3?.fired && r3.owner_resolution && (
          <p className="text-xs text-muted">
            The disagreement stopped the analysis until the project owner decided how to report it:{" "}
            <a className="text-accent underline" href={blobUrl(ESCALATION)}>escalation brief and decision</a>.
          </p>
        )}
        <Sources fields={["investigation_later_purchases.json: cohort_difference.later_population, .later_km_7_day, .later_km_7_day_interval, .b1_population, .b1_count_share, .b1_count_interval", "stop_rules[rule=R3 agreement].fired, .owner_resolution"]} />
      </Section>

      <Section n={3} title="Over the days after the cart session">
        <p className="text-sm text-muted">
          {kmLabel.display_label}. This curve covers {b.kaplan_meier_population}, so it pools the two groups in section 2.
        </p>
        <LineChart
          series={[{ key: "km", name: "Share purchased later (Kaplan–Meier)", color: "var(--series-1)", points: curve.map((p) => ({ x: p.days, y: p.count })) }]}
          bands={[{ seriesKey: "km", name: "95% interval", lower: curve.map((p) => ({ x: p.days, y: p.count_interval[0] })), upper: curve.map((p) => ({ x: p.days, y: p.count_interval[1] })) }]}
          xDomain={[1, curve[curve.length - 1].days]}
          yDomain={y.domain}
          xTicks={[1, 7, 14, 21, curve[curve.length - 1].days]}
          yTicks={y.ticks}
          xFormat="count"
          yFormat="percent"
          xLabel="Days since the cart session started"
          yLabel="Share purchased by the same user in a later session"
          markers={[{ x: 7, label: "7 days" }]}
        />
        <Sources fields={["investigation_later_purchases.json: kaplan_meier.curve[].days, .count, .count_interval; kaplan_meier_population"]} />
      </Section>

      <Section n={4} title="Carted and viewed products">
        <p>
          In the same sessions, {fmtPct(b5.count_share, 1)} {range(b5.count_interval)} of viewed products with no observed cart
          event or purchase in the session were purchased by the same user in a later session within 7 days, compared with{" "}
          {fmtPct(b1.count_share, 1)} of carted products. This is a description of two groups of products, which differ in many
          ways; it says nothing about what adding to the cart does.
        </p>
        <IntervalBars
          max={b1.count_interval[1] * 1.25}
          caption={`Share purchased by the same user in a later session within 7 days; cart ${b1.population}.`}
          rows={[
            { key: "carted", label: "Carted products", value: b1.count_share, lower: b1.count_interval[0], upper: b1.count_interval[1], color: "var(--series-1)", detail: `${fmtInt(b1.followed_pairs)} of ${fmtInt(b1.eligible_pairs)}` },
            { key: "viewed", label: "Viewed products, not carted", value: b5.count_share, lower: b5.count_interval[0], upper: b5.count_interval[1], color: "var(--series-2)", detail: `${fmtInt(b5.followed_pairs)} of ${fmtInt(b5.eligible_pairs)}` },
          ]}
        />
        <p className="text-xs text-muted">{baselineLabel.display_label}.</p>
        <Sources fields={["investigation_later_purchases.json: estimates[spec_key=B5].count_share, .count_interval, .followed_pairs, .eligible_pairs; estimates[spec_key=B1].count_share"]} />
      </Section>

      <Section n={5} title="Other windows and checks">
        <p className="text-sm text-muted">
          Each row has its own population: a window of N days includes only cart sessions with N full days of follow-up.
        </p>
        <div className={tableWrap}>
          <table className="w-full text-sm">
            <thead>
              <tr><th className={th}>Specification</th><th className={`${th} text-right`}>By count</th><th className={`${th} text-right`}>By value</th></tr>
            </thead>
            <tbody>
              {sensitivity.map(({ key, label }) => {
                const e = est(key);
                return (
                  <tr key={key} className="border-t border-line align-top">
                    <td className={td}>
                      {label}
                      <div className="text-xs text-muted">{e.population}; {fmtInt(e.followed_pairs)} of {fmtInt(e.eligible_pairs)}</div>
                    </td>
                    <td className={`${td} num text-right`}>{fmtPct(e.count_share, 1)}<div className="text-xs text-muted">{range(e.count_interval)}</div></td>
                    <td className={`${td} num text-right`}>{fmtPct(e.value_share, 1)}<div className="text-xs text-muted">{range(e.value_interval)}</div></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <Sources fields={["investigation_later_purchases.json: estimates[spec_key=B1,B2,B3,B6,B7,B8].population, .count_share, .count_interval, .value_share, .value_interval, .followed_pairs, .eligible_pairs", "checks[row_key=sensitivity_threshold:most_active_user_threshold_events].value"]} />
      </Section>

      <Section n={6} title="Two things to know">
        <p>
          {fmtPct(withinHour, 1)} of the carted products followed by a later purchase were first purchased within one hour of
          the latest cart event. This may reflect technical session splits rather than return visits: how the store starts a new
          session is not documented, so the two cannot be told apart.
        </p>
        <Sources fields={["investigation_later_purchases.json: within_1_hour_disclosure.share_of_followed_pairs, .population"]} />
        {identityOk && (
          <p>
            Every carted product counted here has a usable user_id: no session in the population has a missing user_id or more
            than one. Whether one user_id is one person across devices cannot be checked in this file.
          </p>
        )}
        <Sources fields={["investigation_later_purchases.json: checks[metric_group=user_id_check].value"]} />
      </Section>

      <Section n={7} title="How this was checked">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            Two independent recomputations from the raw file, written separately from the pipeline, matched all{" "}
            {fmtInt(b.independent_verification.checks)} checks (verification at commit{" "}
            <code>{shortSha(b.independent_verification.verify_git_commit_sha)}</code>).
          </li>
          <li>
            Intervals were recomputed with three other random seeds; the bounds of the 7-day interval stayed within {range([seedLow, seedHigh])}.
          </li>
          <li>
            The planned method check (Kaplan–Meier against the fixed window) did not agree, as section 2 explains, and is
            reported rather than hidden.
          </li>
          <li>
            The definitions, windows, and stopping rules were approved and written into the metric contract before any figure was
            computed: <a className="text-accent underline" href={blobUrl(b.method_record)}>method record</a>,{" "}
            <Link className="text-accent underline" href="/metrics">metric contract</Link> (Changes, 2026-09-26),{" "}
            <a className="text-accent underline" href={blobUrl(REVIEW)}>adversarial review</a>.
          </li>
        </ul>
        <Sources fields={["investigation_later_purchases.json: independent_verification.checks, .all_match, .verify_git_commit_sha; seed_stability[].b1_count_interval; stop_rules; method_record"]} />
      </Section>

      <Section n={8} title="What this cannot show">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Why a carted product was bought later, or whether adding it to the cart made that more likely.</li>
          <li>How much carted value was never bought anywhere: purchases outside this log are unobservable.</li>
          <li>A rate for all of October, or for any store or period other than this one.</li>
        </ul>
      </Section>
    </div>
  );
}
