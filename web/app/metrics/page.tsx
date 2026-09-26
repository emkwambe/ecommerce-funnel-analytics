import type { Metadata } from "next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getMetricsMarkdown } from "@/lib/data";
import { blobUrl } from "@/lib/format";

export const metadata: Metadata = { title: "Metrics · E-commerce Funnel Analytics" };

/** "1. Naming rules" -> "section-1"; "Changes" -> "section-changes" (the anchors other pages link to). */
function sectionId(text: string): string {
  const n = text.match(/^(\d+)\./);
  return `section-${n ? n[1] : text.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

const textOf = (node: React.ReactNode): string =>
  typeof node === "string" ? node : Array.isArray(node) ? node.map(textOf).join("") : "";

export default function MetricsPage() {
  return (
    <div className="space-y-6">
      <p className="rounded-lg border border-line bg-surface p-4 text-sm text-muted">
        Rendered from{" "}
        <a className="text-accent underline" href={blobUrl("docs/metrics.md")}>docs/metrics.md</a>, the metric contract.
        It was committed before any business metric was computed and changes only through dated entries in its Changes
        section. A test fails if this page&apos;s copy differs from the committed file.
      </p>
      <article className="prose prose-neutral max-w-none dark:prose-invert prose-headings:tracking-tight prose-a:text-accent">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h2: ({ children }) => <h2 id={sectionId(textOf(children))} className="scroll-mt-6">{children}</h2>,
            table: ({ children }) => (
              <div className="overflow-x-auto">
                <table>{children}</table>
              </div>
            ),
          }}
        >
          {getMetricsMarkdown()}
        </ReactMarkdown>
      </article>
    </div>
  );
}
