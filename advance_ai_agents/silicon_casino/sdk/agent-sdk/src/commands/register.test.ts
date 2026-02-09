import test from "node:test";
import assert from "node:assert/strict";

import { buildCredentialFromRegisterResult } from "./register.js";

test("buildCredentialFromRegisterResult returns credential when response has required fields", () => {
  const out = buildCredentialFromRegisterResult(
    {
      agent: {
        agent_id: "agent_123",
        api_key: "apa_123",
        name: "BotX"
      }
    },
    "http://localhost:8080/api",
    "FallbackBot"
  );
  assert.ok(out);
  assert.equal(out?.agent_id, "agent_123");
  assert.equal(out?.api_key, "apa_123");
  assert.equal(out?.agent_name, "BotX");
});

test("buildCredentialFromRegisterResult falls back to CLI name and rejects incomplete payload", () => {
  const fallback = buildCredentialFromRegisterResult(
    {
      agent: {
        agent_id: "agent_abc",
        api_key: "apa_abc"
      }
    },
    "http://localhost:8080/api",
    "FallbackBot"
  );
  assert.ok(fallback);
  assert.equal(fallback?.agent_name, "FallbackBot");

  const bad = buildCredentialFromRegisterResult(
    {
      agent: {
        api_key: "apa_missing_agent"
      }
    },
    "http://localhost:8080/api",
    "FallbackBot"
  );
  assert.equal(bad, null);
});
