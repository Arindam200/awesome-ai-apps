"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";
import { MeUser, api, getToken, clearToken, loginUrl } from "@/lib/api";

function GithubMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

interface AuthCtx {
  user: MeUser | null;
  logout: () => Promise<void>;
}
const Ctx = createContext<AuthCtx>({ user: null, logout: async () => {} });
export const useAuth = () => useContext(Ctx);

function SignInScreen() {
  return (
    <div className="mx-auto mt-[16vh] max-w-md px-6 text-center">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
        <Sparkles size={12} className="text-primary" />
        For open-source maintainers
      </span>
      <h1 className="mt-6 font-display text-4xl font-semibold leading-tight tracking-tight text-ink">
        Maintainer Brief
      </h1>
      <p className="mt-4 text-base leading-relaxed text-muted">
        Sign in to point it at your GitHub projects and get a weekly email of what
        actually needs you — duplicate issues to close, PRs ready to merge, newcomers
        going stale, and threads worth a reply.
      </p>
      <a
        href={loginUrl()}
        className="mt-8 inline-flex items-center justify-center gap-2 rounded-[6px] bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-ink/90"
      >
        <GithubMark />
        Sign in with GitHub
      </a>
      <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.16em] text-faint">
        Your projects are private to you
      </p>
    </div>
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<MeUser | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setLoaded(true);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoaded(true));
  }, []);

  const logout = async () => {
    await api.logout().catch(() => {});
    clearToken();
    setUser(null);
    window.location.href = "/";
  };

  // The OAuth callback page must always render (it captures the token).
  if (pathname === "/auth/callback") {
    return <Ctx.Provider value={{ user, logout }}>{children}</Ctx.Provider>;
  }

  if (!loaded) {
    return (
      <p className="mt-[20vh] text-center font-mono text-xs uppercase tracking-[0.16em] text-faint">
        Loading…
      </p>
    );
  }

  if (!user) return <SignInScreen />;

  return <Ctx.Provider value={{ user, logout }}>{children}</Ctx.Provider>;
}
