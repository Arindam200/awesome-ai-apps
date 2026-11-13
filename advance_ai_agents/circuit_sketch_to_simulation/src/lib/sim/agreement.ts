import type { Netlist } from "@/lib/schema/circuit";
import { solve } from "./mna";

// What the generated simulation reports through window.__sim.state().
export type SimState = {
  mode?: string;
  nodes?: Record<string, number>;
  parts?: Record<string, { current?: number; voltage?: number; on?: boolean; brightness?: number }>;
};

export type Mismatch = { what: string; expected: number; got: number | null };

const voltsOk = (a: number, b: number) => Math.abs(a - b) <= Math.max(0.05, 0.03 * Math.abs(a));
const ampsOk = (a: number, b: number) => Math.abs(a - b) <= Math.max(0.0005, 0.03 * Math.abs(a));

// Compare the generated simulation's numbers with the solver's for the same netlist and settings.
export function agreement(netlist: Netlist, state: SimState): Mismatch[] {
  const sol = solve(netlist);
  const out: Mismatch[] = [];
  for (const [net, v] of Object.entries(sol.nodes)) {
    const got = state.nodes?.[net];
    if (typeof got !== "number" || !Number.isFinite(got)) out.push({ what: `voltage at net ${net}`, expected: v, got: null });
    else if (!voltsOk(v, got)) out.push({ what: `voltage at net ${net}`, expected: v, got });
  }
  for (const c of netlist.components) {
    if (c.type === "wire" || c.type === "ground") continue;
    const want = sol.parts[c.id].current;
    const got = state.parts?.[c.id]?.current;
    if (typeof got !== "number" || !Number.isFinite(got)) out.push({ what: `current through ${c.id}`, expected: want, got: null });
    else if (!ampsOk(want, got)) out.push({ what: `current through ${c.id}`, expected: want, got });
  }
  return out;
}

export function describeMismatches(m: Mismatch[]): string {
  return m
    .slice(0, 20)
    .map((x) => `- ${x.what}: solver ${fmt(x.expected, x.what)}, simulation ${x.got == null ? "missing" : fmt(x.got, x.what)}`)
    .join("\n");
}

function fmt(n: number, what: string) {
  return what.startsWith("current") ? `${(n * 1000).toFixed(2)} mA` : `${n.toFixed(3)} V`;
}
