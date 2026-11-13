import { describe, expect, it } from "vitest";
import type { Component, Netlist } from "@/lib/schema/circuit";
import { solve, simulate, withSwitch } from "./mna";
import { checkIssues, findMistakes } from "./checks";
import { equivalent } from "./equivalence";
import { toSpice } from "./spice";

const part = (id: string, type: Component["type"], nodes: string[], value: number | null = null, extra: Partial<Component> = {}): Component => ({
  id, type, nodes, value, ...extra,
});
const net = (...components: Component[]): Netlist => ({ components });

const ledWithResistor = net(
  part("B1", "battery", ["vcc", "gnd"], 9),
  part("R1", "resistor", ["vcc", "a"], 330),
  part("D1", "led", ["a", "gnd"], null, { color: "red" }),
);

describe("solver", () => {
  it("solves a voltage divider", () => {
    const sol = solve(net(part("B1", "battery", ["vcc", "gnd"], 9), part("R1", "resistor", ["vcc", "mid"], 1000), part("R2", "resistor", ["mid", "gnd"], 2000)));
    expect(sol.nodes.mid).toBeCloseTo((9 * 2000) / 3000.2, 3);
    expect(sol.parts.B1.current).toBeCloseTo(9 / 3000.2, 6);
  });

  it("lights an LED through a resistor at about 21 mA", () => {
    const sol = solve(ledWithResistor);
    expect(sol.converged).toBe(true);
    expect(sol.parts.D1.on).toBe(true);
    expect(sol.parts.D1.current).toBeCloseTo((9 - 1.8) / 340.2, 5);
    expect(findMistakes(ledWithResistor)).toEqual([]);
  });

  it("flags an LED with no resistor", () => {
    const n = net(part("B1", "battery", ["vcc", "gnd"], 9), part("D1", "led", ["vcc", "gnd"], null, { color: "red" }));
    const sol = solve(n);
    expect(sol.parts.D1.current).toBeGreaterThan(0.5);
    expect(findMistakes(n, sol).map((f) => f.kind)).toEqual(["no_current_limit"]);
  });

  it("flags a reversed LED and passes no current", () => {
    const n = net(part("B1", "battery", ["vcc", "gnd"], 9), part("R1", "resistor", ["vcc", "a"], 330), part("D1", "led", ["gnd", "a"], null, { color: "red" }));
    const sol = solve(n);
    expect(sol.parts.D1.on).toBe(false);
    expect(Math.abs(sol.parts.R1.current)).toBeLessThan(1e-6);
    expect(findMistakes(n, sol).map((f) => f.kind)).toEqual(["reversed_polarity"]);
  });

  it("flags a wire or closed switch across the battery as a short", () => {
    const wire = net(part("B1", "battery", ["vcc", "gnd"], 9), part("W1", "wire", ["vcc", "gnd"]), part("R1", "resistor", ["vcc", "gnd"], 100));
    expect(findMistakes(wire).map((f) => f.kind)).toContain("short_circuit");
    const sw = net(part("B1", "battery", ["vcc", "gnd"], 9), part("S1", "switch", ["vcc", "gnd"], null, { closed: true }));
    expect(solve(sw).parts.B1.current).toBeGreaterThan(40);
    expect(findMistakes(withSwitch(sw, "S1", false)).map((f) => f.kind)).not.toContain("short_circuit");
  });

  it("switches an LED off and on", () => {
    const n = net(
      part("B1", "battery", ["vcc", "gnd"], 9), part("S1", "switch", ["vcc", "s"], null, { closed: false }),
      part("R1", "resistor", ["s", "a"], 470), part("D1", "led", ["a", "gnd"], null, { color: "green" }),
    );
    expect(solve(n).parts.D1.on).toBe(false);
    const closed = solve(withSwitch(n, "S1", true));
    expect(closed.parts.D1.on).toBe(true);
    expect(closed.parts.D1.brightness).toBeGreaterThan(0.6);
  });

  it("charges a capacitor with the RC time constant", () => {
    const n = net(part("B1", "battery", ["vcc", "gnd"], 9), part("R1", "resistor", ["vcc", "c"], 1000), part("C1", "capacitor", ["c", "gnd"], 100e-6));
    const run = simulate(n, 0.1, 1e-4);
    const atTau = run.at(-1)!.nodes.c;
    expect(atTau).toBeGreaterThan(9 * 0.625);
    expect(atTau).toBeLessThan(9 * 0.64);
    expect(solve(n).nodes.c).toBeCloseTo(9, 2);
  });

  it("splits a potentiometer at the wiper", () => {
    const n = net(part("B1", "battery", ["vcc", "gnd"], 10), part("P1", "potentiometer", ["vcc", "w", "gnd"], 10000, { position: 0.25 }));
    expect(solve(n).nodes.w).toBeCloseTo((10 * 7500) / 10000.2, 2);
  });

  it("flags a wire to nowhere and a missing value", () => {
    const n = net(part("B1", "battery", ["vcc", "gnd"], 9), part("R1", "resistor", ["vcc", "gnd"]), part("R2", "resistor", ["vcc", "dangling"], 100));
    const kinds = findMistakes(n).map((f) => f.kind).sort();
    expect(kinds).toEqual(["missing_value", "open_circuit"]);
  });
});

describe("issue check", () => {
  it("confirms, rejects and keeps model-only issues apart", () => {
    const n = net(part("B1", "battery", ["vcc", "gnd"], 9), part("D1", "led", ["vcc", "gnd"], null, { color: "red" }));
    const { issues, solverOnly } = checkIssues(
      [
        { kind: "no_current_limit", componentIds: ["D1"], explanation: "no resistor", fix: "add 330 ohm" },
        { kind: "short_circuit", componentIds: ["B1"], explanation: "short", fix: "" },
        { kind: "ambiguous_symbol", componentIds: ["D1"], explanation: "could be a diode", fix: "" },
      ],
      findMistakes(n),
    );
    expect(issues.map((i) => i.verdict)).toEqual(["confirmed", "not_reproduced", "model_only"]);
    expect(solverOnly).toEqual([]);
  });
});

describe("equivalence", () => {
  it("matches the same circuit with other ids and net names", () => {
    const renamed = net(
      part("V", "battery", ["p", "n"], 9),
      part("LED", "led", ["x", "n"], null, { color: "red" }),
      part("Rx", "resistor", ["p", "x"], 330),
    );
    expect(equivalent(ledWithResistor, renamed).same).toBe(true);
  });

  it("tells a different circuit apart", () => {
    const parallel = net(part("B1", "battery", ["vcc", "gnd"], 9), part("R1", "resistor", ["vcc", "gnd"], 330), part("D1", "led", ["vcc", "gnd"], null, { color: "red" }));
    expect(equivalent(ledWithResistor, parallel).same).toBe(false);
  });
});

describe("spice", () => {
  it("writes a deck with the battery's internal resistance and a diode model", () => {
    const deck = toSpice(ledWithResistor);
    expect(deck).toContain("VB1 vcc B1_int DC 9");
    expect(deck).toContain("RB1_int B1_int 0 0.2");
    expect(deck).toMatch(/DD1 a 0 D_D1/);
    expect(deck.trim().endsWith(".end")).toBe(true);
  });
});
