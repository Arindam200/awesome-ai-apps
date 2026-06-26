"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Brief, SectionKey, api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import RunNowButton from "@/components/RunNowButton";
import SourceLinks from "@/components/SourceLinks";

function SectionHeader({ title }: { title: string }) {
  return (
    <h2 className="mt-12 border-b border-line pb-2 text-xs font-bold uppercase tracking-[1.5px] text-accent">
      {title}
    </h2>
  );
}

function UrgencyBadge({ level }: { level: string }) {
  const hot = ["high", "critical"].includes(level?.toLowerCase());
  return (
    <span className={`ml-2 text-[10px] font-bold uppercase tracking-wider ${hot ? "text-accent" : "text-muted"}`}>
      {level}
    </span>
  );
}

export default function BriefPage() {
  const { selected, loaded: projLoaded } = useProject();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!selected) {
      setBrief(null);
      setLoaded(projLoaded);
      return;
    }
    setLoaded(false);
    api
      .latestBrief(selected.id)
      .then(setBrief)
      .catch(() => setBrief(null))
      .finally(() => setLoaded(true));
  }, [selected, projLoaded]);

  // no projects yet → onboarding hero
  if (projLoaded && !selected) {
    return (
      <div className="mx-auto mt-16 max-w-xl text-center">
        <div className="text-5xl">📨</div>
        <h1 className="mt-4 font-serif text-4xl">The brief every maintainer wishes they had</h1>
        <p className="mt-3 text-muted">
          Pick an open-source project, add a few documents, and get a weekly
          intelligence brief — feature momentum, ecosystem mentions, competitor
          moves, and security alerts, with cited sources.
        </p>
        <Link
          href="/new"
          className="mt-8 inline-block rounded-sm bg-accent px-5 py-2.5 text-sm font-bold text-white hover:opacity-90"
        >
          Create your first brief →
        </Link>
      </div>
    );
  }

  if (!projLoaded || !loaded) return <p className="text-muted">Loading…</p>;

  const sections: Partial<Record<SectionKey, boolean>> =
    (selected?.config?.newsletter as { sections?: Partial<Record<SectionKey, boolean>> })?.sections ?? {};
  const on = (k: SectionKey) => sections[k] !== false;
  const b = brief?.brief_json;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-serif text-4xl">{selected!.name}</h1>
          {brief && (
            <p className="mt-2 text-sm text-muted">
              {brief.period_start} – {brief.period_end}
              {brief.sent_at && " · delivered"}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <RunNowButton projectId={selected!.id} />
          {brief && (
            <Link
              href="/compose"
              className="rounded-sm bg-accent px-4 py-2 text-sm font-bold text-white hover:opacity-90"
            >
              Compose &amp; Send
            </Link>
          )}
        </div>
      </div>

      {!b && (
        <div className="mt-16 rounded-sm border border-line bg-card p-10 text-center">
          <p className="font-serif text-xl italic text-muted">No brief generated yet.</p>
          <p className="mt-3 text-sm text-muted">
            Add documents (PDFs, decks, reports) on the Documents page, then hit “Run brief now”.
          </p>
        </div>
      )}

      {b && (
        <article className="mt-8 rounded-sm border border-line bg-card px-10 py-8">
          <p className="font-serif text-xl italic leading-relaxed text-ink">{b.headline}</p>

          {on("top_requested_features") && b.top_requested_features?.length > 0 && (
            <>
              <SectionHeader title="Top Requested Features" />
              {b.top_requested_features.map((f, i) => (
                <div key={i} className="mt-5">
                  <h3 className="font-serif text-lg font-bold">
                    {f.cluster_name}
                    <UrgencyBadge level={f.urgency} />
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-ink/80">{f.summary}</p>
                  <div className="mt-2"><SourceLinks ids={f.signal_ids} /></div>
                </div>
              ))}
            </>
          )}

          {on("community_health") && b.community_health && (
            <>
              <SectionHeader title="Community Health" />
              <p className="mt-4 text-sm leading-relaxed text-ink/80">{b.community_health.summary}</p>
              {b.community_health.metrics_callouts?.map((c, i) => (
                <p key={i} className="mt-2 text-sm font-medium">▸ {c}</p>
              ))}
            </>
          )}

          {on("ecosystem_mentions") && b.ecosystem_mentions?.length > 0 && (
            <>
              <SectionHeader title="Ecosystem Mentions" />
              {b.ecosystem_mentions.map((m, i) => (
                <div key={i} className="mt-4">
                  <p className="text-sm leading-relaxed text-ink/80">
                    {m.context}
                    {m.prominence && <span className="ml-1 text-xs text-muted">({m.prominence})</span>}
                  </p>
                  <div className="mt-2"><SourceLinks ids={m.signal_ids} /></div>
                </div>
              ))}
            </>
          )}

          {on("competitor_watch") && b.competitor_watch?.length > 0 && (
            <>
              <SectionHeader title="Competitor Watch" />
              {b.competitor_watch.map((c, i) => (
                <div key={i} className="mt-5">
                  <h3 className="font-serif text-lg font-bold">{c.competitor}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-ink/80">{c.development}</p>
                  <p className="mt-1 text-sm italic text-muted">Why it matters: {c.why_it_matters}</p>
                  <div className="mt-2"><SourceLinks ids={c.signal_ids} /></div>
                </div>
              ))}
            </>
          )}

          {on("security_alerts") && b.security_alerts?.length > 0 && (
            <>
              <SectionHeader title="Security Alerts" />
              {b.security_alerts.map((s, i) => (
                <div key={i} className="mt-4">
                  <h3 className="text-base font-bold">
                    {s.identifier}
                    <UrgencyBadge level={s.severity} />
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-ink/80">{s.action}</p>
                  <div className="mt-2"><SourceLinks ids={s.signal_ids} /></div>
                </div>
              ))}
            </>
          )}

          {on("maintainer_recommendations") && b.maintainer_recommendations?.length > 0 && (
            <>
              <SectionHeader title="Recommended Actions" />
              <ol className="mt-4 space-y-4">
                {b.maintainer_recommendations.map((r, i) => (
                  <li key={i}>
                    <p className="text-sm font-bold">
                      <span className="text-accent">{i + 1}.</span> {r.recommendation}
                      <span className="ml-2 text-[10px] font-bold uppercase tracking-wider text-muted">{r.effort}</span>
                    </p>
                    <p className="mt-1 text-sm text-muted">{r.rationale}</p>
                    <div className="mt-2"><SourceLinks ids={r.supporting_signal_ids} /></div>
                  </li>
                ))}
              </ol>
            </>
          )}
        </article>
      )}
    </div>
  );
}
