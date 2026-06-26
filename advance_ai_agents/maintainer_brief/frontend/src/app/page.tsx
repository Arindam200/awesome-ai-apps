"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  TrendingUp,
  HeartPulse,
  Megaphone,
  Crosshair,
  ShieldAlert,
  ListChecks,
} from "lucide-react";
import { Brief, SectionKey, api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import RunNowButton from "@/components/RunNowButton";
import SourceLinks from "@/components/SourceLinks";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { Card } from "@/components/ui/Card";
import { Badge, levelTone } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { Frame } from "@/components/ui/Frame";

function UrgencyBadge({ level }: { level: string }) {
  if (!level) return null;
  return <Badge tone={levelTone(level)}>{level}</Badge>;
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

  // ── no projects yet → onboarding hero ──────────────────────────
  if (projLoaded && !selected) {
    return (
      <div className="mx-auto mt-10 max-w-3xl">
        <div className="flex flex-col items-center text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            <Sparkles size={12} className="text-primary" />
            Powered by Unsiloed
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] tracking-tight text-ink">
            The brief every maintainer
            <br />
            wishes they <span className="text-primary">had.</span>
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-muted">
            Pick an open-source project, add a few documents, and get a weekly
            intelligence brief — feature momentum, ecosystem mentions, competitor
            moves, and security alerts, every claim linked to its source.
          </p>
          <div className="mt-8">
            <ButtonLink href="/new" arrow>
              Create your first brief
            </ButtonLink>
          </div>
          <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.16em] text-faint">
            Weekly · Cited sources · No noise
          </p>
        </div>

        {/* framed sample preview */}
        <Frame label="Sample brief" dots className="mt-14">
          <div className="space-y-5 p-6">
            <SectionLabel label="Top Requested Features" icon={TrendingUp} index={1} total={6} />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display text-base font-semibold text-ink">
                  WASM plugin support
                </h3>
                <Badge tone="danger">high</Badge>
              </div>
              <p className="mt-1 text-sm leading-relaxed text-muted">
                Clustered across 14 GitHub issues and 3 community threads — the
                most-requested capability this cycle.
              </p>
            </div>
            <SectionLabel label="Security Alerts" icon={ShieldAlert} index={5} total={6} />
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-ink">CVE-2026-1042</h3>
              <Badge tone="gold">moderate</Badge>
            </div>
          </div>
        </Frame>
      </div>
    );
  }

  if (!projLoaded || !loaded)
    return <p className="font-mono text-xs uppercase tracking-[0.16em] text-faint">Loading…</p>;

  const sections: Partial<Record<SectionKey, boolean>> =
    (selected?.config?.newsletter as { sections?: Partial<Record<SectionKey, boolean>> })
      ?.sections ?? {};
  const on = (k: SectionKey) => sections[k] !== false;
  const b = brief?.brief_json;

  return (
    <div className="mx-auto max-w-3xl">
      {/* page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
            {selected!.name}
          </h1>
          {brief && (
            <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
              {brief.period_start} – {brief.period_end}
              {brief.sent_at && " · delivered"}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <RunNowButton projectId={selected!.id} />
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
              Add documents (PDFs, decks, reports) on the Documents page, then hit
              “Run brief now”.
            </p>
          </div>
        </Frame>
      )}

      {b && (
        <Card className="mt-8 px-8 py-8 sm:px-10">
          <p className="font-display text-xl font-medium leading-relaxed text-ink">{b.headline}</p>

          {on("top_requested_features") && b.top_requested_features?.length > 0 && (
            <section className="mt-10">
              <SectionLabel label="Top Requested Features" icon={TrendingUp} index={1} total={6} />
              <div className="mt-5 space-y-5">
                {b.top_requested_features.map((f, i) => (
                  <div key={i}>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-display text-lg font-semibold text-ink">{f.cluster_name}</h3>
                      <UrgencyBadge level={f.urgency} />
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-ink/80">{f.summary}</p>
                    <div className="mt-2">
                      <SourceLinks ids={f.signal_ids} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {on("community_health") && b.community_health && (
            <section className="mt-10">
              <SectionLabel label="Community Health" icon={HeartPulse} index={2} total={6} />
              <p className="mt-4 text-sm leading-relaxed text-ink/80">
                {b.community_health.summary}
              </p>
              <div className="mt-3 space-y-1.5">
                {b.community_health.metrics_callouts?.map((c, i) => (
                  <p key={i} className="flex items-start gap-2 text-sm text-ink">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                    {c}
                  </p>
                ))}
              </div>
            </section>
          )}

          {on("ecosystem_mentions") && b.ecosystem_mentions?.length > 0 && (
            <section className="mt-10">
              <SectionLabel label="Ecosystem Mentions" icon={Megaphone} index={3} total={6} />
              <div className="mt-4 space-y-4">
                {b.ecosystem_mentions.map((m, i) => (
                  <div key={i}>
                    <p className="text-sm leading-relaxed text-ink/80">
                      {m.context}
                      {m.prominence && (
                        <span className="ml-1.5 text-xs text-faint">({m.prominence})</span>
                      )}
                    </p>
                    <div className="mt-2">
                      <SourceLinks ids={m.signal_ids} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {on("competitor_watch") && b.competitor_watch?.length > 0 && (
            <section className="mt-10">
              <SectionLabel label="Competitor Watch" icon={Crosshair} index={4} total={6} />
              <div className="mt-5 space-y-5">
                {b.competitor_watch.map((c, i) => (
                  <div key={i}>
                    <h3 className="font-display text-lg font-semibold text-ink">{c.competitor}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-ink/80">{c.development}</p>
                    <p className="mt-1 text-sm text-muted">
                      <span className="font-medium text-ink">Why it matters:</span>{" "}
                      {c.why_it_matters}
                    </p>
                    <div className="mt-2">
                      <SourceLinks ids={c.signal_ids} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {on("security_alerts") && b.security_alerts?.length > 0 && (
            <section className="mt-10">
              <SectionLabel label="Security Alerts" icon={ShieldAlert} index={5} total={6} />
              <div className="mt-4 space-y-4">
                {b.security_alerts.map((s, i) => (
                  <div key={i}>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-semibold text-ink">{s.identifier}</h3>
                      <UrgencyBadge level={s.severity} />
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-ink/80">{s.action}</p>
                    <div className="mt-2">
                      <SourceLinks ids={s.signal_ids} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {on("maintainer_recommendations") && b.maintainer_recommendations?.length > 0 && (
            <section className="mt-10">
              <SectionLabel label="Recommended Actions" icon={ListChecks} index={6} total={6} />
              <ol className="mt-5 space-y-4">
                {b.maintainer_recommendations.map((r, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-[5px] bg-primary-soft font-mono text-xs font-semibold text-primary">
                      {i + 1}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-ink">
                        {r.recommendation}
                        <span className="ml-2 align-middle">
                          <Badge tone="neutral">{r.effort}</Badge>
                        </span>
                      </p>
                      <p className="mt-1 text-sm text-muted">{r.rationale}</p>
                      <div className="mt-2">
                        <SourceLinks ids={r.supporting_signal_ids} />
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </Card>
      )}
    </div>
  );
}
