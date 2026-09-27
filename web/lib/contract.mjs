// The /metrics page renders docs/metrics.md, but a Changes entry still marked "DRAFT, pending H3" defines nothing:
// its metrics may not be published or answered until the owner approves it (CLAUDE.md rules 3 and 4). The page keeps
// the entry's heading and replaces its body with a notice. Plain JS so pytest can run it with node
// (analysis/tests/test_web.py, test_metrics_page_never_shows_draft_entries_as_defined_metrics).

export const DRAFT_MARKER = "DRAFT, pending H3";

export const DRAFT_NOTICE =
  "*Proposed change awaiting the owner's approval (H3). Nothing in it is a defined metric; its text appears here once it is approved.*";

/** Each "### ... DRAFT, pending H3" entry keeps its heading; its body, up to the next ### or ## heading, is replaced. */
export function withoutDraftEntries(markdown) {
  return markdown.replace(
    /^### ([^\n]*DRAFT, pending H3[^\n]*)\n[\s\S]*?(?=^### |^## |(?![\s\S]))/gm,
    (_entry, heading) => `### ${heading}\n\n${DRAFT_NOTICE}\n\n`,
  );
}
