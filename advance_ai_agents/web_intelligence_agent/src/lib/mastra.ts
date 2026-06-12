import { Agent } from "@mastra/core/agent";
import { Mastra } from "@mastra/core/mastra";
import { createTool } from "@mastra/core/tools";
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { z } from "zod";
import { logActivity } from "./activity";
import { generateWorkflowCode } from "./codegen";
import { caseStudyMarkdownForRun, getRun, updateRun, updateWorkflow, upsertCaseStudyDoc } from "./db";
import { envValue } from "./env";
import { checkWithNebius, createSignalBriefWithNebius, structureWithNebius } from "./nebius";
import {
  fetchWithPlan,
  olostepAnswersTool,
  olostepCrawlTool,
  olostepMapTool,
  olostepScrapeTool,
  olostepSearchTool
} from "./olostep";
import { planWorkflow } from "./planning";
import type { FetchResult, QualityCheck, SignalBrief, StructuredOutput, WorkflowPlan } from "./types";

const NEBIUS_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/";
const NEBIUS_MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b";

const fetchResultSchema = z.object({
  operation: z.enum(["search", "scrape", "answers", "map", "crawl"]),
  data: z.unknown().optional(),
  urls: z.array(z.string()).optional(),
  pages: z.array(z.unknown()).optional(),
  sources: z.array(z.string()),
  raw: z.unknown()
});

const requestSchema = z.object({
  request: z.string().min(1),
  optionalUrl: z.string().optional().default(""),
  runId: z.string().optional(),
  workflowId: z.string().optional()
});

const workflowStateSchema = z.object({
  request: z.string(),
  optionalUrl: z.string(),
  runId: z.string().optional(),
  workflowId: z.string().optional(),
  plan: z.unknown().optional(),
  fetchResult: z.unknown().optional(),
  structuredOutput: z.unknown().optional(),
  qualityCheck: z.unknown().optional(),
  signalBrief: z.unknown().optional(),
  generatedCode: z.string().optional()
});

type WorkflowState = z.infer<typeof workflowStateSchema>;

const nebiusModelConfig = {
  providerId: "nebius",
  modelId: NEBIUS_MODEL,
  url: NEBIUS_BASE_URL,
  apiKey: envValue("NEBIUS_API_KEY")
};

const toolMetadataByOperation = {
  search: { toolId: "olostepSearchTool", toolName: "Olostep Search Tool" },
  scrape: { toolId: "olostepScrapeTool", toolName: "Olostep Scrape Tool" },
  answers: { toolId: "olostepAnswersTool", toolName: "Olostep Answers Tool" },
  map: { toolId: "olostepMapTool", toolName: "Olostep Map Tool" },
  crawl: { toolId: "olostepCrawlTool", toolName: "Olostep Crawl Tool" }
} satisfies Record<WorkflowPlan["selectedOlostepOperation"], { toolId: string; toolName: string }>;

function agentMetadata(agent: Agent, stage: "Collect" | "Reason" | "Verify" | "Code", metadata: Record<string, unknown> = {}) {
  return {
    agentId: agent.id,
    agentName: agent.name,
    stage,
    model: NEBIUS_MODEL,
    ...metadata
  };
}

async function logAgentActivity(inputData: WorkflowState, agent: Agent, stage: "Collect" | "Reason" | "Verify" | "Code", actionType: string, message: string, metadata?: Record<string, unknown>) {
  if (!inputData.runId || !inputData.workflowId) return;
  updateRun(inputData.runId, { stage, status: "running" });
  await logActivity({
    workflowId: inputData.workflowId,
    runId: inputData.runId,
    actorType: "agent",
    actorName: agent.name,
    actionType,
    message,
    metadata: agentMetadata(agent, stage, metadata)
  });
}

function statePlan(inputData: WorkflowState): WorkflowPlan {
  return (inputData.plan as WorkflowPlan | undefined) ?? planWorkflow(inputData.request, inputData.optionalUrl);
}

async function stateFetchResult(inputData: WorkflowState, plan: WorkflowPlan): Promise<FetchResult> {
  return (inputData.fetchResult as FetchResult | undefined) ?? fetchWithPlan(plan);
}

async function stateStructuredOutput(inputData: WorkflowState, plan: WorkflowPlan, fetchResult: FetchResult): Promise<StructuredOutput> {
  return (inputData.structuredOutput as StructuredOutput | undefined) ?? structureWithNebius(plan, fetchResult);
}

