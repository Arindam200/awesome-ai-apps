import { mkdirSync } from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { databaseFileName } from "./env";
import type {
  CaseStudyDocRecord,
  FetchResult,
  QualityCheck,
  SignalBrief,
  StageName,
  StageStatus,
  StructuredOutput,
  TimelineStage,
  WorkflowPlan,
  WorkflowRunRecord
} from "./types";

interface WorkflowRow {
  id: string;
  name: string;
  user_request: string;
  optional_url: string | null;
  task_type: string | null;
  selected_olostep_operation: string | null;
  output_schema_json: string | null;
  generated_code: string | null;
  created_at: string;
  updated_at: string;
}

interface RunRow {
  id: string;
  workflow_id: string;
  status: "running" | "completed" | "failed";
  stage: StageName;
  plan_json: string | null;
  fetch_result_json: string | null;
  structured_data_json: string | null;
  sources_json: string | null;
  quality_check_json: string | null;
  signal_brief_json: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

interface CaseStudyDocRow {
  run_id: string;
  workflow_id: string;
  title: string;
  markdown: string;
  version: number;
  created_at: string;
  updated_at: string;
  last_editor: string;
  deleted_at: string | null;
}

declare global {
  // eslint-disable-next-line no-var
  var __signalForgeDb: DatabaseSync | undefined;
}

function id(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`;
}

function safeJson<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function dbPath(): string {
  const fileName = databaseFileName();
  return path.isAbsolute(fileName) ? fileName : path.join(process.cwd(), fileName);
}

function ensureColumn(db: DatabaseSync, tableName: string, columnName: string, definition: string) {
  const columns = db.prepare(`PRAGMA table_info(${tableName})`).all() as { name: string }[];
  if (!columns.some((column) => column.name === columnName)) {
    db.exec(`ALTER TABLE ${tableName} ADD COLUMN ${columnName} ${definition}`);
  }
}

export function getDb() {
  if (!globalThis.__signalForgeDb) {
    const fullPath = dbPath();
    mkdirSync(path.dirname(fullPath), { recursive: true });
    const db = new DatabaseSync(fullPath);
    db.exec(`
      CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY,
        name TEXT,
        user_request TEXT,
        optional_url TEXT,
        task_type TEXT,
        selected_olostep_operation TEXT,
        output_schema_json TEXT,
        generated_code TEXT,
        created_at TEXT,
        updated_at TEXT
      );

