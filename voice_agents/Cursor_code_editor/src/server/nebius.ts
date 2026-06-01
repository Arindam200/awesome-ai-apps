import { z } from "zod";

import type { CodeActionResult } from "../shared/messages.js";
import { config } from "./config.js";

const polishedSchema = z.object({
  title: z.string().optional(),
  summary: z.string().optional(),
  directAnswer: z.string().optional(),
  purpose: z.string().optional(),
  architecture: z.string().optional(),
  spokenAnswer: z.string().optional(),
  keyFiles: z.array(z.string()).optional(),
  changes: z.array(z.string()).optional(),
  notableRisks: z.array(z.string()).optional(),
  followUps: z.array(z.string()).optional()
});

export async function polishResultWithNebius(
  result: CodeActionResult,
  context: { toolName: string; toolArguments?: unknown }
): Promise<CodeActionResult> {
  // DEMO: Nebius/Minimax turns raw Cursor output into voice-safe and UI-friendly text.
  const content = await callNebius([
    {
      role: "system",
      content: [
        "You are Nebius Minimax polishing a Cursor SDK code-agent result for a voice UI.",
        "Cursor already inspected or edited the code. Do not claim Minimax edited files.",
        "Do not invent files, risks, or changes. Preserve important technical details.",
        "Return JSON only with: title, directAnswer, purpose, architecture, summary, spokenAnswer, keyFiles, changes, notableRisks, followUps.",
        "directAnswer answers the user's request first. purpose explains what the target does. architecture explains moving parts and flow.",
        "summary is for the UI and should be concise, structured, and readable.",
        "spokenAnswer is one or two short plain-English sentences for text-to-speech.",
        "spokenAnswer must be plain speech only. Do not use markdown, bullets, code fences, raw JSON, file contents, asterisks, hashes, backticks, or formatting words like star star.",
        "If files changed, spokenAnswer should summarize what changed and ask for the next decision only when useful."
      ].join(" ")
    },
    {
      role: "user",
      content: JSON.stringify({
        context,
        providerRoles: {
          deepgram: "speech-to-text, Voice Agent orchestration, and text-to-speech",
          nebius: "voice reasoning, tool routing, prompt shaping, and result polishing",
          cursor: "codebase inspection and file edits"
        },
        cursorResult: result
      })
    }
  ]);

  const json = extractJson(content);
  const parsed = polishedSchema.safeParse(json);
  if (!parsed.success) {
    return {
      ...result,
      polishedBy: "Nebius Minimax attempted polishing, but the original Cursor result was used."
    };
  }

  return {
    ...result,
    ...parsed.data,
    action: result.action,
    changes: result.changes ? parsed.data.changes || result.changes : parsed.data.changes,
    raw: result.raw,
    polishedBy: config.nebiusModel
  };
}

export async function createChatTitleWithNebius(firstUserMessage: string): Promise<string> {
  // DEMO: Saved voice sessions get short local titles from the same Nebius endpoint.
  const fallback = fallbackTitle(firstUserMessage);
  const content = await callNebius([
    {
      role: "system",
      content:
        "You write labels for saved voice coding chats. Output only a 3 to 6 word noun-phrase title. Do not answer the user's request. No quotes. No punctuation."
    },
    {
      role: "user",
      content: `User request: ${firstUserMessage}\nChat title:`
    }
  ]);

  return cleanTitle(content, fallback);
}

async function callNebius(messages: Array<{ role: "system" | "user"; content: string }>) {
  // DEMO: Token Factory is used as an OpenAI-compatible chat-completions endpoint.
  const response = await fetch(config.nebiusEndpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${config.nebiusApiKey}`
    },
    body: JSON.stringify({
      model: config.nebiusModel,
      messages,
      temperature: 0.2
    })
  });

  if (!response.ok) {
    throw new Error(`Nebius request failed: ${response.status} ${await response.text()}`);
  }

  const data = (await response.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  return data.choices?.[0]?.message?.content?.trim() || "";
}

function cleanTitle(raw: string, fallback: string) {
  const cleaned = raw
    .replace(/^["']|["']$/g, "")
    .replace(/[.?!:;]+$/g, "")
    .trim();
  const words = cleaned.split(/\s+/).filter(Boolean);
  if (
    words.length < 2 ||
    words.length > 8 ||
    /\b(happy|help|sure|certainly|request|user)\b/i.test(cleaned)
  ) {
    return fallback;
  }
  return cleaned.slice(0, 60);
}

function fallbackTitle(text: string) {
  const stopwords = new Set(["the", "a", "an", "to", "me", "please", "can", "you", "this"]);
  const words = text
    .replace(/[^\w\s/-]/g, " ")
    .split(/\s+/)
    .filter((word) => word && !stopwords.has(word.toLowerCase()))
    .slice(0, 5);
  return words.join(" ") || "Voice coding chat";
}

function extractJson(raw: string) {
  const trimmed = raw.trim();
  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i)?.[1]?.trim();
  const candidate = fenced || trimmed.match(/\{[\s\S]*\}/)?.[0];
  if (!candidate) return null;

  try {
    return JSON.parse(candidate) as unknown;
  } catch {
    return null;
  }
}
