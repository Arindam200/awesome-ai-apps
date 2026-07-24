import { resolveApiBase } from "../utils/config.js";

type HttpClientOptions = {
  apiBase?: string;
};

export type APAClientError = Error & {
  status?: number;
  code?: string;
  body?: unknown;
};

type CreateSessionInput = {
  agentID: string;
  apiKey: string;
  joinMode: "random" | "select";
  roomID?: string;
};

type SubmitActionInput = {
  sessionID: string;
  requestID: string;
  turnID: string;
  action: "fold" | "check" | "call" | "raise" | "bet";
  amount?: number;
  thoughtLog?: string;
};

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) {
    const err = new Error(`empty response (${res.status})`) as APAClientError;
    err.status = res.status;
    throw err;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    const err = new Error(`invalid json response (${res.status})`) as APAClientError;
    err.status = res.status;
    err.body = text;
    throw err;
  }
  if (!res.ok) {
    const p = parsed as { error?: string };
    const err = new Error(`${res.status} ${p?.error || text}`) as APAClientError;
    err.status = res.status;
    err.code = p?.error || "request_failed";
    err.body = parsed;
    throw err;
  }
  return parsed as T;
}

export class APAHttpClient {
  private readonly apiBase: string;

  constructor(opts: HttpClientOptions = {}) {
    this.apiBase = resolveApiBase(opts.apiBase);
  }

  async registerAgent(input: { name: string; description: string }): Promise<any> {
    const res = await fetch(`${this.apiBase}/agents/register`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input)
    });
    return parseJson(res);
  }

  async claimByCode(claimCode: string): Promise<any> {
    const base = this.apiBase.replace(/\/api\/?$/, "");
    const res = await fetch(`${base}/claim/${encodeURIComponent(claimCode)}`);
    return parseJson(res);
  }

  async getAgentMe(apiKey: string): Promise<any> {
    const res = await fetch(`${this.apiBase}/agents/me`, {
      headers: { authorization: `Bearer ${apiKey}` }
    });
    return parseJson(res);
  }

  async bindKey(input: { apiKey: string; provider: string; vendorKey: string; budgetUsd: number }): Promise<any> {
    const res = await fetch(`${this.apiBase}/agents/bind_key`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${input.apiKey}`,
        "content-type": "application/json"
      },
      body: JSON.stringify({
        provider: input.provider,
        api_key: input.vendorKey,
        budget_usd: input.budgetUsd
      })
    });
    return parseJson(res);
  }

  async listPublicRooms(): Promise<{ items: Array<{ id: string; min_buyin_cc: number; name: string }> }> {
    const res = await fetch(`${this.apiBase}/public/rooms`);
    return parseJson(res);
  }

  async createSession(input: CreateSessionInput): Promise<any> {
    const res = await fetch(`${this.apiBase}/agent/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        agent_id: input.agentID,
        api_key: input.apiKey,
        join_mode: input.joinMode,
        room_id: input.joinMode === "select" ? input.roomID : undefined
      })
    });
    return parseJson(res);
  }

  async submitAction(input: SubmitActionInput): Promise<any> {
    const res = await fetch(`${this.apiBase}/agent/sessions/${input.sessionID}/actions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        request_id: input.requestID,
        turn_id: input.turnID,
        action: input.action,
        amount: input.amount,
        thought_log: input.thoughtLog || ""
      })
    });
    return parseJson(res);
  }

  async closeSession(sessionID: string): Promise<void> {
    await fetch(`${this.apiBase}/agent/sessions/${sessionID}`, { method: "DELETE" });
  }

  async healthz(): Promise<any> {
    const base = this.apiBase.replace(/\/api\/?$/, "");
    const res = await fetch(`${base}/healthz`);
    return parseJson(res);
  }
}