      CREATE TABLE IF NOT EXISTS workflow_runs (
        id TEXT PRIMARY KEY,
        workflow_id TEXT,
        status TEXT,
        stage TEXT,
        plan_json TEXT,
        fetch_result_json TEXT,
        structured_data_json TEXT,
        sources_json TEXT,
        quality_check_json TEXT,
        signal_brief_json TEXT,
        error_message TEXT,
        created_at TEXT,
        completed_at TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_workflow_runs_created_at ON workflow_runs(created_at DESC);

      CREATE TABLE IF NOT EXISTS case_study_docs (
        run_id TEXT PRIMARY KEY,
        workflow_id TEXT,
        title TEXT,
        markdown TEXT,
        version INTEGER,
        created_at TEXT,
        updated_at TEXT,
        last_editor TEXT,
        deleted_at TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_case_study_docs_updated_at ON case_study_docs(updated_at DESC);
    `);
    ensureColumn(db, "workflow_runs", "signal_brief_json", "TEXT");
    ensureColumn(db, "case_study_docs", "deleted_at", "TEXT");
    globalThis.__signalForgeDb = db;
  }
  return globalThis.__signalForgeDb;
}

export function createRun(input: { request: string; optionalUrl: string }) {
  const now = new Date().toISOString();
  const workflowId = id("workflow");
  const runId = id("run");

  getDb()
    .prepare(
      `INSERT INTO workflows
       (id, name, user_request, optional_url, task_type, selected_olostep_operation, output_schema_json, generated_code, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .run(workflowId, "Untitled web signal", input.request, input.optionalUrl || null, null, null, null, null, now, now);

  getDb()
    .prepare(
      `INSERT INTO workflow_runs
       (id, workflow_id, status, stage, plan_json, fetch_result_json, structured_data_json, sources_json, quality_check_json, signal_brief_json, error_message, created_at, completed_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .run(runId, workflowId, "running", "Ask", null, null, null, null, null, null, null, now, null);

  return { workflowId, runId, createdAt: now };
}

export function updateWorkflow(workflowId: string, patch: { name?: string; plan?: WorkflowPlan; generatedCode?: string }) {
  const current = getDb().prepare(`SELECT * FROM workflows WHERE id = ?`).get(workflowId) as WorkflowRow | undefined;
  if (!current) return;

  getDb()
    .prepare(
      `UPDATE workflows
       SET name = ?, task_type = ?, selected_olostep_operation = ?, output_schema_json = ?, generated_code = ?, updated_at = ?
       WHERE id = ?`
    )
    .run(
      patch.name ?? current.name,
      patch.plan?.taskType ?? current.task_type,
      patch.plan?.selectedOlostepOperation ?? current.selected_olostep_operation,
      patch.plan ? JSON.stringify(patch.plan.outputSchema) : current.output_schema_json,
      patch.generatedCode ?? current.generated_code,
      new Date().toISOString(),
      workflowId
    );
}

export function updateRun(
  runId: string,
  patch: {
    status?: "running" | "completed" | "failed";
    stage?: StageName;
    plan?: WorkflowPlan;
    fetchResult?: FetchResult;
    structuredOutput?: StructuredOutput;
    qualityCheck?: QualityCheck;
    signalBrief?: SignalBrief;
    errorMessage?: string | null;
    completedAt?: string | null;
  }
) {
  const current = getDb().prepare(`SELECT * FROM workflow_runs WHERE id = ?`).get(runId) as RunRow | undefined;
  if (!current) return;

  getDb()
    .prepare(
      `UPDATE workflow_runs
       SET status = ?, stage = ?, plan_json = ?, fetch_result_json = ?, structured_data_json = ?, sources_json = ?,
           quality_check_json = ?, signal_brief_json = ?, error_message = ?, completed_at = ?
       WHERE id = ?`
    )
    .run(
      patch.status ?? current.status,
      patch.stage ?? current.stage,
      patch.plan ? JSON.stringify(patch.plan) : current.plan_json,
      patch.fetchResult ? JSON.stringify(patch.fetchResult) : current.fetch_result_json,
      patch.structuredOutput ? JSON.stringify(patch.structuredOutput.structuredData) : current.structured_data_json,
      patch.structuredOutput ? JSON.stringify(patch.structuredOutput.sources) : current.sources_json,
      patch.qualityCheck ? JSON.stringify(patch.qualityCheck) : current.quality_check_json,
      patch.signalBrief ? JSON.stringify(patch.signalBrief) : current.signal_brief_json,
      patch.errorMessage === undefined ? current.error_message : patch.errorMessage,
      patch.completedAt === undefined ? current.completed_at : patch.completedAt,
      runId
    );
}

function timelineFor(row: RunRow): TimelineStage[] {
  const modern: StageName[] = ["Ask", "Collect", "Reason", "Verify", "Code"];
  const legacy: StageName[] = ["Request", "Plan", "Fetch", "Structure", "Check", "Save"];
  const order = modern.includes(row.stage) ? modern : legacy;
  const activeIndex = order.indexOf(row.stage);
  return order.map((name, index) => ({
    name,
    status: (
      row.status === "failed" && name === row.stage
        ? "failed"
        : row.status === "completed" || index < activeIndex
          ? "completed"
          : index === activeIndex
            ? row.status === "running" ? "running" : "completed"
            : "pending"
    ) as StageStatus
  }));
}

function runFromRows(workflow: WorkflowRow, run: RunRow): WorkflowRunRecord {
  const plan = safeJson<WorkflowPlan | null>(run.plan_json, null);
  const fetchResult = safeJson<FetchResult | null>(run.fetch_result_json, null);
  const structuredData = safeJson<unknown | null>(run.structured_data_json, null);
  const sources = safeJson<string[]>(run.sources_json, []);
  const structuredOutput: StructuredOutput | null = structuredData
    ? {
        structuredData,
        sources,
        metadata: {
          operation: plan?.selectedOlostepOperation ?? "search",
          sourceCount: sources.length
        }
      }
    : null;

  return {
    id: run.id,
    workflowId: workflow.id,
    status: run.status,
    stage: run.stage,
    plan,
    fetchResult,
    structuredOutput,
    qualityCheck: safeJson<QualityCheck | null>(run.quality_check_json, null),
    signalBrief: safeJson<SignalBrief | null>(run.signal_brief_json, null),
    generatedCode: workflow.generated_code ?? "",
    errorMessage: run.error_message,
    createdAt: run.created_at,
    completedAt: run.completed_at,
    userRequest: workflow.user_request,
    optionalUrl: workflow.optional_url ?? "",
    workflowName: workflow.name,
    timeline: timelineFor(run)
  };
}

export function getRun(runId: string): WorkflowRunRecord | null {
  const run = getDb().prepare(`SELECT * FROM workflow_runs WHERE id = ?`).get(runId) as unknown as RunRow | undefined;
  if (!run) return null;
  const workflow = getDb().prepare(`SELECT * FROM workflows WHERE id = ?`).get(run.workflow_id) as unknown as WorkflowRow | undefined;
  if (!workflow) return null;
  return runFromRows(workflow, run);
}

export function listRuns(limit = 12): WorkflowRunRecord[] {
  const runs = getDb()
    .prepare(`SELECT * FROM workflow_runs ORDER BY created_at DESC LIMIT ?`)
    .all(limit) as unknown as RunRow[];

  return runs
    .map((run) => {
      const workflow = getDb().prepare(`SELECT * FROM workflows WHERE id = ?`).get(run.workflow_id) as unknown as WorkflowRow | undefined;
      if (!workflow) return null;
      return runFromRows(workflow, run);
    })
    .filter(Boolean) as WorkflowRunRecord[];
}

function publicSources(sources: string[]): string[] {
  const seen = new Set<string>();
  return sources
    .filter((source) => {
      try {
        const url = new URL(source);
        const host = url.hostname.toLowerCase();
        if (!["http:", "https:"].includes(url.protocol)) return false;
        if (host === "localhost" || host === "127.0.0.1" || host.endsWith(".local")) return false;
        if (host.includes("storage.googleapis.com") || host.includes("amazonaws.com")) return false;
        if (host.includes("api.olostep.com") || host.includes("api.velt.dev")) return false;
        return true;
      } catch {
        return false;
      }
    })
    .filter((source) => {
      if (seen.has(source)) return false;
      seen.add(source);
      return true;
    });
}

function tableValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not available";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "Not available";
  return String(value);
}

function compactList(items: string[], fallback: string): string {
  const clean = items.map((item) => item.trim()).filter(Boolean);
  if (clean.length === 0) return fallback;
  return clean.map((item) => `* ${item}`).join("\n");
}

function numberedEvidence(items: string[], sources: string[]): string {
  const clean = items.map((item) => item.trim()).filter(Boolean).slice(0, 8);
  if (clean.length === 0) {
    return "1. Claim: Not available\n   Source: Not available";
  }

  return clean
    .map((item, index) => {
      const source = sources[index] ?? sources[0] ?? "Not available";
      return `${index + 1}. Claim: ${item}\n   Source: ${source}`;
    })
    .join("\n\n");
}

function factsFromStructuredData(value: unknown): string[] {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value.slice(0, 8).map((item) => (typeof item === "string" ? item : JSON.stringify(item))).filter(Boolean);
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .slice(0, 8)
      .map(([key, item]) => `${key}: ${typeof item === "string" ? item : JSON.stringify(item)}`);
  }
  return [String(value)];
}

function titleFromMarkdown(markdown: string, fallback: string): string {
  const heading = markdown.match(/^#\s+(.+)$/m)?.[1]?.trim();
  return heading || fallback;
}

export function caseStudyMarkdownForRun(run: WorkflowRunRecord): string {
  const markdown = run.signalBrief?.caseStudy?.markdown?.trim();
  if (markdown) return markdown;

  const brief = run.signalBrief;
  const quality = run.qualityCheck;
  const sources = publicSources([...(run.fetchResult?.sources ?? []), ...(run.structuredOutput?.sources ?? [])]);
  const facts = brief?.facts?.length ? brief.facts : factsFromStructuredData(run.structuredOutput?.structuredData);
  const inferences = brief?.inferences ?? [];
  const gaps = brief?.missingEvidence?.length ? brief.missingEvidence : quality?.missingFields ?? [];
  const title = brief?.caseStudy?.title || run.workflowName || "Signals Case Study";
  const subtitle =
    brief?.caseStudy?.subtitle ||
    `Source-aware case study for ${run.plan?.selectedOlostepOperation ?? run.fetchResult?.operation ?? "live evidence"} research.`;
  const operation = run.plan?.selectedOlostepOperation ?? run.fetchResult?.operation ?? "Not available";
  const confidence = brief ? `${Math.round(brief.confidence * 100)}%` : quality ? `${Math.round(quality.confidence * 100)}%` : "Not available";
  const score = brief ? `${brief.riskOpportunityScore}/100` : "Not available";
  const date = run.completedAt || run.createdAt;
  const goal = run.userRequest || run.plan?.searchQuery || "Not available";

  return `# ${title}

${subtitle}

## 1. Executive Summary

This case study was prepared to answer the research goal: ${goal}

${brief?.executiveSummary || brief?.caseStudy?.lead || `The run collected live web evidence for ${goal}.`}

${brief?.whyItMatters || brief?.caseStudy?.context || "The saved run does not include a complete model-written impact section, so review the evidence and gaps before using this document for decisions."}

## 2. Snapshot

| Field | Details |
| --- | --- |
| Topic | ${tableValue(goal)} |
| Category | ${tableValue(brief?.signalType ?? run.plan?.taskType)} |
| Main capability | ${tableValue(facts[0])} |
| Target users | ${tableValue(brief?.whoShouldCare)} |
| Confidence | ${confidence} |
| Risk / opportunity score | ${score} |
| Primary operation used | ${tableValue(operation)} |
| Last researched | ${tableValue(new Date(date).toLocaleString())} |

## 3. What It Is

${brief?.caseStudy?.context || brief?.executiveSummary || "The saved run contains collected evidence, but it does not include a complete model-written positioning section. Use the evidence and source list below to validate the topic before final use."}

## 4. Who It Is For

${compactList(brief?.whoShouldCare ?? [], "* Not available.")}

## 5. Key Capabilities

| Capability | What it does | Evidence |
| --- | --- | --- |
${facts.slice(0, 6).map((fact, index) => `| ${fact.split(":")[0] || "Capability"} | ${fact.replace(/\|/g, "/")} | ${sources[index] ?? sources[0] ?? "Not available"} |`).join("\n") || "| Not available | Not available | Not available |"}

## 6. Why It Matters

* Current bottleneck: ${brief?.missingEvidence?.[0] || "Teams need source-aware research that answers the stated goal without hiding evidence quality."}
* What changes: ${brief?.whyItMatters || "The run turns collected source material into a reviewable case-study draft."}
* Why teams care: ${brief?.whoShouldCare?.join(", ") || "Analysts and product teams can review claims, gaps, and sources before acting."}
* Potential impact: ${brief ? `Nemotron estimated the risk/opportunity score as ${score}.` : "Not available."}

## 7. Evidence Summary

${numberedEvidence(facts, sources)}

## 8. Analysis

### Confirmed

${compactList(facts, "* Not available.")}

### Inferred

${compactList(inferences.map((item) => (item.startsWith("Inference:") ? item : `Inference: ${item}`)), "* Not available.")}

## 9. Gaps and Open Questions

| Missing information | Why it matters |
| --- | --- |
${gaps.slice(0, 8).map((gap) => `| ${gap.replace(/\|/g, "/")} | Needed to validate the research conclusion before acting. |`).join("\n") || "| Not available | No major gap was saved in the run. |"}

## 10. Recommended Follow-up Research

${compactList(brief?.nextBestQueries ?? [], "* Not available.")}

## 11. Source List

${compactList(sources, "* Not available.")}`;
}

function docFromRow(row: CaseStudyDocRow): CaseStudyDocRecord {
  return {
    runId: row.run_id,
    workflowId: row.workflow_id,
    title: row.title,
    markdown: row.markdown,
    version: row.version,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    lastEditor: row.last_editor,
    deletedAt: row.deleted_at
  };
}

export function upsertCaseStudyDoc(input: {
  runId: string;
  workflowId: string;
  title: string;
  markdown: string;
  lastEditor?: string;
}): CaseStudyDocRecord {
  const now = new Date().toISOString();
  const current = getDb()
    .prepare(`SELECT * FROM case_study_docs WHERE run_id = ?`)
    .get(input.runId) as CaseStudyDocRow | undefined;

  if (current) {
    getDb()
      .prepare(
        `UPDATE case_study_docs
         SET title = ?, markdown = ?, version = ?, updated_at = ?, last_editor = ?, deleted_at = NULL
         WHERE run_id = ?`
      )
      .run(input.title, input.markdown, current.version + 1, now, input.lastEditor ?? current.last_editor, input.runId);
  } else {
    getDb()
      .prepare(
        `INSERT INTO case_study_docs
         (run_id, workflow_id, title, markdown, version, created_at, updated_at, last_editor, deleted_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(input.runId, input.workflowId, input.title, input.markdown, 1, now, now, input.lastEditor ?? "NVIDIA Nemotron on Nebius", null);
  }

  return getCaseStudyDoc(input.runId) as CaseStudyDocRecord;
}

export function saveCaseStudyDoc(input: {
  runId: string;
  markdown: string;
  title?: string;
  lastEditor: string;
}): CaseStudyDocRecord | null {
  const current = getOrCreateCaseStudyDoc(input.runId);
  if (!current) return null;

  return upsertCaseStudyDoc({
    runId: current.runId,
    workflowId: current.workflowId,
    title: input.title?.trim() || titleFromMarkdown(input.markdown, current.title),
    markdown: input.markdown,
    lastEditor: input.lastEditor
  });
}

export function getCaseStudyDoc(runId: string, options: { includeDeleted?: boolean } = {}): CaseStudyDocRecord | null {
  const row = getDb().prepare(`SELECT * FROM case_study_docs WHERE run_id = ?`).get(runId) as CaseStudyDocRow | undefined;
  if (!row) return null;
  if (row.deleted_at && !options.includeDeleted) return null;
  return docFromRow(row);
}

export function getOrCreateCaseStudyDoc(runId: string): CaseStudyDocRecord | null {
  const archived = getCaseStudyDoc(runId, { includeDeleted: true });
  if (archived?.deletedAt) return null;
  const existing = getCaseStudyDoc(runId);
  if (existing) return existing;

  const run = getRun(runId);
  if (!run) return null;
  const markdown = caseStudyMarkdownForRun(run);
  return upsertCaseStudyDoc({
    runId: run.id,
    workflowId: run.workflowId,
    title: titleFromMarkdown(markdown, run.signalBrief?.caseStudy?.title || run.workflowName || "Signals Case Study"),
    markdown,
    lastEditor: run.signalBrief ? "NVIDIA Nemotron on Nebius" : "Signals fallback builder"
  });
}

export function listCaseStudyDocs(limit = 24): CaseStudyDocRecord[] {
  const rows = getDb()
    .prepare(`SELECT * FROM case_study_docs WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT ?`)
    .all(limit) as unknown as CaseStudyDocRow[];
  return rows.map(docFromRow);
}

export function archiveCaseStudyDoc(runId: string): CaseStudyDocRecord | null {
  const current = getCaseStudyDoc(runId);
  if (!current) return null;
  const now = new Date().toISOString();
  getDb()
    .prepare(`UPDATE case_study_docs SET deleted_at = ?, updated_at = ? WHERE run_id = ?`)
    .run(now, now, runId);
  return getCaseStudyDoc(runId, { includeDeleted: true });
}

export function restoreCaseStudyDoc(runId: string, lastEditor = "Signals reviewer"): CaseStudyDocRecord | null {
  const run = getRun(runId);
  if (!run) return null;
  const markdown = caseStudyMarkdownForRun(run);
  return upsertCaseStudyDoc({
    runId: run.id,
    workflowId: run.workflowId,
    title: titleFromMarkdown(markdown, run.signalBrief?.caseStudy?.title || run.workflowName || "Signals Case Study"),
    markdown,
    lastEditor
  });
}
