import { NextRequest, NextResponse } from "next/server";
import { chat, analyzeForWorkflow, type ChatMessage } from "@/lib/nebius";
import { createActivity } from "@/lib/activity";
import { researchWeb } from "@/lib/webResearch";

const RESPONSE_FORMAT_RULES = `Response format:
1) Start with "## Answer" and give the direct answer first.
2) If this is a time-sensitive or externally verified question, include "## Sources Checked" with bullet links.
3) End with "## Optional Automation (n8n)" containing 3-6 concise steps only when automation would be useful.
4) Keep total response practical and concise; avoid generic refusal walls.`;

const DIRECT_ANSWER_PROMPT = `You are FlowSentinel AI.
Answer directly, clearly, and factually.
Do not turn every question into a workflow plan.
Do not provide long workflow-design templates unless the user explicitly asks for full workflow design.
${RESPONSE_FORMAT_RULES}`;

function isBenchmarkQuery(input: string): boolean {
  const q = input.toLowerCase();
  return (
    q.includes("benchmark") ||
    q.includes("latency") ||
    q.includes("tokens/s") ||
    q.includes("throughput") ||
    q.includes("cost per") ||
    q.includes("mmlu") ||
    q.includes("gsm8k")
  );
}

function hasFreshWebSources(
  sources: Array<{ publishedAt?: string }>,
  maxAgeDays: number
): boolean {
  const now = Date.now();
  const maxAgeMs = maxAgeDays * 24 * 60 * 60 * 1000;
  return sources.some((s) => {
    if (!s.publishedAt) return false;
    const parsed = Date.parse(s.publishedAt);
    if (Number.isNaN(parsed)) return false;
    return now - parsed <= maxAgeMs;
  });
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { messages, mode } = body as {
      messages: ChatMessage[];
      mode?: "chat" | "workflow_plan";
    };

    if (!messages?.length) {
      return NextResponse.json({ error: "messages required" }, { status: 400 });
    }

    const userMsg = messages[messages.length - 1]?.content ?? "";

    createActivity(
      "chat_message",
      { name: "User", kind: "human" },
      "Sent message",
      userMsg.slice(0, 120) + (userMsg.length > 120 ? "..." : ""),
      { fullLength: userMsg.length }
    );

    if (mode === "workflow_plan") {
      const plan = await analyzeForWorkflow(userMsg);

      createActivity(
        "ai_response",
        { name: "FlowSentinel AI", kind: "ai" },
        "Generated workflow plan",
        `${plan.suggestedSteps.length} steps — automatable: ${plan.canAutomate}`,
        { steps: plan.suggestedSteps }
      );

      return NextResponse.json({ plan });
    }

    let result;
    let webSourcesUsed = 0;

    const web = await researchWeb(userMsg);
    if (web) {
      webSourcesUsed = web.sources.length;
      const benchmarkRequest = isBenchmarkQuery(userMsg);
      const freshEnough = hasFreshWebSources(web.sources, 180);
      if (benchmarkRequest && !freshEnough) {
        const staleReply = `## Answer
I cannot provide trustworthy "recent" benchmark numbers from the currently retrieved sources because they are stale or missing publish dates for the last 6 months.

## Sources Checked
- Retrieved live sources, but none were recent enough for benchmark-grade claims.
- Please ask again with a date range (for example: "benchmarks from the last 30 days"), or run an automated benchmark workflow against provider APIs.

## Optional Automation (n8n)
1. Trigger a weekly benchmark workflow.
2. Run the same prompt set against each provider API.
3. Capture TTFT, tokens/s, and cost from real responses.
4. Save results to a sheet/database with timestamp.
5. Compare week-over-week deltas and alert on significant changes.`;
        createActivity(
          "system_event",
          { name: "Web Research", kind: "system" },
          "Rejected stale benchmark sources",
          "Blocked benchmark response due to stale/missing recent source dates",
          { source_count: web.sources.length }
        );
        result = {
          content: staleReply,
          model: "guardrail",
          usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
          latency_ms: 0,
        };
      } else {
        const groundedPrompt = `You are FlowSentinel AI. You are given live web research results for the user's question.
Use ONLY the provided sources as factual grounding for time-sensitive claims.
If data is missing, say so clearly.
Always include sources as markdown links.
${RESPONSE_FORMAT_RULES}
Today is ${new Date().toISOString().slice(0, 10)}.
Do NOT provide exact benchmark numbers (latency/tokens/sec/cost) unless those exact numbers are explicitly present in the provided source context.
If sources are stale, explicitly say the data is stale and ask the user whether to run an automation workflow for continuous tracking.

Web research context:
${web.context}`;
        result = await chat(messages, groundedPrompt);
      }

      createActivity(
        "system_event",
        { name: "Web Research", kind: "system" },
        "Fetched live web sources",
        `Sources: ${web.sources.length}`,
        { sources: web.sources.map((s) => s.url) }
      );
    } else {
      const fallbackPrompt = `${DIRECT_ANSWER_PROMPT}
Live web retrieval was unavailable in this request.
Under "## Answer", explicitly state that you cannot verify current facts right now.
Do NOT provide synthetic historical baselines as a substitute for current data.
Under "## Sources Checked", explicitly say no live sources were retrieved in this request.
If appropriate, ask the user to retry shortly.`;
      result = await chat(messages, fallbackPrompt);
    }

    if (!result) {
      result = await chat(messages, DIRECT_ANSWER_PROMPT);
    }

    createActivity(
      "ai_response",
      { name: "FlowSentinel AI", kind: "ai" },
      "Responded",
      result.content.slice(0, 120) + (result.content.length > 120 ? "..." : ""),
      {
        model: result.model,
        tokens: result.usage.total_tokens,
        latency_ms: result.latency_ms,
        web_sources: webSourcesUsed,
      }
    );

    return NextResponse.json({
      content: result.content,
      model: result.model,
      usage: result.usage,
      latency_ms: result.latency_ms,
      web_sources: webSourcesUsed,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    createActivity(
      "system_event",
      { name: "System", kind: "system" },
      "Chat error",
      message.slice(0, 200)
    );
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
