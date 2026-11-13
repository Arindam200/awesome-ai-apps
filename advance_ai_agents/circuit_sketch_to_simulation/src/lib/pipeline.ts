import { normaliseSketch, pngDataUrl } from "@/lib/image";
import { settings, type CallLog } from "@/lib/inkling/client";
import { buildSimulation, reviewSimulation } from "@/lib/inkling/build";
import { readCircuit } from "@/lib/inkling/read";
import { capture, type View } from "@/lib/sandbox";
import type { Netlist } from "@/lib/schema/circuit";
import { agreement, describeMismatches } from "@/lib/sim/agreement";
import { checkIssues, findMistakes } from "@/lib/sim/checks";
import { withSwitch } from "@/lib/sim/mna";
import { newId, saveRun, writeFile, type Round, type Run, type Source } from "@/lib/runs";

export const MAX_ROUNDS = 3;

// Make every switch's starting state explicit so the solver and the generated page agree.
export function settle(n: Netlist): Netlist {
  return {
    components: n.components.map((c) => (c.type === "switch" || c.type === "button" ? { ...c, closed: c.closed ?? c.type === "switch" } : c)),
  };
}

function views(fixed: Netlist, drawn: Netlist): View[] {
  const out: View[] = [
    { label: "Fixed, as it starts", mode: "fixed", netlist: fixed },
    { label: "As drawn", mode: "drawn", netlist: drawn },
  ];
  const switches = fixed.components.filter((c) => c.type === "switch" || c.type === "button");
  if (switches.length) {
    let flipped = fixed;
    const states: Record<string, boolean> = {};
    for (const s of switches) {
      states[s.id] = !s.closed;
      flipped = withSwitch(flipped, s.id, !s.closed);
    }
    out.push({ label: `Fixed, ${switches.map((s) => s.id).join(", ")} flipped`, mode: "fixed", switches: states, netlist: flipped });
  }
  return out;
}

const logsOf = (e: unknown): CallLog[] => {
  const x = e as { log?: CallLog; logs?: CallLog[] };
  return x.logs ?? (x.log ? [x.log] : []);
};

// Starts a run and returns its id at once; the work continues in the background and is
// saved after every step, so the page can poll and leaving it loses nothing.
export async function startRun(image: Buffer, source?: Source): Promise<string> {
  const sketch = await normaliseSketch(image);
  const run: Run = {
    id: newId(),
    createdAt: new Date().toISOString(),
    status: "reading",
    model: settings().model,
    provider: settings().provider,
    progress: { stage: "Reading the sketch", chars: 0 },
    sketch: { file: "sketch.jpg", width: sketch.width, height: sketch.height, hash: sketch.hash, source },
    rounds: [],
    calls: [],
  };
  await saveRun(run);
  await writeFile(run.id, "sketch.jpg", sketch.bytes);
  void execute(run, sketch.dataUrl, sketch.hash);
  return run.id;
}

async function execute(run: Run, sketch: string, hash: string) {
  let lastSave = 0;
  const progress = (stage: string) => (chars: number, thought: number) => {
    run.progress = { stage, chars, thought };
    if (Date.now() - lastSave > 1500) {
      lastSave = Date.now();
      void saveRun(run);
    }
  };

  try {
    const read = await readCircuit({ sketch, replayKey: `read-${hash}`, onProgress: progress("Reading the sketch") });
    run.calls.push(...read.logs);
    const circuit = { ...read.value, asDrawn: settle(read.value.asDrawn), fixed: settle(read.value.fixed) };
    run.read = circuit;
    run.via = read.via;
    run.repaired = read.repaired;
    run.status = "checking";
    await saveRun(run);

    run.check = checkIssues(circuit.issues, findMistakes(circuit.asDrawn));
    run.status = "building";
    run.progress = { stage: "Building the simulation", chars: 0 };
    await saveRun(run);

    const built = await buildSimulation({ read: circuit, sketch, replayKey: `build-${hash}`, onProgress: progress("Building the simulation") });
    run.calls.push(built.log);
    let html = built.html;

    for (let n = 1; n <= MAX_ROUNDS; n++) {
      run.status = "looking";
      run.progress = { stage: `Looking at round ${n}`, chars: 0 };
      const file = `round-${n}.html`;
      await writeFile(run.id, file, html);
      const shots = await capture(html, views(circuit.fixed, circuit.asDrawn));
      const round: Round = { n, file, shots: [] };
      for (const [i, s] of shots.entries()) {
        const name = `round-${n}-${i}.png`;
        await writeFile(run.id, name, s.png);
        const view = views(circuit.fixed, circuit.asDrawn)[i];
        round.shots.push({ label: s.label, file: name, errors: s.errors, mismatches: s.state ? agreement(view.netlist, s.state) : [] });
      }
      run.rounds.push(round);
      await saveRun(run);

      const mismatchText = round.shots
        .filter((s) => s.mismatches.length)
        .map((s) => `${s.label}:\n${describeMismatches(s.mismatches)}`)
        .join("\n");
      const clean = round.shots.every((s) => s.errors.length === 0 && s.mismatches.length === 0);
      if (n === MAX_ROUNDS) break;

      const { review, log } = await reviewSimulation({
        read: circuit,
        sketch,
        html,
        shots: shots.map((s) => ({ label: s.label, dataUrl: pngDataUrl(s.png), errors: s.errors })),
        mismatches: mismatchText,
        replayKey: `look-${hash}-${n}`,
        onProgress: progress(`Looking at round ${n}`),
      });
      run.calls.push(log);
      round.review = { ok: review.ok, problems: review.problems };
      await saveRun(run);
      if ((review.ok && clean) || !review.html) break;
      html = review.html;
    }

    const last = run.rounds.at(-1)!;
    run.result = {
      round: last.n,
      agrees: last.shots.every((s) => s.mismatches.length === 0 && s.errors.length === 0),
      // The last round is only reviewed when it ended the loop early.
      looksRight: last.review ? last.review.ok : null,
    };
    run.status = "done";
    run.progress = { stage: "Done", chars: 0 };
  } catch (e) {
    run.calls.push(...logsOf(e));
    run.status = "failed";
    run.error = e instanceof Error ? e.message : String(e);
  }
  await saveRun(run);
}
