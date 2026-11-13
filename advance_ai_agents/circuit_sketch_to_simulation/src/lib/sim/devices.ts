import type { Component, ComponentType } from "@/lib/schema/circuit";

// Device models shared by the solver and the prompt that asks Inkling to build the
// simulation, so both sides compute the same physics and can be compared number for number.
export const DEVICE = {
  batteryInternalOhms: 0.2,
  ledForwardVolts: { red: 1.8, orange: 1.9, yellow: 2.0, green: 2.1, blue: 3.0, white: 3.0 } as Record<string, number>,
  ledDefaultForwardVolts: 2.0,
  ledOnOhms: 10,
  ledRatedAmps: 0.02,
  ledMaxAmps: 0.03,
  diodeForwardVolts: 0.7,
  diodeOnOhms: 0.5,
  switchClosedOhms: 0.001,
  // Every net also leaks to ground through this tiny conductance so open parts never
  // leave the matrix singular.
  gmin: 1e-12,
} as const;

// Used when the sketch gives no value. The solver also reports these as missing_value.
export const DEFAULT_VALUE: Partial<Record<ComponentType, number>> = {
  battery: 9,
  resistor: 1000,
  potentiometer: 10000,
  capacitor: 100e-6,
  lamp: 20,
};

export const NEEDS_VALUE: ReadonlySet<ComponentType> = new Set(["battery", "resistor", "potentiometer", "capacitor"]);

export function valueOf(c: Component): number {
  return c.value ?? DEFAULT_VALUE[c.type] ?? 0;
}

export function forwardVolts(c: Component): number {
  if (c.type === "diode") return DEVICE.diodeForwardVolts;
  return (c.color && DEVICE.ledForwardVolts[c.color]) || DEVICE.ledDefaultForwardVolts;
}

export function onOhms(c: Component): number {
  return c.type === "diode" ? DEVICE.diodeOnOhms : DEVICE.ledOnOhms;
}

// Plain-language summary of the models for the build prompt.
export function deviceModelText(): string {
  const led = Object.entries(DEVICE.ledForwardVolts).map(([k, v]) => `${k} ${v} V`).join(", ");
  return [
    `Battery: ideal source in series with ${DEVICE.batteryInternalOhms} ohm internal resistance.`,
    `LED: off (no current) until anode-to-cathode voltage exceeds Vf, then I = (V - Vf) / ${DEVICE.ledOnOhms} ohm. Vf by colour: ${led}; ${DEVICE.ledDefaultForwardVolts} V if unknown. Rated ${DEVICE.ledRatedAmps * 1000} mA, burns out above ${DEVICE.ledMaxAmps * 1000} mA.`,
    `Diode: same model with Vf ${DEVICE.diodeForwardVolts} V and ${DEVICE.diodeOnOhms} ohm.`,
    `Switch or button: ${DEVICE.switchClosedOhms} ohm when closed, open circuit when open.`,
    `Lamp: a resistor (value in ohms, ${DEFAULT_VALUE.lamp} ohm if unknown). Potentiometer: two resistors split at the wiper position.`,
    `Capacitor: open circuit at DC.`,
    `Missing values: battery ${DEFAULT_VALUE.battery} V, resistor ${DEFAULT_VALUE.resistor} ohm, potentiometer ${DEFAULT_VALUE.potentiometer} ohm, capacitor ${DEFAULT_VALUE.capacitor} F.`,
  ].join("\n");
}
