import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const artifactDir = "/private/tmp/ai-shark-tank-3d";
const url = "http://localhost:5173/";

await fs.mkdir(artifactDir, { recursive: true });

async function collectStageStats(page) {
  await page.waitForSelector(".digital-stage-canvas", { timeout: 15000 });
  await page.waitForFunction(() => window.__aiSharkTank3dFrames > 8, null, { timeout: 15000 });

  return page.evaluate(async () => {
    const canvas = document.querySelector(".digital-stage-canvas");
    const boxFor = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        bottom: Math.round(rect.bottom),
        right: Math.round(rect.right),
      };
    };
    const overlapArea = (a, b) => {
      if (!a || !b) return 0;
      const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.x, b.x));
      const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y));
      return Math.round(width * height);
    };
    const rect = canvas.getBoundingClientRect();
    const dock = boxFor(".prompt-dock");
    const leftPanel = boxFor(".founder-panel.nemotron");
    const judge = boxFor(".judge-console");
    const rightPanel = boxFor(".founder-panel.deepseek");
    const speechCards = Array.from(document.querySelectorAll(".speech-card")).map((element) => {
      const rect = element.getBoundingClientRect();
      return {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        bottom: Math.round(rect.bottom),
        right: Math.round(rect.right),
      };
    });
    const firstFrame = window.__aiSharkTank3dFrames || 0;
    await new Promise((resolve) => setTimeout(resolve, 320));
    const secondFrame = window.__aiSharkTank3dFrames || 0;
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    const width = gl?.drawingBufferWidth || canvas.width;
    const height = gl?.drawingBufferHeight || canvas.height;
    const positions = [
      [0.5, 0.5],
      [0.36, 0.6],
      [0.64, 0.6],
      [0.5, 0.32],
      [0.22, 0.74],
      [0.78, 0.74],
    ];
    let colorEnergy = 0;
    let alphaSamples = 0;

    if (gl) {
      const pixel = new Uint8Array(4);
      positions.forEach(([x, y]) => {
        gl.readPixels(
          Math.max(0, Math.min(width - 1, Math.floor(width * x))),
          Math.max(0, Math.min(height - 1, Math.floor(height * y))),
          1,
          1,
          gl.RGBA,
          gl.UNSIGNED_BYTE,
          pixel,
        );
        colorEnergy += pixel[0] + pixel[1] + pixel[2];
        if (pixel[3] > 0) alphaSamples += 1;
      });
    }

    return {
      canvasRect: {
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        left: Math.round(rect.left),
        top: Math.round(rect.top),
      },
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
      drawingBuffer: { width, height },
      framesAdvanced: secondFrame > firstFrame,
      frameDelta: secondFrame - firstFrame,
      colorEnergy,
      alphaSamples,
      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
      hasThreeCanvas: Boolean(canvas),
      layout: {
        dock,
        leftPanel,
        judge,
        rightPanel,
        overlapDockLeft: overlapArea(dock, leftPanel),
        overlapDockJudge: overlapArea(dock, judge),
        overlapDockRight: overlapArea(dock, rightPanel),
        overlapDockSpeech: speechCards.reduce((total, card) => total + overlapArea(dock, card), 0),
      },
    };
  });
}

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath,
  args: ["--no-sandbox"],
});

const viewports = [
  { key: "desktop", width: 1440, height: 900 },
  { key: "laptop", width: 1280, height: 720 },
  { key: "compact-laptop", width: 1024, height: 768 },
];

const results = {};
const screenshots = {};

for (const viewport of viewports) {
  const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
  await page.goto(url, { waitUntil: "networkidle" });
  const stats = await collectStageStats(page);
  const screenshotPath = path.join(artifactDir, `${viewport.key}-3d.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  results[viewport.key] = stats;
  screenshots[viewport.key] = screenshotPath;
}

await browser.close();

const ok = Object.values(results).every(
  (stats) =>
    stats.hasThreeCanvas &&
    stats.framesAdvanced &&
    stats.colorEnergy > 40 &&
    stats.noHorizontalOverflow &&
    stats.layout.overlapDockLeft === 0 &&
    stats.layout.overlapDockJudge === 0 &&
    stats.layout.overlapDockRight === 0 &&
    stats.layout.overlapDockSpeech === 0,
);

console.log(
  JSON.stringify(
    {
      ok,
      screenshots,
      results,
    },
    null,
    2,
  ),
);

if (!ok) {
  process.exitCode = 1;
}
