import type { Issue, IssueKind, Netlist } from "@/lib/schema/circuit";
import { DEVICE, NEEDS_VALUE, forwardVolts, valueOf } from "./devices";
import { solve, type Solution } from "./mna";

// Mistakes the solver can prove on its own, with no help from the model.
export type Finding = { kind: IssueKind; componentIds: string[]; detail: string };

const SOLVER_KINDS: ReadonlySet<IssueKind> = new Set(["no_current_limit", "reversed_polarity", "short_circuit", "open_circuit", "missing_value"]);

export function findMistakes(netlist: Netlist, sol: Solution = solve(netlist)): Finding[] {
  const out: Finding[] = [];
  const mA = (a: number) => `${(a * 1000).toFixed(a < 0.1 ? 1 : 0)} mA`;

  for (const c of netlist.components) {
    const p = sol.parts[c.id];
    if (c.value == null && NEEDS_VALUE.has(c.type)) {
      out.push({ kind: "missing_value", componentIds: [c.id], detail: `${c.id} has no value; simulated with ${valueOf(c)}.` });
    }
    if (c.type === "battery" && c.nodes.length >= 2) {
      const limit = valueOf(c) / DEVICE.batteryInternalOhms;
      if (p.current > 0.5 * limit && p.current > 0.5) {
        out.push({ kind: "short_circuit", componentIds: [c.id], detail: `${c.id} drives ${p.current.toFixed(1)} A, near its short-circuit limit of ${limit.toFixed(0)} A.` });
      }
    }
    if (c.type === "led" && p.current > DEVICE.ledMaxAmps) {
      out.push({ kind: "no_current_limit", componentIds: [c.id], detail: `${c.id} carries ${mA(p.current)}; it burns out above ${mA(DEVICE.ledMaxAmps)}.` });
    }
    if ((c.type === "led" || c.type === "diode") && !p.on && -p.voltage > forwardVolts(c)) {
      out.push({ kind: "reversed_polarity", componentIds: [c.id], detail: `${c.id} sees ${(-p.voltage).toFixed(2)} V in reverse; turned around it would conduct.` });
    }
  }

  // A net that only one terminal touches is a wire to nowhere.
  const touches = new Map<string, string[]>();
  for (const c of netlist.components) {
    if (c.type === "ground") continue;
    for (const n of c.nodes) touches.set(n, [...(touches.get(n) ?? []), c.id]);
  }
  const grounded = new Set(netlist.components.filter((c) => c.type === "ground").map((c) => c.nodes[0]));
  for (const [net, ids] of touches) {
    if (ids.length === 1 && !grounded.has(net)) {
      out.push({ kind: "open_circuit", componentIds: ids, detail: `Net "${net}" ends at ${ids[0]} and connects to nothing else.` });
    }
  }
  return out;
}

export type Verdict = "confirmed" | "not_reproduced" | "model_only";
export type CheckedIssue = Issue & { verdict: Verdict; evidence?: string };

// Match each issue the model reported against the solver's own findings on the as-drawn circuit.
export function checkIssues(issues: Issue[], findings: Finding[]): { issues: CheckedIssue[]; solverOnly: Finding[] } {
  const used = new Set<Finding>();
  const checked = issues.map((issue): CheckedIssue => {
    if (!SOLVER_KINDS.has(issue.kind)) return { ...issue, verdict: "model_only" };
    const match =
      findings.find((f) => !used.has(f) && f.kind === issue.kind && f.componentIds.some((id) => issue.componentIds.includes(id))) ??
      findings.find((f) => !used.has(f) && f.kind === issue.kind);
    if (!match) return { ...issue, verdict: "not_reproduced" };
    used.add(match);
    return { ...issue, verdict: "confirmed", evidence: match.detail };
  });
  return { issues: checked, solverOnly: findings.filter((f) => !used.has(f)) };
}
