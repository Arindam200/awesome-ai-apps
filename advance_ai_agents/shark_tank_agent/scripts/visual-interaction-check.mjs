import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const artifactDir = "/private/tmp/ai-shark-tank-interaction";
const url = "http://localhost:5173/";

await fs.mkdir(artifactDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath,
  args: ["--no-sandbox"],
});

const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForSelector(".seat-hotspot.judge", { timeout: 15000 });
await page.waitForTimeout(800);

await page.locator(".seat-hotspot.nemotron").hover({ force: true });
await page.waitForTimeout(250);
const leftHovered = await page.evaluate(() => ({
  roomClass: document.querySelector(".duel-room")?.className,
  hoveredHotspot: document.querySelector(".seat-hotspot.nemotron")?.className,
  frames: window.__aiSharkTank3dFrames || 0,
}));

await page.locator(".seat-hotspot.nemotron").click({ force: true });
await page.waitForTimeout(450);
const leftFocused = await page.evaluate(() => ({
  roomClass: document.querySelector(".duel-room")?.className,
  activeHotspot: document.querySelector(".seat-hotspot.nemotron")?.className,
  frames: window.__aiSharkTank3dFrames || 0,
}));
await page.screenshot({ path: path.join(artifactDir, "01-minimax-focus.png"), fullPage: true });

await page.locator(".seat-hotspot.deepseek").click({ force: true });
await page.waitForTimeout(450);
const rightFocused = await page.evaluate(() => ({
  roomClass: document.querySelector(".duel-room")?.className,
  activeHotspot: document.querySelector(".seat-hotspot.deepseek")?.className,
  frames: window.__aiSharkTank3dFrames || 0,
}));
await page.screenshot({ path: path.join(artifactDir, "02-deepseek-focus.png"), fullPage: true });

await page.locator(".judge-console").click({ force: true });
await page.waitForTimeout(450);
const judgeFocused = await page.evaluate(() => ({
  roomClass: document.querySelector(".duel-room")?.className,
  activeHotspot: document.querySelector(".seat-hotspot.judge")?.className,
  frames: window.__aiSharkTank3dFrames || 0,
}));
await page.screenshot({ path: path.join(artifactDir, "03-judge-focus.png"), fullPage: true });

await browser.close();

const ok =
  !leftHovered.roomClass?.includes("focus-nemotron") &&
  leftFocused.roomClass?.includes("focus-nemotron") &&
  rightFocused.roomClass?.includes("focus-deepseek") &&
  judgeFocused.roomClass?.includes("focus-judge") &&
  rightFocused.frames > leftFocused.frames &&
  judgeFocused.frames > rightFocused.frames;

console.log(
  JSON.stringify(
    {
      ok,
      screenshots: {
        minimax: path.join(artifactDir, "01-minimax-focus.png"),
        deepseek: path.join(artifactDir, "02-deepseek-focus.png"),
        judge: path.join(artifactDir, "03-judge-focus.png"),
      },
      leftHovered,
      leftFocused,
      rightFocused,
      judgeFocused,
    },
    null,
    2,
  ),
);

if (!ok) {
  process.exitCode = 1;
}
