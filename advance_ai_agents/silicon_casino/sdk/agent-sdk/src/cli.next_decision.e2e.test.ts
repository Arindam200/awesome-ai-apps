import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import { promises as fs } from "node:fs";

import { runCLI } from "./cli.js";
import { saveCredential } from "./loop/credentials.js";
import { loadDecisionState } from "./loop/decision_state.js";

type FetchCall = {
  url: string;
  method: string;
  headers?: HeadersInit;
  body?: string;
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" }
  });
}

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    }
  });
  return new Response(stream, {
    status: 200,
    headers: { "content-type": "text/event-stream" }
  });
}

function captureStdout() {
  const writes: string[] = [];
  const original = process.stdout.write.bind(process.stdout);
  process.stdout.write = ((chunk: string | Uint8Array) => {
    writes.push(typeof chunk === "string" ? chunk : Buffer.from(chunk).toString("utf8"));
    return true;
  }) as typeof process.stdout.write;
  return {
    writes,
    restore() {
      process.stdout.write = original;
    }
  };
}

async function withTempCwd<T>(fn: () => Promise<T>): Promise<T> {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "apa-sdk-next-decision-"));
  const prev = process.cwd();
  process.chdir(dir);
  try {
    return await fn();
  } finally {
    process.chdir(prev);
  }
}

test("next-decision creates session, emits decision_request (without protocol fields), and updates state", async () => {
  await withTempCwd(async () => {
    const apiBase = "http://mock.local/api";
    await saveCredential({
      api_base: apiBase,
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    });

    const calls: FetchCall[] = [];
    const originalFetch = globalThis.fetch;
    const stdout = captureStdout();

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method || "GET";
      calls.push({
        url,
        method,
        headers: init?.headers,
        body: typeof init?.body === "string" ? init.body : undefined
      });

      if (url === `${apiBase}/agents/me` && method === "GET") {
        return jsonResponse({ status: "claimed", balance_cc: 10000 });
      }
      if (url === `${apiBase}/public/rooms` && method === "GET") {
        return jsonResponse({ items: [{ id: "room_low", min_buyin_cc: 1000, name: "Low" }] });
      }
      if (url === `${apiBase}/agent/sessions` && method === "POST") {
        return jsonResponse({
          session_id: "sess_1",
          stream_url: "/api/agent/sessions/sess_1/events"
        });
      }
      if (url === `${apiBase}/agent/sessions/sess_1/events` && method === "GET") {
        return sseResponse([
          "id: 101\nevent: message\ndata: {\"event\":\"state_snapshot\",\"data\":{\"turn_id\":\"turn_1\",",
          "\"my_seat\":0,\"current_actor_seat\":0,\"legal_actions\":[\"check\",\"bet\"],",
          "\"action_constraints\":{\"bet\":{\"min\":100,\"max\":1200}}}}\n\n"
        ]);
      }
      throw new Error(`unexpected fetch: ${method} ${url}`);
    }) as typeof globalThis.fetch;

    try {
      await runCLI(["next-decision", "--api-base", apiBase, "--join", "random", "--timeout-ms", "2000"]);
    } finally {
      globalThis.fetch = originalFetch;
      stdout.restore();
    }

    const messages = stdout.writes
      .join("")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    const decision = messages.find((m) => m.type === "decision_request");
    assert.ok(decision);
    assert.equal(decision?.session_id, "sess_1");
    assert.ok(typeof decision?.decision_id === "string");
    assert.equal(decision?.turn_id, undefined);
    assert.equal(decision?.callback_url, undefined);
    assert.deepEqual(decision?.legal_actions, ["check", "bet"]);
    assert.deepEqual(decision?.action_constraints, { bet: { min: 100, max: 1200 } });

    const state = await loadDecisionState();
    assert.equal(state.session_id, "sess_1");
    assert.equal(state.stream_url, `${apiBase}/agent/sessions/sess_1/events`);
    assert.equal(state.last_event_id, "101");
    assert.ok(state.pending_decision?.decision_id);
    assert.equal(state.pending_decision?.session_id, "sess_1");
    assert.equal(state.pending_decision?.callback_url, `${apiBase}/agent/sessions/sess_1/actions`);
    assert.equal(state.pending_decision?.turn_id, "turn_1");
    assert.deepEqual(state.pending_decision?.legal_actions, ["check", "bet"]);
    assert.deepEqual(state.pending_decision?.action_constraints, { bet: { min: 100, max: 1200 } });

    const created = calls.find((c) => c.url === `${apiBase}/agent/sessions` && c.method === "POST");
    assert.ok(created);
    const createdPayload = JSON.parse(String(created?.body || "{}")) as Record<string, unknown>;
    assert.equal(createdPayload.join_mode, "random");
    assert.equal(createdPayload.room_id, undefined);
  });
});

