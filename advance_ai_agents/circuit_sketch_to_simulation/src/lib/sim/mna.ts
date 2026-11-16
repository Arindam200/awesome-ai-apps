import type { Component, Netlist } from "@/lib/schema/circuit";
import { DEVICE, forwardVolts, onOhms, valueOf } from "./devices";

// Nodal analysis with every part reduced to conductances and current sources:
// batteries as Norton equivalents (so a short gives a large but finite current),
// LEDs and diodes as piecewise-linear switches iterated until their states settle,
// capacitors as backward-Euler companions in a transient run and open at DC.

export type PartResult = {
  id: string;
  type: Component["type"];
  // Current entering nodes[0] and leaving nodes[1]. For a battery: current delivered out of plus.
  current: number;
  // V(nodes[0]) - V(nodes[1]).
  voltage: number;
  power: number;
  on?: boolean;
  // 0..1 for LEDs and lamps.
  brightness?: number;
};

export type Solution = {
  // Voltage of every net name in the netlist, the reference net at 0 V.
  nodes: Record<string, number>;
  parts: Record<string, PartResult>;
  reference: string;
  converged: boolean;
};

type Topology = {
  index: Map<string, number>; // net name -> matrix row, -1 for the reference
  reference: string;
  size: number;
};

class UnionFind {
  parent = new Map<string, string>();
  find(a: string): string {
    if (!this.parent.has(a)) this.parent.set(a, a);
    let r = a;
    while (this.parent.get(r) !== r) r = this.parent.get(r)!;
    this.parent.set(a, r);
    return r;
  }
  union(a: string, b: string) {
    this.parent.set(this.find(a), this.find(b));
  }
}

export function nets(netlist: Netlist): string[] {
  const all = new Set<string>();
  for (const c of netlist.components) for (const n of c.nodes) all.add(n);
  return [...all];
}

function topology(netlist: Netlist): { topo: Topology; uf: UnionFind } {
  const uf = new UnionFind();
  for (const n of nets(netlist)) uf.find(n);
  for (const c of netlist.components) if (c.type === "wire" && c.nodes.length >= 2) uf.union(c.nodes[0], c.nodes[1]);
  const ground = netlist.components.find((c) => c.type === "ground");
  const battery = netlist.components.find((c) => c.type === "battery" && c.nodes.length >= 2);
  const reference = uf.find(ground?.nodes[0] ?? battery?.nodes[1] ?? netlist.components[0].nodes[0]);
  const index = new Map<string, number>();
  let size = 0;
  for (const n of nets(netlist)) {
    const root = uf.find(n);
    if (root === reference) index.set(root, -1);
    else if (!index.has(root)) index.set(root, size++);
  }
  return { topo: { index, reference, size }, uf };
}

type Stamp = { G: number[][]; I: number[] };

function row(topo: Topology, uf: UnionFind, net: string): number {
  return topo.index.get(uf.find(net)) ?? -1;
}

function conductance(s: Stamp, a: number, b: number, g: number) {
  if (a >= 0) s.G[a][a] += g;
  if (b >= 0) s.G[b][b] += g;
  if (a >= 0 && b >= 0) {
    s.G[a][b] -= g;
    s.G[b][a] -= g;
  }
}

// A source pushing current i into node a and out of node b.
function source(s: Stamp, a: number, b: number, i: number) {
  if (a >= 0) s.I[a] += i;
  if (b >= 0) s.I[b] -= i;
}

function gaussian(G: number[][], I: number[]): number[] {
  const n = I.length;
  const A = G.map((r, i) => [...r, I[i]]);
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(A[r][col]) > Math.abs(A[pivot][col])) pivot = r;
    [A[col], A[pivot]] = [A[pivot], A[col]];
    const p = A[col][col];
    if (Math.abs(p) < 1e-300) continue;
    for (let r = col + 1; r < n; r++) {
      const f = A[r][col] / p;
      if (f === 0) continue;
      for (let k = col; k <= n; k++) A[r][k] -= f * A[col][k];
    }
  }
  const x = new Array<number>(n).fill(0);
  for (let r = n - 1; r >= 0; r--) {
    let sum = A[r][n];
    for (let k = r + 1; k < n; k++) sum -= A[r][k] * x[k];
    x[r] = Math.abs(A[r][r]) < 1e-300 ? 0 : sum / A[r][r];
  }
  return x;
}

function isSwitch(c: Component) {
  return c.type === "switch" || c.type === "button";
}

function isClosed(c: Component) {
  // A drawn switch with no state is treated as closed, a push button as released.
  return c.closed ?? c.type === "switch";
}

function resistorParts(c: Component): [number, number, number][] {
  // [node index into c.nodes, node index, ohms]
  if (c.type === "potentiometer" && c.nodes.length === 3) {
    const r = Math.max(valueOf(c), 1e-3);
    const p = c.position ?? 0.5;
    return [[0, 1, Math.max(r * p, 1e-3)], [1, 2, Math.max(r * (1 - p), 1e-3)]];
  }
  if (c.type === "potentiometer") return [[0, 1, Math.max(valueOf(c), 1e-3)]];
  return [[0, 1, Math.max(valueOf(c), 1e-6)]];
}

type Options = {
  // Capacitor voltages from the previous step and the step size, for a transient run.
  caps?: Map<string, number>;
  dt?: number;
};