async function stateQualityCheck(inputData: WorkflowState, plan: WorkflowPlan, structuredOutput: StructuredOutput): Promise<QualityCheck> {
  return (inputData.qualityCheck as QualityCheck | undefined) ?? checkWithNebius(plan, structuredOutput);
}

async function stateSignalBrief(
  inputData: WorkflowState,
  plan: WorkflowPlan,
  fetchResult: FetchResult,
  structuredOutput: StructuredOutput,
  qualityCheck: QualityCheck
): Promise<SignalBrief> {
  return (
    (inputData.signalBrief as SignalBrief | undefined) ??
    createSignalBriefWithNebius({ plan, fetchResult, structuredOutput, qualityCheck })
  );
}

export const mastraOlostepSearchTool = createTool({
  id: "olostepSearchTool",
  description: "Search the web for source-backed results using Olostep.",
  inputSchema: z.object({ query: z.string().min(1) }),
  outputSchema: fetchResultSchema,
  execute: async ({ query }) => olostepSearchTool({ query })
});

export const mastraOlostepScrapeTool = createTool({
  id: "olostepScrapeTool",
  description: "Scrape one known URL with Olostep and return source-backed page content.",
  inputSchema: z.object({
    url: z.string().url(),
    extractionPrompt: z.string().optional(),
    outputSchema: z.record(z.string(), z.unknown()).optional()
  }),
  outputSchema: fetchResultSchema,
  execute: async ({ url, extractionPrompt, outputSchema }) => olostepScrapeTool({ url, extractionPrompt, outputSchema })
});

export const mastraOlostepAnswersTool = createTool({
  id: "olostepAnswersTool",
  description: "Ask Olostep for a sourced answer in the requested JSON shape.",
  inputSchema: z.object({
    question: z.string().min(1),
    jsonShape: z.record(z.string(), z.unknown()).optional()
  }),
  outputSchema: fetchResultSchema,
  execute: async ({ question, jsonShape }) => olostepAnswersTool({ question, jsonShape })
});

export const mastraOlostepMapTool = createTool({
  id: "olostepMapTool",
  description: "Map/discover URLs from a site using Olostep.",
  inputSchema: z.object({ url: z.string().url() }),
  outputSchema: fetchResultSchema,
  execute: async ({ url }) => olostepMapTool({ url })
});

export const mastraOlostepCrawlTool = createTool({
  id: "olostepCrawlTool",
  description: "Crawl up to five pages from a site using Olostep.",
  inputSchema: z.object({
    url: z.string().url(),
    limit: z.number().int().min(1).max(5).optional()
  }),
  outputSchema: fetchResultSchema,
  execute: async ({ url, limit }) => olostepCrawlTool({ url, limit })
});

export const signalsPlannerAgent = new Agent({
  id: "signalsPlannerAgent",
  name: "Signals Planner Agent",
  instructions:
    "You are the Signals planning agent. Interpret the local operator request, choose the safest web intelligence operation, define the output schema, and keep the workflow source-grounded. Prefer deterministic planning fallbacks when a request is ambiguous.",
  model: nebiusModelConfig
});

export const olostepEvidenceAgent = new Agent({
  id: "olostepEvidenceAgent",
  name: "Olostep Evidence Agent",
  instructions:
    "You are the Signals evidence agent. Use the appropriate Olostep tool to collect live web evidence for the workflow plan. Return source URLs and never invent evidence.",
  model: nebiusModelConfig,
  tools: {
    olostepSearchTool: mastraOlostepSearchTool,
    olostepScrapeTool: mastraOlostepScrapeTool,
    olostepAnswersTool: mastraOlostepAnswersTool,
    olostepMapTool: mastraOlostepMapTool,
    olostepCrawlTool: mastraOlostepCrawlTool
  }
});

export const nebiusReasoningAgent = new Agent({
  id: "nebiusReasoningAgent",
  name: "Nebius Reasoning Agent",
  instructions:
    "You are the Signals reasoning agent. Use NVIDIA Nemotron on Nebius to structure live evidence, separate facts from inference, and keep every conclusion grounded in retrieved sources.",
  model: nebiusModelConfig
});

export const nebiusVerificationAgent = new Agent({
  id: "nebiusVerificationAgent",
  name: "Nebius Verification Agent",
  instructions:
    "You are the Signals verification agent. Check source grounding, confidence, missing evidence, contradictions, and risk/opportunity scoring. Do not let unsupported claims pass as facts.",
  model: nebiusModelConfig
});

export const nebiusCaseStudyAgent = new Agent({
  id: "nebiusCaseStudyAgent",
  name: "Nebius Case Study Agent",
  instructions:
    "You are the Signals case-study agent. Convert verified research into a clear, source-aware Markdown case study and keep the article compact, factual, and reviewable.",
  model: nebiusModelConfig
});

