import OpenAI from "openai";
import { envValue, requireEnv } from "./env";
import type { FetchResult, QualityCheck, SignalBrief, StructuredOutput, WorkflowPlan } from "./types";

const DEFAULT_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/";
const DEFAULT_MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b";

let client: OpenAI | null = null;

function getClient() {
  if (!client) {
    client = new OpenAI({
      apiKey: requireEnv("NEBIUS_API_KEY"),
      baseURL: envValue("NEBIUS_BASE_URL") || DEFAULT_BASE_URL
    });
  }
  return client;
}

function modelId(): string {
  return envValue("NEBIUS_MODEL") || DEFAULT_MODEL;
}

export function nebiusModelId(): string {
  return modelId();
}

function stripJson(text: string): string {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = fenced?.[1] ?? text;
  const objectMatch = candidate.match(/\{[\s\S]*\}/);
  return (objectMatch?.[0] ?? candidate).trim();
}

function safeSlice(value: unknown, max = 18000): string {
  const text = JSON.stringify(value, null, 2);
  return text.length > max ? `${text.slice(0, max)}\n...truncated` : text;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function cleanPublicSources(sources: string[]): string[] {
  return Array.from(
    new Set(
      sources.filter((source) => {
        const lower = source.toLowerCase();
        return (
          source.startsWith("http") &&
          !lower.includes("olostep-storage") &&
          !lower.includes("markdown_") &&
          !lower.includes("plain_text_")
        );
      })
    )
  );
}

function evidenceText(fetchResult: FetchResult, max = 5000): string {
  const data = fetchResult.data;
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    const text =
      (typeof record.markdown_content === "string" && record.markdown_content) ||
      (typeof record.text_content === "string" && record.text_content) ||
      JSON.stringify(record, null, 2);
    return text.length > max ? `${text.slice(0, max)}\n...truncated` : text;
  }
  const text = JSON.stringify(fetchResult.raw ?? fetchResult, null, 2);
  return text.length > max ? `${text.slice(0, max)}\n...truncated` : text;
}

function fallbackStructuredOutput(plan: WorkflowPlan, fetchResult: FetchResult, reason: string): StructuredOutput {
  const sources = cleanPublicSources(fetchResult.sources).length > 0 ? cleanPublicSources(fetchResult.sources) : fetchResult.sources;
  return {
    structuredData: {
      summary: "Nebius returned malformed structured JSON, so Signals preserved the collected Olostep evidence for downstream analysis.",
      operation: plan.selectedOlostepOperation,
      request: plan.searchQuery,
      evidenceText: evidenceText(fetchResult),
      sources
    },
    sources,
    metadata: {
      operation: plan.selectedOlostepOperation,
      sourceCount: sources.length,
      fallback: true,
      fallbackReason: reason
    }
  };
}

function normalizeCaseStudyMarkdown(markdown: string, researchedAt = new Date()): string {
  const researchedDate = researchedAt.toISOString().slice(0, 10);
  return markdown.replace(/\| Last researched \|[^|\n]*\|/i, `| Last researched | ${researchedDate} |`);
}

async function completeJson(system: string, user: string, maxTokens = 4096, timeoutMs = 120_000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let completion;
  try {
    completion = await getClient().chat.completions.create(
      {
        model: modelId(),
        temperature: 0.1,
        max_tokens: maxTokens,
        messages: [
          { role: "system", content: system },
          { role: "user", content: [{ type: "text", text: user }] }
        ]
      },
      { signal: controller.signal }
    );
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(`Nebius model request timed out after ${Math.round(timeoutMs / 1000)} seconds.`);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }

  const content = completion.choices[0]?.message?.content ?? "";
  try {
    return JSON.parse(stripJson(content)) as unknown;
  } catch {
    throw new Error(`Nebius returned non-JSON output: ${content.slice(0, 300)}`);
  }
}

