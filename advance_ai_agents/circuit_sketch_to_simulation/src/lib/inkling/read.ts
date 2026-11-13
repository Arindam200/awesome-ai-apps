import { CircuitRead, submitCircuitTool } from "@/lib/schema/circuit";
import { deviceModelText } from "@/lib/sim/devices";
import { imagePart, type Message } from "./client";
import { askStructured } from "./structured";

const SYSTEM = `You read hand-drawn electronic circuit diagrams from photos and scans, the way an experienced lab instructor checks a student's notebook.

Read the drawing exactly as drawn first, mistakes included, then say what is wrong, then give a corrected circuit.

Reading rules:
- Every set of points joined by drawn lines is one net. Give nets short names (vcc, gnd, n1, n2...). Parts joined by a line share a net name.
- Lines that cross without a dot are not connected. A dot or a T-junction is a connection.
- Battery or cell: the long plate is plus. nodes = [plus, minus]. A battery with several cells is one battery whose value is the total.
- Resistor: zigzag or rectangle. LED: diode triangle with arrows pointing out; the flat bar is the cathode. nodes = [anode, cathode].
- Switch: a gap with a lever. Push button: a bridge over two contacts. Lamp: a circle with a cross or loop.
- Values are SI numbers: 220 for 220R or 220 ohm, 4700 for 4k7, 4.7e-6 for 4.7uF. Use null when no value is written. Never invent a value for asDrawn.
- If a drawn wire connects two nets that should be separate (for example straight across the battery), keep it in asDrawn as a wire part so the mistake is visible.
- box is where the symbol sits on the image: [x, y, width, height], each 0..1 from the top left.
- If a symbol is unclear, give your best reading with low confidence and add an ambiguous_symbol issue.

Mistakes to look for: an LED with no current-limiting resistor, a part in backwards, a short across the supply, a wire that goes nowhere, a missing value, a switch that can never affect the load.

The corrected circuit (fixed) changes as little as possible: keep every id and net name that stays, give new parts new ids, and pick standard values (E12 resistors). The app simulates it with these device models, so size your fixes for them:
${deviceModelText()}

Call the submit_circuit tool once with the full result. Do not answer in prose.`;

export type Example = { image: string; answer: CircuitRead };

export function readMessages(sketch: string, examples: Example[] = []): Message[] {
  const messages: Message[] = [{ role: "system", content: SYSTEM }];
  for (const [i, ex] of examples.entries()) {
    messages.push({
      role: "user",
      content: [
        { type: "text", text: `Worked example ${i + 1}. The correct submit_circuit arguments for this sketch follow.` },
        imagePart(ex.image),
      ],
    });
    messages.push({ role: "assistant", content: JSON.stringify(ex.answer) });
  }
  messages.push({ role: "user", content: [{ type: "text", text: "Read this circuit." }, imagePart(sketch)] });
  return messages;
}

export async function readCircuit(o: { sketch: string; replayKey: string; examples?: Example[]; onProgress?: (chars: number, thought: number) => void }) {
  return askStructured({
    stage: "read",
    replayKey: o.replayKey,
    messages: readMessages(o.sketch, o.examples),
    tool: submitCircuitTool,
    schema: CircuitRead,
    maxTokens: 48_000,
    onProgress: o.onProgress,
  });
}
