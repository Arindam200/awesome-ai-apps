// One live run on one image: read, check, build and the vision loop, exactly as the app does.
// Usage: pnpm smoke <image> [--read-only]
// Reads .env.local. Set INKLING_RECORD=1 to save the replies as replay fixtures.
import fs from "node:fs";
import path from "node:path";

for (const line of fs.existsSync(".env.local") ? fs.readFileSync(".env.local", "utf8").split("\n") : []) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
}

const { normaliseSketch } = await import("../src/lib/image.ts");
const { readCircuit } = await import("../src/lib/inkling/read.ts");
const { settings } = await import("../src/lib/inkling/client.ts");
const { checkIssues, findMistakes } = await import("../src/lib/sim/checks.ts");
const { settle, startRun } = await import("../src/lib/pipeline.ts");
const { loadRun } = await import("../src/lib/runs.ts");

const file = process.argv[2];
if (!file) {
  console.error("Usage: pnpm smoke <image> [--read-only]");
  process.exit(1);
}
const s = settings();
console.log(`Inkling: ${s.model} via ${s.provider}${s.record ? " (recording replays)" : ""}`);
const image = fs.readFileSync(file);

if (process.argv.includes("--read-only")) {
  const sketch = await normaliseSketch(image);
  const t0 = Date.now();
  const read = await readCircuit({ sketch: sketch.dataUrl, replayKey: `read-${sketch.hash}` });
  const drawn = settle(read.value.asDrawn);
  const check = checkIssues(read.value.issues, findMistakes(drawn));
  console.log(JSON.stringify({ via: read.via, repaired: read.repaired, seconds: (Date.now() - t0) / 1000, usage: read.logs.map((l) => l.usage), read: read.value, check }, null, 2));
  process.exit(0);
}

const id = await startRun(image, { name: path.basename(file) });
console.log(`Run ${id}`);
let last = "";
for (;;) {
  await new Promise((r) => setTimeout(r, 2000));
  const run = await loadRun(id);
  if (!run) continue;
  const line = `${run.status}: ${run.progress.stage}`;
  if (line !== last) console.log(line), (last = line);
  if (run.status === "done" || run.status === "failed") {
    console.log(JSON.stringify({ status: run.status, error: run.error, title: run.read?.title, result: run.result, issues: run.check?.issues.map((i) => `${i.kind} ${i.componentIds} -> ${i.verdict}`), rounds: run.rounds.map((r) => ({ n: r.n, review: r.review, shots: r.shots.map((x) => `${x.label}: ${x.mismatches.length} mismatches, ${x.errors.length} errors`) })), calls: run.calls.map((c) => `${c.stage} ${(c.ms / 1000).toFixed(1)}s in ${c.usage.input} out ${c.usage.output} reasoning ${c.usage.reasoning}${c.error ? " ERROR " + c.error : ""}`) }, null, 2));
    console.log(`Run pnpm dev and open /run/${id}`);
    process.exit(run.status === "done" ? 0 : 1);
  }
}
