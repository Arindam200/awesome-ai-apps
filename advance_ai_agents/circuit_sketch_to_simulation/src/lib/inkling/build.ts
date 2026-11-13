import type { CircuitRead, Netlist } from "@/lib/schema/circuit";
import { deviceModelText } from "@/lib/sim/devices";
import { ask, imagePart, InklingError, type CallLog, type Message } from "./client";

export function referenceNet(n: Netlist): string {
  return n.components.find((c) => c.type === "ground")?.nodes[0] ?? n.components.find((c) => c.type === "battery")?.nodes[1] ?? n.components[0].nodes[0];
}

const CONTRACT = `The page must define, before the load event ends:
window.__sim = {
  setMode(mode),            // "fixed" or "drawn": which netlist is shown and simulated
  setSwitch(id, closed),    // switch or button state
  setValue(id, value),      // SI value of a battery, resistor, potentiometer, lamp or capacitor
  setPosition(id, p),       // potentiometer wiper 0..1
  state()                   // returns { mode, nodes: { [net]: volts }, parts: { [id]: { current, voltage, on?, brightness? } } }
}
Conventions for state(): volts are measured from the reference net (0 V). current is the current entering a part at nodes[0] and leaving at nodes[1]; for a battery it is the current delivered out of its plus terminal. voltage is V(nodes[0]) - V(nodes[1]). brightness is 0..1 for LEDs and lamps. Every net name and every part id in the netlist must appear in state().`;

const SYSTEM = `You build interactive circuit simulations as one self-contained HTML file for engineers.

Requirements:
- One file, inline CSS and JavaScript only. No external scripts, fonts, images or network requests: the page runs under a CSP that blocks them.
- Draw the circuit as a clean schematic in SVG, laid out like the original sketch: use each part's box (x, y, w, h from the top left, 0..1) to place it, snap to a grid, and route wires with right angles.
- Solve the circuit yourself in JavaScript with nodal analysis using exactly the device models given, and re-solve after every interaction.
- Interaction: click a switch to toggle it; hold a push button to press it; sliders for battery voltage, resistor and potentiometer values; hovering a part shows its current and voltage; clicking a net shows its voltage.
- Show it working: LEDs and lamps glow in proportion to brightness; an LED above its maximum current is drawn burnt out with a short note; dots move along wires in the direction of conventional current, faster for more current.
- A toggle at the top switches between "As drawn" and "Fixed". Start in "Fixed". In "As drawn", the mistakes should be visible (a burnt LED, a dead lamp, a short marked in red).
- Show the list of mistakes found next to the circuit.
- Look: background #001A2B, panels #052B42, wires #C1C1FF, highlights and current dots #DAFF33, text white, font: Inter, Arial, sans-serif. Sentence case everywhere: no all-caps labels, no emoji, no italics.
- Fits 1100x720. On a phone (390 px wide) the panels stack and the schematic SVG scales down to the full width (viewBox with width 100%); never crop it or make the page scroll sideways.

${CONTRACT}

Device models:
${deviceModelText()}

Reply with the complete file in one \`\`\`html block and nothing else.`;

export function buildMessages(read: CircuitRead, sketch: string): Message[] {
  const payload = {
    title: read.title,
    summary: read.summary,
    referenceNet: { fixed: referenceNet(read.fixed), drawn: referenceNet(read.asDrawn) },
    fixed: read.fixed,
    asDrawn: read.asDrawn,
    mistakes: read.issues,
  };
  return [
    { role: "system", content: SYSTEM },
    {
      role: "user",
      content: [
        { type: "text", text: `Build the simulation for this circuit. The original sketch is attached for layout.\n\n${JSON.stringify(payload, null, 1)}` },
        imagePart(sketch),
      ],
    },
  ];
}

// Reasoning models can spend most of the output budget thinking; leave room for a full file.
export const MAX_OUTPUT = 120_000;

