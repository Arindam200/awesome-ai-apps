import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const artifactDir = "/private/tmp/ai-shark-tank-visual";
const url = "http://localhost:5173/";

await fs.mkdir(artifactDir, { recursive: true });

const sharks = {
  nemotron: {
    key: "nemotron",
    label: "MiniMax Shark",
    model: "MiniMaxAI/MiniMax-M3",
    thesis: "Operator and execution investor.",
  },
  deepseek: {
    key: "deepseek",
    label: "DeepSeek Flash Shark",
    model: "deepseek-ai/DeepSeek-V4-Flash",
    thesis: "Growth and category investor.",
  },
  judge: {
    key: "judge",
    label: "Nemotron Lightning Shark",
    model: "nvidia/Nemotron-3_5-Lightning",
    thesis: "Lead deal-maker and financial skeptic.",
  },
};

const baseRound = (index, focus, panelQuestion) => ({
  id: `round-${index + 1}`,
  focus,
  panelQuestion,
  sharkAngles: {
    nemotron: "operations",
    deepseek: "growth",
    judge: "deal",
  },
  userAnswer: "",
  sharkReactions: {},
  scores: {},
  interest: {},
  status: "awaiting-answer",
});

const room = {
  id: "visual-room",
  kind: "user-shark-room",
  status: "awaiting-answer",
  businessTitle: "Restaurant Media Agency",
  promptSummary: "A social media agency for local restaurants with revenue, margin, recurring clients, and a dashboard ask.",
  prompt:
    "I run a social media agency for local restaurants. We made $18k revenue last month with 42% margin and want $150k.",
  practiceContext: {
    stage: "early",
    stageLabel: "Early Traction",
    objective: "growth",
    objectiveLabel: "Growth Plan",
    length: "quick",
    lengthLabel: "Quick Room",
    roundCount: 2,
  },
  facts: ["$18k last month", "42% margin", "11 recurring clients", "$150k ask"],
  sharks,
  currentRoundIndex: 0,
  rounds: [
    baseRound(0, "Proof", "What proves restaurant owners need this enough to keep paying every month?"),
    baseRound(1, "Deal", "Why is $150k the right amount, and what milestone does it unlock?"),
  ],
};

function scoredRound(round, answer, scoreBase) {
  return {
    ...round,
    userAnswer: answer,
    sharkReactions: {
      nemotron: {
        shark: "nemotron",
        label: "MiniMax Shark",
        reaction: "The answer is credible because it ties retention to a delivery system, but I need weekly capacity numbers.",
        score: scoreBase,
        interest: scoreBase + 4,
        pressure: "How many shoots can one editor handle without margin dropping?",
        dealSignal: "Operator interest is moving up.",
      },
      deepseek: {
        shark: "deepseek",
        label: "DeepSeek Flash Shark",
        reaction: "The wedge is clear. The stronger path is a restaurant growth OS, not just content services.",
        score: scoreBase - 2,
        interest: scoreBase + 2,
        pressure: "What channel gets the next 30 restaurants repeatably?",
        dealSignal: "Growth interest depends on distribution proof.",
      },
      judge: {
        shark: "judge",
        label: "Nemotron Lightning Shark",
        reaction: "The answer is investable if the ask maps to dashboard milestones and gross margin protection.",
        score: scoreBase + 1,
        interest: scoreBase,
        pressure: "What valuation are you implying with the $150k ask?",
        dealSignal: "Terms are possible, but diligence matters.",
      },
    },
    scores: { nemotron: scoreBase, deepseek: scoreBase - 2, judge: scoreBase + 1 },
    interest: { nemotron: scoreBase + 4, deepseek: scoreBase + 2, judge: scoreBase },
    status: "scored",
  };
}

const finalDeal = {
  outcome: "Conditional deal",
  bestOffer: { shark: "nemotron", label: "MiniMax Shark", terms: "$150k for 15%" },
  verdict: "The sharks like the recurring revenue but want dashboard milestones and margin proof before wiring capital.",
  strongestAnswer: "The founder used revenue, margin, and client count clearly.",
  weakestAnswer: "The founder needs sharper acquisition and valuation logic.",
  dealRisks: ["Editor hiring could compress margins.", "Dashboard may distract from service delivery."],
  nextPractice: ["Practice the $150k use-of-funds answer.", "Prepare CAC, churn, and editor capacity metrics."],
  offers: [
    {
      shark: "nemotron",
      label: "MiniMax Shark",
      decision: "offer",
      amount: "$150k",
      equity: "15%",
      conditions: ["Hire two editors only after dashboard beta is shipped."],
      rationale: "The operating system can scale if delivery capacity stays disciplined.",
      improvementNote: "Bring editor throughput numbers.",
      confidence: 74,
    },
    {
      shark: "deepseek",
      label: "DeepSeek Flash Shark",
      decision: "join",
      amount: "$75k",
      equity: "7.5%",
      conditions: ["Show a repeatable referral channel."],
      rationale: "The category story improves if reporting becomes the retention layer.",
      improvementNote: "Prove distribution.",
      confidence: 68,
    },
    {
      shark: "judge",
      label: "Nemotron Lightning Shark",
      decision: "pass",
      amount: "",
      equity: "",
      conditions: [],
      rationale: "The valuation and use of funds need more discipline.",
      improvementNote: "Tie ask to clean milestones.",
      confidence: 42,
    },
  ],
  counterOffers: [],
};

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath,
  args: ["--no-sandbox"],
});

const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let answerCount = 0;

await page.route("**/api/room/start", async (route) => {
  await route.fulfill({ json: { ok: true, data: room } });
});

