"use client";

import {
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
  Globe,
} from "lucide-react";
import { BriefJson, IssueRef, PrRef, SectionKey } from "@/lib/api";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";

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

/** Pending copy slot: skeleton bar while the LLM writes, text when present. */
function Copy({ text, pending, className = "" }: { text: string; pending?: boolean; className?: string }) {
  if (text) return <span className={className}>{text}</span>;
  if (pending) return <Skeleton className="inline-block h-4 w-56 max-w-full align-middle" />;
  return null;
}

/**
 * The full brief article body — shared by the dashboard brief page and the
 * public no-signin preview. `pending` renders skeleton bars where the LLM copy
 * hasn't arrived yet (two-phase preview).
 */
export default function BriefArticle({
  brief: b,
  sections = {},
  pending = false,
}: {
  brief: BriefJson;
  sections?: Partial<Record<SectionKey, boolean>>;
  pending?: boolean;
}) {
  const on = (k: SectionKey) => sections[k] !== false;
  const ship = b.ship_it;
  const hasShip =
    ship &&
    (ship.ready_to_merge.length ||
      ship.release_summary ||
      ship.needs_review.length ||
      ship.security.length ||
      (pending && ship.unreleased_count));

  return (
    <Card className="mt-8 px-8 py-8 sm:px-10">
      {b.headline ? (
        <p className="font-display text-xl font-medium leading-relaxed text-ink">{b.headline}</p>
      ) : (
        pending && <Skeleton className="h-6 w-3/4" />
      )}

      {/* TRIAGE */}
      {on("triage") && (b.triage?.length ?? 0) > 0 && (
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
                  <Copy text={t.action} pending={pending} />
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
            {ship.ready_to_merge.length > 0 && (
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold text-success">
                  <Check size={15} /> Ready to merge ({ship.ready_to_merge.length})
                </p>
                <div className="mt-2 space-y-2">
                  {ship.ready_to_merge.map((p) => (
                    <PrLine key={p.number} p={p} />
                  ))}
                </div>
              </div>
            )}

            {(ship.release_summary || (pending && ship.unreleased_count > 0)) && (
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                  <Package size={15} className="text-primary" /> Unreleased ({ship.unreleased_count}{" "}
                  merged since {ship.latest_release ?? "last release"})
                </p>
                <p className="mt-2 text-sm leading-relaxed text-ink/80">
                  <Copy text={ship.release_summary} pending={pending} />
                </p>
              </div>
            )}

            {ship.needs_review.length > 0 && (
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                  <Clock size={15} className="text-gold" /> Aging — needs review
                </p>
                <div className="mt-2 space-y-2">
                  {ship.needs_review.map((p) => (
                    <PrLine key={p.number} p={p} />
                  ))}
                </div>
              </div>
            )}

            {ship.security.length > 0 && (
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold text-danger">
                  <ShieldAlert size={15} /> Security
                </p>
                <div className="mt-2 space-y-1.5">
                  {ship.security.map((s) => (
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
      {on("people") && (b.people?.length ?? 0) > 0 && (
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
      {on("worth_replying_to") && (b.worth_replying_to?.length ?? 0) > 0 && (
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

      {/* MENTIONS AROUND THE WEB */}
      {on("mentions") && (b.mentions?.length ?? 0) > 0 && (
        <section className="mt-10">
          <SectionLabel label="Mentions Around the Web" icon={Globe} />
          <div className="mt-4 space-y-4">
            {b.mentions!.map((m, i) => (
              <div key={i}>
                <p className="text-sm">
                  <Badge tone="neutral">{m.domain}</Badge>{" "}
                  <a
                    href={m.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-medium text-ink hover:text-primary"
                  >
                    {m.title}
                    <ExternalLink size={11} className="text-faint" />
                  </a>
                </p>
                {m.why && <p className="mt-1 text-sm text-primary">{m.why}</p>}
              </div>
            ))}
          </div>
        </section>
      )}
    </Card>
  );
}