export function extractHtml(text: string): string | null {
  // A closed fence, else an unclosed one (the reply was cut off), else the whole text.
  const fenced = text.match(/```html\s*([\s\S]*?)```/i) ?? text.match(/```\s*(<!doctype[\s\S]*?)```/i) ?? text.match(/```html\s*([\s\S]*)$/i);
  const body = (fenced ? fenced[1] : text).trim();
  if (/<html|<!doctype|<svg|<body/i.test(body)) return body;
  return null;
}

export async function buildSimulation(o: { read: CircuitRead; sketch: string; replayKey: string; onProgress?: (chars: number, thought: number) => void }): Promise<{ html: string; log: CallLog }> {
  const { reply, log } = await ask({ stage: "build", replayKey: o.replayKey, messages: buildMessages(o.read, o.sketch), maxTokens: MAX_OUTPUT, onProgress: o.onProgress });
  if (reply.finishReason === "length")
    throw Object.assign(new InklingError(`The build reply hit the ${MAX_OUTPUT.toLocaleString("en")} token output limit (${reply.usage.reasoning.toLocaleString("en")} of them reasoning) before the HTML file was complete. Run it again.`, "output"), { logs: [log] });
  const html = extractHtml(reply.text);
  if (!html) throw Object.assign(new InklingError("The build reply had no HTML file.", "output"), { logs: [log] });
  return { html, log };
}

const REVIEW = `You check an interactive circuit simulation you built, by looking at it.

You get: the original hand-drawn sketch, screenshots of your simulation in several states, the numbers a reference solver computed for the same circuit where your simulation disagrees, any JavaScript errors, and the current source.

Check that the schematic matches the sketch (every part present, connected the same way, laid out alike), that it looks right in each state (LEDs lit or dark as they should be, burnt-out parts marked, current dots where current flows), that the text is readable and nothing overlaps, and that window.__sim reports numbers that match the reference solver.

${CONTRACT}

Device models:
${deviceModelText()}

Reply in this format:
VERDICT: ok
or
VERDICT: fix
- one line per problem you see
followed by the complete corrected file in one \`\`\`html block.`;

export type ReviewInput = {
  read: CircuitRead;
  sketch: string;
  html: string;
  shots: { label: string; dataUrl: string; errors: string[] }[];
  mismatches: string;
};

export function reviewMessages(r: ReviewInput): Message[] {
  const content: Message["content"] = [
    { type: "text", text: "Original sketch:" },
    imagePart(r.sketch),
  ];
  for (const s of r.shots) {
    content.push({ type: "text", text: `Screenshot: ${s.label}${s.errors.length ? `\nErrors: ${s.errors.join(" | ")}` : ""}` });
    content.push(imagePart(s.dataUrl));
  }
  content.push({
    type: "text",
    text: `Reference solver disagreements:\n${r.mismatches || "none"}\n\nNetlists:\n${JSON.stringify({ fixed: r.read.fixed, asDrawn: r.read.asDrawn }, null, 1)}\n\nCurrent source:\n\`\`\`html\n${r.html}\n\`\`\``,
  });
  return [
    { role: "system", content: REVIEW },
    { role: "user", content },
  ];
}

export type Review = { ok: boolean; problems: string[]; html: string | null };

export function parseReview(text: string): Review {
  const verdict = text.match(/VERDICT:\s*(ok|fix)/i)?.[1]?.toLowerCase();
  const html = extractHtml(text.replace(/^[\s\S]*?(?=```html)/i, ""));
  const before = text.split(/```/)[0];
  const problems = before
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => /^[-*]\s+/.test(l))
    .map((l) => l.replace(/^[-*]\s+/, ""));
  return { ok: verdict === "ok" || (!verdict && !html), problems, html: verdict === "ok" ? null : html };
}

export async function reviewSimulation(o: ReviewInput & { replayKey: string; onProgress?: (chars: number, thought: number) => void }): Promise<{ review: Review; log: CallLog }> {
  const { reply, log } = await ask({ stage: "look", replayKey: o.replayKey, messages: reviewMessages(o), maxTokens: MAX_OUTPUT, onProgress: o.onProgress });
  const review = parseReview(reply.text);
  // A cut-off fix is not a file; keep the current one and record why.
  if (reply.finishReason === "length" && review.html) return { review: { ...review, html: null, problems: [...review.problems, "The corrected file was cut off at the output limit, so the previous version was kept."] }, log };
  return { review, log };
}
