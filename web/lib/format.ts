const int = new Intl.NumberFormat("en-US");

export const fmtInt = (n: number) => int.format(n);

export const fmtFixed = (n: number, digits: number) =>
  n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const fmtPct = (x: number, digits = 1) => `${fmtFixed(x * 100, digits)}%`;

export const fmtDollars = (x: number, digits = 2) => `$${fmtFixed(x, digits)}`;

/** Large dollar amounts: $229.9M, $12.4K. */
export function fmtDollarsCompact(x: number): string {
  const a = Math.abs(x);
  if (a >= 1e9) return `$${fmtFixed(x / 1e9, 2)}B`;
  if (a >= 1e6) return `$${fmtFixed(x / 1e6, 1)}M`;
  if (a >= 1e3) return `$${fmtFixed(x / 1e3, 1)}K`;
  return fmtDollars(x);
}

/** Large counts: 9.24M, 42.4K. */
export function fmtIntCompact(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e6) return `${fmtFixed(n / 1e6, 2)}M`;
  if (a >= 1e4) return `${fmtFixed(n / 1e3, 1)}K`;
  return fmtInt(n);
}

export const shortSha = (sha: string, n = 7) => sha.slice(0, n);

export const REPO_URL = "https://github.com/emkwambe/ecommerce-funnel-analytics";
export const commitUrl = (sha: string) => `${REPO_URL}/commit/${sha}`;
export const treeUrl = (path: string) => `${REPO_URL}/tree/main/${path}`;
export const blobUrl = (path: string) => `${REPO_URL}/blob/main/${path}`;
