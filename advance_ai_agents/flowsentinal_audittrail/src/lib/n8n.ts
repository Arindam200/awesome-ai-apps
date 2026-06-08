/**
 * n8n workflow client.
 *
 * n8n is 100% free and open source. Run it locally:
 *   npx n8n
 * Then open http://localhost:5678, create a workflow, add a Webhook node,
 * set "Respond" to "When Last Node Finishes", and copy the webhook URL.
 *
 * Webhook trigger:  POST  N8N_WEBHOOK_URL  { ...inputs }
 * Execution status: GET   N8N_BASE_URL/api/v1/executions?limit=1
 */

const N8N_BASE = process.env.N8N_BASE_URL ?? "http://localhost:5678";
const N8N_WEBHOOK = process.env.N8N_WEBHOOK_URL ?? "";
const N8N_API_KEY = process.env.N8N_API_KEY ?? "";

export interface WorkflowRun {
  run_id: string;
  state: "STARTED" | "RUNNING" | "DONE" | "FAILED" | "TERMINATED";
  log: string[];
  outputs: Record<string, unknown>;
  created_ts: string;
  finished_ts: string | null;
}

export interface WorkflowTriggerResult {
  run_id: string;
  state: string;
  outputs: Record<string, unknown>;
}

/**
 * Trigger an n8n workflow via its webhook URL.
 * If the webhook is set to "When Last Node Finishes", this call is synchronous
 * and returns the workflow output directly — no polling needed.
 */
export async function triggerWorkflow(
  inputs: Record<string, string> = {}
): Promise<WorkflowTriggerResult> {
  if (!N8N_WEBHOOK) {
    throw new Error(
      "N8N_WEBHOOK_URL is not set. Run n8n locally (npx n8n) and add the webhook URL to .env.local"
    );
  }

  const res = await fetch(N8N_WEBHOOK, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(inputs),
  });

  if (!res.ok) {
    const text = await res.text();
    if (res.status === 404 && N8N_WEBHOOK.includes("/webhook-test/")) {
      throw new Error(
        "n8n test webhook is not active. In n8n editor click 'Execute workflow' and call once, or switch N8N_WEBHOOK_URL to the production URL (/webhook/...) and activate the workflow."
      );
    }
    throw new Error(`n8n webhook failed (${res.status}): ${text}`);
  }

  // n8n returns the last node's output when response mode = "When Last Node Finishes"
  let outputs: Record<string, unknown> = {};
  try {
    const raw = await res.json();
    outputs = Array.isArray(raw) ? { result: raw } : (raw as Record<string, unknown>);
  } catch {
    // non-JSON response from n8n (e.g., "Workflow got started" text)
    outputs = { message: "Workflow started" };
  }

  const run_id = `n8n_${Date.now()}`;
  return { run_id, state: "DONE", outputs };
}

/**
 * Fetch the latest execution status from n8n REST API.
 * Requires N8N_API_KEY (set in n8n Settings → API → Create API Key).
 */
export async function getWorkflowStatus(run_id: string): Promise<WorkflowRun> {
  if (!N8N_API_KEY) {
    return {
      run_id,
      state: "DONE",
      log: ["n8n API key not set — status polling unavailable"],
      outputs: {},
      created_ts: new Date().toISOString(),
      finished_ts: new Date().toISOString(),
    };
  }

  const res = await fetch(`${N8N_BASE}/api/v1/executions?limit=1`, {
    headers: { "X-N8N-API-KEY": N8N_API_KEY },
  });

  if (!res.ok) {
    throw new Error(`n8n API failed (${res.status})`);
  }

  const data = await res.json();
  const exec = data?.data?.[0];
  if (!exec) {
    return {
      run_id,
      state: "DONE",
      log: ["No executions found"],
      outputs: {},
      created_ts: new Date().toISOString(),
      finished_ts: null,
    };
  }

  const state =
    exec.finished && exec.stoppedAt ? "DONE" :
    exec.status === "error" ? "FAILED" :
    "RUNNING";

  return {
    run_id: exec.id?.toString() ?? run_id,
    state: state as WorkflowRun["state"],
    log: [`Status: ${exec.status}`, `Mode: ${exec.mode}`],
    outputs: exec.data?.resultData?.runData ?? {},
    created_ts: exec.startedAt ?? new Date().toISOString(),
    finished_ts: exec.stoppedAt ?? null,
  };
}

/**
 * Poll until an n8n execution completes (fallback for long-running workflows).
 */
export async function pollUntilDone(
  run_id: string,
  intervalMs = 2000,
  maxWaitMs = 120000
): Promise<WorkflowRun> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const status = await getWorkflowStatus(run_id);
    if (["DONE", "FAILED", "TERMINATED"].includes(status.state)) return status;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Workflow ${run_id} did not complete within ${maxWaitMs}ms`);
}