export const webSignalAgent = nebiusCaseStudyAgent;

export const webSignalAgents = {
  signalsPlannerAgent,
  olostepEvidenceAgent,
  nebiusReasoningAgent,
  nebiusVerificationAgent,
  nebiusCaseStudyAgent
};

export const registeredAgentSummaries = Object.values(webSignalAgents).map((agent) => ({
  id: agent.id,
  name: agent.name
}));

const askStep = createStep({
  id: "Ask",
  description: "Normalize the local operator request.",
  inputSchema: requestSchema,
  outputSchema: workflowStateSchema,
  execute: async ({ inputData }) => {
    const output = {
      request: inputData.request.trim(),
      optionalUrl: inputData.optionalUrl?.trim() ?? "",
      runId: inputData.runId,
      workflowId: inputData.workflowId
    };
    if (output.runId && output.workflowId) {
      updateRun(output.runId, { stage: "Ask", status: "running" });
      await logActivity({
        workflowId: output.workflowId,
        runId: output.runId,
        actorType: "user",
        actorName: "Local operator",
        actionType: "request_submitted",
        message: "Submitted a Signals intelligence request.",
        metadata: { request: output.request, optionalUrl: output.optionalUrl }
      });
    }
    return output;
  }
});

const collectStep = createStep({
  id: "Collect",
  description: "Select the Olostep operation and collect live web evidence.",
  inputSchema: workflowStateSchema,
  outputSchema: workflowStateSchema,
  execute: async ({ inputData }) => {
    const plan = statePlan(inputData);
    await logAgentActivity(
      inputData,
      signalsPlannerAgent,
      "Collect",
      "workflow_planned",
      `Planned the Signals workflow and selected Olostep ${plan.selectedOlostepOperation}.`,
      { mastraWorkflow: webSignalWorkflow.id, taskType: plan.taskType, operation: plan.selectedOlostepOperation }
    );
    if (inputData.workflowId) {
      updateWorkflow(inputData.workflowId, { name: plan.workflowName, plan });
    }
    const selectedTool = toolMetadataByOperation[plan.selectedOlostepOperation];
    await logAgentActivity(
      inputData,
      olostepEvidenceAgent,
      "Collect",
      "tool_selected",
      `Selected ${selectedTool.toolName} for live evidence collection.`,
      { taskType: plan.taskType, operation: plan.selectedOlostepOperation, ...selectedTool }
    );
    const fetchResult = await stateFetchResult(inputData, plan);
    if (inputData.runId && inputData.workflowId) {
      updateRun(inputData.runId, { stage: "Collect", plan, fetchResult });
      await logActivity({
        workflowId: inputData.workflowId,
        runId: inputData.runId,
        actorType: "tool",
        actorName: selectedTool.toolName,
        actionType: "evidence_collected",
        message: `Collected live evidence with Olostep ${plan.selectedOlostepOperation}.`,
        metadata: {
          agentId: olostepEvidenceAgent.id,
          agentName: olostepEvidenceAgent.name,
          stage: "Collect",
          taskType: plan.taskType,
          operation: plan.selectedOlostepOperation,
          sourceCount: fetchResult.sources.length,
          ...selectedTool
        }
      });
    }
    return {
      ...inputData,
      plan,
      fetchResult
    };
  }
});

const reasonStep = createStep({
  id: "Reason",
  description: "Structure live evidence with NVIDIA Nemotron on Nebius.",
  inputSchema: workflowStateSchema,
  outputSchema: workflowStateSchema,
  execute: async ({ inputData }) => {
    await logAgentActivity(inputData, nebiusReasoningAgent, "Reason", "nebius_reasoning_started", "Started Nebius Nemotron structuring and reasoning.", {});
    const plan = statePlan(inputData);
    const fetchResult = await stateFetchResult(inputData, plan);
    const structuredOutput = await structureWithNebius(plan, fetchResult);
    if (inputData.runId && inputData.workflowId) {
      updateRun(inputData.runId, { stage: "Reason", structuredOutput });
      await logActivity({
        workflowId: inputData.workflowId,
        runId: inputData.runId,
        actorType: "agent",
        actorName: nebiusReasoningAgent.name,
        actionType: "structured_evidence",
        message: "Structured live evidence into source-grounded signal data.",
        metadata: agentMetadata(nebiusReasoningAgent, "Reason", {
          operation: plan.selectedOlostepOperation,
          sourceCount: structuredOutput.sources.length
        })
      });
    }
    return {
      ...inputData,
      plan,
      fetchResult,
      structuredOutput
    };
  }
});

