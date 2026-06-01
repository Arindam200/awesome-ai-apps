import type { SummaryDepth } from "../shared/messages.js";
import { config } from "./config.js";

type BuildSettingsOptions = {
  target: string;
  depth: SummaryDepth;
  allowEdits: boolean;
};

export function buildDeepgramSettings(options: BuildSettingsOptions) {
  // DEMO: This Settings object wires Deepgram listen/speak with Nebius as the think model.
  return {
    type: "Settings",
    tags: ["cursor-sdk", "cursor_code_editor"],
    audio: {
      input: {
        encoding: "linear16",
        sample_rate: 24000
      },
      output: {
        encoding: "linear16",
        sample_rate: 24000,
        container: "none"
      }
    },
    agent: {
      language: "en",
      listen: {
        provider: {
          type: "deepgram",
          model: config.deepgramListenModel,
          smart_format: true
        }
      },
      think: buildDeepgramThink(options),
      speak: {
        provider: {
          type: "deepgram",
          model: config.deepgramSpeakModel
        }
      },
      greeting:
        "Hey, I am VoxCode. I am built with Cursor SDK for code work, Deepgram for voice, and Nebius for reasoning. Ask me to summarize this codebase, explain a file, or turn on edit access when you want me to change files."
    }
  };
}

export function buildDeepgramThink(options: BuildSettingsOptions) {
  return {
    provider: {
      type: "open_ai",
      model: config.nebiusModel,
      temperature: 0.2
    },
    endpoint: {
      url: config.nebiusEndpoint,
      headers: {
        authorization: `Bearer ${config.nebiusApiKey}`
      }
    },
    context_length: "max",
    prompt: buildVoiceAgentPrompt(options),
    functions: [
      // DEMO: Deepgram can call this tool only for explicit code-summary questions.
      {
        name: "summarize_code",
        description:
          "Use only when the user explicitly asks to inspect, explain, summarize, map, review, or answer a question about code in the configured workspace. Do not use for greetings, status checks, or provider-role questions.",
        parameters: {
          type: "object",
          properties: {
            target: {
              type: "string",
              description:
                "Relative path, absolute path inside the workspace, or the word workspace."
            },
            depth: {
              type: "string",
              enum: ["brief", "standard", "deep"],
              description: "How detailed the summary should be."
            },
            question: {
              type: "string",
              description: "Optional specific question to answer about the code."
            }
          },
          required: ["target", "depth"]
        }
      },
      // DEMO: Deepgram can call this tool only for concrete edit requests.
      {
        name: "edit_code",
        description:
          "Use only when the user explicitly asks for a concrete file/code change in the configured workspace. Cursor SDK applies the edit; Minimax must not claim to edit files directly.",
        parameters: {
          type: "object",
          properties: {
            target: {
              type: "string",
              description:
                "Relative path, absolute path inside the workspace, or the word workspace."
            },
            instructions: {
              type: "string",
              description:
                "Precise edit request. Include constraints, expected behavior, and tests to run if relevant."
            },
            verify: {
              type: "boolean",
              description:
                "Whether Cursor should run reasonable verification commands if it can infer them."
            }
          },
          required: ["target", "instructions"]
        }
      }
    ]
  };
}

function buildVoiceAgentPrompt(options: BuildSettingsOptions) {
  return [
    "You are the Nebius Minimax reasoning layer inside a Deepgram Voice Agent for a local coding assistant.",
    "Deepgram handles speech-to-text, function-call orchestration, and text-to-speech audio.",
    "Nebius Minimax handles conversation intent, tool routing, argument shaping, and final spoken explanation.",
    "Cursor SDK is the only component that inspects code and edits files.",
    "Your answer is sent directly to text-to-speech, so every assistant response must be plain spoken text.",
    "Use short natural sentences. Do not use visual formatting of any kind.",
    "Do not use the asterisk character, double asterisk emphasis, hash heading marks, bullet marks, numbered-list formatting, code fences, backticks, tables, raw JSON, or full file contents.",
    "Do not say formatting words like star star, hashtag, backtick, heading, bullet, or markdown unless the user is explicitly asking about those characters.",
    "After tool calls, say one or two plain sentences only. Keep detailed lists and raw code for the UI.",
    `Default target: ${options.target || "workspace"}.`,
    `Default summary depth: ${options.depth}.`,
    options.allowEdits
      ? "The user explicitly enabled edit mode for this session. You may call edit_code for clear edit requests."
      : "Edit mode is disabled. Do not call edit_code. If the user asks for an edit, politely say you do not have edit access in this session yet and they must turn on Allow file edits first.",
    "Only call summarize_code when the user explicitly asks about code, architecture, files, implementation, risks, or how the app works.",
    "Do not call summarize_code for casual conversation, status checks, greetings, or questions about whether you are listening.",
    "If the user asks what Deepgram, Nebius, or Cursor does in this app, answer from your system knowledge without calling a code tool unless they ask to inspect code.",
    "For summaries, convert natural speech into clean arguments: target, depth, and a focused question.",
    "For edits, call edit_code only when the user asks for a concrete code change. Convert speech into precise edit instructions and ask one brief clarification if unsafe or ambiguous.",
    "After a tool result, give a brief spoken answer based on spokenAnswer or directAnswer. Do not add formatting. Never claim code was inspected or changed until the function result confirms it."
  ].join("\n");
}
