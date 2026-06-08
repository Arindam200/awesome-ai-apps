"use client";

import { useState, useEffect } from "react";
import { MessageSquare, Sparkles, Play, CheckCircle, AlertCircle, Settings, Shield, Filter } from "lucide-react";
import clsx from "clsx";

interface ActivityRecord {
  id: string;
  type: string;
  actor: { name: string; kind: "human" | "ai" | "system" };
  action: string;
  detail: string;
  timestamp: string;
}

interface Stats {
  total: number;
  byType: Record<string, number>;
  byActor: Record<string, number>;
}

const TYPE_META: Record<string, {
  icon: typeof MessageSquare;
  iconColor: string;
  bgColor: string;
  label: string;
}> = {
  chat_message:       { icon: MessageSquare, iconColor: "text-violet-400",  bgColor: "bg-violet-500/10",  label: "Chat" },
  ai_response:        { icon: Sparkles,      iconColor: "text-violet-300",  bgColor: "bg-violet-500/15",  label: "AI" },
  workflow_triggered: { icon: Play,          iconColor: "text-amber-400",   bgColor: "bg-amber-500/10",   label: "Trigger" },
  workflow_step:      { icon: Settings,      iconColor: "text-sky-400",     bgColor: "bg-sky-500/10",     label: "Step" },
  workflow_completed: { icon: CheckCircle,   iconColor: "text-emerald-400", bgColor: "bg-emerald-500/10", label: "Done" },
  workflow_failed:    { icon: AlertCircle,   iconColor: "text-rose-400",    bgColor: "bg-rose-500/10",    label: "Failed" },
  system_event:       { icon: Settings,      iconColor: "text-ink-muted",   bgColor: "bg-surface-3",      label: "System" },
  secure_access:      { icon: Shield,        iconColor: "text-sky-400",     bgColor: "bg-sky-500/10",     label: "Access" },
};

const ACTOR_BADGE: Record<string, string> = {
  human:  "bg-violet-500/10 text-violet-300 border-violet-500/20",
  ai:     "bg-violet-600/15 text-violet-200 border-violet-400/25",
  system: "bg-surface-3 text-ink-muted border-border-1",
};

const FILTER_TABS = [
  { key: null, label: "All" },
  { key: "chat_message", label: "Chat" },
  { key: "ai_response", label: "AI" },
  { key: "workflow_completed", label: "Workflows" },
  { key: "system_event", label: "System" },
];

function relTime(iso: string) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h`;
}

export default function ActivityFeed() {
  const [activities, setActivities] = useState<ActivityRecord[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, byType: {}, byActor: {} });
  const [filter, setFilter] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const url = filter ? `/api/activities?type=${filter}&limit=60` : "/api/activities?limit=60";
        const r = await fetch(url);
        const d = await r.json();
        setActivities(d.activities ?? []);
        setStats(d.stats ?? { total: 0, byType: {}, byActor: {} });
      } catch {}
    };
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [filter]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-border-1 flex-shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-lg bg-sky-500/15 border border-sky-500/25 flex items-center justify-center">
              <Shield className="w-3 h-3 text-sky-400" />
            </div>
            <span className="text-[13px] font-semibold text-ink-primary">Activity</span>
            <span className="px-2 py-0.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-[10px] font-medium text-sky-300">
              Velt · Immutable
            </span>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-3 text-[11px] text-ink-muted">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
              {stats.byActor?.human ?? 0} human
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-300" />
              {stats.byActor?.ai ?? 0} AI
            </span>
          </div>
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-1">
          {FILTER_TABS.map(({ key, label }) => {
            const count = key ? (stats.byType?.[key] ?? 0) : stats.total;
            return (
              <button
                key={label}
                onClick={() => setFilter(key)}
                className={clsx(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[12px] font-medium transition-all",
                  filter === key
                    ? "bg-surface-4 text-ink-primary border border-border-2"
                    : "text-ink-muted hover:text-ink-secondary hover:bg-surface-3 border border-transparent"
                )}
              >
                {label}
                {count > 0 && (
                  <span className={clsx("text-[10px] tabular-nums", filter === key ? "text-ink-secondary" : "text-ink-muted")}>
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto">
        {activities.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-center animate-fade-in">
            <div className="w-10 h-10 rounded-xl bg-surface-2 border border-border-1 flex items-center justify-center">
              <Shield className="w-4.5 h-4.5 text-ink-muted" />
            </div>
            <p className="text-[13px] text-ink-muted">No activity yet</p>
          </div>
        )}

        <div className="px-5 py-3 space-y-1">
          {activities.map((a, idx) => {
            const meta = TYPE_META[a.type] ?? TYPE_META.system_event;
            const Icon = meta.icon;
            const isLast = idx === activities.length - 1;

            return (
              <div key={a.id} className="relative flex gap-3 pb-1 animate-fade-in">
                {/* Timeline line */}
                {!isLast && (
                  <div className="absolute left-[15px] top-8 w-px h-full bg-border-1" />
                )}

                {/* Icon */}
                <div className={clsx("w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 z-10", meta.bgColor)}>
                  <Icon className={clsx("w-3.5 h-3.5", meta.iconColor)} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 pb-3">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={clsx("text-[10px] font-medium px-1.5 py-0.5 rounded-md border", ACTOR_BADGE[a.actor.kind])}>
                      {a.actor.name}
                    </span>
                    <span className="text-[11px] text-ink-muted">{a.action}</span>
                    <span className="ml-auto text-[10px] text-ink-muted/60 font-mono tabular-nums flex-shrink-0">
                      {relTime(a.timestamp)}
                    </span>
                  </div>
                  <p className="text-[12px] text-ink-muted leading-relaxed line-clamp-2">{a.detail}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-border-1 flex items-center gap-2 flex-shrink-0">
        <span className="live-dot" />
        <span className="text-[11px] text-emerald-400 font-medium">Real-time · {stats.total} total events</span>
        <span className="ml-auto text-[10px] text-ink-muted font-mono">Powered by Velt</span>
      </div>
    </div>
  );
}
