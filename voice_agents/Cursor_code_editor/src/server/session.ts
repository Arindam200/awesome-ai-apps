import WebSocket from "ws";

import type {
  AppEvent,
  ClientJsonMessage,
  CodeActionResult,
  ServerJsonMessage,
  SummaryDepth
} from "../shared/messages.js";
import { config, missingEnv, providerInfo } from "./config.js";
import { editCode, summarizeCode } from "./cursor-agent.js";
import { buildDeepgramSettings, buildDeepgramThink } from "./deepgram.js";
import { polishResultWithNebius } from "./nebius.js";

type FunctionCall = {
  id?: string;
  name?: string;
  arguments?: unknown;
  client_side?: boolean;
};

type SessionOptions = {
  browser: WebSocket;
};

export class VoiceSession {
  private deepgram: WebSocket | null = null;
  private keepAlive: NodeJS.Timeout | null = null;
  private started = false;
  private allowEdits = false;
  private target = "workspace";
  private depth: SummaryDepth = "standard";
  private lastAudioDoneEventAt = 0;
  private pendingEditAccessPrompt = false;

  constructor(private readonly options: SessionOptions) {}

  handleBrowserMessage(data: WebSocket.RawData, isBinary: boolean) {
    if (isBinary) {
      if (this.deepgram?.readyState === WebSocket.OPEN) {
        this.deepgram.send(data);
      }
      return;
    }

    const message = parseClientMessage(data.toString());
    if (!message) return;

    if (message.type === "start") {
      void this.start(message);
      return;
    }

    if (message.type === "stop") {
      this.close();
      return;
    }

    if (message.type === "update_settings") {
      this.updateSessionSettings(message);
      return;
    }
  }

  close() {
    if (this.keepAlive) {
      clearInterval(this.keepAlive);
      this.keepAlive = null;
    }

    if (this.deepgram) {
      this.deepgram.close();
      this.deepgram = null;
    }
  }

  private async start(message: Extract<ClientJsonMessage, { type: "start" }>) {
    if (this.started) return;
    this.started = true;
    this.target = message.target || "workspace";
    this.depth = message.depth;
    this.allowEdits = message.allowEdits;

    const missing = missingEnv();
    if (missing.length > 0) {
      this.sendJson({
        type: "error",
        message: `Missing required env vars: ${missing.join(", ")}. Nebius powers the Voice Agent think step, so NEBIUS_API_KEY is required for voice sessions.`
      });
      return;
    }

    this.sendEvent("system", "Voice session starting", `Target: ${this.target}; depth: ${this.depth}; edits: ${this.allowEdits ? "enabled" : "disabled"}`);
    this.sendJson({ type: "status", status: "connecting", detail: "Opening Deepgram Voice Agent" });
    this.deepgram = new WebSocket("wss://agent.deepgram.com/v1/agent/converse", {
      headers: {
        Authorization: `Token ${config.deepgramApiKey}`
      }
    });

    this.deepgram.on("open", () => {
      this.sendJson({ type: "status", status: "connected", detail: "Deepgram connected" });
      this.sendEvent(
        "deepgram",
        "Settings sent",
        `${config.deepgramListenModel} listen, ${config.deepgramSpeakModel} speak, Nebius ${config.nebiusModel} think`
      );
      this.deepgram?.send(
        JSON.stringify(
          buildDeepgramSettings({
            target: this.target,
            depth: this.depth,
            allowEdits: this.allowEdits
          })
        )
      );
      this.keepAlive = setInterval(() => {
        if (this.deepgram?.readyState === WebSocket.OPEN) {
          this.deepgram.send(JSON.stringify({ type: "KeepAlive" }));
        }
      }, 5000);
    });

    this.deepgram.on("message", (data, isBinary) => {
      if (isBinary) {
        this.options.browser.send(data, { binary: true });
        return;
      }
      void this.handleDeepgramJson(data.toString());
    });

    this.deepgram.on("error", (error) => {
      this.sendJson({ type: "error", message: error.message });
    });

    this.deepgram.on("close", () => {
      this.sendJson({ type: "status", status: "closed", detail: "Deepgram connection closed" });
    });
  }

  private updateSessionSettings(message: Extract<ClientJsonMessage, { type: "update_settings" }>) {
    const previousAllowEdits = this.allowEdits;
    this.target = message.target || "workspace";
    this.depth = message.depth;
    this.allowEdits = message.allowEdits;

    this.sendEvent(
      "system",
      "Session settings updated",
      `Target: ${this.target}; depth: ${this.depth}; edits: ${this.allowEdits ? "enabled" : "disabled"}`
    );

    if (previousAllowEdits !== this.allowEdits) {
      this.pendingEditAccessPrompt = this.allowEdits;
      this.sendJson({
        type: "status",
        status: this.allowEdits ? "edit access enabled" : "edit access disabled",
        detail: this.allowEdits
          ? "Edit access is now enabled for this voice session."
          : "Edit access is now disabled for this voice session."
      });
    }

    if (this.deepgram?.readyState === WebSocket.OPEN) {
      this.deepgram.send(
        JSON.stringify({
          type: "UpdateThink",
          think: buildDeepgramThink({
            target: this.target,
            depth: this.depth,
            allowEdits: this.allowEdits
          })
        })
      );
      this.sendEvent("deepgram", "Think update sent", "Refreshed Nebius prompt and tool config for the live voice session.");
    }
  }

