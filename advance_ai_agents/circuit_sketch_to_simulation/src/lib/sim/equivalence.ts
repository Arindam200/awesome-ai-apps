import type { ComponentType, Netlist } from "@/lib/schema/circuit";
import { valueOf } from "./devices";
import { solve, type Solution } from "./mna";

// Two netlists describe the same circuit when, with the same switch settings, every part
// carries the same current and voltage. Ids and net names may differ, so parts are paired by
// type and value, then by their electrical result. This avoids fragile graph matching.

type Signature = { type: ComponentType; value: number; current: number; voltage: number };

const ELECTRICAL: ReadonlySet<ComponentType> = new Set(["battery", "resistor", "potentiometer", "led", "diode", "lamp", "capacitor"]);

function signature(netlist: Netlist, sol: Solution): Signature[] {
  return netlist.components
    .filter((c) => ELECTRICAL.has(c.type))
    .map((c) => ({ type: c.type, value: valueOf(c), current: Math.abs(sol.parts[c.id].current), voltage: Math.abs(sol.parts[c.id].voltage) }));
}

function close(a: number, b: number, rel: number, abs: number) {
  return Math.abs(a - b) <= Math.max(abs, rel * Math.max(Math.abs(a), Math.abs(b)));
}

function setSwitches(netlist: Netlist, closed: boolean): Netlist {
  return { components: netlist.components.map((c) => (c.type === "switch" || c.type === "button" ? { ...c, closed } : c)) };
}

export type Equivalence = { same: boolean; reason?: string };

export function equivalent(a: Netlist, b: Netlist, rel = 0.02, abs = 1e-4): Equivalence {
  for (const closed of [true, false]) {
    const na = setSwitches(a, closed);
    const nb = setSwitches(b, closed);
    const sa = signature(na, solve(na));
    const sb = signature(nb, solve(nb));
    if (sa.length !== sb.length) return { same: false, reason: `${sa.length} vs ${sb.length} parts` };
    const left = [...sb];
    for (const s of sa) {
      const i = left.findIndex(
        (t) => t.type === s.type && close(t.value, s.value, 0.01, 1e-12) && close(t.current, s.current, rel, abs) && close(t.voltage, s.voltage, rel, 1e-3),
      );
      if (i < 0) return { same: false, reason: `no match for a ${s.type} of ${s.value} (switches ${closed ? "closed" : "open"})` };
      left.splice(i, 1);
    }
  }
  return { same: true };
}
