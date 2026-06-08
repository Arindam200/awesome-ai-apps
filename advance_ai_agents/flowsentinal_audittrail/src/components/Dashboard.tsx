"use client";

import { useEffect, useState } from "react";
import { Play, Activity, Info } from "lucide-react";
import clsx from "clsx";
import ChatPanel from "./ChatPanel";
import WorkflowPanel from "./WorkflowPanel";
import ActivityFeed from "./ActivityFeed";

type Tab = "workflows" | "activity" | "about";

const TABS: { id: Tab; label: string; icon: typeof Play }[] = [
  { id: "workflows", label: "Workflows", icon: Play },
  { id: "activity",  label: "Activity",  icon: Activity },
  { id: "about",     label: "About",     icon: Info },
];

function AboutPanel() {
  return (
    <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
      <div>
        <h3 className="text-[13px] font-semibold text-ink-primary mb-1">FlowSentinel Stack</h3>
        <p className="text-[12px] text-ink-muted leading-relaxed">
          An AI-powered workflow command center combining four platforms into one operational interface.
        </p>
      </div>

      {[
        {
          name: "Nebius Token Factory",
          desc: "Runs Nemotron Super via Nebius using an OpenAI-compatible API.",
          color: "bg-violet-500/10 border-violet-500/20",
          dot: "bg-violet-400",
          link: "studio.nebius.com",
        },
        {
          name: "n8n",
          desc: "Free open-source workflow automation. Run locally with `npx n8n`, build visual pipelines, trigger via webhook.",
          color: "bg-emerald-500/10 border-emerald-500/20",
          dot: "bg-emerald-400",
          link: "n8n.io",
        },
        {
          name: "Velt",
          desc: "Activity Logs SDK. Immutable audit trail for every human and AI action.",
          color: "bg-sky-500/10 border-sky-500/20",
          dot: "bg-sky-400",
          link: "velt.dev/activity-logs",
        },
        {
          name: "Tailscale Funnel",
          desc: "Expose localhost over HTTPS in one command. No open ports, no config.",
          color: "bg-amber-500/10 border-amber-500/20",
          dot: "bg-amber-400",
          link: "tailscale.com/kb/1223/funnel",
        },
      ].map(({ name, desc, color, dot, link }) => (
        <div key={name} className={clsx("p-4 rounded-xl border", color)}>
          <div className="flex items-center gap-2 mb-1.5">
            <span className={clsx("w-2 h-2 rounded-full", dot)} />
            <span className="text-[13px] font-semibold text-ink-primary">{name}</span>
          </div>
          <p className="text-[12px] text-ink-muted leading-relaxed">{desc}</p>
          <a
            href={`https://${link}`}
            target="_blank"
            rel="noopener"
            className="text-[11px] text-ink-muted/60 hover:text-ink-muted mt-1.5 inline-block transition-colors font-mono"
          >
            {link} →
          </a>
        </div>
      ))}

      <div className="pt-2 border-t border-border-1 space-y-2">
        <p className="text-[11px] text-ink-muted leading-relaxed">
          Start n8n locally:{" "}
          <code className="px-1.5 py-0.5 rounded bg-surface-3 text-[10px] font-mono border border-border-1">npx n8n</code>
          {" "}then open{" "}
          <code className="px-1.5 py-0.5 rounded bg-surface-3 text-[10px] font-mono border border-border-1">localhost:5678</code>
        </p>
        <p className="text-[11px] text-ink-muted leading-relaxed">
          Share this dashboard:{" "}
          <code className="px-1.5 py-0.5 rounded bg-surface-3 text-[10px] font-mono border border-border-1">tailscale funnel 3000</code>
        </p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<Tab>("workflows");
  const [plan, setPlan] = useState<{
    analysis: string;
    suggestedSteps: string[];
    canAutomate: boolean;
  } | null>(null);

  const handlePlan = (p: typeof plan) => {
    setPlan(p);
    setActiveTab("workflows");
  };

  useEffect(() => {
    const onOpenActivity = () => setActiveTab("activity");
    const onHashChange = () => {
      if (window.location.hash === "#activity") {
        setActiveTab("activity");
      }
    };
    window.addEventListener("flowsentinel:open-activity-tab", onOpenActivity);
    window.addEventListener("hashchange", onHashChange);
    onHashChange();
    return () => {
      window.removeEventListener("flowsentinel:open-activity-tab", onOpenActivity);
      window.removeEventListener("hashchange", onHashChange);
    };
  }, []);

  return (
    <div id="flowsentinel-dashboard-root" className="flex flex-1 overflow-hidden min-h-0 gap-0">
      {/* LEFT — Chat (58%) */}
      <div className="flex-[58] min-w-0 border-r border-border-1 flex flex-col overflow-hidden">
        <ChatPanel onWorkflowPlan={handlePlan} />
      </div>

      {/* RIGHT — Tabbed panel (42%) */}
      <div className="flex-[42] min-w-0 flex flex-col overflow-hidden">
        {/* Tab bar */}
        <div className="flex-shrink-0 flex items-center gap-1 px-4 pt-3 pb-0 border-b border-border-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={clsx(
                "flex items-center gap-1.5 px-3.5 py-2 rounded-t-xl text-[13px] font-medium border-b-2 transition-all",
                activeTab === id
                  ? "text-ink-primary border-violet-500 bg-surface-2"
                  : "text-ink-muted border-transparent hover:text-ink-secondary hover:bg-surface-2/50"
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
              {id === "activity" && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-dot" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {activeTab === "workflows" && (
            <div className="flex-1 overflow-hidden flex flex-col animate-fade-in">
              <WorkflowPanel plan={plan} />
            </div>
          )}
          {activeTab === "activity" && (
            <div className="flex-1 overflow-hidden flex flex-col animate-fade-in">
              <ActivityFeed />
            </div>
          )}
          {activeTab === "about" && (
            <div className="flex-1 overflow-hidden flex flex-col animate-fade-in">
              <AboutPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
