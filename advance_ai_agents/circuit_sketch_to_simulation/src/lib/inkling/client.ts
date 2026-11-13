import fs from "node:fs/promises";
import path from "node:path";
import OpenAI from "openai";

// Inkling 2 Small on Nebius Token Factory's OpenAI-compatible endpoint.
// Replay serves stored responses from fixtures/replays so tests and UI work need no network.

export type Provider = "nebius" | "replay";
export type Message = OpenAI.Chat.Completions.ChatCompletionMessageParam;
export type Tool = OpenAI.Chat.Completions.ChatCompletionFunctionTool;

export type Settings = {
  provider: Provider;
  model: string;
  baseURL: string;
  apiKey: string;
  keyName: string;
  price: { input: number; cachedInput: number; output: number } | null;
  record: boolean;
};

export function settings(env: NodeJS.ProcessEnv = process.env): Settings {
  const provider: Provider = env.INKLING_PROVIDER === "replay" ? "replay" : "nebius";
  const input = Number(env.INKLING_PRICE_INPUT);
  const output = Number(env.INKLING_PRICE_OUTPUT);
  const cached = env.INKLING_PRICE_CACHED ? Number(env.INKLING_PRICE_CACHED) : input;
  const keyName = "NEBIUS_API_KEY";
  return {
    provider,
    model: env.INKLING_MODEL || "thinkingmachines/Inkling-2-Small",
    baseURL: env.NEBIUS_BASE_URL || "https://api.tokenfactory.eu-west2.nebius.com/v1/",
    apiKey: provider === "replay" ? "" : (env[keyName] ?? ""),
    keyName,
    price: input > 0 && output > 0 ? { input, cachedInput: cached >= 0 ? cached : input, output } : null,
    record: env.INKLING_RECORD === "1",
  };
}

export type Usage = { input: number; cachedInput: number; output: number; reasoning: number };

export type Reply = {
  text: string;
  toolCalls: { name: string; arguments: string }[];
  finishReason: string | null;
  usage: Usage;
  // How long the original call took; stored with recorded replies so replays show real timings.
  ms?: number;
};

// One entry per model call, shown in the run log.
export type CallLog = {
  stage: string;
  provider: Provider;
  model: string;
  startedAt: string;
  ms: number;
  usage: Usage;
  // USD, only when prices are configured or the endpoint is free.
  cost: number | null;
  finishReason: string | null;
  error?: string;
};

export class InklingError extends Error {
  constructor(message: string, readonly kind: "config" | "provider" | "output") {
    super(message);
    this.name = "InklingError";
  }
}

const REPLAY_DIR = path.join(process.cwd(), "fixtures", "replays");

function replayFile(key: string) {
  return path.join(REPLAY_DIR, `${key.replace(/[^a-zA-Z0-9_.-]/g, "_")}.json`);
}

function costOf(s: Settings, u: Usage): number | null {
  if (!s.price) return null;
  return ((u.input - u.cachedInput) * s.price.input + u.cachedInput * s.price.cachedInput + u.output * s.price.output) / 1e6;
}

// Turn provider errors into something a person can act on.
export function explain(message: string, s: Settings) {
  if (/\b401\b|invalid api key|unauthori[sz]ed/i.test(message)) return `The provider rejected the API key. Check ${s.keyName} in .env.local. (${message})`;
  if (/\b429\b|rate limit/i.test(message)) return `The provider is rate limiting this key. Wait a minute and start the run again. (${message})`;
  if (/\b404\b|model.*not.*found|no endpoints/i.test(message)) return `The provider does not serve ${s.model}. Check INKLING_MODEL. (${message})`;
  return message;
}

type StreamUsage = {
  prompt_tokens?: number;
  completion_tokens?: number;
  prompt_tokens_details?: { cached_tokens?: number };
  completion_tokens_details?: { reasoning_tokens?: number };
};

let api: { key: string; client: OpenAI } | undefined;

function clientFor(s: Settings): OpenAI {
  if (!s.apiKey) throw new InklingError(`Set ${s.keyName} in .env.local, or use INKLING_PROVIDER=replay.`, "config");
  const key = `${s.baseURL}|${s.apiKey}`;
  if (api?.key !== key) {
    api = {
      key,
      client: new OpenAI({
        apiKey: s.apiKey,
        baseURL: s.baseURL,
        maxRetries: 1,
        timeout: 20 * 60_000,
      }),
    };
  }
  return api.client;
}

