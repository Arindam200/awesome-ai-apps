import { describe, expect, it } from "vitest";
import { CircuitRead } from "@/lib/schema/circuit";
import { extractJson } from "./structured";
import { extractHtml, parseReview, referenceNet } from "./build";
import { settle } from "@/lib/pipeline";
import { lockDown } from "@/lib/csp";

describe("structured output", () => {
  it("pulls JSON out of prose and fenced blocks, repairing small faults", () => {
    expect(extractJson('Here you go:\n```json\n{"a": 1,}\n```')).toEqual({ a: 1 });
    expect(extractJson('The circuit is {"title": "LED", "ok": true} as read.')).toEqual({ title: "LED", ok: true });
    expect(() => extractJson("no json here")).toThrow();
  });

  it("keeps a read with one bad enum instead of failing it", () => {
    const r = CircuitRead.parse({
      title: "LED",
      summary: "",
      asDrawn: { components: [{ id: "D1", type: "light-emitting diode", nodes: ["a", "b"], value: null }] },
      issues: [{ kind: "too much current", componentIds: ["D1"], explanation: "x", fix: "y" }],
      fixed: { components: [{ id: "D1", type: "led", nodes: ["a", "b"], value: null, color: "pink" }] },
    });
    expect(r.asDrawn.components[0].type).toBe("resistor");
    expect(r.issues[0].kind).toBe("other");
    expect(r.fixed.components[0].color).toBeUndefined();
  });
});

describe("build replies", () => {
  it("extracts the HTML file", () => {
    expect(extractHtml("Sure.\n```html\n<!doctype html><html></html>\n```")).toBe("<!doctype html><html></html>");
    expect(extractHtml("I cannot do that.")).toBeNull();
  });

  it("reads review verdicts", () => {
    expect(parseReview("VERDICT: ok")).toEqual({ ok: true, problems: [], html: null });
    const fix = parseReview("VERDICT: fix\n- R1 is missing\n- LED never lights\n```html\n<html><body>x</body></html>\n```");
    expect(fix.ok).toBe(false);
    expect(fix.problems).toEqual(["R1 is missing", "LED never lights"]);
    expect(fix.html).toContain("<body>x</body>");
  });

  it("uses ground, else the battery's minus, as the reference net", () => {
    expect(referenceNet({ components: [{ id: "B1", type: "battery", nodes: ["p", "n"], value: 9 }] })).toBe("n");
    expect(referenceNet({ components: [{ id: "B1", type: "battery", nodes: ["p", "n"], value: 9 }, { id: "G", type: "ground", nodes: ["p"], value: null }] })).toBe("p");
  });

  it("makes switch states explicit", () => {
    const n = settle({ components: [{ id: "S1", type: "switch", nodes: ["a", "b"], value: null }, { id: "K1", type: "button", nodes: ["a", "b"], value: null }] });
    expect(n.components.map((c) => c.closed)).toEqual([true, false]);
  });

  it("puts the CSP first and drops stray text before the page", () => {
    expect(lockDown("<!DOCTYPE html><html><head><title>x</title></head></html>")).toMatch(/^<!DOCTYPE html><meta http-equiv="Content-Security-Policy" content="default-src 'none'/);
    expect(lockDown("```html\n<!DOCTYPE html><html>")).not.toContain("```");
    expect(lockDown("<svg></svg>")).toMatch(/^<!doctype html><meta http-equiv="Content-Security-Policy"[^>]*><svg>/);
  });

  it("extracts HTML from a reply cut off before its closing fence", () => {
    expect(extractHtml("```html\n<!DOCTYPE html><html><head>")).toBe("<!DOCTYPE html><html><head>");
  });
});
