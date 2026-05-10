import "dotenv/config";
import { Agent } from "@mastra/core/agent";
import { createTool } from "@mastra/core/tools";
import { createOpenAI } from "@ai-sdk/openai";
import { z } from "zod";
import * as readline from "node:readline/promises";

const nebius = createOpenAI({
  apiKey: process.env.NEBIUS_API_KEY,
  baseURL: "https://api.tokenfactory.nebius.com/v1/",
});

const timeTool = createTool({
  id: "get-current-time",
  description: "Return the current ISO timestamp.",
  inputSchema: z.object({}),
  outputSchema: z.object({ now: z.string() }),
  execute: async () => ({ now: new Date().toISOString() }),
});

const agent = new Agent({
  name: "nebius-starter-agent",
  instructions:
    "You are a helpful assistant. Use the get-current-time tool when the user asks about the date or time.",
  model: nebius("Qwen/Qwen3-30B-A3B"),
  tools: { timeTool },
});

async function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("🧵 Mastra starter ready. Type 'exit' to quit.\n");

  while (true) {
    const user = (await rl.question("You: ")).trim();
    if (!user) continue;
    if (["exit", "quit"].includes(user.toLowerCase())) {
      console.log("Goodbye! 👋");
      rl.close();
      break;
    }

    const response = await agent.generate(user);
    console.log(`\nAgent: ${response.text}\n`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