  private async handleDeepgramJson(raw: string) {
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      this.sendJson({ type: "deepgram", event: raw });
      return;
    }

    this.forwardUsefulEvent(event);

    if (event.type !== "FunctionCallRequest" || !Array.isArray(event.functions)) {
      return;
    }

    for (const call of event.functions as FunctionCall[]) {
      await this.handleFunctionCall(call);
    }
  }

  private async handleFunctionCall(call: FunctionCall) {
    // DEMO: This is the bridge from Deepgram FunctionCallRequest to Cursor SDK.
    const name = call.name || "unknown";
    this.sendJson({ type: "function", name, status: "requested" });

    try {
      if (call.client_side === false) {
        this.sendJson({ type: "function", name, status: "completed", detail: "Handled by Deepgram" });
        return;
      }

      if (name === "summarize_code") {
        this.sendEvent("nebius", "Tool routed", "Minimax selected summarize_code and shaped the Cursor arguments.");
        this.sendEvent("cursor", "Summary run started", stringifyDetail(call.arguments));
        const cursorResult = await summarizeCode(call.arguments);
        this.sendEvent("cursor", "Summary run completed", cursorResult.title);
        const result = cleanResultForUi(await this.polish(cursorResult, name, call.arguments));
        this.deepgram?.send(
          JSON.stringify({
            type: "FunctionCallResponse",
            id: call.id,
            name,
            content: voiceResponseContent(result)
          })
        );
        this.sendJson({ type: "result", result });
        this.sendJson({ type: "function", name, status: "completed" });
        return;
      }

      if (name === "edit_code") {
        if (!this.allowEdits) {
          const refusal = cleanResultForUi({
            action: "edit" as const,
            title: "Edit access required",
            summary: "The app did not change any files because Allow file edits is turned off for this voice session.",
            spokenAnswer: "Sorry, I do not have edit access in this session yet. Turn on Allow file edits and ask me again when you are ready.",
            keyFiles: [],
            changes: [],
            notableRisks: ["Cursor SDK can modify files only after the session has explicit edit access."],
            followUps: ["Turn on Allow file edits and repeat the edit request."]
          });
          this.deepgram?.send(
            JSON.stringify({
              type: "FunctionCallResponse",
              id: call.id,
              name,
              content: voiceResponseContent(refusal)
            })
          );
          this.sendJson({ type: "result", result: refusal });
          this.sendJson({ type: "function", name, status: "completed" });
          return;
        }

        this.sendEvent("nebius", "Tool routed", "Minimax selected edit_code and shaped the Cursor edit request.");
        this.sendEvent("cursor", "Edit run started", stringifyDetail(call.arguments));
        const cursorResult = await editCode(call.arguments);
        this.sendEvent("cursor", "Edit run completed", cursorResult.title);
        const result = cleanResultForUi(await this.polish(cursorResult, name, call.arguments));
        this.deepgram?.send(
          JSON.stringify({
            type: "FunctionCallResponse",
            id: call.id,
            name,
            content: voiceResponseContent(result)
          })
        );
        this.sendJson({ type: "result", result });
        this.sendJson({ type: "function", name, status: "completed" });
        return;
      }

      throw new Error(`Unknown function: ${name}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.deepgram?.send(
        JSON.stringify({
          type: "FunctionCallResponse",
          id: call.id,
          name,
          content: plainSpeech(`The tool failed: ${message}`)
        })
      );
      this.sendJson({ type: "function", name, status: "error", detail: message });
      this.sendEvent("system", "Function failed", message, "error");
      this.sendJson({ type: "error", message });
    }
  }

  private async polish(result: CodeActionResult, toolName: string, toolArguments: unknown) {
    try {
      this.sendEvent("nebius", "Polishing Cursor result", config.nebiusModel);
      const polished = await polishResultWithNebius(result, { toolName, toolArguments });
      this.sendEvent("nebius", "Polish completed", polished.spokenAnswer || polished.summary);
      return polished;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.sendEvent("nebius", "Polish failed; using Cursor result", message, "warning");
      return result;
    }
  }

  private forwardUsefulEvent(event: Record<string, unknown>) {
    const type = String(event.type || "");

    if (type === "ConversationText") {
      const role = event.role === "assistant" ? "assistant" : "user";
      const text = typeof event.content === "string" ? event.content : "";
      if (text) this.sendJson({ type: "transcript", role, text });
    }

    if (["Welcome", "SettingsApplied", "AgentThinking", "AgentStartedSpeaking", "AgentAudioDone", "UserStartedSpeaking", "ThinkUpdated"].includes(type)) {
      this.sendJson({ type: "status", status: type });
      if (type === "AgentAudioDone") {
        const now = Date.now();
        if (now - this.lastAudioDoneEventAt < 2500) return;
        this.lastAudioDoneEventAt = now;
        if (this.pendingEditAccessPrompt) {
          setTimeout(() => this.injectEditAccessFollowUp(), 300);
        }
      }
      if (type === "ThinkUpdated" && this.pendingEditAccessPrompt) {
        this.injectEditAccessFollowUp();
      }
      this.sendEvent("deepgram", type);
      return;
    }

    if (type === "InjectionRefused") {
      const message = typeof event.message === "string" ? event.message : "Deepgram refused an injected follow-up.";
      this.pendingEditAccessPrompt = this.allowEdits;
      this.sendEvent("deepgram", "Injection refused", message, "warning");
      return;
    }

    if (type === "Error") {
      this.sendJson({
        type: "error",
        message: typeof event.message === "string" ? event.message : JSON.stringify(event)
      });
      return;
    }

    if (type === "Warning") {
      this.sendJson({ type: "deepgram", event });
    }
  }

  private sendJson(message: ServerJsonMessage) {
    if (this.options.browser.readyState === WebSocket.OPEN) {
      this.options.browser.send(JSON.stringify(message));
    }
  }

  private injectEditAccessFollowUp() {
    if (!this.pendingEditAccessPrompt || this.deepgram?.readyState !== WebSocket.OPEN) return;
    this.pendingEditAccessPrompt = false;
    this.deepgram.send(
      JSON.stringify({
        type: "InjectAgentMessage",
        message: "Edit access is enabled now. Tell me the exact change you want me to make.",
        behavior: "default"
      })
    );
    this.sendEvent("deepgram", "Edit access follow-up injected", "Asked the user to continue the edit request.");
  }

  private sendEvent(
    source: AppEvent["source"],
    label: string,
    detail?: string,
    level: AppEvent["level"] = "info"
  ) {
    this.sendJson({
      type: "event",
      event: {
        source,
        label,
        detail,
        level,
        at: Date.now()
      }
    });
  }
}

function voiceResponseContent(result: Partial<CodeActionResult>) {
  // DEMO: Keep FunctionCallResponse content short so Deepgram has plain speech to say aloud.
  const spoken = result.spokenAnswer || result.directAnswer || result.summary || result.title || "The code tool finished.";
  return plainSpeech(spoken);
}

function plainSpeech(text: string) {
  return text
    .replace(/\\([*_`#~>])/g, "$1")
    .replace(/```[\s\S]*?```/g, "code omitted")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+[.)]\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/[*_~>#|]/g, "")
    .replace(/\bstar\s+star\b/gi, "")
    .replace(/\bhash\s+hash\b/gi, "")
    .replace(/\bbacktick\b/gi, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 420);
}

function cleanResultForUi(result: CodeActionResult): CodeActionResult {
  return {
    ...result,
    title: cleanUiText(result.title),
    summary: cleanUiText(result.summary),
    directAnswer: result.directAnswer ? cleanUiText(result.directAnswer) : undefined,
    purpose: result.purpose ? cleanUiText(result.purpose) : undefined,
    architecture: result.architecture ? cleanUiText(result.architecture) : undefined,
    spokenAnswer: result.spokenAnswer ? plainSpeech(result.spokenAnswer) : undefined,
    keyFiles: result.keyFiles.map(cleanUiText),
    changes: result.changes?.map(cleanUiText),
    notableRisks: result.notableRisks.map(cleanUiText),
    followUps: result.followUps.map(cleanUiText)
  };
}

function cleanUiText(text: string) {
  return text
    .replace(/\\([*_`#~>])/g, "$1")
    .replace(/```[\s\S]*?```/g, "code block omitted")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}

function parseClientMessage(raw: string): ClientJsonMessage | null {
  try {
    const value = JSON.parse(raw) as ClientJsonMessage;
    return value && typeof value === "object" && "type" in value ? value : null;
  } catch {
    return null;
  }
}

export function readyMessage(workspace: string): Extract<ServerJsonMessage, { type: "ready" }> {
  return {
    type: "ready",
    missingEnv: missingEnv(),
    workspace,
    providers: providerInfo()
  };
}

function stringifyDetail(value: unknown) {
  if (!value) return undefined;
  return typeof value === "string" ? value : JSON.stringify(value);
}
