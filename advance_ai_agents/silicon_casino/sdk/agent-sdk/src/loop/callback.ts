import http from "node:http";
import type { AddressInfo } from "node:net";
import { URL } from "node:url";

export type DecisionAction = "fold" | "check" | "call" | "raise" | "bet";

export type DecisionPayload = {
  request_id: string;
  action: DecisionAction;
  amount?: number;
  thought_log?: string;
};

type DecisionResolver = {
  resolve: (payload: DecisionPayload) => void;
  reject: (err: Error) => void;
  timeout: NodeJS.Timeout;
};

export class DecisionCallbackServer {
  private readonly addr: string | undefined;
  private readonly decisions = new Map<string, DecisionResolver>();
  private server: http.Server | null = null;
  private callbackURL = "";

  constructor(addr?: string) {
    this.addr = addr;
  }

  async start(): Promise<string> {
    if (this.server) {
      return this.callbackURL;
    }
    const [host, port] = this.parseAddr();
    this.server = http.createServer(this.handleRequest.bind(this));
    await new Promise<void>((resolve, reject) => {
      this.server?.once("error", reject);
      this.server?.listen(port, host, () => resolve());
    });
    const actual = this.server?.address();
    if (!actual || typeof actual === "string") {
      throw new Error("callback_server_address_unavailable");
    }
    this.callbackURL = `http://${actual.address}:${actual.port}/decision`;
    return this.callbackURL;
  }

  async stop(): Promise<void> {
    const entries = [...this.decisions.values()];
    this.decisions.clear();
    for (const pending of entries) {
      clearTimeout(pending.timeout);
      pending.reject(new Error("callback_server_stopped"));
    }
    if (!this.server) {
      return;
    }
    const s = this.server;
    this.server = null;
    await new Promise<void>((resolve) => s.close(() => resolve()));
  }

  waitForDecision(requestID: string, timeoutMs: number): Promise<DecisionPayload> {
    return new Promise<DecisionPayload>((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.decisions.delete(requestID);
        reject(new Error("decision_timeout"));
      }, timeoutMs);
      this.decisions.set(requestID, { resolve, reject, timeout });
    });
  }

  private async handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const method = req.method || "";
    const url = new URL(req.url || "/", "http://localhost");
    if (method === "GET" && url.pathname === "/healthz") {
      this.reply(res, 200, { ok: true });
      return;
    }
    if (method !== "POST" || url.pathname !== "/decision") {
      this.reply(res, 404, { error: "not_found" });
      return;
    }
    let body = "";
    req.setEncoding("utf8");
    for await (const chunk of req) {
      body += chunk;
    }
    let payload: DecisionPayload | null = null;
    try {
      payload = JSON.parse(body) as DecisionPayload;
    } catch {
      this.reply(res, 400, { error: "invalid_json" });
      return;
    }
    if (!payload || typeof payload.request_id !== "string" || typeof payload.action !== "string") {
      this.reply(res, 400, { error: "invalid_payload" });
      return;
    }
    const pending = this.decisions.get(payload.request_id);
    if (!pending) {
      this.reply(res, 409, { error: "request_not_pending" });
      return;
    }
    this.decisions.delete(payload.request_id);
    clearTimeout(pending.timeout);
    pending.resolve(payload);
    this.reply(res, 200, { ok: true });
  }

  private reply(res: http.ServerResponse, status: number, payload: Record<string, unknown>): void {
    res.statusCode = status;
    res.setHeader("content-type", "application/json");
    res.end(`${JSON.stringify(payload)}\n`);
  }

  private parseAddr(): [string, number] {
    if (!this.addr) {
      return ["127.0.0.1", 0];
    }
    const [host, portRaw] = this.addr.split(":");
    const port = Number(portRaw);
    if (!host || !Number.isFinite(port) || port <= 0) {
      throw new Error(`invalid callback addr: ${this.addr}`);
    }
    return [host, port];
  }
}
