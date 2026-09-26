/**
 * Small inline charts for the investigation pages: horizontal share bars and bars with a 95% interval. Every row
 * carries its value as text beside the mark (direct labels), and a title tooltip with the counts behind it, so
 * identity and value never depend on color alone. Colors are the site's series tokens (validated in both themes).
 */

import { fmtPct } from "@/lib/format";

export type ShareRow = { key: string; label: string; share: number; detail: string };

/** One bar per row, as a share of a whole (0 to 1). */
export function ShareBars({ rows, caption, color = "var(--series-1)" }: { rows: ShareRow[]; caption: string; color?: string }) {
  return (
    <figure className="space-y-2">
      <ul className="space-y-2">
        {rows.map((r) => (
          <li key={r.key} className="space-y-1" title={r.detail}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0">{r.label}</span>
              <span className="num shrink-0 font-semibold">{fmtPct(r.share, 1)}</span>
            </div>
            <div className="h-2 rounded bg-grid" aria-hidden>
              <div className="h-2 rounded" style={{ width: `${Math.max(0, Math.min(1, r.share)) * 100}%`, background: color }} />
            </div>
            <div className="num text-xs text-muted">{r.detail}</div>
          </li>
        ))}
      </ul>
      <figcaption className="text-xs text-muted">{caption}</figcaption>
    </figure>
  );
}

export type IntervalRow = { key: string; label: string; value: number; lower: number; upper: number; detail: string; color: string };

/** One bar per row with its 95% interval as a whisker, on a shared axis from 0 to `max`. */
export function IntervalBars({ rows, max, caption }: { rows: IntervalRow[]; max: number; caption: string }) {
  const x = (v: number) => `${(Math.max(0, Math.min(max, v)) / max) * 100}%`;
  return (
    <figure className="space-y-3">
      <ul className="space-y-3">
        {rows.map((r) => (
          <li key={r.key} className="space-y-1" title={r.detail}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="flex min-w-0 items-center gap-2">
                <svg width="10" height="10" aria-hidden className="shrink-0">
                  <rect width="10" height="10" rx="2" fill={r.color} />
                </svg>
                {r.label}
              </span>
              <span className="num shrink-0 font-semibold">
                {fmtPct(r.value, 1)} <span className="font-normal text-muted">[{fmtPct(r.lower, 1)}, {fmtPct(r.upper, 1)}]</span>
              </span>
            </div>
            <svg className="block h-4 w-full overflow-visible" aria-hidden>
              <rect x="0" y="5" width="100%" height="6" rx="3" fill="var(--grid)" />
              <rect x="0" y="5" width={x(r.value)} height="6" rx="3" fill={r.color} />
              <line x1={x(r.lower)} x2={x(r.upper)} y1="8" y2="8" stroke="var(--ink)" strokeWidth="1.5" />
              <line x1={x(r.lower)} x2={x(r.lower)} y1="3" y2="13" stroke="var(--ink)" strokeWidth="1.5" />
              <line x1={x(r.upper)} x2={x(r.upper)} y1="3" y2="13" stroke="var(--ink)" strokeWidth="1.5" />
            </svg>
            <div className="num text-xs text-muted">{r.detail}</div>
          </li>
        ))}
      </ul>
      <figcaption className="text-xs text-muted">
        {caption} Bars run from 0 to {fmtPct(max, 0)}; whiskers show the 95% interval.
      </figcaption>
    </figure>
  );
}