export function solve(netlist: Netlist, opts: Options = {}): Solution {
  const { topo, uf } = topology(netlist);
  const diodes = netlist.components.filter((c) => (c.type === "led" || c.type === "diode") && c.nodes.length >= 2);
  const on = new Map<string, boolean>(diodes.map((d) => [d.id, false]));
  let x: number[] = [];
  let converged = false;

  const v = (net: string) => {
    const r = row(topo, uf, net);
    return r < 0 ? 0 : x[r];
  };

  for (let iter = 0; iter < 60; iter++) {
    const s: Stamp = {
      G: Array.from({ length: topo.size }, () => new Array<number>(topo.size).fill(0)),
      I: new Array<number>(topo.size).fill(0),
    };
    for (let i = 0; i < topo.size; i++) s.G[i][i] += DEVICE.gmin;

    for (const c of netlist.components) {
      if (c.nodes.length < 2 && c.type !== "ground") continue;
      const a = row(topo, uf, c.nodes[0]);
      const b = c.nodes.length >= 2 ? row(topo, uf, c.nodes[1]) : -1;
      switch (c.type) {
        case "battery": {
          const g = 1 / DEVICE.batteryInternalOhms;
          conductance(s, a, b, g);
          source(s, a, b, valueOf(c) * g);
          break;
        }
        case "resistor":
        case "lamp":
        case "potentiometer":
          for (const [i, j, ohms] of resistorParts(c)) conductance(s, row(topo, uf, c.nodes[i]), row(topo, uf, c.nodes[j]), 1 / ohms);
          break;
        case "switch":
        case "button":
          if (isClosed(c)) conductance(s, a, b, 1 / DEVICE.switchClosedOhms);
          break;
        case "led":
        case "diode":
          if (on.get(c.id)) {
            const g = 1 / onOhms(c);
            conductance(s, a, b, g);
            source(s, a, b, forwardVolts(c) * g);
          }
          break;
        case "capacitor":
          if (opts.dt && opts.caps) {
            const g = valueOf(c) / opts.dt;
            conductance(s, a, b, g);
            source(s, a, b, (opts.caps.get(c.id) ?? 0) * g);
          }
          break;
        case "wire":
        case "ground":
          break;
      }
    }

    x = gaussian(s.G, s.I);
    let changed = false;
    for (const d of diodes) {
      const vak = v(d.nodes[0]) - v(d.nodes[1]);
      const isOn = on.get(d.id)!;
      const current = isOn ? (vak - forwardVolts(d)) / onOhms(d) : 0;
      if (!isOn && vak > forwardVolts(d) + 1e-9) {
        on.set(d.id, true);
        changed = true;
      } else if (isOn && current < -1e-12) {
        on.set(d.id, false);
        changed = true;
      }
    }
    if (!changed) {
      converged = true;
      break;
    }
  }

  const nodes: Record<string, number> = {};
  for (const n of nets(netlist)) nodes[n] = v(n);

  const maxBattery = Math.max(0, ...netlist.components.filter((c) => c.type === "battery").map(valueOf));
  const parts: Record<string, PartResult> = {};
  for (const c of netlist.components) {
    const va = v(c.nodes[0]);
    const vb = c.nodes.length >= 2 ? v(c.nodes[1]) : 0;
    const vab = va - vb;
    let current = 0;
    const extra: Partial<PartResult> = {};
    switch (c.type) {
      case "battery":
        current = (valueOf(c) - vab) / DEVICE.batteryInternalOhms;
        break;
      case "resistor":
      case "lamp":
        current = vab / Math.max(valueOf(c), 1e-6);
        if (c.type === "lamp") {
          const rated = maxBattery > 0 ? (maxBattery * maxBattery) / Math.max(valueOf(c), 1e-6) : 1;
          extra.brightness = clamp01((vab * current) / rated);
        }
        break;
      case "potentiometer": {
        const [i, j, ohms] = resistorParts(c)[0];
        current = (v(c.nodes[i]) - v(c.nodes[j])) / ohms;
        break;
      }
      case "switch":
      case "button":
        current = isClosed(c) ? vab / DEVICE.switchClosedOhms : 0;
        break;
      case "led":
      case "diode":
        extra.on = on.get(c.id) ?? false;
        current = extra.on ? (vab - forwardVolts(c)) / onOhms(c) : 0;
        if (c.type === "led") extra.brightness = clamp01(current / DEVICE.ledRatedAmps);
        break;
      case "capacitor":
        current = opts.dt && opts.caps ? (valueOf(c) / opts.dt) * (vab - (opts.caps.get(c.id) ?? 0)) : 0;
        break;
      case "wire":
      case "ground":
        break;
    }
    parts[c.id] = { id: c.id, type: c.type, current, voltage: vab, power: Math.abs(vab * current), ...extra };
  }
  return { nodes, parts, reference: topo.reference, converged };
}

export type Sample = { t: number; nodes: Record<string, number>; parts: Record<string, PartResult> };

// Transient run from all capacitors discharged.
export function simulate(netlist: Netlist, duration: number, dt: number): Sample[] {
  const caps = new Map<string, number>();
  for (const c of netlist.components) if (c.type === "capacitor") caps.set(c.id, 0);
  const out: Sample[] = [];
  for (let t = dt; t <= duration + dt / 2; t += dt) {
    const sol = solve(netlist, { caps, dt });
    for (const c of netlist.components) if (c.type === "capacitor") caps.set(c.id, sol.parts[c.id].voltage);
    out.push({ t, nodes: sol.nodes, parts: sol.parts });
  }
  return out;
}

export function withSwitch(netlist: Netlist, id: string, closed: boolean): Netlist {
  return { components: netlist.components.map((c) => (c.id === id && isSwitch(c) ? { ...c, closed } : c)) };
}

function clamp01(n: number) {
  return Math.max(0, Math.min(1, n));
}