test("next-decision recovers from 409 and reuses existing session from response body", async () => {
  await withTempCwd(async () => {
    const apiBase = "http://mock.local/api";
    await saveCredential({
      api_base: apiBase,
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    });

    const originalFetch = globalThis.fetch;
    const stdout = captureStdout();

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method || "GET";

      if (url === `${apiBase}/agents/me` && method === "GET") {
        return jsonResponse({ status: "claimed", balance_cc: 10000 });
      }
      if (url === `${apiBase}/public/rooms` && method === "GET") {
        return jsonResponse({ items: [{ id: "room_low", min_buyin_cc: 1000, name: "Low" }] });
      }
      if (url === `${apiBase}/agent/sessions` && method === "POST") {
        return jsonResponse(
          {
            error: "agent_already_in_session",
            session_id: "sess_conflict",
            stream_url: "/api/agent/sessions/sess_conflict/events"
          },
          409
        );
      }
      if (url === `${apiBase}/agent/sessions/sess_conflict/events` && method === "GET") {
        return sseResponse([
          "id: 202\nevent: message\ndata: {\"event\":\"state_snapshot\",\"data\":{\"turn_id\":\"turn_2\",\"my_seat\":1,\"current_actor_seat\":1,",
          "\"legal_actions\":[\"fold\",\"call\",\"raise\"],\"action_constraints\":{\"raise\":{\"min_to\":300,\"max_to\":1500}}}}\n\n"
        ]);
      }
      throw new Error(`unexpected fetch: ${method} ${url}`);
    }) as typeof globalThis.fetch;

    try {
      await runCLI(["next-decision", "--api-base", apiBase, "--join", "random", "--timeout-ms", "2000"]);
    } finally {
      globalThis.fetch = originalFetch;
      stdout.restore();
    }

    const messages = stdout.writes
      .join("")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    const decision = messages.find((m) => m.type === "decision_request");
    assert.ok(decision);
    assert.equal(decision?.session_id, "sess_conflict");
    assert.ok(typeof decision?.decision_id === "string");
    assert.equal(decision?.callback_url, undefined);

    const state = await loadDecisionState();
    assert.equal(state.session_id, "sess_conflict");
    assert.equal(state.stream_url, `${apiBase}/agent/sessions/sess_conflict/events`);
    assert.equal(state.last_event_id, "202");
    assert.equal(state.pending_decision?.session_id, "sess_conflict");
    assert.equal(state.pending_decision?.turn_id, "turn_2");
    assert.deepEqual(state.pending_decision?.legal_actions, ["fold", "call", "raise"]);
    assert.deepEqual(state.pending_decision?.action_constraints, { raise: { min_to: 300, max_to: 1500 } });
  });
});

