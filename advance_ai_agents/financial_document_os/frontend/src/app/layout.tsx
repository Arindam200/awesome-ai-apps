import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Financial Document OS",
  description: "Turn financial PDFs into a queryable database — powered by Unsiloed.",
};

const NAV = [
  { href: "/", label: "Documents" },
  { href: "/explorer", label: "Explorer" },
  { href: "/vendors", label: "Vendors" },
  { href: "/ask", label: "Ask" },
  { href: "/anomalies", label: "Anomalies" },
  { href: "/edit", label: "Edit" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="sticky top-0 z-50 h-14 border-b border-line bg-card">
          <div className="mx-auto flex h-full max-w-6xl items-center justify-between px-6">
            <Link href="/">
              <span className="text-[11px] font-bold uppercase tracking-[2px] text-accent">
                Financial Document OS
              </span>
            </Link>
            <nav className="flex gap-6 text-sm text-muted">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} className="hover:text-ink">
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
