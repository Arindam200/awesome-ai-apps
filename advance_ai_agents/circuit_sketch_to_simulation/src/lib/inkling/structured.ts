import { jsonrepair } from "jsonrepair";
import type { z } from "zod";
import { ask, InklingError, type CallLog, type Message, type Tool } from "./client";

// The prompt asks for the tool call without forcing it with tool_choice. If the model answers in
// text instead, this falls back to JSON in the text.
// A result that fails the schema gets one repair turn with the exact errors.

export function extractJson(text: string): unknown {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  const body = fenced ? fenced[1] : text;
  const start = body.indexOf("{");
  const end = body.lastIndexOf("}");
  if (start < 0 || end <= start) throw new Error("no JSON object in the reply");
  return JSON.parse(jsonrepair(body.slice(start, end + 1)));
}

function parseArgs(args: string): unknown {
  try {
    return JSON.parse(args);
  } catch {
    return JSON.parse(jsonrepair(args));
  }
}

export type Via = "tool" | "text";

export async function askStructured<S extends z.ZodType>(o: {
  stage: string;
  replayKey: string;
  messages: Message[];
  tool: Tool;
  schema: S;
  maxTokens?: number;
  onProgress?: (chars: number, thought: number) => void;
}): Promise<{ value: z.infer<S>; via: Via; repaired: boolean; raw: string; logs: CallLog[] }> {
  const logs: CallLog[] = [];
  const name = o.tool.function.name;
  let messages = o.messages;

  for (let attempt = 0; attempt < 2; attempt++) {
    const { reply, log } = await ask({
      stage: attempt ? `${o.stage} (repair)` : o.stage,
      replayKey: attempt ? `${o.replayKey}-repair` : o.replayKey,
      messages,
      tools: [o.tool],
      maxTokens: o.maxTokens,
      onProgress: o.onProgress,
    });
    logs.push(log);

    const call = reply.toolCalls.find((c) => c.name === name) ?? reply.toolCalls[0];
    let candidate: unknown;
    let via: Via = "tool";
    let raw = call?.arguments ?? reply.text;
    let problem = "";
    try {
      if (call) candidate = parseArgs(call.arguments);
      else {
        via = "text";
        candidate = extractJson(reply.text);
      }
    } catch (e) {
      problem = `The reply was not valid JSON (${e instanceof Error ? e.message : e}).`;
    }

    if (!problem) {
      const parsed = o.schema.safeParse(candidate);
      if (parsed.success) return { value: parsed.data, via, repaired: attempt > 0, raw, logs };
      problem = parsed.error.issues.slice(0, 12).map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`).join("\n");
    }

    raw = raw.slice(0, 20_000);
    messages = [
      ...o.messages,
      { role: "assistant", content: raw },
      { role: "user", content: `That did not match the ${name} schema:\n${problem}\nCall ${name} again with the complete, corrected object.` },
    ];
  }
  throw Object.assign(new InklingError(`The ${o.stage} output did not match the schema after one repair.`, "output"), { logs });
}
