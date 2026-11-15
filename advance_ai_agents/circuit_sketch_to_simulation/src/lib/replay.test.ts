import fs from "node:fs";
import path from "node:path";
import { beforeAll, describe, expect, it } from "vitest";

// Runs the stored replies from a real run through the same code the app uses, with no network.
beforeAll(() => {
  process.env.INKLING_PROVIDER = "replay";
});

describe("replay of a recorded run", () => {
  it("reads the LED sketch, confirms the open circuit and builds a page with window.__sim", async () => {
    const { normaliseSketch } = await import("@/lib/image");
    const { readCircuit } = await import("@/lib/inkling/read");
    const { buildSimulation } = await import("@/lib/inkling/build");
    const { checkIssues, findMistakes } = await import("@/lib/sim/checks");
    const { settle } = await import("@/lib/pipeline");

    const sketch = await normaliseSketch(fs.readFileSync(path.join(process.cwd(), "fixtures/sketches/cghd-c31-d1.jpg")));
    expect(fs.existsSync(path.join(process.cwd(), `fixtures/replays/read-${sketch.hash}.json`))).toBe(true);

    const read = await readCircuit({ sketch: sketch.dataUrl, replayKey: `read-${sketch.hash}` });
    expect(read.via).toBe("tool");
    const types = read.value.fixed.components.map((c) => c.type).sort();
    expect(types).toEqual(expect.arrayContaining(["battery", "led", "resistor", "switch"]));

    const check = checkIssues(read.value.issues, findMistakes(settle(read.value.asDrawn)));
    expect(check.issues.some((i) => i.kind === "open_circuit" && i.verdict === "confirmed")).toBe(true);

    const built = await buildSimulation({ read: read.value, sketch: sketch.dataUrl, replayKey: `build-${sketch.hash}` });
    expect(built.html).toMatch(/window\.__sim\s*=/);
  });
});
