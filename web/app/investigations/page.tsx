import Link from "next/link";
import { getLaterPurchases, getRevenueGap } from "@/lib/data";
import { PageHeader } from "../ui";

export const metadata = { title: "Investigations · E-commerce Funnel Analytics" };

export default function InvestigationsPage() {
  const pages = [
    { href: "/investigations/revenue-figures", question: getRevenueGap().question,
      about: "The difference between revenue and revenue with repeat purchase events collapsed, and where it sits." },
    { href: "/investigations/later-purchases", question: getLaterPurchases().question,
      about: "How much carted value with no observed purchase in the session was followed by a same-user purchase in a later session." },
  ];
  return (
    <div className="space-y-10">
      <PageHeader title="Investigations">
        <p>
          Two questions left open by the headline figures. Each page states its question, its answer at the strength the
          evidence supports, how it was checked, and what it cannot show.
        </p>
      </PageHeader>
      <ul className="space-y-4">
        {pages.map((p) => (
          <li key={p.href} className="rounded-lg border border-line bg-surface p-4">
            <Link href={p.href} className="font-medium text-accent underline">{p.question}</Link>
            <p className="mt-1 text-sm text-muted">{p.about}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
