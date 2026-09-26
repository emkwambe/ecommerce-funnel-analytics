"use client";

import { useRef, useState } from "react";

export type LinePoint = { x: number; y: number };
export type LineSeries = { key: string; name: string; color: string; dashed?: boolean; points: LinePoint[] };
export type Marker = { x: number; label: string };
export type AxisFormat = "dollars" | "dollars0" | "percent" | "percent1" | "fraction" | "count" | "day";

const fmt = (kind: AxisFormat, v: number, prefix = "") => {
  const sign = v < 0 ? "−" : "";
  const a = Math.abs(v);
  switch (kind) {
    case "percent1":
      return `${sign}${(a * 100).toFixed(1)}%`;
    case "count":
      return a >= 1e6 ? `${sign}${(a / 1e6).toFixed(2)}M` : a >= 1e3 ? `${sign}${(a / 1e3).toFixed(0)}K` : `${sign}${a}`;
    case "day":
      return `${prefix} ${a}`.trim();
    case "dollars":
      return `${sign}$${a.toFixed(2)}`;
    case "dollars0":
      return `${sign}$${a.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
    case "percent":
      return `${sign}${(a * 100).toFixed(0)}%`;
    case "fraction":
      return `${sign}${a.toFixed(2)}`;
  }
};

/**
 * Line chart: SVG plot (viewBox 0..100, non-scaling strokes) with HTML axis labels so text stays crisp at any
 * width. A crosshair tracks the pointer (or keyboard focus) and lists every series at the nearest x.
 */
export function LineChart({
  series,
  xDomain,
  yDomain,
  xTicks,
  yTicks,
  xFormat,
  yFormat,
  xLabel,
  yLabel,
  markers = [],
  xPrefix = "",
  height = 240,
}: {
  series: LineSeries[];
  xDomain: [number, number];
  yDomain: [number, number];
  xTicks: number[];
  yTicks: number[];
  xFormat: AxisFormat;
  yFormat: AxisFormat;
  xLabel: string;
  yLabel: string;
  markers?: Marker[];
  /** Label text before a "day" tick, e.g. the month name read from the data. */
  xPrefix?: string;
  height?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const px = (x: number) => ((x - xDomain[0]) / (xDomain[1] - xDomain[0])) * 100;
  const py = (y: number) => 100 - ((y - yDomain[0]) / (yDomain[1] - yDomain[0])) * 100;
  const xs = series[0]?.points.map((p) => p.x) ?? [];

  function nearest(clientX: number) {
    const box = ref.current?.getBoundingClientRect();
    if (!box || xs.length === 0) return;
    const x = xDomain[0] + ((clientX - box.left) / box.width) * (xDomain[1] - xDomain[0]);
    let best = 0;
    xs.forEach((v, i) => {
      if (Math.abs(v - x) < Math.abs(xs[best] - x)) best = i;
    });
    setHover(best);
  }

  const hx = hover === null ? null : xs[hover];

  return (
    <figure className="space-y-2">
      {series.length > 1 && (
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted" aria-label="Legend">
          {series.map((s) => (
            <li key={s.key} className="flex items-center gap-2">
              <svg width="22" height="8" aria-hidden>
                <line x1="1" x2="21" y1="4" y2="4" stroke={s.color} strokeWidth="2" strokeLinecap="round"
                  strokeDasharray={s.dashed ? "4 3" : undefined} />
              </svg>
              {s.name}
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <div className="relative w-12 shrink-0 text-right text-[11px] text-muted" style={{ height }} aria-hidden>
          {yTicks.map((t) => (
            <span key={t} className="num absolute right-0 -translate-y-1/2" style={{ top: `${py(t)}%` }}>
              {fmt(yFormat, t)}
            </span>
          ))}
        </div>
        <div className="min-w-0 flex-1">
          <div
            ref={ref}
            className="relative touch-pan-y outline-none focus-visible:ring-2 focus-visible:ring-accent"
            style={{ height }}
            tabIndex={0}
            role="img"
            aria-label={`${yLabel} by ${xLabel}`}
            onPointerMove={(e) => nearest(e.clientX)}
            onPointerLeave={() => setHover(null)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") setHover((h) => Math.min(xs.length - 1, (h ?? -1) + 1));
              if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? xs.length) - 1));
            }}
            onBlur={() => setHover(null)}
          >
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible">
              {yTicks.map((t) => (
                <line key={`y${t}`} x1="0" x2="100" y1={py(t)} y2={py(t)} stroke={t === 0 ? "var(--zero)" : "var(--grid)"}
                  strokeWidth="1" vectorEffect="non-scaling-stroke" />
              ))}
              {markers.map((m) => (
                <line key={`m${m.x}`} x1={px(m.x)} x2={px(m.x)} y1="0" y2="100" stroke="var(--zero)" strokeWidth="1"
                  strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
              ))}
              {series.map((s) => (
                <polyline key={s.key} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"
                  strokeDasharray={s.dashed ? "5 4" : undefined} vectorEffect="non-scaling-stroke"
                  points={s.points.map((p) => `${px(p.x)},${py(p.y)}`).join(" ")} />
              ))}
              {hx !== null && (
                <line x1={px(hx)} x2={px(hx)} y1="0" y2="100" stroke="var(--muted)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
              )}
            </svg>
            {markers.map((m, i) => {
              const pos = px(m.x);
              const shift = pos > 70 ? "-translate-x-full" : pos < 30 ? "" : "-translate-x-1/2";
              return (
                <span key={`ml${m.x}`} className={`absolute whitespace-nowrap rounded bg-surface px-1 text-[10px] text-muted ${shift}`}
                  style={{ left: `${pos}%`, top: i * 14 }}>
                  {m.label}
                </span>
              );
            })}
            {hx !== null && hover !== null && (
              <div
                className="pointer-events-none absolute z-10 rounded-md border border-line bg-surface px-2 py-1.5 text-xs shadow-sm"
                style={{ left: `${Math.min(70, Math.max(0, px(hx) - 15))}%`, top: 8 }}
                role="status"
              >
                <div className="text-muted">{xLabel}: {fmt(xFormat, hx, xPrefix)}</div>
                {series.map((s) => (
                  <div key={s.key} className="flex items-center gap-1.5 whitespace-nowrap">
                    <svg width="12" height="6" aria-hidden>
                      <line x1="1" x2="11" y1="3" y2="3" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? "3 2" : undefined} />
                    </svg>
                    <span className="num font-semibold">{fmt(yFormat, s.points[hover]?.y ?? NaN)}</span>
                    <span className="text-muted">{s.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="relative h-5 text-[11px] text-muted" aria-hidden>
            {xTicks.map((t, i) => (
              <span key={t} className={`num absolute top-1 whitespace-nowrap ${i === 0 ? "" : i === xTicks.length - 1 ? "-translate-x-full" : "-translate-x-1/2"}`}
                style={{ left: `${px(t)}%` }}>
                {fmt(xFormat, t, xPrefix)}
              </span>
            ))}
          </div>
          <figcaption className="mt-1 text-center text-xs text-muted">{xLabel} · {yLabel}</figcaption>
        </div>
      </div>
    </figure>
  );
}
