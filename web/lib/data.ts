import { readFileSync } from "node:fs";
import { join } from "node:path";

/** Provenance block on every export (CLAUDE.md rule 5), written by python -m funnel.export. */
export type Manifest = {
  git_commit_sha: string;
  git_worktree_dirty: boolean;
  dataset_sha256: string;
  generated_at_utc: string;
  script: string;
};

export type PipelineBuild = {
  git_commit_sha: string;
  generated_at_utc: string;
  dbt_done_counts: Record<string, number> | null;
  test_coverage: { models_built: number; tests_expected: number; tests_run: number; tests_expected_not_run: string[] } | null;
};

type Export = { manifest: Manifest; pipeline_build: PipelineBuild };

export type KpiRow = {
  period_key: string;
  period_type: "day" | "month";
  period_start: string;
  period_label: string;
  sessions: number;
  sessions_with_view: number;
  sessions_with_cart: number;
  sessions_with_purchase: number;
  orders: number;
  viewing_sessions_with_cart: number;
  cart_sessions_with_carted_product_purchase: number;
  cart_sessions_with_no_observed_purchase: number;
  sessions_with_purchase_of_carted_product: number;
  sessions_with_purchases_only_of_uncarted_products: number;
  cart_sessions_with_purchase_of_no_carted_product: number;
  revenue: number;
  revenue_repeat_collapsed: number;
  session_purchase_rate: number;
  view_to_cart_session_rate: number;
  cart_session_purchase_rate: number;
  average_order_value: number;
  revenue_per_session: number;
};

export type CategoryRow = {
  category_key: string;
  category_level: "category_top" | "category_code";
  category: string;
  events: number;
  funnel_pairs: number;
  funnel_pairs_with_cart: number;
  funnel_pairs_with_purchase: number;
  funnel_cart_pairs_with_carted_product_purchase: number;
  purchase_events: number;
  revenue: number;
  carted_pairs: number;
  carted_pairs_with_purchase: number;
  carted_pairs_with_no_observed_purchase: number;
  zero_price_carted_pairs: number;
  carted_value_with_no_observed_purchase: number;
  view_to_cart_step_rate: number | null;
  cart_to_purchase_step_rate: number | null;
};

export type PathRow = { purchase_path: string; purchase_events: number; revenue: number; revenue_share: number };

export type QualityRow = {
  metric_key: string;
  metric_group: "data_quality" | "long_session_sensitivity";
  metric_label: string;
  basis: string;
  value: number;
  value_excluding_long_sessions: number | null;
  sprint0_raw_basis_value: number | null;
  sort_order: number;
};

export type MetricEntry = {
  key: string;
  name: string;
  definition: string;
  display_label: string;
  section: string;
  /** Chart legend label, where the contract gives one; tables and tooltips use display_label. */
  short_label: string | null;
  /** Remainder of a Changes-entry definition after its first sentence. */
  note: string | null;
};

export type ChangesEntry = { title: string; date: string; sections: string[] };

export type DataStory = Export & {
  source: {
    title: string;
    publisher: string;
    kaggle_slug: string;
    kaggle_url: string;
    rees46_url: string;
    obtained_with: string;
    file_name: string;
    size_bytes: number;
    retrieved_at_utc: string;
    sha256: string;
    license_field: string;
    publisher_usage_statement: string;
    attribution_links: string[];
  };
  contents: {
    grain: string;
    raw_rows: number;
    columns: string[];
    event_type_counts: Record<string, number>;
    min_event_time_utc: string;
    max_event_time_utc: string;
    distinct_counts: Record<string, number>;
    order_or_transaction_id_exists: boolean;
  };
  pre_analysis_findings: { finding: string; count: number; profile_field: string }[];
  decisions: { id: string; title: string; summary: string; metrics_section: string; related_sections: string[]; changes: string[] }[];
  changes_entries: ChangesEntry[];
  reconciliation: {
    raw_rows: number;
    exact_duplicate_rows_removed: number;
    deduplicated_events: number;
    null_session_events_excluded: number;
    multi_user_sessions_excluded: number;
    events_in_multi_user_sessions_excluded: number;
    valid_session_events: number;
    valid_sessions: number;
    orders: number;
  };
  data_quality_shares: Record<string, number>;
  limitations: { text: string; supporting_fields: string[] }[];
};

export type Workflow = Export & {
  timeline: { event: string; label: string; sha: string; short_sha: string; date_utc: string; subject: string }[];
  correction_log: {
    source: string;
    n_entries: number;
    by_origin: Record<string, number>;
    by_caught: Record<string, number>;
    by_phase: Record<string, number>;
    origin_rule: string;
    caught_rules: { category: string; keywords: string[] }[];
    entries: { date: string; phase: string; title: string; origin: string; caught_by: string }[];
  };
  workflow_files: string[];
};

export type GapCell = {
  row_key: string;
  dimension: string;
  group_key: string;
  group_label: string;
  repeat_purchase_events: number;
  pairs: number;
  repeat_purchase_value: number;
  share_of_difference: number;
  top_10_pair_share: number | null;
};