export async function structureWithNebius(plan: WorkflowPlan, fetchResult: FetchResult): Promise<StructuredOutput> {
  let json: unknown;
  try {
    json = await completeJson(
      "You structure live web data into strict JSON. Do not invent data. Preserve source URLs. Return only JSON.",
      `Plan:
${JSON.stringify(plan, null, 2)}

Olostep result:
${safeSlice(fetchResult)}

Return exactly:
{
  "structuredData": {},
  "sources": [],
  "metadata": {
    "operation": "${plan.selectedOlostepOperation}",
    "sourceCount": 0
  }
}`
    );
  } catch (error) {
    return fallbackStructuredOutput(plan, fetchResult, error instanceof Error ? error.message : "Nebius structured JSON parse failed.");
  }

  const output = json as Partial<StructuredOutput>;
  if (!output || typeof output !== "object" || !("structuredData" in output)) {
    return fallbackStructuredOutput(plan, fetchResult, "Nebius structure step did not include structuredData.");
  }

  const modelSources = cleanPublicSources(Array.isArray(output.sources) ? output.sources.map(String) : []);
  const fetchedSources = cleanPublicSources(fetchResult.sources).length > 0 ? cleanPublicSources(fetchResult.sources) : fetchResult.sources;
  const sources = Array.from(new Set([...fetchedSources, ...modelSources]));
  return {
    structuredData: output.structuredData,
    sources: sources.length > 0 ? sources : fetchResult.sources,
    metadata: {
      ...(typeof output.metadata === "object" && output.metadata ? output.metadata : {}),
      operation: plan.selectedOlostepOperation,
      sourceCount: sources.length > 0 ? sources.length : fetchResult.sources.length
    }
  };
}

export async function checkWithNebius(plan: WorkflowPlan, output: StructuredOutput): Promise<QualityCheck> {
  let json: unknown;
  try {
    json = await completeJson(
      "You validate source-grounded structured extraction output. Return only JSON.",
      `Plan and schema:
${JSON.stringify({ plan, schema: plan.outputSchema }, null, 2)}

Structured output:
${safeSlice(output)}

Return exactly:
{
  "valid": true,
  "confidence": 0.0,
  "missingFields": [],
  "suspiciousFields": [],
  "notes": []
}`
    );
  } catch (error) {
    return {
      valid: output.sources.length > 0,
      confidence: output.sources.length > 0 ? 0.55 : 0.2,
      missingFields: [],
      suspiciousFields: ["Nebius verification JSON was malformed."],
      notes: [error instanceof Error ? error.message : "Nebius verification step failed; using deterministic fallback check."]
    };
  }

  const check = json as Partial<QualityCheck>;
  return {
    valid: Boolean(check.valid),
    confidence: typeof check.confidence === "number" ? Math.max(0, Math.min(check.confidence, 1)) : 0,
    missingFields: Array.isArray(check.missingFields) ? check.missingFields.map(String) : [],
    suspiciousFields: Array.isArray(check.suspiciousFields) ? check.suspiciousFields.map(String) : [],
    notes: Array.isArray(check.notes) ? check.notes.map(String) : []
  };
}

