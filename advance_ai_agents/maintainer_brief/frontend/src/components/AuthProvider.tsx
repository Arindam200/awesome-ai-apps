"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sparkles, ArrowRight } from "lucide-react";
import { GALLERY, MeUser, api, getToken, clearToken, loginUrl } from "@/lib/api";

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

// Routes that render without a session: the OAuth callback (captures the
// token) and the public repo preview (the conversion moment).
const PUBLIC_PREFIXES = ["/auth/callback", "/preview"];

function SignInScreen() {
  const router = useRouter();
  const [repo, setRepo] = useState("");

  const goPreview = () => {
    const r = repo.trim().replace(/^https?:\/\/github\.com\//, "").replace(/\/+$/, "");
    if (r.split("/").length === 2) router.push(`/preview/${r}`);
  };

  return (
    <div className="mx-auto mt-[12vh] max-w-lg px-6 text-center">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
        <Sparkles size={12} className="text-primary" />
        For open-source maintainers
      </span>
      <h1 className="mt-6 font-display text-4xl font-semibold leading-tight tracking-tight text-ink">
        Maintainer Brief
      </h1>
      <p className="mt-4 text-base leading-relaxed text-muted">
        A weekly email of what actually needs you — duplicate issues to close, PRs
        ready to merge, newcomers going stale, and threads worth a reply.
      </p>

      {/* instant preview — see a real brief before signing in */}
      <div className="mx-auto mt-8 flex max-w-md gap-2">
        <input
          value={repo}
          onChange={(e) => setRepo(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && goPreview()}
          placeholder="org/repo — see your brief instantly"
          className="w-full rounded-[6px] border border-line bg-surface px-3 py-2.5 text-sm text-ink placeholder:text-faint outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15"
        />
        <button
          onClick={goPreview}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-[6px] bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-hover"
        >
          Preview
          <ArrowRight size={14} />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap justify-center gap-1.5">
        {GALLERY.slice(0, 4).map((p) => (
          <button
            key={p.name}
            onClick={() => router.push(`/preview/${p.repos[0]}`)}
            className="rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted transition-colors hover:border-primary hover:text-primary"
          >
            {p.emoji} {p.name}
          </button>
        ))}
      </div>

      <div className="mx-auto mt-8 flex max-w-md items-center gap-3">
        <span className="h-px flex-1 bg-line" />
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-faint">or</span>
        <span className="h-px flex-1 bg-line" />
      </div>

      <a
        href={loginUrl()}
        className="mt-6 inline-flex items-center justify-center gap-2 rounded-[6px] bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-ink/90"
      >
        <GithubMark />
        Sign in with GitHub
      </a>
      <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.16em] text-faint">
        Your projects are private to you
      </p>

      {/* footer — powered by + credit */}
      <div className="mt-14 flex flex-col items-center gap-3 border-t border-line pt-8">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-faint">
          Powered by
        </span>
        <a
          href="https://tokenfactory.nebius.com/"
          target="_blank"
          rel="noreferrer"
          title="Nebius Token Factory"
          className="transition-opacity hover:opacity-80"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/nebius-token-factory.png"
            alt="Nebius Token Factory"
            className="h-14 w-14 rounded-[10px] shadow-sm"
          />
        </a>
        <p className="mt-1 text-xs text-muted">
          Built and maintained by <span className="font-medium text-ink">Shivay Lamba</span>
        </p>
      </div>
    </div>
  );
}

const USER_CACHE_KEY = "mb.user";

function cachedUser(): MeUser | null {
  try {
    const raw = localStorage.getItem(USER_CACHE_KEY);
    return raw ? (JSON.parse(raw) as MeUser) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<MeUser | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      localStorage.removeItem(USER_CACHE_KEY);
      setLoaded(true);
      return;
    }
    // Render-then-revalidate: paint immediately from the cached user, then
    // confirm the session in the background (401 drops back to sign-in).
    const cached = cachedUser();
    if (cached) {
      setUser(cached);
      setLoaded(true);
    }
    api
      .me()
      .then((u) => {
        setUser(u);
        localStorage.setItem(USER_CACHE_KEY, JSON.stringify(u));
      })
      .catch(() => {
        clearToken();
        localStorage.removeItem(USER_CACHE_KEY);
        setUser(null);
      })
      .finally(() => setLoaded(true));
  }, []);

  const logout = async () => {
    await api.logout().catch(() => {});
    clearToken();
    // clear all per-user caches so an account switch never shows stale data
    localStorage.removeItem(USER_CACHE_KEY);
    localStorage.removeItem("mb.projects");
    localStorage.removeItem("mb.selectedProjectId");
    setUser(null);
    window.location.href = "/";
  };

  // Public routes render without a session.
  if (PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
    return <Ctx.Provider value={{ user, logout }}>{children}</Ctx.Provider>;
  }

  if (!loaded) {
    // Only visible on a signed-in user's very first load (no cache yet).
    return (
      <div className="mx-auto mt-[18vh] max-w-sm space-y-3 px-6">
        <div className="mx-auto h-8 w-2/3 animate-pulse rounded-[4px] bg-line" />
        <div className="mx-auto h-4 w-5/6 animate-pulse rounded-[4px] bg-line" />
        <div className="mx-auto h-4 w-3/4 animate-pulse rounded-[4px] bg-line" />
      </div>
    );
  }

  if (!user) return <SignInScreen />;

  return <Ctx.Provider value={{ user, logout }}>{children}</Ctx.Provider>;
}
