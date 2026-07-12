"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Plus, Newspaper, Send, Activity, FileText, Settings2, LogOut } from "lucide-react";
import { useProject } from "./ProjectProvider";
import { useAuth } from "./AuthProvider";

const NAV = [
  { href: "/", label: "Brief", icon: Newspaper },
  { href: "/compose", label: "Compose", icon: Send },
  { href: "/signals", label: "Signals", icon: Activity },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings2 },
];

function LogoMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 8V3h5" stroke="#3553FF" strokeWidth="2.5" />
      <path d="M16 21h5v-5" stroke="#3553FF" strokeWidth="2.5" />
      <rect x="8" y="8" width="8" height="8" rx="1.5" fill="#3553FF" />
    </svg>
  );
}

export default function Header() {
  const { projects, selected, setSelectedId } = useProject();
  const { user, logout } = useAuth();
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

  // Logged-out (public preview): minimal bar — logo + sign-in, no nav/switcher.
  if (!user) {
    return (
      <header className="sticky top-0 z-50 bg-surface/90 backdrop-blur">
        <div className="h-[3px] bg-primary" />
        <div className="border-b border-line">
          <div className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-6">
            <Link href="/" className="flex items-center gap-2">
              <LogoMark />
              <span className="font-display text-[15px] font-semibold tracking-tight text-ink">
                Maintainer Brief
              </span>
            </Link>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-50 bg-surface/90 backdrop-blur">
      <div className="h-[3px] bg-primary" />
      <div className="border-b border-line">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-6">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2">
              <LogoMark />
              <span className="font-display text-[15px] font-semibold tracking-tight text-ink">
                Maintainer Brief
              </span>
            </Link>

            <span className="h-5 w-px bg-line" />

            {/* project switcher */}
            <div ref={ref} className="relative">
              <button
                onClick={() => setOpen((o) => !o)}
                className="flex items-center gap-1.5 rounded-[6px] border border-line px-2.5 py-1 text-sm text-ink transition-colors hover:bg-surface-2"
              >
                <span className="max-w-[160px] truncate font-medium">
                  {selected ? selected.name : "Select project"}
                </span>
                <ChevronDown size={14} className="text-muted" />
              </button>
              {open && (
                <div className="absolute left-0 top-10 z-50 w-60 overflow-hidden rounded-[6px] border border-line bg-surface py-1 shadow-[0_12px_32px_-12px_rgba(43,41,38,0.25)]">
                  {projects.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => {
                        setSelectedId(p.id);
                        setOpen(false);
                      }}
                      className={`block w-full px-3 py-1.5 text-left text-sm transition-colors hover:bg-surface-2 ${
                        selected?.id === p.id ? "font-semibold text-primary" : "text-ink"
                      }`}
                    >
                      {p.name}
                    </button>
                  ))}
                  <div className="my-1 border-t border-line" />
                  <Link
                    href="/new"
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-left text-sm font-semibold text-primary transition-colors hover:bg-primary-soft"
                  >
                    <Plus size={14} /> New brief
                  </Link>
                </div>
              )}
            </div>
          </div>

          <nav className="flex items-center gap-1">
            {NAV.map((n) => {
              const active = pathname === n.href;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`relative rounded-[6px] px-3 py-1.5 text-sm transition-colors ${
                    active ? "text-ink" : "text-muted hover:text-ink"
                  }`}
                >
                  {n.label}
                  {active && (
                    <span className="absolute inset-x-3 -bottom-[1px] h-[2px] rounded-full bg-primary" />
                  )}
                </Link>
              );
            })}
          </nav>

          {user && (
            <div className="flex items-center gap-2 pl-2">
              <span className="h-5 w-px bg-line" />
              {user.avatar_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.avatar_url} alt="" className="h-6 w-6 rounded-full" />
              )}
              <span className="hidden text-sm text-muted sm:inline">{user.login}</span>
              <button
                onClick={logout}
                title="Sign out"
                className="rounded-[6px] p-1.5 text-muted transition-colors hover:bg-surface-2 hover:text-ink"
              >
                <LogOut size={15} />
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
