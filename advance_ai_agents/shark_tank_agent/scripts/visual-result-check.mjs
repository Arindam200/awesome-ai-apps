import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const artifactDir = "/private/tmp/ai-shark-tank-result";
const url = "http://localhost:5173/";

await fs.mkdir(artifactDir, { recursive: true });

const report = {
  id: "visual-report",
  reportId: "visual-report",
  reportUrl: "/reports/visual-report",
  kind: "user-shark-room",
  status: "complete",
  winner: "conditional_deal",
  businessTitle: "Restaurant Media Agency",
  promptSummary: "A restaurant social media agency with recurring clients and an AI dashboard ask.",
  prompt: "I run a social media agency for local restaurants with $18k revenue, 42% margin, and 11 clients.",
  practiceContext: {
    stage: "early",
    stageLabel: "Early Traction",
    objective: "growth",
    objectiveLabel: "Growth Plan",
    length: "quick",
    lengthLabel: "Quick Room",
    roundCount: 2,
  },
  sharks: {
    nemotron: { label: "MiniMax Shark", model: "MiniMaxAI/MiniMax-M3" },
    deepseek: { label: "DeepSeek Flash Shark", model: "deepseek-ai/DeepSeek-V4-Flash" },
    judge: { label: "Nemotron Lightning Shark", model: "nvidia/Nemotron-3_5-Lightning" },
  },
  promptDiagnostics: {
    stageFit: "Early traction fits the facts.",
    strongestSignal: "$18k revenue with 11 recurring clients.",
    firstPracticeMove: "Prove retention and channel repeatability.",
    missingFacts: ["CAC", "LTV", "Retention"],
  },
  currentRoundIndex: 1,
  rounds: [
    {
      id: "round-1",
      focus: "Proof",
      panelQuestion: "What proof shows restaurants keep paying?",
      userAnswer: "We have 11 recurring clients and track booking lift by campaign.",
      scores: { nemotron: 78, deepseek: 76, judge: 75 },
      interest: { nemotron: 82, deepseek: 79, judge: 71 },
      sharkReactions: {
        nemotron: { label: "MiniMax Shark", reaction: "Good proof, but I want editor capacity numbers." },
        deepseek: { label: "DeepSeek Flash Shark", reaction: "The growth wedge is promising." },
        judge: { label: "Nemotron Lightning Shark", reaction: "The answer needs valuation math next." },
      },
    },
    {
      id: "round-2",
      focus: "Deal",
      panelQuestion: "Why is $150k the right ask?",
      userAnswer: "It funds two editors and a reporting beta to reach 30 clients.",
      scores: { nemotron: 83, deepseek: 80, judge: 78 },
      interest: { nemotron: 86, deepseek: 82, judge: 76 },
      sharkReactions: {
        nemotron: { label: "MiniMax Shark", reaction: "This is closer to a fundable operating plan." },
        deepseek: { label: "DeepSeek Flash Shark", reaction: "The dashboard can become a retention layer." },
        judge: { label: "Nemotron Lightning Shark", reaction: "Conditional offer only until the valuation is clearer." },
      },
    },
  ],
  finalDeal: {
    outcome: "Conditional deal",
    bestOffer: { shark: "nemotron", label: "MiniMax Shark", terms: "$150k for 15%" },
    verdict: "The sharks like the traction but want tighter milestone proof.",
    strongestAnswer: "The founder tied revenue and client count to the ask.",
    weakestAnswer: "The founder still needs CAC, churn, and valuation logic.",
    dealRisks: ["Margin compression", "Founder-led acquisition"],
    nextPractice: ["Practice valuation math", "Prepare retention proof"],
    offers: [
      {
        shark: "nemotron",
        label: "MiniMax Shark",
        decision: "offer",
        amount: "$150k",
        equity: "15%",
        conditions: ["Keep margin above 38%."],
        rationale: "Operationally plausible if hiring is staged.",
      },
      {
        shark: "deepseek",
        label: "DeepSeek Flash Shark",
        decision: "join",
        amount: "$75k",
        equity: "7.5%",
        conditions: ["Show repeatable acquisition."],
        rationale: "The growth story needs a channel loop.",
      },
      {
        shark: "judge",
        label: "Nemotron Lightning Shark",
        decision: "pass",
        amount: "",
        equity: "",
        conditions: [],
        rationale: "Valuation is not yet justified.",
      },
    ],
    counterOffers: [],
  },
};

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath,
  args: ["--no-sandbox"],
});

const viewports = [
  { key: "desktop-result", width: 1440, height: 900 },
  { key: "laptop-result", width: 1280, height: 720 },
  { key: "compact-laptop-result", width: 1024, height: 768 },
];

const screenshots = {};
const results = {};

for (const viewport of viewports) {
  const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
  await page.route("**/api/reports", async (route) => {
    await route.fulfill({
      json: {
        ok: true,
        data: [
          {
            id: report.id,
            createdAt: new Date().toISOString(),
            title: report.businessTitle,
            winner: report.winner,
            kind: report.kind,
            dealOutcome: report.finalDeal.outcome,
            reportUrl: report.reportUrl,
            prompt: report.prompt,
            promptSummary: report.promptSummary,
            stageLabel: "Early Traction",
            objectiveLabel: "Growth Plan",
            lengthLabel: "Quick Room",
            readinessScore: 79,
          },
        ],
        summary: { sessionCount: 1, averageReadiness: 79, bestReadiness: 79 },
      },
    });
  });
  await page.route("**/api/reports/visual-report", async (route) => {
    await route.fulfill({ json: { ok: true, data: report } });
  });

  await page.goto(url, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /^reports$/i }).click();
  await page.getByRole("dialog", { name: /saved reports/i }).waitFor({ timeout: 10000 });
  await page.getByRole("button", { name: /^load$/i }).click();
  await page.getByRole("dialog", { name: /deal report/i }).waitFor({ timeout: 10000 });
  await page.screenshot({ path: path.join(artifactDir, `${viewport.key}.png`), fullPage: true });

  results[viewport.key] = await page.evaluate(() => ({
    noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
    hasOutcome: /Conditional deal/i.test(document.body.innerText),
    hasOffers: /MiniMax Shark/i.test(document.body.innerText) && /Pass/i.test(document.body.innerText),
    hasTabs: /Transcript/i.test(document.body.innerText) && /Drills/i.test(document.body.innerText),
  }));
  screenshots[viewport.key] = path.join(artifactDir, `${viewport.key}.png`);
}

await browser.close();

const ok = Object.values(results).every(
  (stats) => stats.noHorizontalOverflow && stats.hasOutcome && stats.hasOffers && stats.hasTabs,
);

console.log(JSON.stringify({ ok, screenshots, results }, null, 2));

if (!ok) {
  process.exitCode = 1;
}
