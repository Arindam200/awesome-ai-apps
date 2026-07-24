import { APAHttpClient, type APAClientError } from "./http/client.js";
import { resolveApiBase, requireArg } from "./utils/config.js";
import { defaultCredentialPath, loadCredential, saveCredential } from "./loop/credentials.js";
import { loadDecisionState, saveDecisionState } from "./loop/decision_state.js";
import { TurnTracker } from "./loop/state.js";
import { buildCredentialFromRegisterResult } from "./commands/register.js";
import { recoverSessionFromConflict, resolveStreamURL } from "./commands/session_recovery.js";

type ArgMap = Record<string, string | boolean>;

function parseArgs(argv: string[]): { command: string; args: ArgMap } {
  const [command = "help", ...rest] = argv;
  const args: ArgMap = {};
  for (let i = 0; i < rest.length; i += 1) {
    const token = rest[i];
    if (!token.startsWith("--")) {
      continue;
    }
    const key = token.slice(2);
    const next = rest[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
      continue;
    }
    args[key] = next;
    i += 1;
  }
  return { command, args };
}

function readString(args: ArgMap, key: string, envKey?: string): string | undefined {
  const fromArg = args[key];
  if (typeof fromArg === "string") {
    return fromArg;
  }
  if (envKey) {
    return process.env[envKey];
  }
  return undefined;
}

function readNumber(args: ArgMap, key: string, fallback?: number): number {
  const raw = args[key];
  if (raw === undefined && fallback !== undefined) {
    return fallback;
  }
  if (typeof raw !== "string") {
    throw new Error(`missing --${key}`);
  }
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new Error(`invalid --${key}`);
  }
  return value;
}

function printHelp(): void {
  console.log(`apa-bot commands:
  apa-bot register --name <name> --description <desc> [--api-base <url>]
  apa-bot claim (--claim-code <code> | --claim-url <url>) [--api-base <url>]
  apa-bot me [--api-base <url>]
  apa-bot bind-key --provider <openrouter|nebius> --vendor-key <key> --budget-usd <num> [--api-base <url>]
  apa-bot next-decision --join <random|select> [--room-id <id>]
                       [--timeout-ms <ms>] [--api-base <url>]
  apa-bot submit-decision --decision-id <id> --action <fold|check|call|raise|bet>
                          [--amount <num>] [--thought-log <text>] [--api-base <url>]
  apa-bot doctor [--api-base <url>]

Config priority: CLI args > env (API_BASE) > defaults.`);
}

async function requireApiKey(apiBase: string): Promise<string> {
  const cached = await loadCredential(apiBase, undefined);
  if (!cached?.api_key) {
    const path = defaultCredentialPath();
    throw new Error(`api_key_not_found for api_base=${apiBase} (run apa-bot register). path=${path}`);
  }
  return cached.api_key;
}

function claimCodeFromUrl(raw: string): string {
  try {
    const url = new URL(raw);
    const parts = url.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1] || "";
  } catch {
    return "";
  }
}

type SseEvent = {
  id: string;
  event: string;
  data: string;
};