test("submit-decision uses pending decision metadata and clears pending entry", async () => {
  await withTempCwd(async () => {
    const apiBase = "http://mock.local/api";
    await saveCredential({
      api_base: apiBase,
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    });

    const calls: FetchCall[] = [];
    const originalFetch = globalThis.fetch;
    const stdout = captureStdout();

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method || "GET";
      calls.push({
        url,
        method,
        headers: init?.headers,
        body: typeof init?.body === "string" ? init.body : undefined
      });

      if (url === `${apiBase}/agents/me` && method === "GET") {
        return jsonResponse({ status: "claimed", balance_cc: 10000 });
      }
      if (url === `${apiBase}/public/rooms` && method === "GET") {
        return jsonResponse({ items: [{ id: "room_low", min_buyin_cc: 1000, name: "Low" }] });
      }
      if (url === `${apiBase}/agent/sessions` && method === "POST") {
        return jsonResponse({
          session_id: "sess_1",
          stream_url: "/api/agent/sessions/sess_1/events"
        });
      }
      if (url === `${apiBase}/agent/sessions/sess_1/events` && method === "GET") {
        return sseResponse([
          "id: 301\nevent: message\ndata: {\"event\":\"state_snapshot\",\"data\":{\"turn_id\":\"turn_3\",",
          "\"my_seat\":0,\"current_actor_seat\":0,\"legal_actions\":[\"call\"]}}\n\n"
        ]);
      }
      if (url === `${apiBase}/agent/sessions/sess_1/actions` && method === "POST") {
        return jsonResponse({ accepted: true, request_id: "req_ok" });
      }
      throw new Error(`unexpected fetch: ${method} ${url}`);
    }) as typeof globalThis.fetch;

    try {
      await runCLI(["next-decision", "--api-base", apiBase, "--join", "random", "--timeout-ms", "2000"]);
      const state = await loadDecisionState();
      const decisionID = state.pending_decision?.decision_id;
      assert.ok(decisionID);
      await runCLI(["submit-decision", "--api-base", apiBase, "--decision-id", decisionID as string, "--action", "call"]);
    } finally {
      globalThis.fetch = originalFetch;
      stdout.restore();
    }

    const actionCall = calls.find((c) => c.url === `${apiBase}/agent/sessions/sess_1/actions` && c.method === "POST");
    assert.ok(actionCall);
    const payload = JSON.parse(String(actionCall?.body || "{}")) as Record<string, unknown>;
    assert.equal(payload.turn_id, "turn_3");
    assert.equal(payload.action, "call");

    const finalState = await loadDecisionState();
    assert.equal(finalState.pending_decision, undefined);
  });
});

test("submit-decision blocks bet/raise without amount locally", async () => {
  await withTempCwd(async () => {
    const apiBase = "http://mock.local/api";
    await saveCredential({
      api_base: apiBase,
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    });

    const calls: FetchCall[] = [];
    const originalFetch = globalThis.fetch;
    const stdout = captureStdout();

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method || "GET";
      calls.push({ url, method, headers: init?.headers, body: typeof init?.body === "string" ? init.body : undefined });

      if (url === `${apiBase}/agents/me` && method === "GET") {
        return jsonResponse({ status: "claimed", balance_cc: 10000 });
      }
      if (url === `${apiBase}/public/rooms` && method === "GET") {
        return jsonResponse({ items: [{ id: "room_low", min_buyin_cc: 1000, name: "Low" }] });
      }
      if (url === `${apiBase}/agent/sessions` && method === "POST") {
        return jsonResponse({ session_id: "sess_2", stream_url: "/api/agent/sessions/sess_2/events" });
      }
      if (url === `${apiBase}/agent/sessions/sess_2/events` && method === "GET") {
        return sseResponse([
          "id: 401\nevent: message\ndata: {\"event\":\"state_snapshot\",\"data\":{\"turn_id\":\"turn_4\",",
          "\"my_seat\":0,\"current_actor_seat\":0,\"legal_actions\":[\"bet\"],\"action_constraints\":{\"bet\":{\"min\":100,\"max\":500}}}}\n\n"
        ]);
      }
      throw new Error(`unexpected fetch: ${method} ${url}`);
    }) as typeof globalThis.fetch;

    try {
      await runCLI(["next-decision", "--api-base", apiBase, "--join", "random", "--timeout-ms", "2000"]);
      const state = await loadDecisionState();
      const decisionID = state.pending_decision?.decision_id;
      assert.ok(decisionID);
      await assert.rejects(
        async () =>
          runCLI(["submit-decision", "--api-base", apiBase, "--decision-id", decisionID as string, "--action", "bet"]),
        /amount_required_for_bet_or_raise/
      );
    } finally {
      globalThis.fetch = originalFetch;
      stdout.restore();
    }

    const actionCall = calls.find((c) => c.url.includes("/actions") && c.method === "POST");
    assert.equal(actionCall, undefined);
  });
});

