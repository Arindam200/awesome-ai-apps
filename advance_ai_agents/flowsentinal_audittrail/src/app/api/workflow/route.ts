import { NextRequest, NextResponse } from "next/server";
import { triggerWorkflow, getWorkflowStatus } from "@/lib/n8n";
import { createActivity } from "@/lib/activity";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { inputs } = body as { inputs?: Record<string, string> };

    createActivity(
      "workflow_triggered",
      { name: "User", kind: "human" },
      "Triggered n8n workflow",
      `Inputs: ${JSON.stringify(inputs ?? {}).slice(0, 100)}`,
      { inputs }
    );

    const result = await triggerWorkflow(inputs);

    const actType = result.state === "DONE" ? "workflow_completed" : "workflow_failed";
    createActivity(
      actType,
      { name: "n8n", kind: "system" },
      result.state === "DONE" ? "Workflow completed" : "Workflow failed",
      `Run ${result.run_id} — state: ${result.state}`,
      { run_id: result.run_id, outputs: result.outputs }
    );

    return NextResponse.json({
      run_id: result.run_id,
      state: result.state,
      outputs: result.outputs,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    createActivity(
      "workflow_failed",
      { name: "System", kind: "system" },
      "Workflow trigger error",
      message.slice(0, 200)
    );
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  try {
    const runId = req.nextUrl.searchParams.get("run_id");
    if (!runId) return NextResponse.json({ error: "run_id required" }, { status: 400 });
    const status = await getWorkflowStatus(runId);
    return NextResponse.json(status);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