export async function ask(o: {
  stage: string;
  // Name of the stored response used in replay mode and written when recording.
  replayKey: string;
  messages: Message[];
  tools?: Tool[];
  maxTokens?: number;
  temperature?: number;
  onProgress?: (chars: number, thought: number) => void;
  settings?: Settings;
}): Promise<{ reply: Reply; log: CallLog }> {
  const s = o.settings ?? settings();
  const startedAt = new Date().toISOString();
  const t0 = Date.now();

  if (s.provider === "replay") {
    let raw: string;
    try {
      raw = await fs.readFile(replayFile(o.replayKey), "utf8");
    } catch {
      throw new InklingError(`No stored response "${o.replayKey}" in fixtures/replays.`, "config");
    }
    const reply = JSON.parse(raw) as Reply;
    return { reply, log: { stage: o.stage, provider: "replay", model: s.model, startedAt, ms: reply.ms ?? 0, usage: reply.usage, cost: costOf(s, reply.usage), finishReason: reply.finishReason } };
  }

  const client = clientFor(s);
  let text = "";
  let thought = 0;
  let finishReason: string | null = null;
  let usage: StreamUsage = {};
  const calls = new Map<number, { name: string; arguments: string }>();

  try {
    const stream = await client.chat.completions.create({
      model: s.model,
      messages: o.messages,
      tools: o.tools,
      max_tokens: o.maxTokens ?? 32_000,
      temperature: o.temperature,
      stream: true,
      stream_options: { include_usage: true },
    });
    for await (const chunk of stream) {
      if (chunk.usage) usage = chunk.usage as StreamUsage;
      const choice = chunk.choices?.[0];
      if (!choice) continue;
      if (choice.finish_reason) finishReason = choice.finish_reason;
      const delta = choice.delta;
      if (delta?.content) text += delta.content;
      // Reasoning models think before they write; count it so the UI shows the call is alive.
      const r = (delta as { reasoning_content?: string; reasoning?: string } | undefined);
      thought += (r?.reasoning_content ?? r?.reasoning ?? "").length;
      for (const tc of delta?.tool_calls ?? []) {
        const cur = calls.get(tc.index) ?? { name: "", arguments: "" };
        if (tc.function?.name) cur.name += tc.function.name;
        if (tc.function?.arguments) cur.arguments += tc.function.arguments;
        calls.set(tc.index, cur);
      }
      o.onProgress?.(text.length + [...calls.values()].reduce((n, c) => n + c.arguments.length, 0), thought);
    }
  } catch (e) {
    const message = explain(e instanceof Error ? e.message : String(e), s);
    const log: CallLog = { stage: o.stage, provider: s.provider, model: s.model, startedAt, ms: Date.now() - t0, usage: toUsage(usage), cost: null, finishReason, error: message };
    throw Object.assign(new InklingError(message, "provider"), { log });
  }

  const reply: Reply = { text, toolCalls: [...calls.values()], finishReason, usage: toUsage(usage), ms: Date.now() - t0 };
  if (s.record) {
    await fs.mkdir(REPLAY_DIR, { recursive: true });
    await fs.writeFile(replayFile(o.replayKey), JSON.stringify(reply, null, 2));
  }
  return {
    reply,
    log: { stage: o.stage, provider: s.provider, model: s.model, startedAt, ms: Date.now() - t0, usage: reply.usage, cost: costOf(s, reply.usage), finishReason },
  };
}

function toUsage(u: StreamUsage): Usage {
  return {
    input: u.prompt_tokens ?? 0,
    cachedInput: u.prompt_tokens_details?.cached_tokens ?? 0,
    output: u.completion_tokens ?? 0,
    reasoning: u.completion_tokens_details?.reasoning_tokens ?? 0,
  };
}

export function imagePart(dataUrl: string): OpenAI.Chat.Completions.ChatCompletionContentPartImage {
  return { type: "image_url", image_url: { url: dataUrl } };
}
