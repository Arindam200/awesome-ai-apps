"use client";

import { useState } from "react";
import { Play, CheckCircle2, XCircle, Circle, Loader2, ExternalLink, ChevronRight } from "lucide-react";
import clsx from "clsx";

type StepStatus = "idle" | "running" | "done" | "failed";

interface Step {
  label: string;
  status: StepStatus;
}

interface Run {
  id: string;
  state: string;
  steps: Step[];
  log: string[];
  startedAt: string;
}

interface WorkflowPanelProps {
  plan?: { analysis: string; suggestedSteps: string[]; canAutomate: boolean } | null;
}

const StepIcon = ({ status }: { status: StepStatus }) => {
  if (status === "done") return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
  if (status === "failed") return <XCircle className="w-4 h-4 text-rose-400" />;
  if (status === "running") return <Loader2 className="w-4 h-4 text-violet-400 animate-spin" />;
  return <Circle className="w-4 h-4 text-ink-muted/50" />;
};

const STATE_STYLES: Record<string, string> = {
  DONE: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  FAILED: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  TERMINATED: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  RUNNING: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  STARTING: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  STARTED: "bg-violet-500/10 text-violet-400 border-violet-500/20",
};

export default function WorkflowPanel({ plan }: WorkflowPanelProps) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [triggering, setTriggering] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const trigger = async () => {
    if (triggering) return;
    setTriggering(true);

    const rawSteps = plan?.suggestedSteps?.length ? plan.suggestedSteps : ["Initialize", "Process", "Output"];
    const steps: Step[] = rawSteps.map((s) => ({ label: s, status: "idle" }));
    const run: Run = {
      id: `run_${Date.now().toString(36)}`,
      state: "STARTING",
      steps,
      log: [],
      startedAt: new Date().toISOString(),
    };

    setRuns((p) => [run, ...p.slice(0, 4)]);
    setExpanded(run.id);

    try {
      // Mark first step running while we wait
      update(run.id, {
        steps: [{ ...steps[0], status: "running" }, ...steps.slice(1)],
      });

      const res = await fetch("/api/workflow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          inputs: {
            query: plan?.analysis ?? "default",
            analysis: plan?.analysis ?? "",
            steps: plan?.suggestedSteps?.join(" | ") ?? "",
          },
        }),
      });
      const data = await res.json();

      if (data.error) {
        update(run.id, {
          state: "FAILED",
          steps: steps.map((s) => ({ ...s, status: "failed" as StepStatus })),
          log: [`Error: ${data.error}`],
        });
      } else {
        // n8n webhook (sync mode) returns immediately with results
        const outputLines: string[] = [`Run ID: ${data.run_id}`, `State: ${data.state}`];
        const outputs = data.outputs;
        if (outputs && typeof outputs === "object") {
          Object.entries(outputs).forEach(([k, v]) => {
            const val = typeof v === "string" ? v : JSON.stringify(v);
            outputLines.push(`${k}: ${val.slice(0, 200)}`);
          });
        } else if (outputs) {
          outputLines.push(`Output: ${String(outputs).slice(0, 200)}`);
        }
        update(run.id, {
          state: "DONE",
          steps: steps.map((s) => ({ ...s, status: "done" as StepStatus })),
          log: outputLines,
        });
      }
    } catch (err) {
      update(run.id, {
        state: "FAILED",
        steps: steps.map((s) => ({ ...s, status: "failed" as StepStatus })),
        log: [`Network error: ${err}`],
      });
    } finally {
      setTriggering(false);
    }
  };

  const update = (id: string, patch: Partial<Run>) =>
    setRuns((p) => p.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const activeRun = expanded ? runs.find((r) => r.id === expanded) : null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-border-1 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-lg bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center">
            <Play className="w-3 h-3 text-emerald-400" fill="currentColor" />
          </div>
          <span className="text-[13px] font-semibold text-ink-primary">Workflows</span>
          <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-medium text-emerald-300">
            n8n
          </span>
        </div>
        <button
          onClick={trigger}
          disabled={triggering}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-[12px] font-semibold text-white bg-emerald-600/80 hover:bg-emerald-600 border border-emerald-500/30 transition-all shadow-glow-emerald disabled:opacity-40 disabled:cursor-not-allowed active:scale-95"
        >
          {triggering
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Play className="w-3.5 h-3.5" fill="currentColor" />
          }
          Execute
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* Staged plan */}
        {plan && !activeRun && (
          <div className="animate-slide-up">
            <p className="text-[11px] font-medium text-ink-muted uppercase tracking-wider mb-3">
              Staged Pipeline
            </p>
            <div className="bg-surface-2 border border-border-1 rounded-2xl p-4">
              <p className="text-[13px] text-ink-secondary leading-relaxed mb-4">{plan.analysis}</p>
              <div className="space-y-3">
                {plan.suggestedSteps.map((step, i) => (
                  <div key={i} className="relative flex items-start gap-3">
                    {i < plan.suggestedSteps.length - 1 && (
                      <div className="step-connector" />
                    )}
                    <div className="w-5 h-5 rounded-full bg-surface-3 border border-border-2 flex items-center justify-center flex-shrink-0 mt-0.5 z-10">
                      <span className="text-[10px] font-mono text-ink-muted">{i + 1}</span>
                    </div>
                    <span className="text-[13px] text-ink-secondary pt-0.5 leading-snug">{step}</span>
                  </div>
                ))}
              </div>
              {plan.canAutomate && (
                <div className="mt-4 pt-3 border-t border-border-1 flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-[12px] text-emerald-400">Ready to automate</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Empty state */}
        {runs.length === 0 && !plan && (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-center animate-fade-in">
            <div className="w-12 h-12 rounded-2xl bg-surface-2 border border-border-1 flex items-center justify-center">
              <Play className="w-5 h-5 text-ink-muted" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-ink-secondary">No runs yet</p>
              <p className="text-[12px] text-ink-muted mt-1">Plan a workflow in the chat, then execute it here.</p>
            </div>
          </div>
        )}

        {/* Active run */}
        {activeRun && (
          <div className="animate-slide-up">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[11px] font-medium text-ink-muted uppercase tracking-wider">Active Run</p>
              <span className={clsx("px-2.5 py-1 rounded-full text-[11px] font-medium border", STATE_STYLES[activeRun.state] ?? STATE_STYLES.STARTED)}>
                {activeRun.state}
              </span>
            </div>

            <div className="bg-surface-2 border border-border-1 rounded-2xl p-4 space-y-3">
              {activeRun.steps.map((step, i) => (
                <div key={i} className="relative flex items-center gap-3">
                  {i < activeRun.steps.length - 1 && (
                    <div className="absolute left-[7.5px] top-5 w-px h-5 bg-border-1" />
                  )}
                  <StepIcon status={step.status} />
                  <span className={clsx("text-[13px] leading-snug", {
                    "text-ink-primary font-medium": step.status === "done" || step.status === "running",
                    "text-rose-400": step.status === "failed",
                    "text-ink-muted": step.status === "idle",
                  })}>
                    {step.label}
                  </span>
                  {step.status === "done" && (
                    <span className="ml-auto text-[11px] text-emerald-400 font-medium">Done</span>
                  )}
                  {step.status === "running" && (
                    <span className="ml-auto text-[11px] text-violet-400 font-medium">Running…</span>
                  )}
                </div>
              ))}
            </div>

            {/* Log */}
            {activeRun.log.length > 0 && (
              <div className="mt-3 bg-bg rounded-xl border border-border-1 p-3 max-h-28 overflow-y-auto">
                {activeRun.log.slice(-10).map((line, i) => (
                  <div key={i} className="text-[11px] font-mono text-ink-muted leading-relaxed">{line}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Past runs */}
        {runs.length > 1 && (
          <div>
            <p className="text-[11px] font-medium text-ink-muted uppercase tracking-wider mb-2">History</p>
            <div className="space-y-1.5">
              {runs.slice(1).map((r) => (
                <button
                  key={r.id}
                  onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                  className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-surface-2 border border-border-1 hover:border-border-2 transition-all text-left"
                >
                  <span className={clsx("w-2 h-2 rounded-full flex-shrink-0", {
                    "bg-emerald-400": r.state === "DONE",
                    "bg-rose-400": r.state === "FAILED",
                    "bg-amber-400": r.state === "RUNNING",
                    "bg-ink-muted": true,
                  })} />
                  <span className="text-[12px] text-ink-secondary font-mono flex-1 truncate">{r.id}</span>
                  <span className={clsx("text-[11px] font-medium border px-2 py-0.5 rounded-full", STATE_STYLES[r.state] ?? "text-ink-muted border-border-1")}>
                    {r.state}
                  </span>
                  <ChevronRight className={clsx("w-3.5 h-3.5 text-ink-muted transition-transform", expanded === r.id && "rotate-90")} />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
