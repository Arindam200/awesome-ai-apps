import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import { promises as fs } from "node:fs";

import { loadCredential, saveCredential } from "./credentials.js";

test("saveCredential and loadCredential roundtrip", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "apa-sdk-creds-"));
  const filePath = path.join(dir, "credentials.json");

  await saveCredential(
    {
      api_base: "http://localhost:8080/api",
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    },
    filePath
  );

  const loaded = await loadCredential("http://localhost:8080/api", "BotA", filePath);
  assert.ok(loaded);
  assert.equal(loaded?.agent_id, "agent_1");
  assert.equal(loaded?.api_key, "apa_1");
});

test("loadCredential without agentName returns single match for api base", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "apa-sdk-creds-"));
  const filePath = path.join(dir, "credentials.json");

  await saveCredential(
    {
      api_base: "http://localhost:8080/api",
      agent_name: "BotA",
      agent_id: "agent_1",
      api_key: "apa_1"
    },
    filePath
  );

  const loaded = await loadCredential("http://localhost:8080/api", undefined, filePath);
  assert.ok(loaded);
  assert.equal(loaded?.agent_name, "BotA");
});
