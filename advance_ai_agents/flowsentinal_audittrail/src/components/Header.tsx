"use client";

import { useState, useEffect } from "react";
import { Layers, Zap, Activity, Globe, ChevronDown } from "lucide-react";
import clsx from "clsx";
import { VeltCommentTool, VeltCommentsSidebarButton } from "@veltdev/react";

interface Stats {
  total: number;
  byActor: Record<string, number>;
}

const SERVICES = [
  { label: "Nebius", color: "bg-violet-500", dot: "bg-violet-400" },
  { label: "n8n", color: "bg-emerald-500", dot: "bg-emerald-400" },
  { label: "Velt", color: "bg-sky-500", dot: "bg-sky-400" },
  { label: "Tailscale", color: "bg-amber-500", dot: "bg-amber-400" },
];

export default function Header() {
  const [stats, setStats] = useState<Stats>({ total: 0, byActor: {} });
  const openActivityTab = () => {
    if (typeof window !== "undefined") {
      window.location.hash = "activity";
      window.dispatchEvent(new CustomEvent("flowsentinel:open-activity-tab"));
    }
  };

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const r = await fetch("/api/activities?limit=1");
        const d = await r.json();
        setStats(d.stats ?? { total: 0, byActor: {} });
      } catch {}
    };
    fetch_();
    const id = setInterval(fetch_, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="h-14 flex-shrink-0 glass border-b border-border-1 flex items-center px-5 gap-4 z-20">
      {/* Logo */}
      <div className="flex items-center gap-2.5 mr-2">
        <div className="w-8 h-8 rounded-xl bg-gradient-violet flex items-center justify-center shadow-glow-violet flex-shrink-0">
          <Layers className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>
        <span className="font-semibold text-[15px] text-gradient-subtle tracking-tight">
          FlowSentinel
        </span>
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-border-1" />

      {/* Service status pills */}
      <div className="flex items-center gap-1.5">
        {SERVICES.map(({ label, dot }) => (
          <div
            key={label}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-2 border border-border-1"
          >
            <span className={clsx("w-1.5 h-1.5 rounded-full", dot)} />
            <span className="text-[11px] font-medium text-ink-secondary">{label}</span>
          </div>
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Live event counter */}
      <button
        type="button"
        onClick={openActivityTab}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-2 border border-border-1 hover:border-border-2 transition-colors"
        title="Open activity panel"
      >
        <Activity className="w-3.5 h-3.5 text-violet-400" />
        <span className="text-[12px] font-medium text-ink-secondary tabular-nums">
          {stats.total} events
        </span>
      </button>

      {/* AI actions */}
      <button
        type="button"
        onClick={openActivityTab}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-600/10 border border-violet-500/20 hover:border-violet-400/30 transition-colors"
        title="Open activity panel"
      >
        <Zap className="w-3.5 h-3.5 text-violet-400" />
        <span className="text-[12px] font-medium text-violet-300 tabular-nums">
          {stats.byActor?.ai ?? 0} AI
        </span>
      </button>

      {/* Live indicator */}
      <div className="flex items-center gap-2">
        <span className="live-dot" />
        <span className="text-[12px] font-medium text-emerald-400">Live</span>
      </div>

      {/* Velt SDK actions (for generating collaboration analytics) */}
      <div className="flex items-center gap-2">
        <VeltCommentTool
          targetElementId="flowsentinel-dashboard-root"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-[12px] font-medium text-sky-300"
        />
        <VeltCommentsSidebarButton
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-[12px] font-medium text-sky-300"
        />
      </div>
    </header>
  );
}