test("submit-decision blocks out-of-range amount locally", async () => {
  await withTempCwd(async () => {
    const apiBase = "http://mock.local/api";
    await saveCredential({
      api_base: apiBase,
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    });

    const calls: FetchCall[] = [];
    const originalFetch = globalThis.fetch;
    const stdout = captureStdout();

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method || "GET";
      calls.push({ url, method, headers: init?.headers, body: typeof init?.body === "string" ? init.body : undefined });

      if (url === `${apiBase}/agents/me` && method === "GET") {
        return jsonResponse({ status: "claimed", balance_cc: 10000 });
      }
      if (url === `${apiBase}/public/rooms` && method === "GET") {
        return jsonResponse({ items: [{ id: "room_low", min_buyin_cc: 1000, name: "Low" }] });
      }
      if (url === `${apiBase}/agent/sessions` && method === "POST") {
        return jsonResponse({ session_id: "sess_3", stream_url: "/api/agent/sessions/sess_3/events" });
      }
      if (url === `${apiBase}/agent/sessions/sess_3/events` && method === "GET") {
        return sseResponse([
          "id: 501\nevent: message\ndata: {\"event\":\"state_snapshot\",\"data\":{\"turn_id\":\"turn_5\",",
          "\"my_seat\":0,\"current_actor_seat\":0,\"legal_actions\":[\"raise\"],\"action_constraints\":{\"raise\":{\"min_to\":300,\"max_to\":600}}}}\n\n"
        ]);
      }
      throw new Error(`unexpected fetch: ${method} ${url}`);
    }) as typeof globalThis.fetch;

    try {
      await runCLI(["next-decision", "--api-base", apiBase, "--join", "random", "--timeout-ms", "2000"]);
      const state = await loadDecisionState();
      const decisionID = state.pending_decision?.decision_id;
      assert.ok(decisionID);
      await assert.rejects(
        async () =>
          runCLI([
            "submit-decision",
            "--api-base",
            apiBase,
            "--decision-id",
            decisionID as string,
            "--action",
            "raise",
            "--amount",
            "700"
          ]),
        /amount_out_of_range/
      );
    } finally {
      globalThis.fetch = originalFetch;
      stdout.restore();
    }

    const actionCall = calls.find((c) => c.url.includes("/actions") && c.method === "POST");
    assert.equal(actionCall, undefined);
  });
});

test("next-decision emits table_closing when table is closing", async () => {
  await withTempCwd(async () => {
    const apiBase = "http://mock.local/api";
    await saveCredential({
      api_base: apiBase,
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    });

    const originalFetch = globalThis.fetch;
    const stdout = captureStdout();

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method || "GET";

      if (url === `${apiBase}/agents/me` && method === "GET") {
        return jsonResponse({ status: "claimed", balance_cc: 10000 });
      }
      if (url === `${apiBase}/public/rooms` && method === "GET") {
        return jsonResponse({ items: [{ id: "room_low", min_buyin_cc: 1000, name: "Low" }] });
      }
      if (url === `${apiBase}/agent/sessions` && method === "POST") {
        return jsonResponse({ session_id: "sess_4", stream_url: "/api/agent/sessions/sess_4/events" });
      }
      if (url === `${apiBase}/agent/sessions/sess_4/events` && method === "GET") {
        return sseResponse([
          "id: 601\nevent: message\ndata: {\"event\":\"reconnect_grace_started\",\"data\":{\"disconnected_agent_id\":\"agent_x\",\"deadline_ts\":123}}\n\n"
        ]);
      }
      throw new Error(`unexpected fetch: ${method} ${url}`);
    }) as typeof globalThis.fetch;

    try {
      await runCLI(["next-decision", "--api-base", apiBase, "--join", "random", "--timeout-ms", "2000"]);
    } finally {
      globalThis.fetch = originalFetch;
      stdout.restore();
    }

    const messages = stdout.writes
      .join("")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    assert.equal(messages.length, 1);
    assert.equal(messages[0]?.type, "table_closing");
    assert.equal(messages[0]?.reason, "table_closing");
  });
});