export type RevenueGap = Export & {
  question: string;
  method_record: string;
  contract: string;
  totals: {
    revenue: number;
    revenue_repeat_collapsed: number;
    revenue_difference: number;
    repeat_purchase_events: number;
    pairs: number;
    repeat_purchase_value: number;
  };
  dimensions: Record<"time_since_previous_purchase" | "price_vs_first_purchase" | "purchase_events_in_pair" | "time_by_price" | "category_top", GapCell[]>;
  thresholds: { threshold_seconds: number; threshold_label: string; repeat_purchase_events_within: number; repeat_purchase_value_within: number; share_of_difference: number }[];
  secondary_cases: {
    exact_duplicate_rows: { event_type: string; group_size: string; group_size_label: string; duplicate_groups: number; rows_removed: number }[];
    cart_no_view_reconciliation: {
      sprint0_raw_basis_count: number;
      raw_basis_count: number;
      in_null_session_events: number;
      in_multi_user_sessions: number;
      removed_as_exact_duplicates: number;
      contract_basis_count: number;
      difference: number;
      remainder: number;
    };
  };
  independent_verification: { checks: number; all_match: boolean; verify_git_commit_sha: string; verify_generated_at_utc: string };
};

export type LaterEstimate = {
  spec_key: "B1" | "B2" | "B3" | "B5" | "B6" | "B7" | "B8";
  pair_type: "carted" | "viewed";
  window_days: number;
  cutoff: string;
  population: string;
  eligible_pairs: number;
  followed_pairs: number;
  count_share: number;
  count_interval: [number, number];
  eligible_value: number;
  followed_value: number;
  value_share: number;
  value_interval: [number, number];
  users: number;
};

export type LaterPurchases = Export & {
  question: string;
  method_record: string;
  contract: string;
  estimates: LaterEstimate[];
  kaplan_meier: {
    curve: { days: number; count: number; count_interval: [number, number]; value_weighted: number; value_weighted_interval: [number, number] }[];
    pairs: number;
    events: number;
    users: number;
    resamples: number;
    seed: number;
  };
  kaplan_meier_population: string;
  cohort_difference: {
    b1_population: string;
    b1_count_share: number;
    b1_count_interval: [number, number];
    later_population: string;
    later_km_7_day: number;
    later_km_7_day_interval: [number, number];
    matched_km_7_day: number;
  };
  within_1_hour_disclosure: { share_of_followed_pairs: number; population: string };
  seed_stability: { seed: number; b1_count_interval: [number, number]; b1_value_interval: [number, number]; km_7_day_count_interval: [number, number] }[];
  stop_rules: { rule: string; fired: boolean; owner_resolution: string | null }[];
  dominance: { share_of_followed_pairs_held_by_top_0_1_pct_users: number; exceeds_limit: boolean; limit: number };
  checks: { row_key: string; metric_group: string; metric_key: string; value: number }[];
  independent_verification: { checks: number; all_match: boolean; verify_git_commit_sha: string; verify_generated_at_utc: string };
};

function read<T>(name: string): T {
  return JSON.parse(readFileSync(join(process.cwd(), "public", "data", name), "utf-8")) as T;
}

export const getKpis = () => read<Export & { month: KpiRow; daily: KpiRow[] }>("kpis.json");
export const getFunnelCategory = () =>
  read<Export & {
    category_top: CategoryRow[];
    category_code: CategoryRow[];
    unknown_shares: Record<string, number>;
    disclosures: string[];
  }>("funnel_category.json");
export const getPurchasePaths = () => read<Export & { rows: PathRow[] }>("purchase_paths.json");
export const getDataQuality = () => read<Export & { rows: QualityRow[] }>("data_quality.json");
export const getMetricsIndex = () => read<Export & { metrics: MetricEntry[] }>("metrics_index.json");
export const getDataStory = () => read<DataStory>("data_story.json");
export const getWorkflow = () => read<Workflow>("workflow.json");
export const getRevenueGap = () => read<RevenueGap>("investigation_revenue_gap.json");
export const getLaterPurchases = () => read<LaterPurchases>("investigation_later_purchases.json");

/** A metric by its metrics_index key, e.g. "2026-09-26_item_9" for a numbered Changes-entry item. */
export function metricByKey(key: string): MetricEntry {
  const found = getMetricsIndex().metrics.find((m) => m.key === key);
  if (!found) throw new Error(`metrics_index.json has no metric with key "${key}"`);
  return found;
}

/** A metric's definition and display label by name, from metrics_index.json (parsed from docs/metrics.md). */
export function metric(name: string): MetricEntry {
  const found = getMetricsIndex().metrics.find((m) => m.name === name);
  if (!found) throw new Error(`metrics_index.json has no metric named "${name}"`);
  return found;
}

export function getMetricsMarkdown(): string {
  return readFileSync(join(process.cwd(), "content", "metrics.md"), "utf-8");
}