function fallbackSignalBrief(input: {
  plan: WorkflowPlan;
  fetchResult: FetchResult;
  structuredOutput: StructuredOutput;
  qualityCheck?: QualityCheck;
  reason: string;
}): SignalBrief {
  const sources = cleanPublicSources(input.structuredOutput.sources).length > 0 ? cleanPublicSources(input.structuredOutput.sources) : input.structuredOutput.sources;
  const title = input.plan.workflowName || "Signals case study";
  const researchedAt = new Date().toISOString();
  const capability = input.plan.selectedOlostepOperation;
  const sourceList = sources.length > 0 ? sources.map((source) => `- ${source}`).join("\n") : "- Not available";
  const researchGoal = input.plan.searchQuery || "Not available";
  const markdown = `# ${title}

Source-aware case study for the research goal: ${researchGoal}

## 1. Executive Summary

This case study was created to answer the user's research goal: ${researchGoal}

Web Intelligence Agent collected live evidence with Olostep, but Nebius returned malformed JSON during final case-study generation. Instead of discarding the run, this fallback document preserves the available evidence, sources, and open questions so the work remains reviewable.

Use this document as a recovery draft. It identifies what was collected, what remains unsupported, and what to research next before sharing conclusions.

## 2. Snapshot

| Field | Details |
| --- | --- |
| Topic | ${researchGoal} |
| Category | ${input.plan.taskType || "Not available"} |
| Main capability | ${capability || "Not available"} |
| Target users | Not available |
| Confidence | ${input.qualityCheck ? `${Math.round(input.qualityCheck.confidence * 100)}%` : "Not available"} |
| Risk / opportunity score | Not available |
| Primary operation used | ${capability || "Not available"} |
| Last researched | ${researchedAt} |

## 3. What It Is

The available evidence was collected for the stated research goal, but a completed model-written positioning section was not safely returned. Review the Evidence Summary and Source List before converting this fallback into a final case study.

## 4. Who It Is For

* Not available: user groups were not safely extracted from the model response.

## 5. Key Capabilities

| Capability | What it does | Evidence |
| --- | --- | --- |
| Live evidence collection | Collected page evidence through the selected Olostep operation. | ${sources[0] ?? "Not available"} |

## 6. Why It Matters

* Current bottleneck: Teams need source-aware research that can be reviewed instead of opaque summaries.
* What changes: The run remains auditable even though final model formatting failed.
* Why teams care: Analysts can inspect the collected evidence, source list, and missing information before acting.
* Potential impact: Not available from the saved evidence.

## 7. Evidence Summary

1. Claim: Signals collected live source material for this workflow run.
   Source: ${sources[0] ?? "Not available"}

## 8. Analysis

### Confirmed

- Live evidence was collected through ${capability}.

### Inferred

- Inference: The run needs manual review because Nebius did not return valid case-study JSON.

## 9. Gaps and Open Questions

| Missing information | Why it matters |
| --- | --- |
| Completed Nebius case-study JSON | Required for a polished analyst document |
| Source-specific facts | Required to avoid unsupported conclusions |

## 10. Recommended Follow-up Research

* ${researchGoal}
* ${researchGoal} pricing
* ${researchGoal} documentation
* ${researchGoal} customer proof
* ${researchGoal} compliance
* ${researchGoal} API or integration details

## 11. Source List

${sourceList}`;

  return {
    executiveSummary: "Signals preserved collected evidence, but Nebius returned malformed case-study JSON for this run.",
    signalType: "generic",
    whyItMatters: "The workflow remains auditable and reviewable even when a model response is malformed.",
    whoShouldCare: ["Analysts reviewing this run"],
    facts: sources.length > 0 ? [`Evidence was collected from ${sources[0]}.`] : ["Evidence was collected by Olostep."],
    inferences: ["Inference: Manual review is needed because the model response was malformed."],
    contradictions: [],
    missingEvidence: ["Completed Nebius case-study JSON"],
    riskOpportunityScore: 0,
    confidence: input.qualityCheck?.confidence ?? 0.3,
    nextBestQueries: [
      input.plan.searchQuery,
      `${input.plan.searchQuery} pricing`,
      `${input.plan.searchQuery} documentation`,
      `${input.plan.searchQuery} customer case study`,
      `${input.plan.searchQuery} compliance`
    ],
    monitorSpec: {
      intent: input.plan.searchQuery,
      cadence: "manual for local MVP",
      triggerConditions: [],
      outputFields: []
    },
    caseStudy: {
      title,
      subtitle: "Fallback case study from saved Olostep evidence",
      markdown: normalizeCaseStudyMarkdown(markdown),
      lead: "Signals collected evidence, but Nebius returned malformed JSON.",
      context: input.reason,
      evidence: sources,
      analysis: "Manual review is needed because the model did not return valid case-study JSON.",
      sourceNotes: input.reason,
      narrative: "Signals preserved the collected evidence for review instead of discarding the run.",
      evidenceHighlights: sources,
      analystTakeaways: ["Inference: rerun the workflow or review the evidence manually."],
      recommendedActions: ["Rerun the workflow", "Review the source list", "Open the saved evidence tab"]
    },
    model: modelId()
  };
}