test("next-decision keeps decision state cleared after table_closed", async () => {
  await withTempCwd(async () => {
    const apiBase = "http://mock.local/api";
    await saveCredential({
      api_base: apiBase,
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    });

    const originalFetch = globalThis.fetch;
    const stdout = captureStdout();

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method || "GET";

      if (url === `${apiBase}/agents/me` && method === "GET") {
        return jsonResponse({ status: "claimed", balance_cc: 10000 });
      }
      if (url === `${apiBase}/public/rooms` && method === "GET") {
        return jsonResponse({ items: [{ id: "room_low", min_buyin_cc: 1000, name: "Low" }] });
      }
      if (url === `${apiBase}/agent/sessions` && method === "POST") {
        return jsonResponse({ session_id: "sess_closed", stream_url: "/api/agent/sessions/sess_closed/events" });
      }
      if (url === `${apiBase}/agent/sessions/sess_closed/events` && method === "GET") {
        return sseResponse([
          "id: 650\nevent: message\ndata: {\"event\":\"table_closed\",\"data\":{\"reason\":\"opponent_reconnect_timeout\"}}\n\n"
        ]);
      }
      throw new Error(`unexpected fetch: ${method} ${url}`);
    }) as typeof globalThis.fetch;

    try {
      await runCLI(["next-decision", "--api-base", apiBase, "--join", "random", "--timeout-ms", "2000"]);
    } finally {
      globalThis.fetch = originalFetch;
      stdout.restore();
    }

    const messages = stdout.writes
      .join("")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    assert.equal(messages.length, 1);
    assert.equal(messages[0]?.type, "table_closed");

    const state = await loadDecisionState();
    assert.equal(state.session_id, "");
    assert.equal(state.stream_url, "");
    assert.equal(state.last_event_id, "");
    assert.equal(state.pending_decision, undefined);
  });
});

test("submit-decision emits table_closing and clears pending decision", async () => {
  await withTempCwd(async () => {
    const apiBase = "http://mock.local/api";
    await saveCredential({
      api_base: apiBase,
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    });

    const originalFetch = globalThis.fetch;
    const stdout = captureStdout();

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method || "GET";

      if (url === `${apiBase}/agents/me` && method === "GET") {
        return jsonResponse({ status: "claimed", balance_cc: 10000 });
      }
      if (url === `${apiBase}/public/rooms` && method === "GET") {
        return jsonResponse({ items: [{ id: "room_low", min_buyin_cc: 1000, name: "Low" }] });
      }
      if (url === `${apiBase}/agent/sessions` && method === "POST") {
        return jsonResponse({ session_id: "sess_5", stream_url: "/api/agent/sessions/sess_5/events" });
      }
      if (url === `${apiBase}/agent/sessions/sess_5/events` && method === "GET") {
        return sseResponse([
          "id: 701\nevent: message\ndata: {\"event\":\"state_snapshot\",\"data\":{\"turn_id\":\"turn_7\",\"my_seat\":0,\"current_actor_seat\":0,\"legal_actions\":[\"call\"]}}\n\n"
        ]);
      }
      if (url === `${apiBase}/agent/sessions/sess_5/actions` && method === "POST") {
        return jsonResponse({ error: "table_closing" }, 409);
      }
      throw new Error(`unexpected fetch: ${method} ${url}`);
    }) as typeof globalThis.fetch;

    try {
      await runCLI(["next-decision", "--api-base", apiBase, "--join", "random", "--timeout-ms", "2000"]);
      const state = await loadDecisionState();
      const decisionID = state.pending_decision?.decision_id;
      assert.ok(decisionID);
      await runCLI(["submit-decision", "--api-base", apiBase, "--decision-id", decisionID as string, "--action", "call"]);
    } finally {
      globalThis.fetch = originalFetch;
      stdout.restore();
    }

    const messages = stdout.writes
      .join("")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    const tableClosing = messages.find((m) => m.type === "table_closing");
    assert.ok(tableClosing);

    const finalState = await loadDecisionState();
    assert.equal(finalState.pending_decision, undefined);
  });
});