function emit(message: Record<string, unknown>): void {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function toErrorPayload(err: unknown): Record<string, unknown> {
  const apiErr = err as APAClientError;
  const code = apiErr?.code || "cli_error";
  const message = err instanceof Error ? err.message : String(err);
  return {
    type: "error",
    error: code,
    message
  };
}

type PendingDecision = NonNullable<Awaited<ReturnType<typeof loadDecisionState>>["pending_decision"]>;

function readLegalActions(state: Record<string, unknown>): string[] {
  const raw = state["legal_actions"];
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw as string[];
}

type ParsedActionConstraints = {
  bet?: { min: number; max: number };
  raise?: { min_to: number; max_to: number };
};

function readActionConstraints(state: Record<string, unknown>): ParsedActionConstraints | undefined {
  const raw = state["action_constraints"];
  if (!raw || typeof raw !== "object") {
    return undefined;
  }
  const src = raw as Record<string, unknown>;
  const out: ParsedActionConstraints = {};
  const bet = src["bet"];
  if (bet && typeof bet === "object") {
    const b = bet as Record<string, unknown>;
    const min = Number(b["min"]);
    const max = Number(b["max"]);
    if (Number.isFinite(min) && Number.isFinite(max)) {
      out.bet = { min, max };
    }
  }
  const raise = src["raise"];
  if (raise && typeof raise === "object") {
    const r = raise as Record<string, unknown>;
    const minTo = Number(r["min_to"]);
    const maxTo = Number(r["max_to"]);
    if (Number.isFinite(minTo) && Number.isFinite(maxTo)) {
      out.raise = { min_to: minTo, max_to: maxTo };
    }
  }
  if (!out.bet && !out.raise) {
    return undefined;
  }
  return out;
}

function parseAction(raw: string): "fold" | "check" | "call" | "raise" | "bet" {
  if (raw === "fold" || raw === "check" || raw === "call" || raw === "raise" || raw === "bet") {
    return raw;
  }
  throw new Error("invalid --action");
}


async function parseSSEOnce(
  url: string,
  lastEventId: string,
  timeoutMs: number,
  onEvent: (evt: SseEvent) => Promise<boolean>
): Promise<string> {
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (lastEventId) {
    headers["Last-Event-ID"] = lastEventId;
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let latestId = lastEventId;
  let buffer = "";
  let currentId = "";
  let currentEvent = "";
  let currentData = "";

  try {
    const res = await fetch(url, { method: "GET", headers, signal: controller.signal });
    if (!res.ok || !res.body) {
      throw new Error(`stream_open_failed_${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        if (line.startsWith("id:")) {
          currentId = line.slice(3).trim();
          continue;
        }
        if (line.startsWith("event:")) {
          currentEvent = line.slice(6).trim();
          continue;
        }
        if (line.startsWith("data:")) {
          const piece = line.slice(5).trimStart();
          currentData = currentData ? `${currentData}\n${piece}` : piece;
          continue;
        }
        if (line !== "") {
          continue;
        }
        if (!currentData) {
          currentId = "";
          currentEvent = "";
          continue;
        }
        const evt: SseEvent = {
          id: currentId,
          event: currentEvent,
          data: currentData
        };
        if (evt.id) latestId = evt.id;
        const shouldStop = await onEvent(evt);
        currentId = "";
        currentEvent = "";
        currentData = "";
        if (shouldStop) {
          controller.abort();
          break;
        }
      }
    }
  } catch (err) {
    if (!(err instanceof Error && err.name === "AbortError")) {
      throw err;
    }
  } finally {
    clearTimeout(timeout);
  }
  return latestId;
}

function pickRoom(
  rooms: Array<{ id: string; min_buyin_cc: number; name?: string }>,
  joinMode: "random" | "select",
  roomId?: string
): { id: string; min_buyin_cc: number } {
  if (rooms.length === 0) {
    throw new Error("no_rooms_available");
  }
  if (joinMode === "select") {
    const match = rooms.find((room) => room.id === roomId);
    if (!match) {
      throw new Error("room_not_found");
    }
    return { id: match.id, min_buyin_cc: match.min_buyin_cc };
  }
  const sorted = [...rooms].sort((a, b) => a.min_buyin_cc - b.min_buyin_cc);
  return { id: sorted[0].id, min_buyin_cc: sorted[0].min_buyin_cc };
}

async function sessionExists(apiBase: string, sessionId: string): Promise<boolean> {
  const res = await fetch(`${apiBase}/agent/sessions/${sessionId}/state`);
  return res.ok;
}

async function ensureSession(
  client: APAHttpClient,
  apiBase: string,
  agentId: string,
  apiKey: string,
  joinMode: "random" | "select",
  roomId?: string
): Promise<{ session_id: string; stream_url: string }> {
  const cachedState = await loadDecisionState();
  if (cachedState.session_id && cachedState.stream_url) {
    const ok = await sessionExists(apiBase, cachedState.session_id);
    if (ok) {
      return { session_id: cachedState.session_id, stream_url: cachedState.stream_url };
    }
  }

  const me = await client.getAgentMe(apiKey);
  if (me?.status === "pending") {
    emit({ type: "claim_required", message: "agent is pending; complete claim before starting" });
    throw new Error("agent_pending");
  }
  const balance = Number(me?.balance_cc ?? 0);
  const rooms = await client.listPublicRooms();
  if (joinMode === "select") {
    const pickedRoom = pickRoom(rooms.items || [], joinMode, roomId);
    if (balance < pickedRoom.min_buyin_cc) {
      throw new Error(`insufficient_balance (balance=${balance}, min=${pickedRoom.min_buyin_cc})`);
    }
  } else {
    const lowestRoom = pickRoom(rooms.items || [], "random");
    if (balance < lowestRoom.min_buyin_cc) {
      throw new Error(`insufficient_balance (balance=${balance}, min=${lowestRoom.min_buyin_cc})`);
    }
  }
  const sessionInput =
    joinMode === "select"
      ? { agentID: agentId, apiKey, joinMode: "select" as const, roomID: roomId }
      : { agentID: agentId, apiKey, joinMode: "random" as const };
  const session = await client.createSession(sessionInput).catch(async (err: unknown) => {
    const recovered = recoverSessionFromConflict(err, apiBase);
    if (!recovered) {
      throw err;
    }
    await saveDecisionState({
      session_id: recovered.session_id,
      stream_url: recovered.stream_url,
      last_event_id: "",
      last_turn_id: ""
    });
    return {
      session_id: recovered.session_id,
      stream_url: recovered.stream_url
    };
  });
  const sessionId = String(session.session_id || "");
  const streamURL = String(session.stream_url || "");
  const resolvedStreamURL = resolveStreamURL(apiBase, streamURL);
  await saveDecisionState({
    session_id: sessionId,
    stream_url: resolvedStreamURL,
    last_event_id: "",
    last_turn_id: ""
  });
  return { session_id: sessionId, stream_url: resolvedStreamURL };
}

async function runNextDecision(args: ArgMap): Promise<void> {
  const apiBase = resolveApiBase(readString(args, "api-base", "API_BASE"));
  const joinRaw = requireArg("--join", readString(args, "join"));
  const joinMode = joinRaw === "select" ? "select" : "random";
  const roomId = joinMode === "select" ? requireArg("--room-id", readString(args, "room-id")) : undefined;
  const timeoutMs = readNumber(args, "timeout-ms", 5000);

  const client = new APAHttpClient({ apiBase });
  const cached = await loadCredential(apiBase, undefined);
  if (!cached) {
    throw new Error("credential_not_found (run apa-bot register first)");
  }
  const agentId = cached.agent_id;
  const apiKey = cached.api_key;

  const { session_id: sessionId, stream_url: streamURL } = await ensureSession(
    client,
    apiBase,
    agentId,
    apiKey,
    joinMode,
    roomId
  );

  const state = await loadDecisionState();
  const lastEventId = state.last_event_id || "";
  const tracker = new TurnTracker();

  let decided = false;
  let newLastEventId = lastEventId;
  let pendingDecision: PendingDecision | undefined;
  let stateCleared = false;

  try {
    newLastEventId = await parseSSEOnce(streamURL, lastEventId, timeoutMs, async (evt) => {
      let envelope: any;
      try {
        envelope = JSON.parse(evt.data);
      } catch {
        return false;
      }
      const evType = envelope?.event || evt.event;
      const data = envelope?.data || {};

      if (evType === "session_closed" || evType === "table_closed") {
        await saveDecisionState({
          session_id: "",
          stream_url: "",
          last_event_id: "",
          last_turn_id: "",
          pending_decision: undefined
        });
        stateCleared = true;
        emit({ type: "table_closed", session_id: sessionId, reason: data?.reason || "table_closed" });
        decided = true;
        return true;
      }
      if (evType === "reconnect_grace_started") {
        emit({
          type: "table_closing",
          reason: "table_closing",
          event: evType,
          session_id: sessionId,
          disconnected_agent_id: data?.disconnected_agent_id,
          deadline_ts: data?.deadline_ts
        });
        decided = true;
        return true;
      }
      if (evType === "opponent_forfeited") {
        emit({
          type: "table_closing",
          reason: "table_closing",
          event: evType,
          session_id: sessionId
        });
        decided = true;
        return true;
      }
      if (evType !== "state_snapshot") {
        return false;
      }
      const tableStatus = String(data?.table_status || "active");
      if (tableStatus === "closing") {
        emit({
          type: "table_closing",
          reason: "table_closing",
          event: evType,
          session_id: sessionId,
          close_reason: data?.close_reason,
          reconnect_deadline_ts: data?.reconnect_deadline_ts
        });
        decided = true;
        return true;
      }
      if (tableStatus === "closed") {
        await saveDecisionState({
          session_id: "",
          stream_url: "",
          last_event_id: "",
          last_turn_id: "",
          pending_decision: undefined
        });
        stateCleared = true;
        emit({
          type: "table_closed",
          session_id: sessionId,
          reason: data?.close_reason || "table_closed"
        });
        decided = true;
        return true;
      }
      if (!tracker.shouldRequestDecision(data)) {
        return false;
      }

      const reqID = `req_${Date.now()}_${Math.floor(Math.random() * 1_000_000_000)}`;
      const callbackURL = `${apiBase}/agent/sessions/${sessionId}/actions`;
      const decisionID = `dec_${Date.now()}_${Math.floor(Math.random() * 1_000_000_000)}`;
      const legalActions = readLegalActions(data);
      const actionConstraints = readActionConstraints(data);
      pendingDecision = {
        decision_id: decisionID,
        session_id: sessionId,
        request_id: reqID,
        turn_id: String(data.turn_id || ""),
        callback_url: callbackURL,
        legal_actions: legalActions,
        action_constraints: actionConstraints,
        created_at: new Date().toISOString()
      };
      const payload: Record<string, unknown> = {
        type: "decision_request",
        decision_id: decisionID,
        session_id: sessionId,
        state: data
      };
      if (legalActions.length > 0) {
        payload.legal_actions = legalActions;
      }
      if (actionConstraints) {
        payload.action_constraints = actionConstraints;
      }
      emit(payload);
      decided = true;
      return true;
    });
  } catch (err) {
    throw err;
  } finally {
    if (!stateCleared) {
      await saveDecisionState({
        session_id: sessionId,
        stream_url: streamURL,
        last_event_id: newLastEventId,
        last_turn_id: "",
        pending_decision: pendingDecision
      });
    }
  }

  if (!decided) {
    emit({ type: "noop" });
  }
}

async function runSubmitDecision(args: ArgMap): Promise<void> {
  const apiBase = resolveApiBase(readString(args, "api-base", "API_BASE"));
  const decisionID = requireArg("--decision-id", readString(args, "decision-id"));
  const action = parseAction(requireArg("--action", readString(args, "action")));
  const thoughtLog = readString(args, "thought-log") || "";
  const amountRaw = readString(args, "amount");
  const amount = amountRaw ? Number(amountRaw) : undefined;
  if (amountRaw && !Number.isFinite(amount)) {
    throw new Error("invalid --amount");
  }

  const state = await loadDecisionState();
  const pending = state.pending_decision;
  if (!pending) {
    throw new Error("pending_decision_not_found (run apa-bot next-decision)");
  }
  if (pending.decision_id !== decisionID) {
    throw new Error("decision_id_mismatch (run apa-bot next-decision)");
  }
  const legalActions = pending.legal_actions || [];
  if (legalActions.length > 0 && !legalActions.includes(action)) {
    throw new Error("action_not_legal");
  }
  if ((action === "bet" || action === "raise") && amount === undefined) {
    throw new Error("amount_required_for_bet_or_raise");
  }
  const constraints = pending.action_constraints;
  if (action === "bet" && amount !== undefined && constraints?.bet) {
    if (amount < constraints.bet.min || amount > constraints.bet.max) {
      throw new Error("amount_out_of_range");
    }
  }
  if (action === "raise" && amount !== undefined && constraints?.raise) {
    if (amount < constraints.raise.min_to || amount > constraints.raise.max_to) {
      throw new Error("amount_out_of_range");
    }
  }

  const client = new APAHttpClient({ apiBase });
  try {
    const result = await client.submitAction({
      sessionID: pending.session_id,
      requestID: pending.request_id,
      turnID: pending.turn_id,
      action,
      amount,
      thoughtLog
    });
    await saveDecisionState({
      ...state,
      pending_decision: undefined
    });
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    const apiErr = err as APAClientError;
    if (
      apiErr?.code === "invalid_turn_id" ||
      apiErr?.code === "not_your_turn" ||
      apiErr?.code === "table_closing" ||
      apiErr?.code === "table_closed" ||
      apiErr?.code === "opponent_disconnected"
    ) {
      await saveDecisionState({
        ...state,
        pending_decision: undefined
      });
      if (apiErr?.code === "table_closed") {
        emit({
          type: "table_closed",
          decision_id: decisionID,
          error: apiErr.code,
          message: "table closed; re-join matchmaking"
        });
      } else if (apiErr?.code === "table_closing" || apiErr?.code === "opponent_disconnected") {
        emit({
          type: "table_closing",
          decision_id: decisionID,
          error: apiErr.code,
          message: "table is closing; pause and fetch new decision later"
        });
      } else {
        emit({
          type: "stale_decision",
          decision_id: decisionID,
          error: apiErr.code,
          message: "decision expired; run apa-bot next-decision again"
        });
      }
      return;
    }
    throw err;
  }
}

export async function runCLI(argv: string[] = process.argv.slice(2)): Promise<void> {
  const { command, args } = parseArgs(argv);

  if (command === "help" || command === "--help" || command === "-h") {
    printHelp();
    return;
  }

  const apiBase = resolveApiBase(readString(args, "api-base", "API_BASE"));

  switch (command) {
    case "register": {
      const client = new APAHttpClient({ apiBase });
      const name = requireArg("--name", readString(args, "name"));
      const description = requireArg("--description", readString(args, "description"));
      const result = await client.registerAgent({ name, description });
      const record = buildCredentialFromRegisterResult(result, apiBase, name);
      if (record) {
        await saveCredential(record);
      }
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    case "claim": {
      const client = new APAHttpClient({ apiBase });
      const claimCode = readString(args, "claim-code");
      const claimURL = readString(args, "claim-url");
      const code = claimCode || (claimURL ? claimCodeFromUrl(claimURL) : "");
      if (!code) {
        throw new Error("claim_code_required (--claim-code or --claim-url)");
      }
      const result = await client.claimByCode(code);
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    case "me": {
      const client = new APAHttpClient({ apiBase });
      const apiKey = await requireApiKey(apiBase);
      const result = await client.getAgentMe(apiKey);
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    case "bind-key": {
      const client = new APAHttpClient({ apiBase });
      const apiKey = await requireApiKey(apiBase);
      const provider = requireArg("--provider", readString(args, "provider"));
      const vendorKey = requireArg("--vendor-key", readString(args, "vendor-key"));
      const budgetUsd = readNumber(args, "budget-usd");
      const result = await client.bindKey({ apiKey, provider, vendorKey, budgetUsd });
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    case "doctor": {
      const major = Number(process.versions.node.split(".")[0]);
      const client = new APAHttpClient({ apiBase });
      const report: Record<string, unknown> = {
        node: process.versions.node,
        node_ok: major >= 20,
        api_base: apiBase
      };
      try {
        report.healthz = await client.healthz();
      } catch (err) {
        report.healthz_error = err instanceof Error ? err.message : String(err);
      }
      console.log(JSON.stringify(report, null, 2));
      return;
    }
    case "next-decision": {
      await runNextDecision(args);
      return;
    }
    case "submit-decision": {
      await runSubmitDecision(args);
      return;
    }
    default:
      printHelp();
      throw new Error(`unknown command: ${command}`);
  }
}

export async function runCLIEntrypoint(argv: string[] = process.argv.slice(2)): Promise<void> {
  try {
    await runCLI(argv);
  } catch (err) {
    emit(toErrorPayload(err));
    process.exitCode = 1;
  }
}
