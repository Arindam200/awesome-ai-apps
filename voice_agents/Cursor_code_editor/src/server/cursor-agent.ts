import { z } from "zod";

import type { CodeActionResult, SummaryDepth } from "../shared/messages.js";
import { config } from "./config.js";

const summarizeArgsSchema = z.object({
  target: z.string().min(1).default("workspace"),
  depth: z.enum(["brief", "standard", "deep"]).default("standard"),
  question: z.string().optional()
});

const editArgsSchema = z.object({
  target: z.string().min(1).default("workspace"),
  instructions: z.string().min(8),
  verify: z.boolean().optional().default(true)
});

export async function summarizeCode(args: unknown): Promise<CodeActionResult> {
  // DEMO: Summary runs are read-only, even though the same Cursor SDK can edit files.
  const parsed = summarizeArgsSchema.parse(normalizeArgs(args));
  const depthGuide = {
    brief:
      "Brief means 3-5 sentences, up to 4 key files, only the highest-signal risks and follow-ups.",
    standard:
      "Standard means a practical product-engineering summary with 2-4 short paragraphs and up to 8 key files.",
    deep:
      "Deep means include architecture, data flow, important modules, operational risks, and concrete follow-ups. Keep it structured, not verbose."
  } satisfies Record<SummaryDepth, string>;
  const prompt = [
    "You are summarizing code for a voice-controlled app.",
    "This is a read-only task. Do not edit, create, delete, move, or format files.",
    `Workspace: ${config.codeWorkspace}`,
    `Target: ${parsed.target}`,
    `Depth: ${parsed.depth}`,
    depthGuide[parsed.depth],
    parsed.question ? `Specific question: ${parsed.question}` : undefined,
    "",
    "Return concise JSON only with this shape:",
    '{"title":"...","directAnswer":"...","purpose":"...","architecture":"...","summary":"...","keyFiles":["..."],"notableRisks":["..."],"followUps":["..."],"spokenAnswer":"..."}',
    "directAnswer answers the user's question first.",
    "purpose says what the target does in one or two sentences.",
    "architecture explains the main moving parts and data/control flow.",
    "summary should be a compact synthesis of directAnswer, purpose, and architecture.",
    "The spokenAnswer must be one or two short plain-English sentences suitable for text-to-speech.",
    "Do not put markdown, code fences, raw JSON, bullets, file contents, asterisks, hashes, or backticks in spokenAnswer.",
    "Keep values accurate to what you inspected."
  ]
    .filter(Boolean)
    .join("\n");

  const raw = await runCursor(prompt);
  return parseActionResult(raw, "summarize", parsed.depth);
}

export async function editCode(args: unknown): Promise<CodeActionResult> {
  // DEMO: Edit prompts are scoped and only reached after session-level edit consent.
  const parsed = editArgsSchema.parse(normalizeArgs(args));
  const prompt = [
    "You are editing code in a local workspace at the user's request.",
    `Workspace: ${config.codeWorkspace}`,
    `Target: ${parsed.target}`,
    `Edit request: ${parsed.instructions}`,
    parsed.verify
      ? "Run reasonable focused validation if the project makes the command obvious."
      : "Do not run validation commands unless required to understand the edit.",
    "",
    "Keep the change scoped. Preserve unrelated user work. Do not touch secrets.",
    "After finishing, return concise JSON only with this shape:",
    '{"title":"...","summary":"...","spokenAnswer":"...","keyFiles":["..."],"changes":["..."],"notableRisks":["..."],"followUps":["..."]}',
    "spokenAnswer must be one or two short plain-English sentences with no markdown, code, raw file contents, hashes, asterisks, or backticks.",
    "If you cannot safely make the edit, explain why in summary and leave changes empty."
  ].join("\n");

  const raw = await runCursor(prompt, { force: true });
  return parseActionResult(raw, "edit", "standard");
}

async function runCursor(prompt: string, options: { force?: boolean } = {}) {
  const { Agent } = await import("@cursor/sdk");
  // DEMO: Cursor SDK creates the local coding agent pointed at CODE_WORKSPACE.
  const agent = await Agent.create({
    apiKey: config.cursorApiKey,
    name: "Voice code summarizer",
    model: { id: config.cursorModel },
    local: { cwd: config.codeWorkspace }
  });

  try {
    const run = await agent.send(prompt, {
      ...(options.force ? { local: { force: true } } : {})
    });
    let assistantText = "";

    for await (const event of run.stream()) {
      if (event.type !== "assistant") continue;
      for (const block of event.message.content) {
        if (block.type === "text") {
          assistantText += block.text;
        }
      }
    }

    const result = await run.wait();
    return assistantText || result.result || "";
  } finally {
    await agent[Symbol.asyncDispose]();
  }
}

function parseActionResult(
  raw: string,
  action: CodeActionResult["action"],
  depth: SummaryDepth
): CodeActionResult {
  const json = extractJson(raw);

  if (json) {
    const parsed = z
      .object({
        title: z.string().default(action === "edit" ? "Code edit" : "Code summary"),
        summary: z.string().default(raw),
        directAnswer: z.string().optional(),
        purpose: z.string().optional(),
        architecture: z.string().optional(),
        keyFiles: z.array(z.string()).default([]),
        changes: z.array(z.string()).optional(),
        notableRisks: z.array(z.string()).default([]),
        followUps: z.array(z.string()).default([]),
        spokenAnswer: z.string().optional(),
        polishedBy: z.string().optional()
      })
      .safeParse(json);

    if (parsed.success) {
      return { action, raw, ...parsed.data };
    }
  }

  return {
    action,
    title: action === "edit" ? "Code edit result" : `${labelDepth(depth)} summary`,
    summary: raw.trim() || "The Cursor agent returned no summary text.",
    keyFiles: [],
    changes: action === "edit" ? [] : undefined,
    notableRisks: [],
    followUps: [],
    raw
  };
}

function normalizeArgs(args: unknown) {
  if (typeof args === "string") {
    try {
      return JSON.parse(args);
    } catch {
      return {};
    }
  }
  return args && typeof args === "object" ? args : {};
}

function extractJson(raw: string) {
  const trimmed = raw.trim();
  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i)?.[1]?.trim();
  const candidate = fenced || trimmed.match(/\{[\s\S]*\}/)?.[0];
  if (!candidate) return null;

  try {
    return JSON.parse(candidate);
  } catch {
    return null;
  }
}

function labelDepth(depth: SummaryDepth) {
  return depth.charAt(0).toUpperCase() + depth.slice(1);
}
