"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  ListChecks,
  Rocket,
  Users,
  MessagesSquare,
  ArrowRight,
  Heart,
  MessageCircle,
  Clock,
  ShieldAlert,
  Check,
  Package,
  ExternalLink,
} from "lucide-react";
import { Brief, BriefJson, IssueRef, PrRef, SectionKey, api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import RunNowButton from "@/components/RunNowButton";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { Frame } from "@/components/ui/Frame";

const KIND_TONE: Record<string, "blue" | "danger" | "gold" | "neutral"> = {
  duplicates: "blue",
  hot: "danger",
  unanswered: "gold",
  stalled: "neutral",
};

function IssueChip({ i }: { i: IssueRef }) {
  return (
    <a
      href={i.url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 rounded-[4px] border border-line bg-surface px-2 py-0.5 font-mono text-[10px] text-muted transition-colors hover:border-primary hover:text-primary"
    >
      #{i.number}
      {i.reactions > 0 && (
        <span className="flex items-center gap-0.5">
          <Heart size={9} /> {i.reactions}
        </span>
      )}
      {i.comments > 0 && (
        <span className="flex items-center gap-0.5">
          <MessageCircle size={9} /> {i.comments}
        </span>
      )}
    </a>
  );
}

function PrLine({ p, ageColor = "text-gold" }: { p: PrRef; ageColor?: string }) {
  return (
    <div className="text-sm leading-relaxed">
      <a href={p.url} target="_blank" rel="noreferrer" className="text-ink hover:text-primary">
        <span className="font-mono text-xs text-faint">#{p.number}</span> {p.title}
      </a>
      {p.author && <span className="text-xs text-faint"> · @{p.author}</span>}
      {p.age_days != null && p.age_days >= 7 && (
        <span className={`text-xs ${ageColor}`}> · {p.age_days}d</span>
      )}
      {p.note && <p className="mt-0.5 text-xs text-muted">{p.note}</p>}
    </div>
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
    return <p className="font-mono text-xs uppercase tracking-[0.16em] text-faint">Loading…</p>;

  const sections: Partial<Record<SectionKey, boolean>> =
    (selected?.config?.newsletter as { sections?: Partial<Record<SectionKey, boolean>> })
      ?.sections ?? {};
  const on = (k: SectionKey) => sections[k] !== false;
  const b = brief?.brief_json as BriefJson | undefined;
  const ship = b?.ship_it;
  const hasShip =
    ship &&
    (ship.ready_to_merge.length ||
      ship.release_summary ||
      ship.needs_review.length ||
      ship.security.length);

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
              Hit “Run brief now” to pull your repo’s live state and generate this week’s brief.
            </p>
          </div>
        </Frame>
      )}

      {b && (
        <Card className="mt-8 px-8 py-8 sm:px-10">
          <p className="font-display text-xl font-medium leading-relaxed text-ink">{b.headline}</p>

          {/* TRIAGE */}
          {on("triage") && b.triage?.length > 0 && (
            <section className="mt-10">
              <SectionLabel label="Triage This Week" icon={ListChecks} />
              <div className="mt-5 space-y-6">
                {b.triage.map((t, i) => (
                  <div key={i}>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-display text-base font-semibold text-ink">{t.title}</h3>
                      <Badge tone={KIND_TONE[t.kind] ?? "neutral"}>{t.kind}</Badge>
                    </div>
                    <p className="mt-1.5 flex items-start gap-1.5 text-sm font-medium text-primary">
                      <ArrowRight size={15} className="mt-0.5 shrink-0" />
                      {t.action}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {t.issues.map((iss) => (
                        <IssueChip key={iss.number} i={iss} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* SHIP IT */}
          {on("ship_it") && hasShip && (
            <section className="mt-10">
              <SectionLabel label="Ship It" icon={Rocket} />
              <div className="mt-4 space-y-5">
                {ship!.ready_to_merge.length > 0 && (
                  <div>
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-success">
                      <Check size={15} /> Ready to merge ({ship!.ready_to_merge.length})
                    </p>
                    <div className="mt-2 space-y-2">
                      {ship!.ready_to_merge.map((p) => (
                        <PrLine key={p.number} p={p} />
                      ))}
                    </div>
                  </div>
                )}

                {ship!.release_summary && (
                  <div>
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                      <Package size={15} className="text-primary" /> Unreleased (
                      {ship!.unreleased_count} merged since {ship!.latest_release ?? "last release"})
                    </p>
                    <p className="mt-2 text-sm leading-relaxed text-ink/80">
                      {ship!.release_summary}
                    </p>
                  </div>
                )}

                {ship!.needs_review.length > 0 && (
                  <div>
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                      <Clock size={15} className="text-gold" /> Aging — needs review
                    </p>
                    <div className="mt-2 space-y-2">
                      {ship!.needs_review.map((p) => (
                        <PrLine key={p.number} p={p} />
                      ))}
                    </div>
                  </div>
                )}

                {ship!.security.length > 0 && (
                  <div>
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-danger">
                      <ShieldAlert size={15} /> Security
                    </p>
                    <div className="mt-2 space-y-1.5">
                      {ship!.security.map((s) => (
                        <a
                          key={s.id}
                          href={s.url}
                          target="_blank"
                          rel="noreferrer"
                          className="block text-sm text-ink hover:text-primary"
                        >
                          <span className="font-mono text-xs text-danger">{s.id}</span>
                          <span className="text-xs text-faint"> · {s.severity}</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* PEOPLE */}
          {on("people") && b.people?.length > 0 && (
            <section className="mt-10">
              <SectionLabel label="People" icon={Users} />
              <p className="mt-3 text-sm text-muted">
                First-time contributors whose PRs are going stale — a reply keeps them around.
              </p>
              <div className="mt-3 space-y-3">
                {b.people.map((p) => (
                  <div key={p.number} className="text-sm">
                    <span className="font-semibold text-ink">@{p.author}</span>{" "}
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-ink hover:text-primary"
                    >
                      <span className="font-mono text-xs text-faint">#{p.number}</span> {p.title}
                    </a>
                    {p.age_days != null && (
                      <span className="text-xs text-gold"> · {p.age_days}d waiting</span>
                    )}
                    {p.note && <p className="mt-0.5 text-xs text-muted">{p.note}</p>}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* WORTH REPLYING TO */}
          {on("worth_replying_to") && b.worth_replying_to?.length > 0 && (
            <section className="mt-10">
              <SectionLabel label="Worth Replying To" icon={MessagesSquare} />
              <div className="mt-4 space-y-4">
                {b.worth_replying_to.map((t, i) => (
                  <div key={i}>
                    <p className="text-sm">
                      <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
                        {t.source}
                      </span>{" "}
                      <a
                        href={t.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-medium text-ink hover:text-primary"
                      >
                        {t.title}
                        <ExternalLink size={11} className="text-faint" />
                      </a>
                    </p>
                    {t.why && <p className="mt-0.5 text-sm text-primary">{t.why}</p>}
                  </div>
                ))}
              </div>
            </section>
          )}
        </Card>
      )}
    </div>
  );
}
