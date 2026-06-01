import path from "node:path";

import dotenv from "dotenv";

import type { ProviderInfo } from "../shared/messages.js";

const projectRoot = process.cwd();

dotenv.config({ path: path.join(projectRoot, ".env") });

export const config = {
  projectRoot,
  port: Number(process.env.PORT || 8787),
  cursorApiKey: process.env.CURSOR_API_KEY?.trim() || "",
  deepgramApiKey: process.env.DEEPGRAM_API_KEY?.trim() || "",
  nebiusApiKey: process.env.NEBIUS_API_KEY?.trim() || "",
  nebiusEndpoint:
    process.env.NEBIUS_ENDPOINT?.trim() ||
    "https://api.tokenfactory.us-central1.nebius.com/v1/chat/completions",
  nebiusModel: process.env.NEBIUS_MODEL?.trim() || "MiniMaxAI/MiniMax-M2.5",
  cursorModel: process.env.CURSOR_MODEL?.trim() || "composer-2",
  deepgramListenModel: process.env.DEEPGRAM_LISTEN_MODEL?.trim() || "nova-3",
  deepgramSpeakModel: process.env.DEEPGRAM_SPEAK_MODEL?.trim() || "aura-2-thalia-en",
  codeWorkspace: path.resolve(
    process.env.CODE_WORKSPACE?.trim() || path.resolve(projectRoot, "..")
  )
};

export function providerInfo(): ProviderInfo[] {
  return [
    {
      id: "deepgram",
      name: "Deepgram",
      role: "Speech-to-text, Voice Agent orchestration, and text-to-speech audio.",
      models: [config.deepgramListenModel, config.deepgramSpeakModel]
    },
    {
      id: "nebius",
      name: "Nebius Token Factory",
      role: "Minimax reasoning for voice intent, tool routing, prompt shaping, and response polishing.",
      models: [config.nebiusModel]
    },
    {
      id: "cursor",
      name: "Cursor SDK",
      role: "Local coding agent that inspects the workspace and applies file edits.",
      models: [config.cursorModel]
    }
  ];
}

export function missingEnv() {
  return [
    ["CURSOR_API_KEY", config.cursorApiKey],
    ["DEEPGRAM_API_KEY", config.deepgramApiKey],
    ["NEBIUS_API_KEY", config.nebiusApiKey]
  ]
    .filter(([, value]) => !value)
    .map(([name]) => name);
}
