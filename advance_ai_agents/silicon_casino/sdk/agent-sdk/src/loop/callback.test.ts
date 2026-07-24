import test from "node:test";
import assert from "node:assert/strict";

import { DecisionCallbackServer } from "./callback.js";

test("callback server receives decision and resolves pending request", async (t) => {
  const server = new DecisionCallbackServer("127.0.0.1:18787");
  let callbackURL = "";
  try {
    callbackURL = await server.start();
  } catch (err) {
    const code = err && typeof err === "object" ? (err as NodeJS.ErrnoException).code : "";
    if (code === "EPERM" || code === "EACCES") {
      t.skip("listen not permitted in this environment");
      return;
    }
    throw err;
  }

  const decisionPromise = server.waitForDecision("req_1", 2000);
  const res = await fetch(callbackURL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      request_id: "req_1",
      action: "call",
      thought_log: "ok"
    })
  });
  assert.equal(res.status, 200);
  const decision = await decisionPromise;
  assert.equal(decision.request_id, "req_1");
  assert.equal(decision.action, "call");
  await server.stop();
});