await page.route("**/api/room/visual-room/answer", async (route) => {
  const request = route.request();
  const body = request.postDataJSON();
  answerCount += 1;
  const rounds = [...room.rounds];
  rounds[0] = scoredRound(rounds[0], answerCount === 1 ? body.answer : "First answer", 78);
  if (answerCount >= 2) {
    rounds[1] = scoredRound(rounds[1], body.answer, 82);
  }
  const data = {
    ...room,
    rounds,
    currentRoundIndex: answerCount >= 2 ? 1 : 1,
    status: answerCount >= 2 ? "complete" : "awaiting-answer",
    finalDeal: answerCount >= 2 ? finalDeal : null,
    reportId: answerCount >= 2 ? "visual-report" : null,
    reportUrl: answerCount >= 2 ? "/reports/visual-report" : null,
    winner: answerCount >= 2 ? "conditional_deal" : null,
  };
  await route.fulfill({ json: { ok: true, data } });
});

await page.route("**/api/room/visual-room/counter", async (route) => {
  const data = {
    ...room,
    status: "complete",
    currentRoundIndex: 1,
    rounds: [
      scoredRound(room.rounds[0], "Restaurants keep paying because reels and ads map to bookings.", 78),
      scoredRound(room.rounds[1], "The $150k funds two editors, dashboard beta, and 30 client milestone.", 82),
    ],
    finalDeal: {
      ...finalDeal,
      counterOffer: "I counter at $150k for 10% with dashboard milestones.",
      counterOffers: [
        {
          shark: "nemotron",
          label: "MiniMax Shark",
          decision: "revise",
          revisedAmount: "$150k",
          revisedEquity: "12%",
          conditions: ["Margin stays above 38% for two months."],
          message: "I will move, but only if the operating milestones are binding.",
          finalAdvice: "Counter with proof, not hope.",
        },
      ],
    },
  };
  await route.fulfill({ json: { ok: true, data } });
});

await page.goto(url, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(artifactDir, "01-empty-room.png"), fullPage: true });
await page.locator("textarea").fill(room.prompt);
await page.getByRole("button", { name: /enter the tank/i }).click();
await page.getByRole("button", { name: /submit answer/i }).waitFor({ timeout: 10000 });
await page.screenshot({ path: path.join(artifactDir, "02-active-question.png"), fullPage: true });
await page.locator("textarea").fill("Restaurants keep paying because we connect content output to booking trends and weekly campaigns.");
await page.getByRole("button", { name: /submit answer/i }).click();
await page.getByText(/Round 2/i).first().waitFor({ timeout: 10000 });
await page.screenshot({ path: path.join(artifactDir, "03-answer-scored.png"), fullPage: true });
await page.locator("textarea").fill("The $150k hires two editors, ships reporting beta, and should unlock 30 recurring clients.");
await page.getByRole("button", { name: /submit answer/i }).click();
await page.getByRole("dialog", { name: /deal report/i }).waitFor({ timeout: 10000 });
await page.screenshot({ path: path.join(artifactDir, "04-final-deal.png"), fullPage: true });
await page.getByLabel(/close report/i).last().click();
await page.locator("textarea").fill("I counter at $150k for 10% with dashboard, client, and margin milestones.");
await page.getByRole("button", { name: /send counter/i }).click();
await page.getByRole("dialog", { name: /deal report/i }).waitFor({ timeout: 10000 });
await page.screenshot({ path: path.join(artifactDir, "05-counter-response.png"), fullPage: true });

const summary = await page.evaluate(() => {
  const boxFor = (selector) => {
    const element = document.querySelector(selector);
    if (!element) return null;
    const rect = element.getBoundingClientRect();
    return {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      right: Math.round(rect.right),
      bottom: Math.round(rect.bottom),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      text: (element.innerText || "").slice(0, 180),
    };
  };
  const areaOverlap = (a, b) => {
    if (!a || !b) return 0;
    const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.x, b.x));
    const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y));
    return Math.round(width * height);
  };
  const dock = boxFor(".prompt-dock");
  const judge = boxFor(".judge-console");
  const leftPanel = boxFor(".founder-panel.nemotron");
  const rightPanel = boxFor(".founder-panel.deepseek");
  return {
    noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
    hasDealReport: /Conditional deal/i.test(document.body.innerText),
    hasCounter: /Counter-offer responses/i.test(document.body.innerText),
    hasSharkScores: /MiniMax Shark/i.test(document.body.innerText) && /DeepSeek Flash Shark/i.test(document.body.innerText),
    overlaps: {
      leftJudge: areaOverlap(leftPanel, judge),
      rightJudge: areaOverlap(rightPanel, judge),
      dockJudge: areaOverlap(dock, judge),
      dockLeft: areaOverlap(dock, leftPanel),
      dockRight: areaOverlap(dock, rightPanel),
    },
    dock,
    judge,
    leftPanel,
    rightPanel,
  };
});

await browser.close();

const ok =
  summary.noHorizontalOverflow &&
  summary.hasDealReport &&
  summary.hasCounter &&
  summary.hasSharkScores &&
  Object.values(summary.overlaps).every((value) => value === 0);

console.log(
  JSON.stringify(
    {
      ok,
      screenshots: {
        empty: path.join(artifactDir, "01-empty-room.png"),
        activeQuestion: path.join(artifactDir, "02-active-question.png"),
        answerScored: path.join(artifactDir, "03-answer-scored.png"),
        finalDeal: path.join(artifactDir, "04-final-deal.png"),
        counterResponse: path.join(artifactDir, "05-counter-response.png"),
      },
      summary,
    },
    null,
    2,
  ),
);

if (!ok) {
  process.exitCode = 1;
}