const verifyStep = createStep({
  id: "Verify",
  description: "Verify source grounding and produce a Nebius Signal Brief.",
  inputSchema: workflowStateSchema,
  outputSchema: workflowStateSchema,
  execute: async ({ inputData }) => {
    await logAgentActivity(inputData, nebiusVerificationAgent, "Verify", "source_check_started", "Started source-grounding verification, gap analysis, and scoring.", {});
    const plan = statePlan(inputData);
    const fetchResult = await stateFetchResult(inputData, plan);
    const structuredOutput = await stateStructuredOutput(inputData, plan, fetchResult);
    const qualityCheck = await stateQualityCheck(inputData, plan, structuredOutput);
    const signalBrief = await stateSignalBrief(inputData, plan, fetchResult, structuredOutput, qualityCheck);
    if (inputData.runId && inputData.workflowId) {
      updateRun(inputData.runId, { stage: "Verify", qualityCheck, signalBrief });
      await logActivity({
        workflowId: inputData.workflowId,
        runId: inputData.runId,
        actorType: "agent",
        actorName: nebiusVerificationAgent.name,
        actionType: "source_check_completed",
        message: "Completed source grounding, contradiction checks, confidence scoring, and Signal Brief creation.",
        metadata: {
          ...agentMetadata(nebiusVerificationAgent, "Verify"),
          operation: plan.selectedOlostepOperation,
          model: signalBrief.model,
          signalType: signalBrief.signalType,
          confidence: signalBrief.confidence,
          riskOpportunityScore: signalBrief.riskOpportunityScore,
          qualityValid: qualityCheck.valid
        }
      });
    }
    return {
      ...inputData,
      plan,
      fetchResult,
      structuredOutput,
      qualityCheck,
      signalBrief
    };
  }
});

const codeStep = createStep({
  id: "Code",
  description: "Generate reusable code for the selected workflow.",
  inputSchema: workflowStateSchema,
  outputSchema: workflowStateSchema,
  execute: async ({ inputData }) => {
    await logAgentActivity(inputData, nebiusCaseStudyAgent, "Code", "case_study_generation_started", "Started case-study document creation and reusable workflow code generation.", {});
    const plan = statePlan(inputData);
    const generatedCode = generateWorkflowCode(plan);
    if (inputData.runId && inputData.workflowId) {
      updateWorkflow(inputData.workflowId, { generatedCode });
      const run = getRun(inputData.runId);
      const signalBrief = inputData.signalBrief as SignalBrief | undefined;
      if (run && signalBrief) {
        const markdown = caseStudyMarkdownForRun(run);
        upsertCaseStudyDoc({
          runId: inputData.runId,
          workflowId: inputData.workflowId,
          title: signalBrief.caseStudy.title,
          markdown,
          lastEditor: "NVIDIA Nemotron on Nebius"
        });
        await logActivity({
          workflowId: inputData.workflowId,
          runId: inputData.runId,
          actorType: "agent",
          actorName: nebiusCaseStudyAgent.name,
          actionType: "case_study_created",
          message: "Saved the Nebius-generated case study document for collaborative review.",
          metadata: agentMetadata(nebiusCaseStudyAgent, "Code", {
            title: signalBrief.caseStudy.title,
            version: 1,
            operation: plan.selectedOlostepOperation
          })
        });
      }
      await logActivity({
        workflowId: inputData.workflowId,
        runId: inputData.runId,
        actorType: "tool",
        actorName: "SQLite Run Store",
        actionType: "run_saved",
        message: "Saved Signals run, structured evidence, case-study document, and generated code.",
        metadata: {
          toolId: "sqliteRunStore",
          toolName: "SQLite Run Store",
          stage: "Code",
          workflowId: inputData.workflowId,
          runId: inputData.runId
        }
      });
      updateRun(inputData.runId, { stage: "Code", status: "completed", completedAt: new Date().toISOString() });
    }
    return {
      ...inputData,
      plan,
      generatedCode
    };
  }
});

export const webSignalWorkflow = createWorkflow({
  id: "webSignalWorkflow",
  description: "Ask -> Collect -> Reason -> Verify -> Code web intelligence workflow.",
  inputSchema: requestSchema,
  outputSchema: workflowStateSchema
})
  .then(askStep)
  .then(collectStep)
  .then(reasonStep)
  .then(verifyStep)
  .then(codeStep)
  .commit();

export const mastra = new Mastra({
  agents: webSignalAgents,
  workflows: { webSignalWorkflow }
});
