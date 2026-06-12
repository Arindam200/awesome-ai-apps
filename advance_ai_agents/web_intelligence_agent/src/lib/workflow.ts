import { logActivity } from "./activity";
import { createRun, getRun, updateRun } from "./db";
import { signalsPlannerAgent, webSignalWorkflow } from "./mastra";
import type { QualityCheck, SignalBrief, StructuredOutput, WorkflowPlan, FetchResult } from "./types";

type MastraWorkflowState = {
  request?: string;
  optionalUrl?: string;
  runId?: string;
  workflowId?: string;
  plan?: WorkflowPlan;
  fetchResult?: FetchResult;
  structuredOutput?: StructuredOutput;
  qualityCheck?: QualityCheck;
  signalBrief?: SignalBrief;
  generatedCode?: string;
};

function successfulOutput(result: unknown): MastraWorkflowState {
  const workflowResult = result as {
    status?: string;
    result?: MastraWorkflowState;
    error?: Error;
    steps?: Record<string, { status?: string; output?: MastraWorkflowState }>;
  };

  if (workflowResult.status !== "success") {
    throw workflowResult.error ?? new Error(`Mastra workflow ended with status ${workflowResult.status ?? "unknown"}.`);
  }

  return workflowResult.result ?? workflowResult.steps?.Code?.output ?? {};
}

export async function executeWebSignalWorkflow(input: {
  workflowId: string;
  runId: string;
  request: string;
  optionalUrl?: string;
}) {
  try {
    const mastraRun = await webSignalWorkflow.createRun({ runId: `mastra_${input.runId}` });
    const mastraResult = await mastraRun.start({
      inputData: {
        request: input.request,
        optionalUrl: input.optionalUrl ?? "",
        workflowId: input.workflowId,
        runId: input.runId
      }
    });
    const output = successfulOutput(mastraResult);
    if (!output.plan || !output.fetchResult || !output.structuredOutput || !output.qualityCheck || !output.signalBrief) {
      throw new Error("Mastra workflow completed without the expected Signals outputs.");
    }
    return getRun(input.runId);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown workflow error";
    updateRun(input.runId, {
      status: "failed",
      errorMessage: message,
      completedAt: new Date().toISOString()
    });
    await logActivity({
      workflowId: input.workflowId,
      runId: input.runId,
      actorType: "agent",
      actorName: signalsPlannerAgent.name,
      actionType: "workflow_failed",
      message,
      metadata: {
        agentId: signalsPlannerAgent.id,
        agentName: signalsPlannerAgent.name,
        stage: "Ask"
      }
    });
    return getRun(input.runId);
  }
}

export function startWebSignalWorkflow(input: { request: string; optionalUrl?: string }) {
  const request = input.request.trim();
  const optionalUrl = input.optionalUrl?.trim() ?? "";
  if (!request) {
    throw new Error("A request is required.");
  }

  const { workflowId, runId } = createRun({ request, optionalUrl });
  void executeWebSignalWorkflow({ workflowId, runId, request, optionalUrl }).catch(() => undefined);
  return getRun(runId);
}

export async function runWebSignalWorkflow(input: { request: string; optionalUrl?: string }) {
  const request = input.request.trim();
  const optionalUrl = input.optionalUrl?.trim() ?? "";
  if (!request) {
    throw new Error("A request is required.");
  }

  const { workflowId, runId } = createRun({ request, optionalUrl });
  return executeWebSignalWorkflow({ workflowId, runId, request, optionalUrl });
}
