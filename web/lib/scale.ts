/** Linear-scale helpers for the inline SVG charts. Domains are derived from the data being drawn. */

export type Domain = [number, number];

function niceStep(span: number, target: number): number {
  const raw = span / Math.max(1, target);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
  return nice * mag;
}

/** A domain covering every value (and zero), extended to nice tick boundaries. */
export function niceDomain(values: number[], targetTicks = 5): { domain: Domain; ticks: number[] } {
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values);
  const step = niceStep(hi - lo || 1, targetTicks);
  const d0 = Math.floor(lo / step) * step;
  const d1 = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let t = d0; t <= d1 + step / 2; t += step) ticks.push(Number((Math.round(t / step) * step).toPrecision(12)));
  return { domain: [d0, d1], ticks };
}

/** Position as a percentage of the plot width, for SVG attributes such as x="42.5%". */
export function pct(x: number, [d0, d1]: Domain): string {
  return `${(((x - d0) / (d1 - d0)) * 100).toFixed(3)}%`;
}
