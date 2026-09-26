import Link from "next/link";
import { getKpis, getPurchasePaths, metric } from "@/lib/data";
import { fmtDollars, fmtDollarsCompact, fmtInt, fmtPct } from "@/lib/format";
import { niceDomain } from "@/lib/scale";
import { LineChart } from "./line-chart";
import { Kpi, Section, Sources, tableWrap, td, th } from "./ui";

const monthName = (isoDate: string) =>
  new Date(`${isoDate}T00:00:00Z`).toLocaleString("en-US", { month: "short", timeZone: "UTC" });
const dayOfMonth = (isoDate: string) => Number(isoDate.slice(8, 10));

export default function Home() {
  const { month: m, daily } = getKpis();
  // "October 2019", from the month row, not typed.
  const monthYear = new Date(`${m.period_start}T00:00:00Z`).toLocaleString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
  const noCartPathLabel = "Purchase with no observed same-session cart event";
  const noCartPath = getPurchasePaths().rows.find((r) => r.purchase_path === noCartPathLabel);
  if (!noCartPath) throw new Error(`purchase_paths.json has no row "${noCartPathLabel}"`);
  const days = [...daily].sort((a, b) => a.period_start.localeCompare(b.period_start));
  const prefix = monthName(m.period_start);
  const xs = days.map((d) => dayOfMonth(d.period_start));
  const xDomain: [number, number] = [Math.min(...xs), Math.max(...xs)];
  // Weekly ticks from the first day, kept inside the data range.
  const xTicks = xs.filter((x) => (x - xDomain[0]) % 7 === 0);
  const sessionsScale = niceDomain(days.map((d) => d.sessions));
  const rateScale = niceDomain(days.map((d) => d.session_purchase_rate));
  const minRate = days.reduce((a, b) => (b.session_purchase_rate < a.session_purchase_rate ? b : a));
  const maxRate = days.reduce((a, b) => (b.session_purchase_rate > a.session_purchase_rate ? b : a));

  return (
    <div className="space-y-12">
      <header className="space-y-5">
        <span className="inline-flex items-center gap-2 rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-sm font-medium text-accent">
          <span aria-hidden className="h-2 w-2 rounded-full bg-accent" />
          Sprint 1 · pipeline and definitions
        </span>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">E-commerce Funnel Analytics: {monthYear}</h1>
        <p className="max-w-2xl text-lg leading-relaxed">
          <span className="font-medium">The question:</span>{" "}
          <span className="text-muted">
            Where in the view-to-purchase funnel do sessions most often end with no observed purchase, which categories
            hold the most carted value with no observed purchase in the session, and what should the team test first?
          </span>
        </p>
      </header>

      <Section n={1} title="What the data shows">
        <div className="space-y-2">
          <p>
            In {monthYear}, {fmtPct(noCartPath.revenue_share, 1)} of revenue came from purchases with no observed
            same-session cart event, and{" "}
            {fmtPct(m.sessions_with_purchases_only_of_uncarted_products / m.sessions_with_purchase, 1)} of purchasing
            sessions contained only such purchases.
          </p>
          <Sources fields={[
            `purchase_paths.json: rows["${noCartPath.purchase_path}"].revenue_share`,
            "kpis.json: month.sessions_with_purchases_only_of_uncarted_products, .sessions_with_purchase",
          ]} />
        </div>
        <div className="space-y-2">
          <p>
            {fmtPct(m.view_to_cart_session_rate, 1)} of viewing sessions had an observed cart event;{" "}
            {fmtPct(m.cart_session_purchase_rate, 1)} of sessions with an observed cart event had an observed purchase
            of a carted product. These rates use different denominators; comparing them describes where observed
            sessions end, not why.
          </p>
          <Sources fields={["kpis.json: month.view_to_cart_session_rate, .cart_session_purchase_rate"]} />
        </div>
        <p className="text-sm text-muted">
          This sprint defines every metric, builds and tests the pipeline, and describes the funnel. It makes no
          recommendation yet: what to test first is the next sprint&apos;s question.
        </p>
      </Section>

      <Section n={2} title={`The month in numbers (${prefix} ${m.period_start.slice(0, 4)}, UTC)`}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Kpi entry={metric("Sessions")} value={fmtInt(m.sessions)} basis="valid sessions" />
          <Kpi entry={metric("Order")} label="Orders" value={fmtInt(m.orders)} basis="sessions with an observed purchase" />
          <Kpi
            entry={metric("Session purchase rate")}
            value={fmtPct(m.session_purchase_rate, 2)}
            basis={`${fmtInt(m.sessions_with_purchase)} of ${fmtInt(m.sessions)} sessions`}
          />
          <Kpi
            entry={metric("Revenue (primary)")}
            value={fmtDollarsCompact(m.revenue)}
            basis={`${fmtDollars(m.revenue)}; repeat purchase events collapsed: ${fmtDollars(m.revenue_repeat_collapsed)}`}
          />
          <Kpi
            entry={metric("Average order value")}
            value={fmtDollars(m.average_order_value)}
            basis={`${fmtDollarsCompact(m.revenue)} over ${fmtInt(m.orders)} orders`}
          />
          <Kpi
            entry={metric("Revenue per session")}
            value={fmtDollars(m.revenue_per_session)}
            basis={`${fmtDollarsCompact(m.revenue)} over ${fmtInt(m.sessions)} sessions`}
          />
        </div>
        <p className="text-sm text-muted">
          Repeated purchase events of one product in a session may be extra units or repeated logging, and the data
          cannot tell which. Collapsing them lowers revenue from {fmtDollars(m.revenue)} to{" "}
          {fmtDollars(m.revenue_repeat_collapsed)}, so both figures are shown.
        </p>
        <Sources fields={["kpis.json: month.sessions, .orders, .session_purchase_rate, .revenue, .revenue_repeat_collapsed, .average_order_value, .revenue_per_session"]} />
      </Section>

      <Section n={3} title="By UTC day of session start">
        <p className="text-muted">
          Each session, its order, and its revenue count on the UTC day of the session&apos;s first event. The store&apos;s
          local time zone is unknown.
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2 rounded-lg border border-line bg-surface p-4">
            <h3 className="text-sm font-semibold">Sessions</h3>
            <LineChart
              series={[{ key: "s", name: "Sessions", color: "var(--series-1)", points: days.map((d) => ({ x: dayOfMonth(d.period_start), y: d.sessions })) }]}
              xDomain={xDomain}
              yDomain={sessionsScale.domain}
              xTicks={xTicks}
              yTicks={sessionsScale.ticks}
              xFormat="day"
              yFormat="count"
              xPrefix={prefix}
              xLabel="UTC day of session start"
              yLabel="Sessions"
              height={200}
            />
          </div>
          <div className="space-y-2 rounded-lg border border-line bg-surface p-4">
            <h3 className="text-sm font-semibold">{metric("Session purchase rate").display_label}</h3>
            <LineChart
              series={[{ key: "r", name: "Session purchase rate", color: "var(--series-1)", points: days.map((d) => ({ x: dayOfMonth(d.period_start), y: d.session_purchase_rate })) }]}
              xDomain={xDomain}
              yDomain={rateScale.domain}
              xTicks={xTicks}
              yTicks={rateScale.ticks}
              xFormat="day"
              yFormat="percent1"
              xPrefix={prefix}
              xLabel="UTC day of session start"
              yLabel="Session purchase rate"
              height={200}
            />
          </div>
        </div>
        <p className="text-sm text-muted">
          The daily session purchase rate ranged from {fmtPct(minRate.session_purchase_rate, 2)} ({prefix}{" "}
          {dayOfMonth(minRate.period_start)}) to {fmtPct(maxRate.session_purchase_rate, 2)} ({prefix}{" "}
          {dayOfMonth(maxRate.period_start)}).
        </p>
        <Sources fields={["kpis.json: daily[].period_start, .sessions, .session_purchase_rate"]} />
        <details className="text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">Daily table</summary>
          <div className={`${tableWrap} mt-3`}>
            <table className="w-full text-sm">
              <thead className="border-b border-line">
                <tr>
                  <th className={th}>UTC day</th>
                  <th className={`${th} text-right`}>Sessions</th>
                  <th className={`${th} text-right`}>Orders</th>
                  <th className={`${th} text-right`}>Session purchase rate</th>
                  <th className={`${th} text-right`}>Revenue</th>
                </tr>
              </thead>
              <tbody>
                {days.map((d) => (
                  <tr key={d.period_key} className="border-b border-line last:border-0">
                    <td className={`${td} num whitespace-nowrap`}>{prefix} {dayOfMonth(d.period_start)}</td>
                    <td className={`${td} num text-right`}>{fmtInt(d.sessions)}</td>
                    <td className={`${td} num text-right`}>{fmtInt(d.orders)}</td>
                    <td className={`${td} num text-right`}>{fmtPct(d.session_purchase_rate, 2)}</td>
                    <td className={`${td} num text-right`}>{fmtDollarsCompact(d.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </Section>

      <Section n={4} title="Where to look next">
        <ul className="space-y-1 text-sm">
          <li><Link href="/funnel" className="text-accent underline">The session funnel</Link>, purchase paths, and categories.</li>
          <li><Link href="/investigations" className="text-accent underline">Investigations</Link>: why there are two revenue figures, and whether carted products were purchased in a later session.</li>
          <li><Link href="/data-quality" className="text-accent underline">Data quality</Link>, with each metric&apos;s basis and the long-session sensitivity.</li>
          <li><Link href="/data" className="text-accent underline">The data</Link>: source, contents, decisions, and the reconciliation from raw rows to orders.</li>
          <li><Link href="/metrics" className="text-accent underline">Metric definitions</Link>, the contract every number follows.</li>
          <li><Link href="/how-its-built" className="text-accent underline">How it was built</Link> with Claude Code, including the correction log.</li>
        </ul>
      </Section>
    </div>
  );
}
