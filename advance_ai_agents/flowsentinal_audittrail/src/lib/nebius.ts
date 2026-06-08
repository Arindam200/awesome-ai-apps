import OpenAI from "openai";

const MODEL_SELECTOR = process.env.NEBIUS_MODEL?.trim() || "nemotron super";

let _client: OpenAI | null = null;
let _resolvedModel: string | null = null;

function getClient(): OpenAI {
  if (!_client) {
    const apiKey = process.env.NEBIUS_API_KEY?.trim();
    if (!apiKey) {
      throw new Error(
        "NEBIUS_API_KEY is missing or empty. Add it to .env.local and restart the dev server."
      );
    }

    _client = new OpenAI({
      baseURL: "https://api.tokenfactory.nebius.com/v1/",
      apiKey,
    });
  }
  return _client;
}

function tokenizeSelector(selector: string): string[] {
  return selector
    .toLowerCase()
    .replace(/[\/_\-.]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

async function resolveModel(client: OpenAI): Promise<string> {
  if (_resolvedModel) return _resolvedModel;

  const selector = MODEL_SELECTOR;

  // If user provides a fully-qualified model id, use it directly.
  if (selector.includes("/")) {
    _resolvedModel = selector;
    return _resolvedModel;
  }

  const list = await client.models.list();
  const models = list.data ?? [];
  const selectorTokens = tokenizeSelector(selector);

  const preferred = models.find((m) => {
    const haystack = `${m.id}`.toLowerCase();
    return selectorTokens.every((t) => haystack.includes(t));
  });

  if (preferred?.id) {
    _resolvedModel = preferred.id;
    return _resolvedModel;
  }

  const sample = models.slice(0, 6).map((m) => m.id).join(", ");
  throw new Error(
    `No model matched "${selector}". Set NEBIUS_MODEL to a valid Nebius model ID from /v1/models. Example available models: ${sample}`
  );
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface NebiusResponse {
  content: string;
  model: string;
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  latency_ms: number;
}

function stripThinking(text: string): string {
  let cleaned = text.replace(/<think>[\s\S]*?<\/think>/g, "");
  cleaned = cleaned.replace(/<think>[\s\S]*/g, "");
  return cleaned.trim();
}

const SYSTEM_PROMPT = `You are FlowSentinel AI — an intelligent assistant embedded in a workflow command center.
Answer the user's question directly and accurately.

Rules:
- Prefer a concise direct answer first.
- Do not turn every question into a workflow plan.
- Mention n8n/Velt workflow suggestions only when the user explicitly asks for automation, workflow design, or implementation steps.
- For time-sensitive questions, clearly distinguish confirmed facts from unknowns.

Format responses in clean markdown.`;

export async function chat(
  messages: ChatMessage[],
  systemOverride?: string
): Promise<NebiusResponse> {
  const client = getClient();
  const model = await resolveModel(client);
  const start = Date.now();

  let completion;
  try {
    completion = await client.chat.completions.create({
      model,
      max_tokens: 4096,
      messages: [
        { role: "system", content: systemOverride ?? SYSTEM_PROMPT },
        ...messages,
      ],
    });
  } catch (err) {
    if (err instanceof OpenAI.APIError && err.status === 404) {
      throw new Error(
        `Model "${model}" returned 404 from Nebius. Set NEBIUS_MODEL to an enabled model ID from https://api.tokenfactory.nebius.com/v1/models (for example, a Nemotron Super model visible in your account).`
      );
    }
    throw err;
  }

  const raw = completion.choices[0]?.message?.content ?? "";
  const content = stripThinking(raw);

  return {
    content,
    model,
    usage: {
      prompt_tokens: completion.usage?.prompt_tokens ?? 0,
      completion_tokens: completion.usage?.completion_tokens ?? 0,
      total_tokens: completion.usage?.total_tokens ?? 0,
    },
    latency_ms: Date.now() - start,
  };
}

export async function analyzeForWorkflow(query: string): Promise<{
  analysis: string;
  suggestedSteps: string[];
  canAutomate: boolean;
}> {
  const result = await chat(
    [{ role: "user", content: query }],
    `You are an AI workflow planner. Given a user request, respond with EXACTLY this JSON format (no markdown fences):
{
  "analysis": "Brief analysis of what needs to happen",
  "suggestedSteps": ["Step 1 description", "Step 2 description", ...],
  "canAutomate": true/false
}
Be specific about each step.
Prefer n8n-compatible steps (Webhook, HTTP Request, Function, IF, Respond to Webhook, Schedule Trigger, etc.).
Mention Velt logging checkpoints in the analysis when relevant.
Keep the analysis under 2 sentences.`
  );

  try {
    const jsonMatch = result.content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
  } catch {
    // Fall through to default
  }

  return {
    analysis: result.content,
    suggestedSteps: ["Analyze input", "Process with AI", "Generate output"],
    canAutomate: true,
  };
}
