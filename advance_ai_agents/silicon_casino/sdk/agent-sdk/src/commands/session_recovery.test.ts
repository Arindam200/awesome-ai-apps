import test from "node:test";
import assert from "node:assert/strict";

import { recoverSessionFromConflict } from "./session_recovery.js";

test("recoverSessionFromConflict returns resumable session for 409 agent_already_in_session", () => {
  const err = {
    status: 409,
    code: "agent_already_in_session",
    body: {
      error: "agent_already_in_session",
      session_id: "sess_1",
      stream_url: "/api/agent/sessions/sess_1/events"
    }
  };
  const recovered = recoverSessionFromConflict(err, "http://localhost:8080/api");
  assert.ok(recovered);
  assert.equal(recovered?.session_id, "sess_1");
  assert.equal(recovered?.stream_url, "http://localhost:8080/api/agent/sessions/sess_1/events");
});

test("recoverSessionFromConflict returns null for unrelated errors", () => {
  const err = {
    status: 500,
    code: "internal_error",
    body: { error: "internal_error" }
  };
  const recovered = recoverSessionFromConflict(err, "http://localhost:8080/api");
  assert.equal(recovered, null);
});
