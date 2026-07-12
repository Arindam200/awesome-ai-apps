"use client";

import { useCallback, useEffect, useState } from "react";
import { Sparkles, ListChecks, Rocket, Check } from "lucide-react";
import { Brief, BriefJson, SectionKey, api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import RunNowButton from "@/components/RunNowButton";
import BriefArticle from "@/components/BriefArticle";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { Badge } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { Frame } from "@/components/ui/Frame";
import { BriefSkeleton } from "@/components/ui/Skeleton";

export default function BriefPage() {
  const { selected, loaded: projLoaded } = useProject();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [loaded, setLoaded] = useState(false);

  const refetchBrief = useCallback(() => {
    if (!selected) return;
    api
      .latestBrief(selected.id)
      .then(setBrief)
      .catch(() => setBrief(null))
      .finally(() => setLoaded(true));
  }, [selected]);

  useEffect(() => {
    if (!selected) {
      setBrief(null);
      setLoaded(projLoaded);
      return;
    }
    setLoaded(false);
    refetchBrief();
  }, [selected, projLoaded, refetchBrief]);

  // ── onboarding hero ────────────────────────────────────────────
  if (projLoaded && !selected) {
    return (
      <div className="mx-auto mt-10 max-w-3xl">
        <div className="flex flex-col items-center text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            <Sparkles size={12} className="text-primary" />
            For open-source maintainers
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] tracking-tight text-ink">
            Know what to do
            <br />
            in your repo <span className="text-primary">this week.</span>
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-muted">
            Point Maintainer Brief at a GitHub project and get a weekly email of
            what actually needs you: duplicate issues to close, PRs ready to
            merge, newcomers going stale, and threads worth a reply.
          </p>
          <div className="mt-8">
            <ButtonLink href="/new" arrow>
              Create your first brief
            </ButtonLink>
          </div>
          <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.16em] text-faint">
            Weekly · Every item links to the source
          </p>
        </div>

        <Frame label="Sample brief" dots className="mt-14">
          <div className="space-y-5 p-6">
            <SectionLabel label="Triage This Week" icon={ListChecks} />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display text-base font-semibold text-ink">
                  Duplicate: dark-mode flicker
                </h3>
                <Badge tone="blue">duplicates</Badge>
              </div>
              <p className="mt-1 text-sm font-medium text-primary">
                → Close #482 and #491 as duplicates of #470, ship the fix.
              </p>
            </div>
            <SectionLabel label="Ship It" icon={Rocket} />
            <p className="text-sm text-muted">
              <Check size={14} className="mr-1 inline text-success" />4 PRs approved and
              ready to merge.
            </p>
          </div>
        </Frame>
      </div>
    );
  }

  if (!projLoaded || !loaded)
    return (
      <div className="mx-auto max-w-3xl">
        <BriefSkeleton />
      </div>
    );

  const sections: Partial<Record<SectionKey, boolean>> =
    (selected?.config?.newsletter as { sections?: Partial<Record<SectionKey, boolean>> })
      ?.sections ?? {};
  const b = brief?.brief_json as BriefJson | undefined;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
            {selected!.name}
          </h1>
          {b?.stats && (
            <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
              {b.stats.open_issues != null && `${b.stats.open_issues} open issues · `}
              {b.stats.open_prs != null && `${b.stats.open_prs} open PRs`}
              {brief?.sent_at && " · delivered"}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <RunNowButton projectId={selected!.id} onDone={refetchBrief} />
          {brief && (
            <ButtonLink href="/compose" size="md">
              Compose &amp; Send
            </ButtonLink>
          )}
        </div>
      </div>

      {!b && (
        <Frame className="mt-12">
          <span className="br" />
          <div className="px-10 py-14 text-center">
            <p className="font-display text-xl font-semibold text-ink">No brief generated yet.</p>
            <p className="mt-3 text-sm text-muted">
              Hit “Run brief now” to pull your repo’s live state and generate this week’s brief.
            </p>
          </div>
        </Frame>
      )}

      {b && <BriefArticle brief={b} sections={sections} />}
    </div>
  );
}
