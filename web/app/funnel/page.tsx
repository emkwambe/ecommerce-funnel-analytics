import type { Metadata } from "next";
import { getFunnelCategory, getKpis, getPurchasePaths, metric, type CategoryRow } from "@/lib/data";
import { fmtDollarsCompact, fmtInt, fmtPct } from "@/lib/format";
import { PageHeader, Section, Sources, tableWrap, td, th } from "../ui";

export const metadata: Metadata = { title: "Funnel · E-commerce Funnel Analytics" };

function Bar({ share }: { share: number }) {
  return (
    <div className="mt-1 h-2 rounded bg-grid" aria-hidden>
      <div className="h-2 rounded bg-series-1" style={{ width: `${Math.max(0, Math.min(1, share)) * 100}%` }} />
    </div>
  );
}

const rate = (r: number | null) => (r === null ? "—" : fmtPct(r, 1));

// Below the sm breakpoint the three funnel columns fold into a line under the category name,
// so the table fits a 390 px screen without hiding any figure.
const wide = "hidden sm:table-cell";

function CategoryTable({ rows, caption }: { rows: CategoryRow[]; caption: string }) {
  return (
    <div className={tableWrap}>
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="border-b border-line">
          <tr>
            <th className={th}>Category</th>
            <th className={`${th} text-right`}>Carted value with no observed purchase in this session</th>
            <th className={`${th} text-right`}>Revenue</th>
            <th className={`${th} ${wide} text-right`}>Sessions entering (view)</th>
            <th className={`${th} ${wide} text-right`}>View to cart event</th>
            <th className={`${th} ${wide} text-right`}>Cart event to purchase</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.category_key} className="border-b border-line last:border-0">
              <td className={`${td} [overflow-wrap:anywhere]`}>
                <span className={r.category === "unknown" ? "italic text-muted" : ""}>{r.category}</span>
                <div className="num mt-1 text-xs text-muted sm:hidden">
                  {fmtInt(r.funnel_pairs)} entering · view to cart event {rate(r.view_to_cart_step_rate)} · cart event
                  to purchase {rate(r.cart_to_purchase_step_rate)}
                </div>
              </td>
              <td className={`${td} num text-right`}>
                {fmtDollarsCompact(r.carted_value_with_no_observed_purchase)}
                <div className="text-xs text-muted">{fmtInt(r.carted_pairs_with_no_observed_purchase)} pairs</div>
              </td>
              <td className={`${td} num text-right`}>{fmtDollarsCompact(r.revenue)}</td>
              <td className={`${td} ${wide} num text-right`}>{fmtInt(r.funnel_pairs)}</td>
              <td className={`${td} ${wide} num text-right`}>
                {rate(r.view_to_cart_step_rate)}
                <div className="text-xs text-muted">{fmtInt(r.funnel_pairs_with_cart)}</div>
              </td>
              <td className={`${td} ${wide} num text-right`}>
                {rate(r.cart_to_purchase_step_rate)}
                <div className="text-xs text-muted">{fmtInt(r.funnel_cart_pairs_with_carted_product_purchase)}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function FunnelPage() {
  const { month: m } = getKpis();
  const paths = getPurchasePaths().rows;
  const cat = getFunnelCategory();
  const top = cat.category_top;
  const codes = cat.category_code;
  const totalCarted = top.reduce((s, r) => s + r.carted_value_with_no_observed_purchase, 0);
  const leaders = top.filter((r) => r.category !== "unknown").slice(0, 3);
  const unknownTop = top.find((r) => r.category === "unknown");

  const steps = [
    { entry: metric("Sessions"), n: m.sessions },
    { entry: metric("Sessions with a view"), n: m.sessions_with_view },
    { entry: metric("Sessions with an observed cart event"), n: m.sessions_with_cart },
  ];
  const purchaseStep = metric("Sessions with a purchase");
  // Changes 2026-09-26 (third entry), item 1: the purchase step split by session-level purchase path.
  const purchaseGroups = [
    {
      entry: metric("Sessions with an observed purchase of a product with an observed same-session cart event"),
      n: m.sessions_with_purchase_of_carted_product,
      color: "var(--series-1)",
    },
    {
      entry: metric("Sessions with observed purchases only of products with no observed same-session cart event"),
      n: m.sessions_with_purchases_only_of_uncarted_products,
      color: "var(--series-2)",
    },
  ];
  const noCartedPurchase = metric("Sessions with an observed cart event and an observed purchase, none of a carted product");
  const cartRowsTotal =
    m.cart_sessions_with_carted_product_purchase + m.cart_sessions_with_no_observed_purchase + m.cart_sessions_with_purchase_of_no_carted_product;
  const rates = [
    { entry: metric("Session purchase rate"), value: m.session_purchase_rate, num: m.sessions_with_purchase, den: m.sessions },
    { entry: metric("View-to-cart session rate"), value: m.view_to_cart_session_rate, num: m.viewing_sessions_with_cart, den: m.sessions_with_view },
    { entry: metric("Cart-session purchase rate"), value: m.cart_session_purchase_rate, num: m.cart_sessions_with_carted_product_purchase, den: m.sessions_with_cart },
  ];
  const noPurchase = metric("Cart sessions with no observed purchase");

  return (
    <div className="space-y-12">
      <PageHeader title="The session funnel">
        <p>
          Descriptive only: where sessions stop between a view and a purchase, which paths purchases take, and where
          carted value with no observed purchase sits. No observed purchase in a session does not mean no purchase: it may
          have happened in another session or on another device.
        </p>
      </PageHeader>

      <Section n={1} title="Session funnel">
        <ul className="space-y-3">
          {steps.map((s) => (
            <li key={s.entry.key} className="text-sm">
              <div className="flex justify-between gap-3">
                <span title={s.entry.definition}>{s.entry.display_label}</span>
                <span className="num text-muted">
                  {fmtInt(s.n)} <span className="text-xs">({fmtPct(s.n / m.sessions, 2)} of sessions)</span>
                </span>
              </div>
              <Bar share={s.n / m.sessions} />
            </li>
          ))}
          <li className="text-sm">
            <div className="flex justify-between gap-3">
              <span title={purchaseStep.definition}>{purchaseStep.display_label}</span>
              <span className="num text-muted">
                {fmtInt(m.sessions_with_purchase)}{" "}
                <span className="text-xs">({fmtPct(m.sessions_with_purchase / m.sessions, 2)} of sessions)</span>
              </span>
            </div>
            <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
              {purchaseGroups.map((g) => (
                <li key={g.entry.key} className="flex items-center gap-1.5">
                  <span aria-hidden className="h-2 w-3 rounded-sm" style={{ background: g.color }} />
                  {g.entry.short_label}
                </li>
              ))}
            </ul>
            <div className="mt-1 flex h-2 gap-[2px] rounded bg-grid" role="img"
              aria-label={purchaseGroups.map((g) => `${g.entry.display_label}: ${fmtInt(g.n)}`).join("; ")}>
              {purchaseGroups.map((g, i) => (
                <div
                  key={g.entry.key}
                  title={`${g.entry.display_label}: ${fmtInt(g.n)} (${fmtPct(g.n / m.sessions_with_purchase, 1)} of sessions with an observed purchase)`}
                  className={`h-2 ${i === 0 ? "rounded-l" : ""} ${i === purchaseGroups.length - 1 ? "rounded-r" : ""}`}
                  style={{ width: `${(g.n / m.sessions) * 100}%`, background: g.color }}
                />
              ))}
            </div>
            <ul className="mt-2 space-y-0.5 text-xs text-muted">
              {purchaseGroups.map((g) => (
                <li key={g.entry.key} className="num">
                  {g.entry.display_label}: {fmtInt(g.n)} ({fmtPct(g.n / m.sessions_with_purchase, 1)})
                </li>
              ))}
            </ul>
          </li>
        </ul>
        <div className={tableWrap}>
          <table className="w-full text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className={th}>Rate</th>
                <th className={`${th} text-right`}>Value</th>
                <th className={`${th} text-right`}>Count</th>
              </tr>
            </thead>
            <tbody>
              {rates.map((r) => (
                <tr key={r.entry.key} className="border-b border-line last:border-0">
                  <td className={td}>
                    {r.entry.display_label}
                    <div className="text-xs text-muted">{r.entry.definition}</div>
                  </td>
                  <td className={`${td} num text-right`}>{fmtPct(r.value, 2)}</td>
                  <td className={`${td} num text-right text-muted`}>
                    {fmtInt(r.num)} of {fmtInt(r.den)}
                  </td>
                </tr>
              ))}
              {[
                { entry: noPurchase, n: m.cart_sessions_with_no_observed_purchase },
                { entry: noCartedPurchase, n: m.cart_sessions_with_purchase_of_no_carted_product },
              ].map((r) => (
                <tr key={r.entry.key} className="border-b border-line">
                  <td className={td}>
                    {r.entry.display_label}
                    <div className="text-xs text-muted">{r.entry.definition}</div>
                  </td>
                  <td className={`${td} num text-right`}>{fmtPct(r.n / m.sessions_with_cart, 2)}</td>
                  <td className={`${td} num text-right text-muted`}>
                    {fmtInt(r.n)} of {fmtInt(m.sessions_with_cart)}
                  </td>
                </tr>
              ))}
              <tr>
                <td className={`${td} text-xs text-muted`}>
                  The last three rows partition {steps[2].entry.display_label.toLowerCase()} (metrics.md Changes,
                  2026-09-26).
                </td>
                <td className={`${td} num text-right text-xs text-muted`}>{fmtPct(cartRowsTotal / m.sessions_with_cart, 2)}</td>
                <td className={`${td} num text-right text-xs text-muted`}>
                  {fmtInt(cartRowsTotal)} of {fmtInt(m.sessions_with_cart)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted">
          {m.view_to_cart_session_rate < m.cart_session_purchase_rate
            ? "Of the two step rates, the lower is from a view to a cart event: "
            : "Of the two step rates, the lower is from a cart event to a purchase: "}
          {fmtPct(m.view_to_cart_session_rate, 1)} of viewing sessions have an observed cart event, and{" "}
          {fmtPct(m.cart_session_purchase_rate, 1)} of sessions with a cart event have an observed purchase of a carted
          product.
          {m.sessions_with_purchase > m.sessions_with_cart &&
            " More sessions have an observed purchase than an observed cart event, because a purchase counts whether or not the product was carted in the same session."}{" "}
          {fmtInt(m.sessions_with_purchases_only_of_uncarted_products)} of the {fmtInt(m.sessions_with_purchase)} sessions with
          an observed purchase ({fmtPct(m.sessions_with_purchases_only_of_uncarted_products / m.sessions_with_purchase, 1)})
          bought only products with no observed cart event in the same session, so the purchase bar is not a narrower step
          of the cart-event bar above it.
        </p>
        <Sources fields={["kpis.json: month.sessions, .sessions_with_view, .sessions_with_cart, .sessions_with_purchase, .view_to_cart_session_rate, .cart_session_purchase_rate, .cart_sessions_with_no_observed_purchase", "kpis.json: month.sessions_with_purchase_of_carted_product, .sessions_with_purchases_only_of_uncarted_products, .cart_sessions_with_purchase_of_no_carted_product", "metrics_index.json: display_label, short_label, definition (metrics.md §6; Changes 2026-09-26)"]} />
      </Section>

      <Section n={2} title="Purchase paths">
        <ul className="space-y-3">
          {paths.map((p) => (
            <li key={p.purchase_path} className="text-sm">
              <div className="flex flex-wrap justify-between gap-x-3">
                <span>{p.purchase_path}</span>
                <span className="num text-muted">
                  {fmtPct(p.revenue_share, 1)} of revenue · {fmtDollarsCompact(p.revenue)} · {fmtInt(p.purchase_events)} purchase events
                </span>
              </div>
              <Bar share={p.revenue_share} />
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">
          Each purchase event is classified by whether its product has a cart event anywhere in the same session. A
          purchase with no observed same-session cart event may have been carted in an earlier session.
        </p>
        <Sources fields={["purchase_paths.json: rows[].purchase_path, .purchase_events, .revenue, .revenue_share"]} />
      </Section>

      <Section n={3} title="Categories">
        <p className="text-sm">
          The three named top-level categories holding the most carted value with no observed purchase in this session are{" "}
          {leaders.map((r, i) => (
            <span key={r.category_key}>
              {i > 0 && (i === leaders.length - 1 ? ", and " : ", ")}
              <span className="font-medium">{r.category}</span> (
              <span className="num">{fmtDollarsCompact(r.carted_value_with_no_observed_purchase)}</span>,{" "}
              {fmtPct(r.carted_value_with_no_observed_purchase / totalCarted, 1)})
            </span>
          ))}
          {unknownTop && (
            <>
              . The unknown category holds {fmtDollarsCompact(unknownTop.carted_value_with_no_observed_purchase)} (
              {fmtPct(unknownTop.carted_value_with_no_observed_purchase / totalCarted, 1)})
            </>
          )}
          , out of {fmtDollarsCompact(totalCarted)} in total.
        </p>
        <p className="rounded-lg border border-line bg-surface p-4 text-sm text-muted">
          Unknown category: {fmtPct(cat.unknown_shares.unknown_category_event_share, 1)} of events and{" "}
          {fmtPct(cat.unknown_shares.unknown_category_revenue_share, 1)} of revenue.
        </p>
        <CategoryTable rows={top} caption="Top-level categories" />
        <ul className="list-disc space-y-1 pl-5 text-xs text-muted">
          {cat.disclosures.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
        <Sources fields={["funnel_category.json: category_top[].funnel_pairs, .view_to_cart_step_rate, .cart_to_purchase_step_rate, .revenue, .carted_value_with_no_observed_purchase", "funnel_category.json: unknown_shares, disclosures"]} />
        <details className="text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">
            Drill-down: all {fmtInt(codes.length)} full category codes
          </summary>
          <div className="mt-3">
            <CategoryTable rows={codes} caption="Full category codes" />
          </div>
        </details>
      </Section>
    </div>
  );
}
