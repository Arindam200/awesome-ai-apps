export type StageName =
  | "Ask"
  | "Collect"
  | "Reason"
  | "Verify"
  | "Code"
  | "Request"
  | "Plan"
  | "Fetch"
  | "Structure"
  | "Check"
  | "Save";
export type StageStatus = "pending" | "running" | "completed" | "failed";
export type ActorType = "user" | "agent" | "tool";
export type TaskType =
  | "known_url_extract"
  | "web_research"
  | "page_monitor"
  | "site_discovery"
  | "multi_page_scan";
export type OlostepOperation = "search" | "scrape" | "answers" | "map" | "crawl";

export interface TimelineStage {
  name: StageName;
  status: StageStatus;
}

export interface WorkflowPlan {
  workflowName: string;
  taskType: TaskType;
  selectedOlostepOperation: OlostepOperation;
  searchQuery: string;
  targetUrls: string[];
  outputSchema: Record<string, unknown>;
  assumptions: string[];
  steps: string[];
}

export interface FetchResult {
  operation: OlostepOperation;
  data?: unknown;
  urls?: string[];
  pages?: unknown[];
  sources: string[];
  raw: unknown;
}

export interface StructuredOutput {
  structuredData: unknown;
  sources: string[];
  metadata: {
    operation: OlostepOperation;
    sourceCount: number;
    [key: string]: unknown;
  };
}

export interface QualityCheck {
  valid: boolean;
  confidence: number;
  missingFields: string[];
  suspiciousFields: string[];
  notes: string[];
}

export interface SignalBrief {
  executiveSummary: string;
  signalType: string;
  whyItMatters: string;
  whoShouldCare: string[];
  facts: string[];
  inferences: string[];
  contradictions: string[];
  missingEvidence: string[];
  riskOpportunityScore: number;
  confidence: number;
  nextBestQueries: string[];
  monitorSpec: {
    intent: string;
    cadence: string;
    triggerConditions: string[];
    outputFields: string[];
  };
  caseStudy: {
    title: string;
    subtitle: string;
    markdown?: string;
    lead: string;
    context: string;
    evidence: string[];
    analysis: string;
    sourceNotes: string;
    narrative: string;
    evidenceHighlights: string[];
    analystTakeaways: string[];
    recommendedActions: string[];
  };
  model: string;
}

export interface WorkflowRunRecord {
  id: string;
  workflowId: string;
  status: "running" | "completed" | "failed";
  stage: StageName;
  plan: WorkflowPlan | null;
  fetchResult: FetchResult | null;
  structuredOutput: StructuredOutput | null;
  qualityCheck: QualityCheck | null;
  signalBrief: SignalBrief | null;
  generatedCode: string;
  errorMessage: string | null;
  createdAt: string;
  completedAt: string | null;
  userRequest: string;
  optionalUrl: string;
  workflowName: string;
  timeline: TimelineStage[];
}

export interface CaseStudyDocRecord {
  runId: string;
  workflowId: string;
  title: string;
  markdown: string;
  version: number;
  createdAt: string;
  updatedAt: string;
  lastEditor: string;
  deletedAt: string | null;
}

export interface SetupStatus {
  missing: string[];
  configured: Record<string, boolean>;
  runtime?: {
    mastraAgentActive: boolean;
    mastraWorkflow: string;
    registeredAgents: Array<{
      id: string;
      name: string;
    }>;
    registeredTools: string[];
    model: string;
    sqlite: boolean;
    veltAuditConfigured: boolean;
    veltRestAuthOk?: boolean;
    veltRestAuthMessage?: string;
    veltOrgDiagnostics?: {
      maskedOrganizationId: string;
      mismatch: boolean;
      configuredKeys: Record<string, boolean>;
      maskedValues: Record<string, string>;
    };
  };
}
