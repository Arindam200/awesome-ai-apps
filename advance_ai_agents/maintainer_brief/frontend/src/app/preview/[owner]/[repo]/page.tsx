"use client";

import { use, useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { PreviewBrief, api, loginUrl } from "@/lib/api";
import BriefArticle from "@/components/BriefArticle";
import { BriefSkeleton } from "@/components/ui/Skeleton";

const POLL_MS = 2000;
const POLL_CAP_MS = 90_000;

function GithubMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

function agoLabel(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 2) return "generated just now";
  if (mins < 60) return `generated ${mins}m ago`;
  return `generated ${Math.round(mins / 60)}h ago`;
}

export default function PreviewPage({
  params,
}: {
  params: Promise<{ owner: string; repo: string }>;
}) {
  const { owner, repo } = use(params);
  const fullRepo = `${owner}/${repo}`;
  const [preview, setPreview] = useState<PreviewBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollStart = useRef(0);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const poll = (id: number) => {
      if (cancelled || Date.now() - pollStart.current > POLL_CAP_MS) return;
      timer = setTimeout(async () => {
        try {
          const p = await api.preview(id);
          if (cancelled) return;
          setPreview(p);
          if (p.status === "phase1") poll(id);
        } catch {
          /* transient poll failure — stop quietly, placeholder stays useful */
        }
      }, POLL_MS);
    };

    api
      .createPreview(fullRepo)
      .then((p) => {
        if (cancelled) return;
        setPreview(p);
        pollStart.current = Date.now();
        if (p.status === "phase1") poll(p.preview_id);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)));

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [fullRepo]);

  if (error) {
    return (
      <div className="mx-auto mt-[18vh] max-w-md text-center">
        <p className="font-display text-2xl font-semibold text-ink">Couldn’t preview {fullRepo}</p>
        <p className="mt-3 text-sm text-muted">{error}</p>
        <a href="/" className="mt-6 inline-block text-sm text-primary">← Try another repo</a>
      </div>
    );
  }

  const b = preview?.brief_json;
  const pending = preview?.status === "phase1";

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-faint">
            <Sparkles size={11} className="mr-1 inline text-primary" />
            Brief preview {preview?.generated_at && `· ${agoLabel(preview.generated_at)}`}
            {pending && " · writing the analysis…"}
          </p>
          <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-ink">
            {fullRepo}
          </h1>
          {b?.stats && (
            <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
              {b.stats.open_issues != null && `${b.stats.open_issues} open issues · `}
              {b.stats.open_prs != null && `${b.stats.open_prs} open PRs`}
            </p>
          )}
        </div>
        <a
          href={loginUrl()}
          className="inline-flex items-center gap-2 rounded-[6px] bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-hover"
        >
          <GithubMark />
          Get this weekly — sign in
        </a>
      </div>

      {!b && <BriefSkeleton />}
      {b && <BriefArticle brief={b} pending={pending} />}

      <div className="mt-10 rounded-[6px] border border-line bg-surface p-6 text-center">
        <p className="font-display text-lg font-semibold text-ink">
          This is a one-off snapshot.
        </p>
        <p className="mt-1.5 text-sm text-muted">
          Sign in to get a brief like this for your repos, every week, in your inbox —
          with duplicate clustering, contributor-churn alerts, and community threads.
        </p>
        <a
          href={loginUrl()}
          className="mt-5 inline-flex items-center justify-center gap-2 rounded-[6px] bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-ink/90"
        >
          <GithubMark />
          Sign in with GitHub
        </a>
      </div>
    </div>
  );
}
