"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { API_URL, Run, authHeaders } from "@/lib/api";
import { Button } from "@/components/ui/Button";

const STAGE_LABELS: Record<string, string> = {
  ingest: "Ingesting signals",
  route: "Classifying documents",
  extract: "Extracting with Unsiloed",
  normalize: "Normalizing signals",
  analyze: "Computing trends",
  synthesize: "Writing the brief",
  render: "Rendering newsletter",
  send: "Sending email",
};

export default function RunNowButton({
  projectId,
  dryRun = true,
}: {
  projectId: number;
  dryRun?: boolean;
}) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const start = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/runs`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ project_id: projectId, dry_run: dryRun }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      const { run_id } = await res.json();
      timer.current = setInterval(async () => {
        const r: Run = await fetch(`${API_URL}/runs/${run_id}`, {
          headers: authHeaders(),
        }).then((x) => x.json());
        setRun(r);
        if (r.status !== "running") {
          stopPolling();
          if (r.status === "succeeded") window.location.reload();
        }
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const running = run?.status === "running";

  return (
    <div className="flex items-center gap-4">
      <Button variant="secondary" onClick={start} disabled={running}>
        <Play size={14} strokeWidth={2.25} className="text-primary" />
        {running ? "Running…" : "Run brief now"}
      </Button>
      {running && run?.stage && (
        <span className="flex items-center gap-2 text-sm text-muted">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary" />
          {STAGE_LABELS[run.stage] ?? run.stage}
          {run.stage === "extract" &&
            typeof run.stats?.new_documents === "number" &&
            ` (${run.stats.new_documents} new docs)`}
        </span>
      )}
      {run?.status === "failed" && (
        <span className="text-sm text-danger">Run failed: {run.error}</span>
      )}
      {error && <span className="text-sm text-danger">{error}</span>}
    </div>
  );
}
