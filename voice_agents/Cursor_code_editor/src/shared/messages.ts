export type SummaryDepth = "brief" | "standard" | "deep";

export type ClientStartMessage = {
  type: "start";
  target: string;
  depth: SummaryDepth;
  allowEdits: boolean;
};

export type ClientJsonMessage =
  | ClientStartMessage
  | { type: "update_settings"; target: string; depth: SummaryDepth; allowEdits: boolean }
  | { type: "stop" }
  | { type: "keepalive" };

export type ProviderInfo = {
  id: "deepgram" | "nebius" | "cursor";
  name: string;
  role: string;
  models: string[];
};

export type TimelineRole =
  | "system"
  | "user"
  | "assistant"
  | "function"
  | "error";

export type CodeActionResult = {
  action: "summarize" | "edit";
  title: string;
  summary: string;
  directAnswer?: string;
  purpose?: string;
  architecture?: string;
  keyFiles: string[];
  changes?: string[];
  notableRisks: string[];
  followUps: string[];
  spokenAnswer?: string;
  polishedBy?: string;
  raw?: string;
};

export type AppEvent = {
  source: "system" | "deepgram" | "nebius" | "cursor";
  label: string;
  detail?: string;
  level?: "info" | "warning" | "error";
  at: number;
};

export type ServerJsonMessage =
  | { type: "ready"; missingEnv: string[]; workspace: string; providers: ProviderInfo[] }
  | { type: "status"; status: string; detail?: string }
  | { type: "transcript"; role: "user" | "assistant"; text: string }
  | { type: "function"; name: string; status: "requested" | "completed" | "error"; detail?: string }
  | { type: "event"; event: AppEvent }
  | { type: "result"; result: CodeActionResult }
  | { type: "deepgram"; event: unknown }
  | { type: "error"; message: string };
