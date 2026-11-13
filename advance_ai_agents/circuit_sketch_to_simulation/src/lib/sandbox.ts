import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { chromium, type Browser } from "playwright-core";
import type { Netlist } from "@/lib/schema/circuit";
import type { SimState } from "@/lib/sim/agreement";
import { lockDown } from "@/lib/csp";

export function findChrome(): string | undefined {
  if (process.env.INKWIRE_CHROME_PATH) return process.env.INKWIRE_CHROME_PATH;
  const roots = [path.join(/*turbopackIgnore: true*/ os.homedir(), "Library/Caches/ms-playwright"), path.join(/*turbopackIgnore: true*/ os.homedir(), ".cache/ms-playwright")];
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const dir of fs.readdirSync(root).filter((d) => d.startsWith("chromium-")).sort().reverse()) {
      for (const rel of [
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
      ]) {
        const p = path.join(/*turbopackIgnore: true*/ root, dir, rel);
        if (fs.existsSync(p)) return p;
      }
    }
  }
  return undefined;
}

let browser: Promise<Browser> | undefined;
function getBrowser() {
  browser ??= chromium.launch({ executablePath: findChrome(), headless: true }).catch((e) => {
    browser = undefined;
    throw new Error(`Could not start Chrome for the vision loop. Set INKWIRE_CHROME_PATH. (${e instanceof Error ? e.message : e})`);
  });
  return browser;
}

export type Shot = { label: string; png: Buffer; state: SimState | null; errors: string[] };

// A view of the simulation to capture: which netlist it shows and which switches are flipped.
export type View = { label: string; mode: "fixed" | "drawn"; switches?: Record<string, boolean>; netlist: Netlist };

export async function capture(html: string, views: View[]): Promise<Shot[]> {
  const b = await getBrowser();
  const context = await b.newContext({ viewport: { width: 1100, height: 720 }, deviceScaleFactor: 1, javaScriptEnabled: true, offline: true });
  await context.route("**/*", (route) => (route.request().url().startsWith("data:") ? route.continue() : route.abort()));
  const shots: Shot[] = [];
  try {
    for (const view of views) {
      const page = await context.newPage();
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (m) => {
        if (m.type() === "error") errors.push(m.text());
      });
      await page.setContent(lockDown(html), { waitUntil: "load", timeout: 15_000 }).catch((e) => errors.push(String(e)));
      const state = await page
        .evaluate(
          async ({ mode, switches }) => {
            const sim = (window as unknown as { __sim?: Record<string, (...a: unknown[]) => unknown> }).__sim;
            if (!sim || typeof sim.state !== "function") return null;
            sim.setMode?.(mode);
            for (const [id, closed] of Object.entries(switches ?? {})) sim.setSwitch?.(id, closed);
            await new Promise((r) => setTimeout(r, 600));
            return JSON.parse(JSON.stringify(sim.state()));
          },
          { mode: view.mode, switches: view.switches },
        )
        .catch((e) => {
          errors.push(String(e));
          return null;
        });
      if (state === null) errors.push("window.__sim.state() is missing or failed.");
      const png = await page.screenshot({ type: "png", timeout: 10_000 });
      shots.push({ label: view.label, png, state, errors: [...new Set(errors)].slice(0, 10) });
      await page.close();
    }
  } finally {
    await context.close();
  }
  return shots;
}
