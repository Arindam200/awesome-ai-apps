"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useProject } from "./ProjectProvider";

const NAV = [
  { href: "/", label: "Brief" },
  { href: "/compose", label: "Compose" },
  { href: "/signals", label: "Signals" },
  { href: "/documents", label: "Documents" },
  { href: "/settings", label: "Settings" },
];

export default function Header() {
  const { projects, selected, setSelectedId } = useProject();
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <header className="sticky top-0 z-50 h-14 border-b border-line bg-card">
      <div className="mx-auto flex h-full max-w-5xl items-center justify-between gap-4 px-6">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-[11px] font-bold uppercase tracking-[2px] text-accent">
            Maintainer&nbsp;Brief
          </Link>

          {/* project switcher */}
          <div ref={ref} className="relative">
            <button
              onClick={() => setOpen((o) => !o)}
              className="flex items-center gap-1.5 rounded-sm border border-line px-2.5 py-1 text-sm hover:bg-paper"
            >
              <span className="max-w-[160px] truncate font-medium">
                {selected ? selected.name : "Select project"}
              </span>
              <span className="text-muted">▾</span>
            </button>
            {open && (
              <div className="absolute left-0 top-9 z-50 w-60 rounded-sm border border-line bg-card py-1 shadow-lg">
                {projects.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setSelectedId(p.id);
                      setOpen(false);
                    }}
                    className={`block w-full px-3 py-1.5 text-left text-sm hover:bg-paper ${
                      selected?.id === p.id ? "font-bold text-accent" : ""
                    }`}
                  >
                    {p.name}
                  </button>
                ))}
                <div className="my-1 border-t border-line" />
                <Link
                  href="/new"
                  onClick={() => setOpen(false)}
                  className="block px-3 py-1.5 text-left text-sm font-bold text-accent hover:bg-accent-soft"
                >
                  ＋ New brief
                </Link>
              </div>
            )}
          </div>
        </div>

        <nav className="flex gap-5 text-sm text-muted">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`hover:text-ink ${pathname === n.href ? "text-ink" : ""}`}
            >
              {n.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
