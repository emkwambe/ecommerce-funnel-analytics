import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { getDataStory } from "@/lib/data";
import { REPO_URL, commitUrl, shortSha } from "@/lib/format";
import { ThemeToggle, themeInitScript } from "./theme-toggle";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "E-commerce Funnel Analytics",
  description: "Where sessions end with no observed purchase in a large e-commerce event log, and what to test first.",
};

const NAV = [
  { href: "/funnel", label: "Funnel" },
  { href: "/investigations", label: "Investigations" },
  { href: "/how-its-built", label: "How it's built" },
  { href: "/data", label: "Data" },
  { href: "/data-quality", label: "Data quality" },
  { href: "/metrics", label: "Metrics" },
  { href: "/questions", label: "Further research" },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const { manifest, source } = getDataStory();
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}>
        <header className="border-b border-line">
          <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-4 sm:px-6">
            <Link href="/" className="font-semibold tracking-tight">
              E-commerce Funnel Analytics
            </Link>
            <nav className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm sm:gap-x-4">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} className="text-muted hover:text-ink">
                  {n.label}
                </Link>
              ))}
              <a
                href={REPO_URL}
                aria-label="GitHub"
                title="GitHub"
                className="inline-flex items-center text-muted hover:text-ink"
                data-testid="github-link"
              >
                {/* The GitHub mark (Octicons "mark-github"), drawn in the current text color so it follows the theme. */}
                <svg aria-hidden="true" viewBox="0 0 16 16" width="20" height="20" fill="currentColor">
                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                </svg>
              </a>
              <ThemeToggle />
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto max-w-4xl space-y-2 px-4 py-6 text-xs text-muted sm:px-6">
            <p className="text-sm text-ink">An analytics case study built with Claude Code by Eddy Mkwambe.</p>
            <p data-testid="attribution">
              Data: {source.title} by REES46.{" "}
              <a className="underline" href={source.kaggle_url}>Kaggle dataset page</a>
              {" · "}
              <a className="underline" href={source.rees46_url}>REES46 Marketing Platform</a>
            </p>
            <p>
              Data exported by <code>{manifest.script}</code> at commit{" "}
              <a className="underline" href={commitUrl(manifest.git_commit_sha)}>
                {shortSha(manifest.git_commit_sha)}
              </a>{" "}
              on {manifest.generated_at_utc}. Dataset SHA-256 <code className="break-all">{manifest.dataset_sha256}</code>.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
