import { z } from "zod";

// One schema for what Inkling reads off a sketch, what the solver runs and what the
// generated simulation must agree with. Values are plain SI numbers (volts, ohms, farads).

export const COMPONENT_TYPES = [
  "battery", "resistor", "potentiometer", "led", "diode", "lamp", "switch", "button", "capacitor", "wire", "ground",
] as const;
export type ComponentType = (typeof COMPONENT_TYPES)[number];

export const ISSUE_KINDS = [
  "no_current_limit", "reversed_polarity", "short_circuit", "open_circuit", "missing_value", "ambiguous_symbol", "other",
] as const;
export type IssueKind = (typeof ISSUE_KINDS)[number];

export const LED_COLORS = ["red", "orange", "yellow", "green", "blue", "white"] as const;

// Normalised box on the sketch: x, y, width, height, each 0..1 from the top left.
const Box = z.tuple([z.number(), z.number(), z.number(), z.number()]);

export const Component = z.object({
  id: z.string().min(1),
  type: z.enum(COMPONENT_TYPES).catch("resistor"),
  // Net names. Two for most parts: battery [plus, minus], led/diode [anode, cathode];
  // potentiometer [end a, wiper, end b]; ground [net].
  nodes: z.array(z.string().min(1)).min(1).max(3),
  // Volts for a battery, ohms for a resistor, potentiometer or lamp, farads for a capacitor.
  // null when the sketch gives no value.
  value: z.number().nullable().catch(null),
  label: z.string().optional().catch(undefined),
  color: z.enum(LED_COLORS).optional().catch(undefined),
  closed: z.boolean().optional().catch(undefined),
  position: z.number().min(0).max(1).optional().catch(undefined),
  box: Box.optional().catch(undefined),
  confidence: z.number().min(0).max(1).optional().catch(undefined),
});
export type Component = z.infer<typeof Component>;

export const Issue = z.object({
  kind: z.enum(ISSUE_KINDS).catch("other"),
  componentIds: z.array(z.string()).catch([]),
  explanation: z.string(),
  fix: z.string().catch(""),
});
export type Issue = z.infer<typeof Issue>;

export const Netlist = z.object({ components: z.array(Component).min(1) });
export type Netlist = z.infer<typeof Netlist>;

export const CircuitRead = z.object({
  title: z.string().catch("Circuit"),
  summary: z.string().catch(""),
  asDrawn: Netlist,
  issues: z.array(Issue).catch([]),
  fixed: Netlist,
});
export type CircuitRead = z.infer<typeof CircuitRead>;

// JSON Schema for the submit_circuit tool. Written by hand so the model sees short,
// plain descriptions rather than zod internals.
const componentJson = {
  type: "object",
  required: ["id", "type", "nodes", "value"],
  properties: {
    id: { type: "string", description: "Short id like B1, R1, D1, S1, as labelled on the sketch when it has labels" },
    type: { type: "string", enum: [...COMPONENT_TYPES] },
    nodes: {
      type: "array", items: { type: "string" }, minItems: 1, maxItems: 3,
      description: "Net names. battery: [plus, minus]. led/diode: [anode, cathode]. potentiometer: [end, wiper, end]. ground: [net]. Parts joined by a drawn wire share a net name.",
    },
    value: { type: ["number", "null"], description: "SI number: volts, ohms or farads (220 for 220 ohm, 4.7e-6 for 4.7 uF). null if the sketch shows none." },
    label: { type: "string", description: "Text written next to the part, as written" },
    color: { type: "string", enum: [...LED_COLORS], description: "LED colour if written or implied" },
    closed: { type: "boolean", description: "Switch or button drawn closed" },
    position: { type: "number", description: "Potentiometer wiper position 0..1" },
    box: { type: "array", items: { type: "number" }, minItems: 4, maxItems: 4, description: "[x, y, w, h] of the symbol on the sketch, each 0..1 from the top left" },
    confidence: { type: "number", description: "0..1, how sure you are of this part" },
  },
};

export const submitCircuitTool = {
  type: "function" as const,
  function: {
    name: "submit_circuit",
    description: "Submit the circuit read from the sketch: the parts as drawn, the mistakes found and a corrected version.",
    parameters: {
      type: "object",
      required: ["title", "summary", "asDrawn", "issues", "fixed"],
      properties: {
        title: { type: "string", description: "What the circuit is meant to do, a few words" },
        summary: { type: "string", description: "One or two sentences on how it works" },
        asDrawn: { type: "object", required: ["components"], properties: { components: { type: "array", items: componentJson } } },
        issues: {
          type: "array",
          items: {
            type: "object", required: ["kind", "componentIds", "explanation", "fix"],
            properties: {
              kind: { type: "string", enum: [...ISSUE_KINDS] },
              componentIds: { type: "array", items: { type: "string" } },
              explanation: { type: "string" },
              fix: { type: "string" },
            },
          },
        },
        fixed: { type: "object", required: ["components"], properties: { components: { type: "array", items: componentJson } } },
      },
    },
  },
};