export async function createSignalBriefWithNebius(input: {
  plan: WorkflowPlan;
  fetchResult: FetchResult;
  structuredOutput: StructuredOutput;
  qualityCheck?: QualityCheck;
}): Promise<SignalBrief> {
  let json: unknown;
  const researchedAt = new Date();
  try {
    json = await completeJson(
      "You are an NVIDIA Nemotron analyst running on Nebius, a senior research editor, and a case-study writer. Turn the complete agent run into a long, source-grounded, business-readable intelligence document. Use the user's request as the editorial assignment. Use the Mastra plan, Olostep evidence, Nebius structured extraction, and verification output together. The final case study must read like a polished product/market case study, not like a JSON summary or extraction report. Write substantial prose with clear narrative flow, but never add unsupported claims. Do not invent facts. Do not invent metrics. Do not turn inferences into facts. Do not repeat sections. Do not include raw internal tool URLs unless they are useful public sources. Do not include generated code. Separate confirmed facts from inference. Return only JSON.",
      `User intent and collection plan:
${JSON.stringify(input.plan, null, 2)}

Live Olostep evidence:
${safeSlice(input.fetchResult, 14000)}

Structured extraction:
${safeSlice(input.structuredOutput, 8000)}

Quality check:
${safeSlice(input.qualityCheck ?? null, 3000)}

Current run date:
${researchedAt.toISOString().slice(0, 10)}

Return exactly:
{
  "executiveSummary": "string",
  "signalType": "market | competitor | pricing | docs | product | research | generic",
  "whyItMatters": "string",
  "whoShouldCare": ["string"],
  "facts": ["source-backed fact"],
  "inferences": ["clearly labeled model inference"],
  "contradictions": ["string"],
  "missingEvidence": ["string"],
  "riskOpportunityScore": 0,
  "confidence": 0,
  "nextBestQueries": ["string"],
  "monitorSpec": {
    "intent": "string",
    "cadence": "manual for local MVP",
    "triggerConditions": ["string"],
    "outputFields": ["string"]
  },
  "caseStudy": {
    "title": "article headline",
    "subtitle": "short dek/subtitle",
    "markdown": "# Case Study Title\\n\\n## 1. Executive Summary\\n\\n...",
    "lead": "one strong opening paragraph",
    "context": "background paragraph explaining the market/company context",
    "evidence": ["source-grounded evidence point written for an article"],
    "analysis": "2-3 paragraphs of source-grounded analysis separating fact from inference",
    "sourceNotes": "short note about source quality, contradictions, and gaps",
    "narrative": "3-5 short paragraphs written as normal analyst prose, grounded in the evidence",
    "evidenceHighlights": ["source-grounded evidence highlight"],
    "analystTakeaways": ["clearly labeled interpretation or implication"],
    "recommendedActions": ["specific next action"]
  }
}

The caseStudy.markdown field must be a polished, readable, long-form Markdown case study in this exact format. Target roughly 1,500 to 2,500 words when the evidence is sufficient. Use a clear marketing-quality editorial style, but keep every claim grounded in the input evidence. The case study must reflect the user's research goal, not merely summarize collected source data. Make it useful to a product, strategy, or engineering team deciding whether the signal matters.

# {{Case Study Title}}

Use a strong, specific headline. It should say what the case study is really about, not just the company or page name.

## 1. Executive Summary

Write 4 to 6 short paragraphs that answer the user's research goal. Explain what the product/company/topic is, who it is for, what problem it solves, why it matters now, and what the evidence supports. Make the opening feel like a strong product or market case study, not a dry extraction report. Include the main thesis of the document. Do not add facts or metrics that are not in the input.

## 2. Snapshot

| Field | Details |
| --- | --- |
| Topic | |
| Category | |
| Main capability | |
| Target users | |
| Confidence | |
| Risk / opportunity score | |
| Primary operation used | |
| Last researched | |

Use only values available in the input. If missing, write "Not available."

## 3. What It Is

Explain the product/topic in plain English. Use factual statements only. Keep it between 120 and 220 words if the evidence supports that length. Marketing-style clarity is welcome, but avoid unsupported superlatives, hype, or claims not grounded in the evidence.

## 4. Who It Is For

Use bullets grouped by role or team type. For each role, explain the use case and why the evidence suggests that role matters. Only include user groups supported by the input.

## 5. Key Capabilities

| Capability | What it does | Evidence |
| --- | --- | --- |

Each row should map one source-supported capability to one clear explanation and one proof point. Evidence should mention the public source name or URL. Do not include weak or speculative capabilities.

## 6. Why It Matters

Write this section as a business-impact narrative with 1 to 2 paragraphs before the bullets. Then use this structure:

* Current bottleneck:
* What changes:
* Why teams care:
* Potential impact:

Keep this grounded. Tie the importance back to the user's research goal. If impact is not measured in the input, describe it qualitatively and do not invent numbers.

## 7. Evidence Summary

Use this format:

1. Claim: ...
   Source: ...

Only include useful public sources. Remove duplicates and temporary/generated/internal sources. Include enough evidence points to show how the thesis was built, not just one or two claims.

## 8. Analysis

### Confirmed

List what is clearly supported by sources. Keep this factual. Use complete sentences or concise bullets.

### Inferred

Each inference must start with "Inference:". Make implications useful for business readers, but do not present inference as fact. Explain why the inference follows from the evidence.

## 9. Gaps and Open Questions

| Missing information | Why it matters |
| --- | --- |

Only include gaps that are actually missing from the input.

## 10. Recommended Follow-up Research

List 5 to 7 specific next queries that would help a product, strategy, or engineering team validate the case study and close the most important evidence gaps. Make the queries concrete enough to paste into a search or another Signals run.

## 11. Source List

List only clean public source URLs. Remove duplicates, generated answer URLs, temporary storage URLs, and irrelevant links.`
,
      12000,
      180_000
    );
  } catch (error) {
    return fallbackSignalBrief({
      ...input,
      reason: error instanceof Error ? error.message : "Nebius case-study generation failed."
    });
  }

  const brief = json as Partial<SignalBrief>;
  const facts = stringArray(brief.facts);
  const inferences = stringArray(brief.inferences);
  const nextBestQueries = stringArray(brief.nextBestQueries);
  const evidenceHighlights = stringArray(brief.caseStudy?.evidenceHighlights);
  const analystTakeaways = stringArray(brief.caseStudy?.analystTakeaways);
  const recommendedActions = stringArray(brief.caseStudy?.recommendedActions);
  const caseEvidence = stringArray(brief.caseStudy?.evidence);
  const narrativeFallback = [
    brief.executiveSummary ?? "Nemotron summarized the collected evidence for this run.",
    brief.whyItMatters ?? "Review the saved evidence and quality check before acting on this signal."
  ].join("\n\n");

  return {
    executiveSummary: String(brief.executiveSummary ?? "No summary returned."),
    signalType: String(brief.signalType ?? "generic"),
    whyItMatters: String(brief.whyItMatters ?? "No rationale returned."),
    whoShouldCare: stringArray(brief.whoShouldCare),
    facts,
    inferences,
    contradictions: stringArray(brief.contradictions),
    missingEvidence: stringArray(brief.missingEvidence),
    riskOpportunityScore:
      typeof brief.riskOpportunityScore === "number" ? Math.max(0, Math.min(100, brief.riskOpportunityScore)) : 0,
    confidence: typeof brief.confidence === "number" ? Math.max(0, Math.min(1, brief.confidence)) : 0,
    nextBestQueries,
    monitorSpec: {
      intent: String(brief.monitorSpec?.intent ?? input.plan.searchQuery),
      cadence: String(brief.monitorSpec?.cadence ?? "manual for local MVP"),
      triggerConditions: stringArray(brief.monitorSpec?.triggerConditions),
      outputFields: stringArray(brief.monitorSpec?.outputFields)
    },
    caseStudy: {
      title: String(brief.caseStudy?.title ?? brief.executiveSummary ?? input.plan.workflowName),
      subtitle: String(brief.caseStudy?.subtitle ?? `Signals case study for ${input.plan.selectedOlostepOperation} evidence`),
      markdown: typeof brief.caseStudy?.markdown === "string" ? normalizeCaseStudyMarkdown(brief.caseStudy.markdown, researchedAt) : undefined,
      lead: String(brief.caseStudy?.lead ?? brief.executiveSummary ?? "Nemotron summarized the collected evidence for this run."),
      context: String(brief.caseStudy?.context ?? brief.whyItMatters ?? "Review the saved evidence and quality check before acting on this signal."),
      evidence: caseEvidence.length > 0 ? caseEvidence : evidenceHighlights.length > 0 ? evidenceHighlights : facts,
      analysis: String(brief.caseStudy?.analysis ?? narrativeFallback),
      sourceNotes: String(
        brief.caseStudy?.sourceNotes ??
          [
            stringArray(brief.contradictions).length > 0 ? `Contradictions: ${stringArray(brief.contradictions).join("; ")}` : "No contradictions detected.",
            stringArray(brief.missingEvidence).length > 0 ? `Missing evidence: ${stringArray(brief.missingEvidence).join("; ")}` : "No missing evidence called out."
          ].join(" ")
      ),
      narrative: String(brief.caseStudy?.narrative ?? narrativeFallback),
      evidenceHighlights: evidenceHighlights.length > 0 ? evidenceHighlights : facts,
      analystTakeaways: analystTakeaways.length > 0 ? analystTakeaways : inferences,
      recommendedActions: recommendedActions.length > 0 ? recommendedActions : nextBestQueries
    },
    model: modelId()
  };
}
