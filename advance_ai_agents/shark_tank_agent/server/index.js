import "dotenv/config";
import express from "express";
import cors from "cors";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import { jsonrepair } from "jsonrepair";
import { Mastra } from "@mastra/core";
import { Agent } from "@mastra/core/agent";
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { LibSQLStore } from "@mastra/libsql";
import { z } from "zod";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const distPath = path.resolve(__dirname, "../dist");
const dataPath = path.resolve(__dirname, "../data");
const dbPath = path.join(dataPath, "reports.sqlite");
const mastraDbPath = path.join(dataPath, "mastra.sqlite");
const CACHE_VERSION = "user-shark-room-v3";
const LLM_CALL_TIMEOUT_MS = Number(process.env.NEBIUS_CALL_TIMEOUT_MS || 90_000);

fs.mkdirSync(dataPath, { recursive: true });
const db = new DatabaseSync(dbPath);
db.exec(`
  CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    cache_key TEXT UNIQUE,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    winner TEXT NOT NULL,
    prompt TEXT NOT NULL,
    data TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS llm_chunks (
    cache_key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    step TEXT NOT NULL,
    data TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS drill_attempts (
    id TEXT PRIMARY KEY,
    report_id TEXT,
    created_at TEXT NOT NULL,
    drill_name TEXT NOT NULL,
    drill_prompt TEXT NOT NULL,
    answer TEXT NOT NULL,
    score INTEGER NOT NULL,
    data TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    prompt TEXT NOT NULL,
    data TEXT NOT NULL
  )
`);

const reportColumns = db.prepare("PRAGMA table_info(reports)").all().map((column) => column.name);
if (!reportColumns.includes("cache_key")) {
  db.exec("ALTER TABLE reports ADD COLUMN cache_key TEXT");
}
db.exec("CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_cache_key ON reports(cache_key)");

const app = express();
const port = Number(process.env.PORT || 8790);
const defaultBaseUrl =
  process.env.NEBIUS_BASE_URL || "https://api.tokenfactory.nebius.com/v1/";

const modelConfig = {
  nemotron: {
    label: "MiniMax Shark",
    model: process.env.NEBIUS_NEMOTRON_MODEL || "MiniMaxAI/MiniMax-M3",
    baseUrl: process.env.NEBIUS_NEMOTRON_BASE_URL || defaultBaseUrl,
  },
  deepseek: {
    label: "DeepSeek Flash Shark",
    model: process.env.NEBIUS_DEEPSEEK_MODEL || "deepseek-ai/DeepSeek-V4-Flash",
    baseUrl: process.env.NEBIUS_DEEPSEEK_BASE_URL || defaultBaseUrl,
  },
  judge: {
    label: "Nemotron Lightning Shark",
    model: process.env.NEBIUS_JUDGE_MODEL || "nvidia/Nemotron-3_5-Lightning",
    baseUrl: process.env.NEBIUS_JUDGE_BASE_URL || defaultBaseUrl,
  },
};

function nebiusModel(role) {
  return {
    providerId: "nebius",
    modelId: role.model,
    url: role.baseUrl,
    apiKey: process.env.NEBIUS_API_KEY || "",
  };
}

const miniMaxFounderAgent = new Agent({
  id: "minimax-shark-agent",
  name: "MiniMax Shark",
  model: () => nebiusModel(modelConfig.nemotron),
  instructions:
    "You are the operator/execution shark in an AI Shark Tank practice room. You evaluate founders through operating rigor, concrete numbers, hiring plans, delivery capacity, margin control, automation, retention, and measurable scaling milestones.",
});

const deepSeekFounderAgent = new Agent({
  id: "deepseek-flash-shark-agent",
  name: "DeepSeek Flash Shark",
  model: () => nebiusModel(modelConfig.deepseek),
  instructions:
    "You are the growth/category shark in an AI Shark Tank practice room. You evaluate founders through market positioning, partnerships, distribution loops, product/data leverage, category expansion, and defensibility.",
});

const investorJudgeAgent = new Agent({
  id: "nemotron-lightning-shark-agent",
  name: "Nemotron Lightning Shark",
  model: () => nebiusModel(modelConfig.judge),
  instructions:
    "You are the lead deal-maker and financial skeptic in an AI Shark Tank practice room. Extract business facts, ask hard questions, score founder answers, negotiate realistic terms, and write practical practice notes without inventing facts.",
});

const fallbackQuestions = [
  "Give me the 30-second pitch. What exactly do you sell, who buys it first, and why now?",
  "What proof do you have that the sharpest first customer segment urgently wants this and will keep paying?",
  "Walk me through the business model, pricing, margins, and the next revenue milestone.",
  "How will you acquire customers repeatedly without founder-led hustle every time?",
  "What is your creative scaling plan from the current revenue and traction?",
  "What role should technology, automation, data, or AI play in scaling this company?",
  "Who are the closest competitors or substitutes, and what makes this company hard to copy?",
  "What is the biggest operational or market risk, and how will you reduce it?",
  "What exactly would you do with the investment, and what milestones should it unlock?",
  "What deal terms would make this investable, and why should I believe this can become big?",
];

const practiceStages = {
  idea: {
    label: "Idea",
    prompt:
      "The founder may be pre-revenue. Test problem clarity, target customer, validation plan, prototype, founder insight, and the first proof needed before fundraising.",
  },
  early: {
    label: "Early Traction",
    prompt:
      "The founder has first customers, pilots, revenue, or usage. Test repeatability, retention, margin, customer acquisition, use of funds, and next milestone.",
  },
  scaling: {
    label: "Scaling",
    prompt:
      "The founder is already operating with meaningful traction. Test operating leverage, hiring, unit economics, market expansion, defensibility, and execution risk.",
  },
  fundraising: {
    label: "Fundraising",
    prompt:
      "The founder wants investor readiness. Test deal terms, milestone framing, investor objections, upside, risk, and proof needed to close capital.",
  },
};

const practiceObjectives = {
  clarity: {
    label: "Pitch Clarity",
    prompt:
      "Optimize feedback for simple pitch narrative, customer pain, why now, and one memorable investor hook.",
  },
  growth: {
    label: "Growth Plan",
    prompt:
      "Optimize feedback for acquisition loops, channel strategy, partnerships, expansion, and creative scaling.",
  },
  economics: {
    label: "Unit Economics",
    prompt:
      "Optimize feedback for pricing, margin, payback, retention, operating capacity, and financial proof.",
  },
  deal: {
    label: "Investor Deal",
    prompt:
      "Optimize feedback for funding ask, valuation logic, milestone use of capital, risk reduction, and final terms.",
  },
};

const skillCategories = [
  { key: "clarity", label: "Clarity" },
  { key: "proof", label: "Proof" },
  { key: "economics", label: "Economics" },
  { key: "scale", label: "Scale" },
  { key: "moat", label: "Moat" },
  { key: "deal", label: "Deal" },
];

const practiceLengths = {
  quick: { label: "Quick Room", roundCount: 3, questionsPerShark: 1 },
  full: { label: "Full Room", roundCount: 6, questionsPerShark: 2 },
};

app.use(cors());
app.use(express.json({ limit: "1mb" }));

function flattenMessageContent(content) {
  if (typeof content === "string") {
    return content;
  }

  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") {
          return part;
        }
        if (part?.type === "text") {
          return part.text;
        }
        return JSON.stringify(part);
      })
      .filter(Boolean)
      .join("\n");
  }

  return String(content || "");
}

function splitAgentMessages(messages) {
  const system = [];
  const prompt = [];

  for (const message of messages || []) {
    const content = flattenMessageContent(message.content);
    if (!content) {
      continue;
    }

    if (message.role === "system") {
      system.push(content);
      continue;
    }

    prompt.push(`${String(message.role || "user").toUpperCase()}:\n${content}`);
  }

  return {
    instructions: system.join("\n\n"),
    prompt: prompt.join("\n\n"),
  };
}

function getAgentForRole(role) {
  if (role === modelConfig.nemotron) {
    return miniMaxFounderAgent;
  }
  if (role === modelConfig.deepseek) {
    return deepSeekFounderAgent;
  }
  return investorJudgeAgent;
}

async function withTimeout(promise, label) {
  let timeout;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timeout = setTimeout(() => {
          reject(new Error(`${label} timed out after ${Math.round(LLM_CALL_TIMEOUT_MS / 1000)}s.`));
        }, LLM_CALL_TIMEOUT_MS);
      }),
    ]);
  } finally {
    clearTimeout(timeout);
  }
}

function sanitizeInput(value, fallback = "") {
  return String(value || fallback).trim().slice(0, 5000);
}

function toScore(value, fallback = 65) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }

  const scaled = numeric > 0 && numeric <= 10 ? numeric * 10 : numeric;
  return Math.max(0, Math.min(100, Math.round(scaled)));
}

function isWeakPitchText(value) {
  const text = sanitizeInput(value).toLowerCase();
  return (
    text.length < 40 ||
    text === "..." ||
    text.includes("clearest customer pain, the current proof, and the next measurable milestone") ||
    text.includes("this business already has concrete traction, and the next pitch should tie") ||
    text.includes("validate the next growth step with a measurable experiment") ||
    text.includes("validate willingness to pay with a small, specific customer segment")
  );
}

function isPlaceholderText(value) {
  const text = sanitizeInput(value).toLowerCase();
  const labeledOnlyPattern =
    /^(reaction|score|interest|pressure|deal signal|deal_signal|investor note|investor_note|decision|amount|equity|conditions|rationale|improvement|confidence|message|final advice|final_advice|revised amount|revised_amount|revised equity|revised_equity):?$/i;
  return (
    !text ||
    labeledOnlyPattern.test(text) ||
    text === "..." ||
    text === "short title" ||
    text === "one sentence business summary" ||
    text === "fact from user prompt" ||
    text.includes("the answer needs clearer proof before this shark can move closer to a deal") ||
    text.includes("what proof can you show that this answer is repeatable") ||
    text.includes("tighten the answer with customer proof, economics, and a milestone") ||
    text.includes("the shark needs clearer logic before changing terms") ||
    text.includes("make the counter specific, rational, and tied to milestones") ||
    text.includes("specific investor language tied to the counter-offer") ||
    text.includes("specific investor language tied to counter-offer") ||
    text.includes("i need to fill") ||
    text.includes("let's think like") ||
    text.includes("let's draft") ||
    text.includes("round 1 focus") ||
    text.includes("operator angle") ||
    text.includes("growth angle") ||
    text.includes("deal-maker angle") ||
    text.includes("missing fact investors will ask for") ||
    text.includes("best proof already stated") ||
    text.includes("concise investor reaction to the user's answer") ||
    text.includes("one optional follow-up pressure point") ||
    text.includes("how this affects your willingness to invest") ||
    text.includes("one note to help the founder improve") ||
    text.includes("why you made this decision") ||
    text.includes("what founder should improve") ||
    text.includes("response to founder") ||
    text.includes("what founder should learn")
  );
}

function isPlaceholderReaction(reaction = {}) {
  const reactionText = sanitizeInput(reaction.reaction);
  return (
    isPlaceholderText(reaction.reaction) ||
    isPlaceholderText(reaction.pressure) ||
    isPlaceholderText(reaction.dealSignal) ||
    isPlaceholderText(reaction.investorNote) ||
    reactionText.length < 40
  );
}

function extractLabeledValue(text, labels, fallback = "") {
  const source = String(text || "");
  const labelPattern = labels.map((label) => label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const nextLabelPattern =
    "REACTION|SCORE|INTEREST|PRESSURE|DEAL SIGNAL|DEAL_SIGNAL|INVESTOR NOTE|INVESTOR_NOTE|DECISION|AMOUNT|EQUITY|CONDITIONS|RATIONALE|IMPROVEMENT|CONFIDENCE|MESSAGE|FINAL ADVICE|FINAL_ADVICE|REVISED AMOUNT|REVISED_AMOUNT|REVISED EQUITY|REVISED_EQUITY|FOCUS\\s+\\d+|QUESTION\\s+\\d+|ANGLE\\s+\\d+";
  const labeledOnly = new RegExp(`^(?:${nextLabelPattern})\\s*:?$`, "i");
  const pattern = new RegExp(`(?:^|\\n)\\s*(?:${labelPattern})\\s*:\\s*([\\s\\S]*?)(?=\\n\\s*(?:${nextLabelPattern})\\s*:|$)`, "gi");
  const values = Array.from(source.matchAll(pattern))
    .map((match) => sanitizeInput(match?.[1]))
    .map((value) => value.replace(/^["']|["']$/g, "").trim())
    .filter((value) => value && !labeledOnly.test(value));
  const value = values.at(-1) || sanitizeInput(fallback);
  if (labeledOnly.test(value)) {
    return sanitizeInput(fallback);
  }
  return value;
}

function parseListValue(value) {
  return sanitizeInput(value)
    .split(/\n|;|\|/)
    .map((item) => sanitizeInput(item.replace(/^[-*]\s*/, "")))
    .filter(Boolean)
    .slice(0, 5);
}

function parseModelJson(text) {
  const trimmed = String(text || "")
    .trim()
    .replace(/^```(?:json)?/i, "")
    .replace(/```$/i, "")
    .replace(/"\s*\+\s*"/g, "")
    .replace(/"\s*\+\s*\n\s*"/g, "")
    .replace(/\n\s*\+\s*"/g, "\n\"")
    .replace(/,\s*([}\]])/g, "$1")
    .trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    const match = trimmed.match(/\{[\s\S]*\}/);
    if (!match) {
      throw new Error("Model did not return JSON.");
    }

    try {
      return JSON.parse(match[0]);
    } catch {
      return JSON.parse(jsonrepair(match[0]));
    }
  }
}

async function callText({ role, messages, temperature = 0.55, maxTokens = 2600 }) {
  if (!process.env.NEBIUS_API_KEY) {
    throw new Error("Missing NEBIUS_API_KEY. Add it to ai-shark-tank/.env and restart the server.");
  }

  const agent = getAgentForRole(role);
  const { instructions, prompt } = splitAgentMessages(messages);
  const result = await withTimeout(
    agent.generate(prompt || "Continue.", {
      instructions: instructions || undefined,
      maxSteps: 1,
      modelSettings: {
        temperature,
        maxOutputTokens: maxTokens,
      },
    }),
    role.label,
  );

  return String(result.text || (result.object ? JSON.stringify(result.object) : ""));
}

async function callJson({ role, messages, temperature = 0.5, maxTokens = 2800 }) {
  const text = await callText({ role, messages, temperature, maxTokens });
  try {
    return parseModelJson(text);
  } catch {
    const repaired = await callText({
      role,
      temperature: 0,
      maxTokens,
      messages: [
        {
          role: "system",
          content:
            "Repair malformed JSON. Return only valid JSON with double-quoted property names, no string concatenation, and no markdown.",
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: `Repair this into valid JSON while preserving meaning. Remove JavaScript-style + string concatenation if present.\n\n${text}`,
            },
          ],
        },
      ],
    });

    try {
      return parseModelJson(repaired);
    } catch {
      const repairRole = role?.label === modelConfig.deepseek.label ? modelConfig.nemotron : modelConfig.deepseek;
      const secondRepair = await callText({
        role: repairRole,
        temperature: 0,
        maxTokens,
        messages: [
          {
            role: "system",
            content:
              "Convert malformed model output into strict JSON. Return only one valid JSON object with double-quoted property names. No prose, markdown, analysis, or placeholders.",
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: `The previous JSON repair failed. Repair this output into valid JSON while preserving the intended fields and meaning.\n\n${text}\n\nFirst failed repair:\n${repaired}`,
              },
            ],
          },
        ],
      });
      return parseModelJson(secondRepair);
    }
  }
}

function buildPromptFromBody(body) {
  const prompt = sanitizeInput(body.prompt);
  if (prompt) {
    return prompt;
  }

  const parts = [
    sanitizeInput(body.idea) && `Business idea: ${sanitizeInput(body.idea)}`,
    sanitizeInput(body.customer) && `Target customer: ${sanitizeInput(body.customer)}`,
    sanitizeInput(body.traction) && `Traction/proof: ${sanitizeInput(body.traction)}`,
    sanitizeInput(body.ask) && `Investment ask: ${sanitizeInput(body.ask)}`,
    sanitizeInput(body.intensity) && `Room intensity: ${sanitizeInput(body.intensity)}`,
  ].filter(Boolean);

  return parts.join("\n").slice(0, 5000);
}

function normalizePracticeContext(body = {}) {
  const stageKey = Object.hasOwn(practiceStages, body.stage) ? body.stage : "early";
  const objectiveKey = Object.hasOwn(practiceObjectives, body.objective) ? body.objective : "growth";
  const lengthKey = Object.hasOwn(practiceLengths, body.length) ? body.length : "full";

  return {
    stage: stageKey,
    stageLabel: practiceStages[stageKey].label,
    stagePrompt: practiceStages[stageKey].prompt,
    objective: objectiveKey,
    objectiveLabel: practiceObjectives[objectiveKey].label,
    objectivePrompt: practiceObjectives[objectiveKey].prompt,
    length: lengthKey,
    lengthLabel: practiceLengths[lengthKey].label,
    roundCount: practiceLengths[lengthKey].roundCount,
    questionsPerShark: practiceLengths[lengthKey].questionsPerShark,
  };
}

function practiceContextPrompt(practiceContext) {
  return [
    `Founder stage: ${practiceContext.stageLabel}`,
    practiceContext.stagePrompt,
    `Practice objective: ${practiceContext.objectiveLabel}`,
    practiceContext.objectivePrompt,
    `Room length: ${practiceContext.lengthLabel} (${practiceContext.roundCount} investor questions, ${practiceContext.questionsPerShark || 1} per shark)`,
  ].join("\n");
}

function normalizePromptDiagnostics(raw = {}) {
  return {
    stageFit: sanitizeInput(raw.stageFit, "The prompt gives enough context to start investor practice.").slice(0, 220),
    missingFacts: Array.isArray(raw.missingFacts)
      ? raw.missingFacts.slice(0, 5).map((item) => sanitizeInput(item).slice(0, 150))
      : [],
    strongestSignal: sanitizeInput(raw.strongestSignal, "The clearest signal is the founder's stated traction or customer insight.").slice(0, 180),
    firstPracticeMove: sanitizeInput(raw.firstPracticeMove, "Practice explaining the customer pain, proof, and next milestone in one tight answer.").slice(0, 180),
  };
}

function normalizeSkillScores(raw = {}) {
  return skillCategories.map((category) => {
    const source = raw[category.key] || {};
    return {
      key: category.key,
      label: category.label,
      score: toScore(source.score, 65),
      note: sanitizeInput(source.note, `${category.label} needs sharper investor-grade proof.`).slice(0, 160),
    };
  });
}

function normalizePracticeDrills(raw = []) {
  const drills = Array.isArray(raw) ? raw : [];
  return drills.slice(0, 3).map((drill, index) => ({
    name: sanitizeInput(drill.name, `Drill ${index + 1}`).slice(0, 80),
    goal: sanitizeInput(drill.goal, "Sharpen one investor-critical part of the pitch.").slice(0, 180),
    prompt: sanitizeInput(drill.prompt, "Answer this investor question in 45 seconds with one metric, one risk, and one next milestone.").slice(0, 320),
  }));
}

const sharkKeys = ["nemotron", "deepseek", "judge"];

function sharkProfiles() {
  return {
    nemotron: {
      key: "nemotron",
      label: modelConfig.nemotron.label,
      model: modelConfig.nemotron.model,
      thesis: "Operator and execution investor. Cares about delivery systems, hiring, margin, retention, and what the founder can actually operate next.",
    },
    deepseek: {
      key: "deepseek",
      label: modelConfig.deepseek.label,
      model: modelConfig.deepseek.model,
      thesis: "Growth and category investor. Cares about wedge, distribution, partnerships, market expansion, and defensibility.",
    },
    judge: {
      key: "judge",
      label: modelConfig.judge.label,
      model: modelConfig.judge.model,
      thesis: "Lead deal-maker and financial skeptic. Cares about valuation logic, risk, terms, proof quality, and whether a real offer can be made.",
    },
  };
}

function sharkLabel(key) {
  return sharkProfiles()[key]?.label || "Shark";
}

const fallbackSharkQuestions = {
  nemotron: [
    {
      focus: "Operating proof",
      question: "Walk me through how you deliver this repeatedly without quality dropping, and what operating metric proves it is working.",
      angle: "Pressure delivery systems, margin, capacity, retention, and hiring risk.",
    },
    {
      focus: "Execution plan",
      question: "What exactly changes in the next 90 days if you get capital, and how will you measure whether the execution plan is working?",
      angle: "Pressure use of funds, operational milestones, staffing, and throughput.",
    },
  ],
  deepseek: [
    {
      focus: "Growth wedge",
      question: "Who is the sharpest first customer segment, why do they buy now, and what channel can repeatedly reach them?",
      angle: "Pressure positioning, distribution, market pull, and category expansion.",
    },
    {
      focus: "Scale loop",
      question: "What growth loop or partnership can make this scale beyond founder-led selling?",
      angle: "Pressure acquisition loops, partnerships, data leverage, and defensibility.",
    },
  ],
  judge: [
    {
      focus: "Deal logic",
      question: "Why is this ask the right amount, what milestone does it unlock, and what makes the terms fair for investors?",
      angle: "Pressure valuation, risk, capital use, and investability.",
    },
    {
      focus: "Risk and return",
      question: "What is the biggest reason I should pass today, and what proof would change that decision?",
      angle: "Pressure downside risk, missing proof, and realistic deal conditions.",
    },
  ],
};

function normalizeRoomRounds(raw = {}, practiceContext) {
  const rounds = Array.isArray(raw.rounds) ? raw.rounds : [];
  return fallbackQuestions.slice(0, practiceContext.roundCount).map((fallback, index) => {
    const round = rounds[index] || {};
    return {
      id: `round-${index + 1}`,
      focus: sanitizeInput(round.focus, `Investor round ${index + 1}`).slice(0, 100),
      panelQuestion: sanitizeInput(round.panelQuestion || round.question, fallback).slice(0, 520),
      sharkAngles: {
        nemotron: sanitizeInput(round.sharkAngles?.nemotron, "Pressure the operating plan and capacity.").slice(0, 180),
        deepseek: sanitizeInput(round.sharkAngles?.deepseek, "Pressure the market and growth logic.").slice(0, 180),
        judge: sanitizeInput(round.sharkAngles?.judge, "Pressure the deal, risk, and valuation.").slice(0, 180),
      },
      userAnswer: "",
      sharkReactions: {},
      scores: {},
      interest: {},
      status: "awaiting-answer",
    };
  });
}

function normalizeSharkQuestionSet(rawQuestions = [], sharkKey, count) {
  const source = Array.isArray(rawQuestions) ? rawQuestions : [];
  const fallback = fallbackSharkQuestions[sharkKey] || fallbackSharkQuestions.judge;

  return Array.from({ length: count }, (_, index) => {
    const item = source[index] || {};
    const fallbackItem = fallback[index % fallback.length];
    return {
      askingShark: sharkKey,
      askingSharkLabel: sharkLabel(sharkKey),
      focus: sanitizeInput(item.focus, fallbackItem.focus).slice(0, 100),
      question: sanitizeInput(item.question || item.panelQuestion, fallbackItem.question).slice(0, 520),
      angle: sanitizeInput(item.angle, fallbackItem.angle).slice(0, 180),
    };
  });
}

function normalizeRoomRoundsFromSharkQuestions(questionSets = {}, practiceContext) {
  const perShark = practiceContext.questionsPerShark || 1;
  const ordered = [];
  for (let questionIndex = 0; questionIndex < perShark; questionIndex += 1) {
    for (const sharkKey of sharkKeys) {
      const question = questionSets[sharkKey]?.[questionIndex];
      if (question) {
        ordered.push(question);
      }
    }
  }

  return ordered.slice(0, practiceContext.roundCount).map((question, index) => ({
    id: `round-${index + 1}`,
    askingShark: question.askingShark,
    askingSharkLabel: question.askingSharkLabel,
    focus: question.focus,
    panelQuestion: question.question,
    sharkAngles: {
      nemotron:
        question.askingShark === "nemotron"
          ? question.angle
          : "React to the founder answer through operating rigor, capacity, margin, and execution risk.",
      deepseek:
        question.askingShark === "deepseek"
          ? question.angle
          : "React to the founder answer through growth, market wedge, distribution, and defensibility.",
      judge:
        question.askingShark === "judge"
          ? question.angle
          : "React to the founder answer through deal logic, risk, valuation, and investor terms.",
    },
    userAnswer: "",
    sharkReactions: {},
    scores: {},
    interest: {},
    status: "awaiting-answer",
  }));
}

function normalizeSharkReaction(raw = {}, sharkKey) {
  return {
    shark: sharkKey,
    label: sharkLabel(sharkKey),
    reaction: sanitizeInput(raw.reaction, "The answer needs clearer proof before this shark can move closer to a deal.").slice(0, 520),
    score: toScore(raw.score, 60),
    interest: toScore(raw.interest, 50),
    pressure: sanitizeInput(raw.pressure, "What proof can you show that this answer is repeatable?").slice(0, 260),
    dealSignal: sanitizeInput(raw.dealSignal, "Still evaluating.").slice(0, 220),
    investorNote: sanitizeInput(raw.investorNote, "Tighten the answer with customer proof, economics, and a milestone.").slice(0, 240),
  };
}

function normalizeOffer(raw = {}, sharkKey) {
  const decision = ["offer", "pass", "join"].includes(String(raw.decision || "").toLowerCase())
    ? String(raw.decision).toLowerCase()
    : "pass";
  return {
    shark: sharkKey,
    label: sharkLabel(sharkKey),
    decision,
    amount: decision === "pass" ? "" : sanitizeInput(raw.amount, "Conditional check pending diligence.").slice(0, 120),
    equity: decision === "pass" ? "" : sanitizeInput(raw.equity, "Negotiable").slice(0, 80),
    conditions: Array.isArray(raw.conditions)
      ? raw.conditions.slice(0, 5).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    rationale: sanitizeInput(raw.rationale, "The founder must show stronger proof before this shark commits.").slice(0, 520),
    improvementNote: sanitizeInput(raw.improvementNote, "Answer with sharper metrics, proof, risk control, and use of funds.").slice(0, 260),
    confidence: toScore(raw.confidence, decision === "pass" ? 35 : 68),
  };
}

function normalizeCounterResponse(raw = {}, sharkKey) {
  const decision = ["accept", "revise", "walk"].includes(String(raw.decision || "").toLowerCase())
    ? String(raw.decision).toLowerCase()
    : "revise";
  return {
    shark: sharkKey,
    label: sharkLabel(sharkKey),
    decision,
    revisedAmount: sanitizeInput(raw.revisedAmount, "").slice(0, 120),
    revisedEquity: sanitizeInput(raw.revisedEquity, "").slice(0, 80),
    conditions: Array.isArray(raw.conditions)
      ? raw.conditions.slice(0, 5).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    message: sanitizeInput(raw.message, "The shark needs clearer logic before changing terms.").slice(0, 520),
    finalAdvice: sanitizeInput(raw.finalAdvice, "Make the counter specific, rational, and tied to milestones.").slice(0, 260),
  };
}

async function repairCounterOfferResponse({ sharkKey, prompt, practiceContext, room, counter, rawOutput }) {
  const repairRole = sharkKey === "deepseek" ? modelConfig.nemotron : modelConfig.deepseek;
  const repairedText = await callText({
    role: repairRole,
    temperature: 0.16,
    maxTokens: 1400,
    messages: [
      {
        role: "system",
        content:
          "Write a final Shark Tank counter-offer response using only the requested labels. Do not copy placeholders, schema text, instructions, draft notes, markdown, or analysis.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Respond using exactly these labels:",
              "DECISION:",
              "REVISED AMOUNT:",
              "REVISED EQUITY:",
              "CONDITIONS:",
              "MESSAGE:",
              "FINAL ADVICE:",
              "",
              `Write as ${sharkLabel(sharkKey)}.`,
              sharkProfiles()[sharkKey].thesis,
              "decision must be accept, revise, or walk.",
              "If the founder materially solved your objections, revise into a conditional offer. If not, walk.",
              "",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              `Business prompt:\n${prompt}`,
              "",
              `Final deal before counter:\n${JSON.stringify(room.finalDeal)}`,
              "",
              `Founder counter-offer:\n${counter}`,
              "",
              `Malformed previous output:\n${rawOutput}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return normalizeCounterResponse(
    {
      decision: extractLabeledValue(repairedText, ["DECISION"]),
      revisedAmount: extractLabeledValue(repairedText, ["REVISED AMOUNT", "REVISED_AMOUNT"]),
      revisedEquity: extractLabeledValue(repairedText, ["REVISED EQUITY", "REVISED_EQUITY"]),
      conditions: parseListValue(extractLabeledValue(repairedText, ["CONDITIONS"])),
      message: extractLabeledValue(repairedText, ["MESSAGE"]),
      finalAdvice: extractLabeledValue(repairedText, ["FINAL ADVICE", "FINAL_ADVICE"]),
    },
    sharkKey,
  );
}

function isPlaceholderCounterResponse(response = {}) {
  const message = sanitizeInput(response.message);
  return (
    isPlaceholderText(response.message) ||
    isPlaceholderText(response.finalAdvice) ||
    message.length < 40
  );
}

function roomTotals(room) {
  const totals = {};
  const counts = {};
  for (const round of room.rounds || []) {
    for (const key of sharkKeys) {
      const score = Number(round.scores?.[key]);
      if (Number.isFinite(score)) {
        totals[key] = (totals[key] || 0) + score;
        counts[key] = (counts[key] || 0) + 1;
      }
    }
  }

  return Object.fromEntries(
    sharkKeys.map((key) => [key, counts[key] ? Math.round(totals[key] / counts[key]) : null]),
  );
}

function dealOutcomeKey(outcome) {
  const normalized = sanitizeInput(outcome).toLowerCase();
  if (normalized.includes("no")) return "no_deal";
  if (normalized.includes("conditional")) return "conditional_deal";
  return "deal";
}

function isReportableDealOutcome(outcome) {
  return ["Deal", "Conditional deal", "No deal"].includes(sanitizeInput(outcome));
}

function saveRoom(room) {
  const now = new Date().toISOString();
  const createdAt = room.createdAt || now;
  const updatedRoom = { ...room, createdAt, updatedAt: now };
  db.prepare(
    "INSERT OR REPLACE INTO rooms (id, created_at, updated_at, status, prompt, data) VALUES (?, ?, ?, ?, ?, ?)",
  ).run(updatedRoom.id, createdAt, now, updatedRoom.status, updatedRoom.prompt, JSON.stringify(updatedRoom));
  return updatedRoom;
}

function getRoom(id) {
  const row = db.prepare("SELECT data FROM rooms WHERE id = ?").get(id);
  if (!row) return null;
  return JSON.parse(row.data);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function winnerName(winner) {
  if (winner === "deal") return "Deal";
  if (winner === "conditional_deal") return "Conditional deal";
  if (winner === "no_deal") return "No deal";
  if (winner === "nemotron") return modelConfig.nemotron.label;
  if (winner === "deepseek") return modelConfig.deepseek.label;
  return "Tie";
}

function getCacheKey(prompt, practiceContext = normalizePracticeContext()) {
  const normalizedPrompt = sanitizeInput(prompt)
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
  const modelSignature = JSON.stringify({
    nemotron: modelConfig.nemotron.model,
    nemotronBase: modelConfig.nemotron.baseUrl,
    deepseek: modelConfig.deepseek.model,
    deepseekBase: modelConfig.deepseek.baseUrl,
    judge: modelConfig.judge.model,
    judgeBase: modelConfig.judge.baseUrl,
  });

  return createHash("sha256")
    .update(`${CACHE_VERSION}\n${normalizedPrompt}\n${JSON.stringify(practiceContext)}\n${modelSignature}`)
    .digest("hex");
}

function getStepCacheKey({ prompt, step, extra = "", practiceContext = normalizePracticeContext() }) {
  return createHash("sha256")
    .update(
      JSON.stringify({
        version: CACHE_VERSION,
        prompt: sanitizeInput(prompt).toLowerCase().replace(/\s+/g, " ").trim(),
        practiceContext,
        step,
        extra,
        models: modelConfig,
      }),
    )
    .digest("hex");
}

async function withChunkCache({ prompt, practiceContext, step, extra, producer }) {
  const cacheKey = getStepCacheKey({ prompt, practiceContext, step, extra });
  const row = db.prepare("SELECT data FROM llm_chunks WHERE cache_key = ?").get(cacheKey);
  if (row) {
    return JSON.parse(row.data);
  }

  const data = await producer();
  db.prepare(
    "INSERT OR REPLACE INTO llm_chunks (cache_key, created_at, step, data) VALUES (?, ?, ?, ?)",
  ).run(cacheKey, new Date().toISOString(), step, JSON.stringify(data));
  return data;
}

async function withChunkCacheMeta({ prompt, practiceContext, step, extra, producer }) {
  const cacheKey = getStepCacheKey({ prompt, practiceContext, step, extra });
  const row = db.prepare("SELECT data FROM llm_chunks WHERE cache_key = ?").get(cacheKey);
  if (row) {
    return { cached: true, data: JSON.parse(row.data) };
  }

  const data = await producer();
  db.prepare(
    "INSERT OR REPLACE INTO llm_chunks (cache_key, created_at, step, data) VALUES (?, ?, ?, ?)",
  ).run(cacheKey, new Date().toISOString(), step, JSON.stringify(data));
  return { cached: false, data };
}

function saveReport(data, cacheKey) {
  if (cacheKey) {
    const existing = db.prepare("SELECT id, created_at FROM reports WHERE cache_key = ?").get(cacheKey);
    if (existing) {
      return { id: existing.id, createdAt: existing.created_at };
    }
  }

  const id = randomUUID();
  const createdAt = new Date().toISOString();
  try {
    db.prepare(
      "INSERT INTO reports (id, cache_key, created_at, title, winner, prompt, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
    ).run(
      id,
      cacheKey || null,
      createdAt,
      data.businessTitle || "AI Shark Tank Report",
      data.winner || "tie",
      data.prompt || "",
      JSON.stringify({ ...data, reportId: id, reportUrl: `/reports/${id}`, generatedAt: data.generatedAt || createdAt }),
    );
  } catch (error) {
    const existing = cacheKey
      ? db.prepare("SELECT id, created_at FROM reports WHERE cache_key = ?").get(cacheKey)
      : null;
    if (existing) {
      return { id: existing.id, createdAt: existing.created_at };
    }

    throw error;
  }

  return { id, createdAt };
}

function updateReportData(id, data) {
  const existing = db.prepare("SELECT created_at FROM reports WHERE id = ?").get(id);
  if (!existing) return null;
  db.prepare("UPDATE reports SET winner = ?, title = ?, prompt = ?, data = ? WHERE id = ?").run(
    data.winner || "tie",
    data.businessTitle || "AI Shark Tank Report",
    data.prompt || "",
    JSON.stringify({ ...data, reportId: id, reportUrl: `/reports/${id}` }),
    id,
  );
  return { id, createdAt: existing.created_at };
}

function getReport(id) {
  const row = db.prepare("SELECT data FROM reports WHERE id = ?").get(id);
  return row
    ? {
        ...enrichReportData(JSON.parse(row.data)),
        drillAttempts: listDrillAttemptsForReport(id),
      }
    : null;
}

function derivePracticeDrills(report = {}) {
  const existing = normalizePracticeDrills(report.practiceDrills);
  if (existing.length) {
    return existing;
  }

  const rounds = Array.isArray(report.rounds) ? report.rounds : [];
  return rounds.slice(0, 3).map((round, index) => ({
    name: sanitizeInput(round.title || round.focus, `Round ${index + 1} Drill`).slice(0, 80),
    goal: sanitizeInput(
      round.focus,
      "Practice answering a real investor question from this room.",
    ).slice(0, 180),
    prompt: sanitizeInput(
      round.panelQuestion || round.question,
      "Answer this investor question in 45 seconds with one metric, one risk, and one next milestone.",
    ).slice(0, 320),
  }));
}

function enrichReportData(report = {}) {
  return {
    ...report,
    practiceDrills: derivePracticeDrills(report),
  };
}

function saveDrillAttempt({ reportId, drill, answer, feedback }) {
  const id = randomUUID();
  const createdAt = new Date().toISOString();
  db.prepare(
    "INSERT INTO drill_attempts (id, report_id, created_at, drill_name, drill_prompt, answer, score, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
  ).run(
    id,
    reportId || null,
    createdAt,
    drill.name,
    drill.prompt,
    answer,
    toScore(feedback.score),
    JSON.stringify({
      id,
      reportId: reportId || null,
      createdAt,
      drill,
      answer,
      feedback,
    }),
  );

  return { id, createdAt };
}

function drillAttemptFromRow(row) {
  let data = {};
  try {
    data = JSON.parse(row.data);
  } catch {
    data = {};
  }

  return {
    id: row.id,
    reportId: row.report_id,
    createdAt: row.created_at,
    drillName: row.drill_name,
    drillPrompt: row.drill_prompt,
    score: toScore(row.score),
    verdict: sanitizeInput(data.feedback?.verdict).slice(0, 180),
    nextPracticeMove: sanitizeInput(data.feedback?.nextPracticeMove).slice(0, 180),
  };
}

function listDrillAttempts(limit = 24) {
  const rows = db
    .prepare("SELECT id, report_id, created_at, drill_name, drill_prompt, score, data FROM drill_attempts ORDER BY created_at DESC LIMIT ?")
    .all(Math.max(1, Math.min(50, Number(limit) || 24)));

  return rows.map(drillAttemptFromRow);
}

function listDrillAttemptsForReport(reportId, limit = 8) {
  const rows = db
    .prepare("SELECT id, report_id, created_at, drill_name, drill_prompt, score, data FROM drill_attempts WHERE report_id = ? ORDER BY created_at DESC LIMIT ?")
    .all(reportId, Math.max(1, Math.min(20, Number(limit) || 8)));

  return rows.map(drillAttemptFromRow);
}

function summarizeDrillAttempts(attempts) {
  const scores = attempts
    .map((attempt) => Number(attempt.score))
    .filter((score) => Number.isFinite(score));
  const latest = attempts[0] || null;
  const best = attempts.reduce((bestAttempt, attempt) => {
    if (!bestAttempt || attempt.score > bestAttempt.score) {
      return attempt;
    }
    return bestAttempt;
  }, null);

  const recent = attempts.slice(0, 5);
  const trend =
    scores.length >= 2
      ? scores[0] - scores[Math.min(scores.length - 1, 4)]
      : null;

  return {
    attemptCount: attempts.length,
    averageScore: scores.length
      ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length)
      : null,
    bestScore: best?.score ?? null,
    latestScore: latest?.score ?? null,
    trend,
    latest,
    best,
    recent,
  };
}

function getWeakestSkill(skillScores) {
  if (!Array.isArray(skillScores)) {
    return null;
  }

  return skillScores
    .filter((skill) => Number.isFinite(Number(skill.score)))
    .reduce((weakest, skill) => {
      const current = {
        label: sanitizeInput(skill.label, "Skill"),
        score: toScore(skill.score),
        note: sanitizeInput(skill.note).slice(0, 160),
      };

      return !weakest || current.score < weakest.score ? current : weakest;
    }, null);
}

function countBy(items) {
  return items.reduce((counts, item) => {
    if (!item?.key || !item?.label) {
      return counts;
    }

    counts[item.key] ||= { key: item.key, label: item.label, count: 0 };
    counts[item.key].count += 1;
    return counts;
  }, {});
}

function sortedCounts(items) {
  return Object.values(countBy(items)).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function averageSkillScores(reports) {
  const buckets = new Map();

  for (const report of reports) {
    for (const skill of report.skillScores || []) {
      if (!skill?.key || !Number.isFinite(Number(skill.score))) {
        continue;
      }

      const existing = buckets.get(skill.key) || {
        key: skill.key,
        label: sanitizeInput(skill.label, skill.key),
        total: 0,
        count: 0,
        latestNote: "",
      };
      existing.total += toScore(skill.score);
      existing.count += 1;
      existing.latestNote ||= sanitizeInput(skill.note).slice(0, 160);
      buckets.set(skill.key, existing);
    }
  }

  return Array.from(buckets.values())
    .map((bucket) => ({
      key: bucket.key,
      label: bucket.label,
      score: Math.round(bucket.total / bucket.count),
      count: bucket.count,
      note: bucket.latestNote,
    }))
    .sort((a, b) => a.score - b.score || a.label.localeCompare(b.label));
}

function objectiveForSkill(skillKey, fallback = "growth") {
  const map = {
    clarity: "clarity",
    proof: "clarity",
    economics: "economics",
    scale: "growth",
    moat: "growth",
    deal: "deal",
  };
  return map[skillKey] || fallback;
}

function practiceLabel(kind, key, fallback) {
  if (kind === "stage") {
    return practiceStages[key]?.label || fallback;
  }
  if (kind === "objective") {
    return practiceObjectives[key]?.label || fallback;
  }
  if (kind === "length") {
    return practiceLengths[key]?.label || fallback;
  }
  return fallback;
}

function createTrainingPlan({ reports, drillProgress, weakestAverage, latestDrill, recommendedSetup }) {
  if (!reports.length) {
    return [
      {
        title: "Set the baseline",
        action: "Run a Quick Room with your rough business idea.",
        detail: "Start with a short investor room so the app can identify the first weak skill.",
      },
      {
        title: "Tighten the pitch",
        action: "Open Founder Prep and use the rewritten pitch.",
        detail: "Practice one clean version before running a full investor duel.",
      },
      {
        title: "Save one drill",
        action: "Complete one shark-scored drill from the report.",
        detail: "The dashboard starts tracking your own score after the first answer.",
      },
    ];
  }

  const plan = [];
  plan.push({
    title: "Next room",
    action: `${recommendedSetup.lengthLabel}: ${recommendedSetup.stageLabel} / ${recommendedSetup.objectiveLabel}`,
    detail: recommendedSetup.reason,
  });

  if (weakestAverage) {
    plan.push({
      title: `Repair ${weakestAverage.label}`,
      action: `Answer three investor questions focused on ${weakestAverage.label.toLowerCase()}.`,
      detail: weakestAverage.note || `Average score is ${weakestAverage.score}; the next practice should target this skill directly.`,
    });
  } else {
    plan.push({
      title: "Create a fresh scorecard",
      action: "Run one new room so the sharks can generate readiness and skill scores.",
      detail: "Older reports may not include the newer skill map, so a fresh run improves the dashboard.",
    });
  }

  if (latestDrill) {
    plan.push({
      title: "Human rep",
      action: latestDrill.prompt,
      detail: drillProgress?.attemptCount
        ? `Latest drill score is ${drillProgress.latestScore ?? "-"}; try to beat your best score of ${drillProgress.bestScore ?? "-"}.`
        : "Score your own answer once so the dashboard can track founder improvement.",
    });
  } else {
    plan.push({
      title: "Generate drills",
      action: "Run a new report and open its practice drills.",
      detail: "Drills turn the simulation into active rehearsal instead of passive reading.",
    });
  }

  return plan.slice(0, 3);
}

function createPlanSetup({ latest, latestDrill, recommendedSetup, trainingPlan }) {
  const focusLine = trainingPlan
    .map((item, index) => `${index + 1}. ${item.title}: ${item.action}`)
    .join("\n");
  const drillLine = latestDrill
    ? `Human drill to practice:\n${latestDrill.prompt}`
    : "Human drill to practice:\nRun the room, open the report, and score one founder answer.";

  return {
    ...recommendedSetup,
    prompt: [
      latest?.prompt && `Business prompt:\n${latest.prompt}`,
      "Training focus:",
      focusLine,
      drillLine,
    ]
      .filter(Boolean)
      .join("\n\n")
      .slice(0, 5000),
  };
}

function listReports(limit = 24) {
  const rows = db
    .prepare("SELECT id, created_at, title, winner, prompt, data FROM reports ORDER BY created_at DESC LIMIT ?")
    .all(Math.max(1, Math.min(50, Number(limit) || 24)));

  return rows.map((row) => {
    let data = {};
    try {
      data = JSON.parse(row.data);
    } catch {
      data = {};
    }

    const stage = data.practiceContext?.stage || "early";
    const objective = data.practiceContext?.objective || "growth";
    const length = data.practiceContext?.length || "full";

    return {
      id: row.id,
      createdAt: row.created_at,
      title: row.title,
      winner: row.winner,
      kind: data.kind || "pitch-duel",
      dealOutcome: data.finalDeal?.outcome || null,
      reportUrl: `/reports/${row.id}`,
      prompt: data.prompt || row.prompt || "",
      promptSummary: data.promptSummary || "",
      stage,
      stageLabel: practiceLabel("stage", stage, data.practiceContext?.stageLabel || "Practice"),
      objective,
      objectiveLabel: practiceLabel("objective", objective, data.practiceContext?.objectiveLabel || "Pitch"),
      length,
      lengthLabel: practiceLabel("length", length, data.practiceContext?.lengthLabel || `${Array.isArray(data.rounds) ? data.rounds.length : 0} rounds`),
      readinessScore: data.readinessScore ?? null,
      weakestSkill: getWeakestSkill(data.skillScores),
      skillScores: Array.isArray(data.skillScores) ? data.skillScores : [],
      practiceDrills: derivePracticeDrills(data),
      totals: data.totals || null,
      finalDeal: data.finalDeal || null,
    };
  });
}

function summarizeReports(reports, drillAttempts = []) {
  const readinessScores = reports
    .filter((report) => report.readinessScore != null)
    .map((report) => Number(report.readinessScore))
    .filter((score) => Number.isFinite(score));

  const skillAverages = averageSkillScores(reports);
  const weakestAverage = skillAverages[0] || null;
  const latest = reports[0] || null;
  const recommendedObjective = objectiveForSkill(weakestAverage?.key, latest?.objective || "growth");
  const latestDrill = reports.find((report) => report.practiceDrills?.length)?.practiceDrills?.[0] || null;
  const drillProgress = summarizeDrillAttempts(drillAttempts);
  const recommendedSetup = reports.length
    ? {
        stage: latest.stage || "early",
        stageLabel: latest.stageLabel || "Early Traction",
        objective: recommendedObjective,
        objectiveLabel: practiceObjectives[recommendedObjective]?.label || "Growth Plan",
        length: "quick",
        lengthLabel: practiceLengths.quick.label,
        reason: weakestAverage
          ? `${weakestAverage.label} is the lowest average skill, so the next quick room should target it.`
          : "Run a quick room next to create a fresher baseline.",
      }
    : {
        stage: "early",
        stageLabel: practiceStages.early.label,
        objective: "growth",
        objectiveLabel: practiceObjectives.growth.label,
        length: "quick",
        lengthLabel: practiceLengths.quick.label,
        reason: "Start with a short room to establish a baseline before running a full investor duel.",
      };

  const trainingPlan = createTrainingPlan({
    reports,
    drillProgress,
    weakestAverage,
    latestDrill,
    recommendedSetup,
  });

  return {
    sessionCount: reports.length,
    averageReadiness: readinessScores.length
      ? Math.round(readinessScores.reduce((sum, score) => sum + score, 0) / readinessScores.length)
      : null,
    bestReadiness: readinessScores.length ? Math.max(...readinessScores) : null,
    latestStage: reports[0]?.stageLabel || null,
    latestWinner: reports[0]?.winner || null,
    latestWeakestSkill: reports.find((report) => report.weakestSkill)?.weakestSkill || null,
    dashboard: {
      stageMix: sortedCounts(reports.map((report) => ({ key: report.stage, label: report.stageLabel }))),
      focusMix: sortedCounts(reports.map((report) => ({ key: report.objective, label: report.objectiveLabel }))),
      skillAverages,
      latestDrill,
      drillProgress,
      recommendedSetup,
      trainingPlan,
      planSetup: createPlanSetup({
        latest,
        latestDrill,
        recommendedSetup,
        trainingPlan,
      }),
    },
  };
}

function getCachedReport(cacheKey) {
  const row = db.prepare("SELECT data FROM reports WHERE cache_key = ?").get(cacheKey);
  if (!row) {
    return null;
  }

  const data = JSON.parse(row.data);
  return {
    ...enrichReportData(data),
    cached: true,
  };
}

function buildSimulationData({ prompt, practiceContext, brief, nemotron, deepseek, judgement, negotiation, report, currentRoundIndex }) {
  const partialRounds = brief.questions.map((question, index) => ({
    ...question,
    nemotron: nemotron?.answers?.[index] || null,
    deepseek: deepseek?.answers?.[index] || null,
    scores: judgement?.rounds?.[index]?.scores || null,
    winner: judgement?.rounds?.[index]?.winner || null,
    judgeComment: judgement?.rounds?.[index]?.judgeComment || "",
  }));

  return {
    generatedAt: report?.createdAt || new Date().toISOString(),
    prompt,
    practiceContext,
    models: modelConfig,
    businessTitle: brief.businessTitle,
    promptSummary: brief.promptSummary,
    promptDiagnostics: brief.promptDiagnostics || null,
    facts: brief.facts,
    nemotron: {
      label: modelConfig.nemotron.label,
      model: modelConfig.nemotron.model,
      openingPosition: nemotron?.openingPosition || `${modelConfig.nemotron.label} is preparing its pitch.`,
    },
    deepseek: {
      label: modelConfig.deepseek.label,
      model: modelConfig.deepseek.model,
      openingPosition: deepseek?.openingPosition || "DeepSeek is preparing its pitch.",
    },
    judge: {
      label: modelConfig.judge.label,
      model: modelConfig.judge.model,
    },
    rounds: judgement?.rounds || partialRounds,
    totals: judgement?.totals || null,
    winner: judgement?.winner || null,
    verdict: judgement?.verdict || "",
    strongestMoment: judgement?.strongestMoment || "",
    weakestMoment: judgement?.weakestMoment || "",
    nextPractice: judgement?.nextPractice || [],
    readinessScore: judgement?.readinessScore || null,
    skillScores: judgement?.skillScores || [],
    practiceDrills: judgement?.practiceDrills || [],
    rewrittenPitch: judgement?.rewrittenPitch || "",
    investorHooks: judgement?.investorHooks || [],
    investorObjections: judgement?.investorObjections || [],
    nextDataToCollect: judgement?.nextDataToCollect || [],
    recommendedAskFraming: judgement?.recommendedAskFraming || "",
    negotiation: negotiation || null,
    reportId: report?.id || null,
    reportUrl: report?.id ? `/reports/${report.id}` : null,
    currentRoundIndex,
  };
}

function sendStream(response, event) {
  response.write(`${JSON.stringify(event)}\n`);
}

function renderSharkRoomReportHtml(report) {
  const rounds = Array.isArray(report.rounds) ? report.rounds : [];
  const facts = Array.isArray(report.facts) ? report.facts : [];
  const finalDeal = report.finalDeal || {};
  const offers = Array.isArray(finalDeal.offers) ? finalDeal.offers : [];
  const counters = Array.isArray(finalDeal.counterOffers) ? finalDeal.counterOffers : [];
  const bestOffer = finalDeal.bestOffer || {};
  const practiceDrills = Array.isArray(report.practiceDrills) ? report.practiceDrills : [];

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(report.businessTitle)} · AI Shark Tank Deal Memo</title>
    <style>
      :root { color: #111; background: #f7f7f4; font-family: Helvetica, "Helvetica Neue", Arial, sans-serif; }
      body { margin: 0; }
      main { width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 44px 0 72px; }
      header { border-bottom: 1px solid #d8d8d3; padding-bottom: 24px; }
      .kicker { color: #60605b; font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
      h1 { margin: 8px 0 10px; font-size: clamp(34px, 6vw, 72px); line-height: .94; }
      h2 { margin: 32px 0 12px; font-size: 26px; }
      h3 { margin: 0 0 8px; font-size: 18px; }
      p { color: #333; line-height: 1.55; }
      .summary, .offers, .skills { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
      .box, .offer, .round, .drill { border: 1px solid #d8d8d3; border-radius: 10px; padding: 16px; background: #fff; }
      .box span, .offer span, .round span, .drill span { display: block; color: #777; font-size: 12px; font-weight: 700; text-transform: uppercase; }
      .box strong { display: block; margin-top: 6px; font-size: 22px; }
      .offer strong { text-transform: capitalize; }
      ul { padding-left: 20px; }
      li { margin: 7px 0; color: #333; }
      .round { margin-top: 14px; }
      .answer { border-top: 1px solid #ecece7; margin-top: 12px; padding-top: 12px; }
      .muted { color: #666; }
      @media print { body { background: #fff; } main { width: auto; padding: 24px; } .box, .offer, .round { break-inside: avoid; } }
      @media (max-width: 760px) { .summary, .offers, .skills { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <main>
      <header>
        <div class="kicker">AI Shark Tank Deal Memo</div>
        <h1>${escapeHtml(report.businessTitle)}</h1>
        <p>${escapeHtml(report.promptSummary)}</p>
        <p class="muted">Generated ${escapeHtml(new Date(report.generatedAt).toLocaleString())}</p>
        <div class="summary">
          <div class="box"><span>Outcome</span><strong>${escapeHtml(finalDeal.outcome || winnerName(report.winner))}</strong></div>
          <div class="box"><span>Best offer</span><strong>${escapeHtml(bestOffer.label || bestOffer.shark || "None")}</strong></div>
          <div class="box"><span>Rounds</span><strong>${escapeHtml(rounds.length)}</strong></div>
        </div>
      </header>

      <section>
        <h2>Business Facts</h2>
        <ul>${facts.map((fact) => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>
      </section>

      <section>
        <h2>Final Deal</h2>
        <p>${escapeHtml(finalDeal.verdict || "")}</p>
        <div class="offers">
          ${offers.map((offer) => `
            <article class="offer">
              <span>${escapeHtml(offer.label)}</span>
              <h3>${escapeHtml(offer.decision)}</h3>
              <p><strong>${escapeHtml(offer.amount || "No check")}</strong>${offer.equity ? ` for ${escapeHtml(offer.equity)}` : ""}</p>
              <p>${escapeHtml(offer.rationale)}</p>
              <ul>${(offer.conditions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </article>
          `).join("")}
        </div>
      </section>

      ${counters.length ? `
      <section>
        <h2>Counter-Offers</h2>
        ${counters.map((counter) => `
          <article class="round">
            <span>${escapeHtml(counter.label)} · ${escapeHtml(counter.decision)}</span>
            <p>${escapeHtml(counter.message)}</p>
            <p><strong>${escapeHtml(counter.revisedAmount || "")}</strong>${counter.revisedEquity ? ` for ${escapeHtml(counter.revisedEquity)}` : ""}</p>
            <p class="muted">${escapeHtml(counter.finalAdvice)}</p>
          </article>
        `).join("")}
      </section>` : ""}

      <section>
        <h2>Practice Notes</h2>
        <p><strong>Strongest answer:</strong> ${escapeHtml(finalDeal.strongestAnswer || "")}</p>
        <p><strong>Weakest answer:</strong> ${escapeHtml(finalDeal.weakestAnswer || "")}</p>
        <ul>${(finalDeal.nextPractice || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </section>

      <section>
        <h2>Practice Drills</h2>
        ${practiceDrills.map((drill) => `
          <article class="drill">
            <span>${escapeHtml(drill.name)}</span>
            <p>${escapeHtml(drill.goal)}</p>
            <p><strong>${escapeHtml(drill.prompt)}</strong></p>
          </article>
        `).join("")}
      </section>

      <section>
        <h2>Transcript</h2>
        ${rounds.map((round, index) => `
          <article class="round">
            <span>Round ${index + 1} · ${escapeHtml(round.focus)}</span>
            <h3>${escapeHtml(round.panelQuestion)}</h3>
            <p><strong>Founder answer:</strong> ${escapeHtml(round.userAnswer)}</p>
            ${sharkKeys.map((key) => {
              const reaction = round.sharkReactions?.[key] || {};
              return `<div class="answer"><strong>${escapeHtml(sharkLabel(key))} · ${escapeHtml(round.scores?.[key] ?? "-")}</strong><p>${escapeHtml(reaction.reaction || "")}</p><p class="muted">${escapeHtml(reaction.pressure || "")}</p></div>`;
            }).join("")}
          </article>
        `).join("")}
      </section>
    </main>
  </body>
</html>`;
}

function renderReportHtml(report) {
  if (report.kind === "user-shark-room") {
    return renderSharkRoomReportHtml(report);
  }

  const rounds = Array.isArray(report.rounds) ? report.rounds : [];
  const negotiation = report.negotiation || {};
  const facts = Array.isArray(report.facts) ? report.facts : [];
  const practice = Array.isArray(report.nextPractice) ? report.nextPractice : [];
  const hooks = Array.isArray(report.investorHooks) ? report.investorHooks : [];
  const objections = Array.isArray(report.investorObjections) ? report.investorObjections : [];
  const dataToCollect = Array.isArray(report.nextDataToCollect) ? report.nextDataToCollect : [];
  const diagnostics = report.promptDiagnostics || {};
  const missingFacts = Array.isArray(diagnostics.missingFacts) ? diagnostics.missingFacts : [];
  const skillScores = Array.isArray(report.skillScores) ? report.skillScores : [];
  const practiceDrills = Array.isArray(report.practiceDrills) ? report.practiceDrills : [];

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(report.businessTitle)} · AI Shark Tank Report</title>
    <style>
      :root { color: #111; background: #f7f7f4; font-family: Helvetica, "Helvetica Neue", Arial, sans-serif; }
      body { margin: 0; }
      main { width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 44px 0 72px; }
      header { border-bottom: 1px solid #d8d8d3; padding-bottom: 24px; }
      .kicker { color: #60605b; font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
      h1 { margin: 8px 0 10px; font-size: clamp(34px, 6vw, 72px); line-height: .94; letter-spacing: -0.03em; }
      h2 { margin: 32px 0 12px; font-size: 26px; letter-spacing: -0.02em; }
      h3 { margin: 0 0 8px; font-size: 18px; }
      p { color: #333; line-height: 1.55; }
      .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 22px; }
      .box { border: 1px solid #d8d8d3; border-radius: 10px; padding: 16px; background: #fff; }
      .box span { display: block; color: #777; font-size: 12px; font-weight: 700; text-transform: uppercase; }
      .box strong { display: block; margin-top: 6px; font-size: 22px; }
      ul { padding-left: 20px; }
      li { margin: 7px 0; color: #333; }
      .round { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; border-top: 1px solid #d8d8d3; padding-top: 18px; margin-top: 18px; }
      .round-head { grid-column: 1 / -1; }
      .answer { background: #fff; border: 1px solid #deded9; border-radius: 10px; padding: 16px; }
      .score { color: #111; font-weight: 800; }
      .decision { border: 2px solid #111; border-radius: 12px; padding: 18px; background: #fff; }
      .skills { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
      .skill { border: 1px solid #d8d8d3; border-radius: 10px; padding: 14px; background: #fff; }
      .skill strong { display: block; font-size: 22px; }
      .skill span { color: #777; font-size: 12px; font-weight: 700; text-transform: uppercase; }
      .drills { display: grid; gap: 12px; }
      .drill { border: 1px solid #d8d8d3; border-radius: 10px; padding: 14px; background: #fff; }
      .muted { color: #666; }
      @media print { body { background: #fff; } main { width: auto; padding: 24px; } .box, .answer, .decision { break-inside: avoid; } }
      @media (max-width: 760px) { .summary, .round, .skills { grid-template-columns: 1fr; } .round-head { grid-column: auto; } }
    </style>
  </head>
  <body>
    <main>
      <header>
        <div class="kicker">AI Shark Tank Final Report</div>
        <h1>${escapeHtml(report.businessTitle)}</h1>
        <p>${escapeHtml(report.promptSummary)}</p>
        <p class="muted">Generated ${escapeHtml(new Date(report.generatedAt).toLocaleString())}</p>
        <div class="summary">
          <div class="box"><span>Winner</span><strong>${escapeHtml(winnerName(report.winner))}</strong></div>
          <div class="box"><span>${escapeHtml(modelConfig.nemotron.label.replace(" Founder", ""))}</span><strong>${escapeHtml(report.totals?.nemotron ?? "-")}</strong></div>
          <div class="box"><span>DeepSeek</span><strong>${escapeHtml(report.totals?.deepseek ?? "-")}</strong></div>
          <div class="box"><span>Readiness</span><strong>${escapeHtml(report.readinessScore ?? "-")}</strong></div>
        </div>
      </header>

      <section>
        <h2>Practice Context</h2>
        <p><strong>Stage:</strong> ${escapeHtml(report.practiceContext?.stageLabel || "Early Traction")}</p>
        <p><strong>Objective:</strong> ${escapeHtml(report.practiceContext?.objectiveLabel || "Growth Plan")}</p>
        <p><strong>Room:</strong> ${escapeHtml(report.practiceContext?.lengthLabel || `${rounds.length} rounds`)}</p>
      </section>

      <section>
        <h2>Business Facts</h2>
        <ul>${facts.map((fact) => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>
      </section>

      <section>
        <h2>Founder Readiness Brief</h2>
        <p><strong>Stage fit:</strong> ${escapeHtml(diagnostics.stageFit || "")}</p>
        <p><strong>Strongest signal:</strong> ${escapeHtml(diagnostics.strongestSignal || "")}</p>
        <p><strong>First practice move:</strong> ${escapeHtml(diagnostics.firstPracticeMove || "")}</p>
        <ul>${missingFacts.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </section>

      <section>
        <h2>Practice Pitch</h2>
        <p>${escapeHtml(report.rewrittenPitch || "")}</p>
        <p><strong>Ask framing:</strong> ${escapeHtml(report.recommendedAskFraming || "")}</p>
      </section>

      <section>
        <h2>Founder Skill Map</h2>
        <div class="skills">
          ${skillScores.map((skill) => `
            <div class="skill">
              <span>${escapeHtml(skill.label)}</span>
              <strong>${escapeHtml(skill.score ?? "-")}</strong>
              <p>${escapeHtml(skill.note || "")}</p>
            </div>
          `).join("")}
        </div>
      </section>

      <section>
        <h2>Practice Drills</h2>
        <div class="drills">
          ${practiceDrills.map((drill) => `
            <div class="drill">
              <h3>${escapeHtml(drill.name)}</h3>
              <p><strong>Goal:</strong> ${escapeHtml(drill.goal)}</p>
              <p><strong>Rehearse:</strong> ${escapeHtml(drill.prompt)}</p>
            </div>
          `).join("")}
        </div>
      </section>

      <section>
        <h2>Final Negotiation</h2>
        <div class="decision">
          <h3>${escapeHtml(negotiation.decision || "Final decision")}</h3>
          <p><strong>Offer:</strong> ${escapeHtml(negotiation.offer || "No formal offer.")}</p>
          <p><strong>Negotiation:</strong> ${escapeHtml(negotiation.negotiationSummary || "")}</p>
          <p><strong>Reason:</strong> ${escapeHtml(negotiation.reason || report.verdict || "")}</p>
        </div>
      </section>

      <section>
        <h2>Round Transcript</h2>
        ${rounds.map((round, index) => `
          <article class="round">
            <div class="round-head">
              <div class="kicker">Round ${index + 1} · ${escapeHtml(round.focus)}</div>
              <h3>${escapeHtml(round.question)}</h3>
              <p><strong>${escapeHtml(winnerName(round.winner))}</strong>: ${escapeHtml(round.judgeComment)}</p>
            </div>
            <div class="answer">
              <h3>${escapeHtml(modelConfig.nemotron.label)} <span class="score">${escapeHtml(round.scores?.nemotron ?? "-")}</span></h3>
              <p>${escapeHtml(round.nemotron?.answer)}</p>
              <p class="muted">${escapeHtml(round.nemotron?.boldMove)}</p>
            </div>
            <div class="answer">
              <h3>DeepSeek Founder <span class="score">${escapeHtml(round.scores?.deepseek ?? "-")}</span></h3>
              <p>${escapeHtml(round.deepseek?.answer)}</p>
              <p class="muted">${escapeHtml(round.deepseek?.boldMove)}</p>
            </div>
          </article>
        `).join("")}
      </section>

      <section>
        <h2>Practice Notes</h2>
        <p><strong>Strongest moment:</strong> ${escapeHtml(report.strongestMoment)}</p>
        <p><strong>Weakest moment:</strong> ${escapeHtml(report.weakestMoment)}</p>
        <h3>Investor hooks</h3>
        <ul>${hooks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        <h3>Objections to rehearse</h3>
        <ul>${objections.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        <h3>Data to collect</h3>
        <ul>${dataToCollect.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        <ul>${practice.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </section>
    </main>
  </body>
</html>`;
}

async function createInvestorBrief({ prompt, practiceContext }) {
  const raw = await callJson({
    role: modelConfig.deepseek,
    temperature: 0.35,
    maxTokens: 2200,
    messages: [
      {
        role: "system",
        content:
          "You are a disciplined Shark Tank-style investor judge. Extract facts, expose risk, and write concise investor questions. Return JSON only.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "The user gave one natural-language business prompt.",
              "Extract only what is stated or safely inferred. Do not invent traction, revenue, customers, profit, or investment terms.",
              "Also diagnose whether the founder gave enough information for their selected stage and what proof is missing.",
              `Create exactly ${practiceContext.roundCount} investor questions for a two-founder model duel.`,
              "Adapt the questions to this practice context:",
              practiceContextPrompt(practiceContext),
              "Do not ask all questions as if the company is mature. Real investor practice must work for idea-stage, early traction, scaling, and fundraising-stage founders.",
              "",
              "Return JSON with this shape:",
              JSON.stringify({
                businessTitle: "short title",
                promptSummary: "one sentence summary",
                facts: ["fact from prompt"],
                promptDiagnostics: {
                  stageFit: "whether the chosen stage matches the facts and what to watch",
                  missingFacts: ["important missing founder detail"],
                  strongestSignal: "best fact or signal already in the prompt",
                  firstPracticeMove: "first thing the founder should tighten before answering investors",
                },
                questions: fallbackQuestions.slice(0, practiceContext.roundCount).map((question, index) => ({
                  id: `round-${index + 1}`,
                  title: "round title",
                  focus: "what this round tests",
                  question,
                })),
              }),
              "",
              `Business prompt:\n${prompt}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  const questions = Array.isArray(raw.questions) ? raw.questions : [];
  const normalizedQuestions = fallbackQuestions.slice(0, practiceContext.roundCount).map((fallback, index) => {
    const question = questions[index] || {};
    return {
      id: `round-${index + 1}`,
      title: sanitizeInput(question.title, `Round ${index + 1}`).slice(0, 64),
      focus: sanitizeInput(question.focus, "Investor confidence").slice(0, 140),
      question: sanitizeInput(question.question, fallback).slice(0, 420),
    };
  });

  return {
    businessTitle: sanitizeInput(raw.businessTitle, "Founder Duel").slice(0, 80),
    promptSummary: sanitizeInput(raw.promptSummary, prompt).slice(0, 260),
    facts: Array.isArray(raw.facts)
      ? raw.facts.slice(0, 8).map((fact) => sanitizeInput(fact).slice(0, 180))
      : [],
    promptDiagnostics: normalizePromptDiagnostics(raw.promptDiagnostics),
    questions: normalizedQuestions,
  };
}

function normalizeFounderPrep(raw = {}, prompt, practiceContext) {
  return {
    generatedAt: new Date().toISOString(),
    practiceContext,
    businessTitle: sanitizeInput(raw.businessTitle, "Founder Prep").slice(0, 80),
    promptSummary: sanitizeInput(raw.promptSummary, prompt).slice(0, 260),
    readinessScore: toScore(raw.readinessScore, 62),
    stageFit: sanitizeInput(
      raw.stageFit,
      "The prompt has enough information to begin investor practice, but the founder should tighten the proof and milestone.",
    ).slice(0, 260),
    strongestSignal: sanitizeInput(
      raw.strongestSignal,
      "The strongest signal is the clearest traction, customer insight, or proof already stated.",
    ).slice(0, 220),
    missingFacts: Array.isArray(raw.missingFacts)
      ? raw.missingFacts.slice(0, 5).map((item) => sanitizeInput(item).slice(0, 160))
      : [],
    pitchAngle: sanitizeInput(
      raw.pitchAngle,
      "Frame the business around the urgent customer pain, the current proof, and the next fundable milestone.",
    ).slice(0, 320),
    rewrittenPitch: sanitizeInput(
      raw.rewrittenPitch,
      "Practice a tighter pitch that names the customer, pain, proof, business model, ask, and next milestone.",
    ).slice(0, 900),
    askFraming: sanitizeInput(
      raw.askFraming,
      "Tie the ask to a measurable milestone and explain how it reduces the biggest investor risk.",
    ).slice(0, 320),
    likelyFirstQuestions: Array.isArray(raw.likelyFirstQuestions)
      ? raw.likelyFirstQuestions.slice(0, 4).map((item) => sanitizeInput(item).slice(0, 220))
      : fallbackQuestions.slice(0, Math.min(4, practiceContext.roundCount)),
    scaleLevers: Array.isArray(raw.scaleLevers)
      ? raw.scaleLevers.slice(0, 4).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    riskWatch: Array.isArray(raw.riskWatch)
      ? raw.riskWatch.slice(0, 4).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    nextMove: sanitizeInput(
      raw.nextMove,
      "Answer the first investor question in 45 seconds with one customer, one metric, one risk, and one milestone.",
    ).slice(0, 260),
  };
}

function normalizeDrillFeedback(raw = {}, answer) {
  return {
    generatedAt: new Date().toISOString(),
    score: toScore(raw.score, 60),
    verdict: sanitizeInput(
      raw.verdict,
      "The answer has a useful foundation, but it needs tighter proof, numbers, and a clearer investor milestone.",
    ).slice(0, 260),
    strongestLine: sanitizeInput(
      raw.strongestLine,
      "The strongest part was naming the business direction.",
    ).slice(0, 200),
    missingProof: Array.isArray(raw.missingProof)
      ? raw.missingProof.slice(0, 4).map((item) => sanitizeInput(item).slice(0, 160))
      : [],
    sharperAnswer: sanitizeInput(
      raw.sharperAnswer,
      answer || "Practice a direct answer with one customer, one metric, one risk, and one next milestone.",
    ).slice(0, 900),
    investorFollowUp: sanitizeInput(
      raw.investorFollowUp,
      "What proof can you show that this answer is repeatable and not a one-off result?",
    ).slice(0, 260),
    nextPracticeMove: sanitizeInput(
      raw.nextPracticeMove,
      "Repeat the answer in 45 seconds and replace one vague claim with a metric or customer example.",
    ).slice(0, 260),
  };
}

async function createDrillFeedback({ prompt, practiceContext, report, drill, answer }) {
  const raw = await callJson({
    role: modelConfig.deepseek,
    temperature: 0.3,
    maxTokens: 1200,
    messages: [
      {
        role: "system",
        content:
          "You are an investor pitch coach. Score a founder's practice answer, identify missing proof, and rewrite it into a stronger investor-ready answer. Return JSON only.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Judge this founder's answer to one practice drill.",
              "Do not invent new business facts. If the founder did not provide proof, say what proof is missing.",
              "Score relative to the founder stage and practice objective.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              "Return JSON with this shape:",
              JSON.stringify({
                score: 0,
                verdict: "brief coaching verdict",
                strongestLine: "best part of the answer",
                missingProof: ["specific proof missing"],
                sharperAnswer: "stronger answer the founder should practice",
                investorFollowUp: "one follow-up investor question",
                nextPracticeMove: "one immediate practice move",
              }),
              "",
              `Business prompt:\n${prompt}`,
              "",
              `Report context:\n${JSON.stringify({
                businessTitle: report?.businessTitle,
                promptSummary: report?.promptSummary,
                readinessScore: report?.readinessScore,
                weakestMoment: report?.weakestMoment,
                recommendedAskFraming: report?.recommendedAskFraming,
              })}`,
              "",
              `Practice drill:\n${JSON.stringify(drill)}`,
              "",
              `Founder answer:\n${answer}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return normalizeDrillFeedback(raw, answer);
}

async function createFounderPrep({ prompt, practiceContext }) {
  const raw = await callJson({
    role: modelConfig.deepseek,
    temperature: 0.28,
    maxTokens: 1500,
    messages: [
      {
        role: "system",
        content:
          "You are a Founder Coach and Shark Tank investor judge. Prepare founders for investor practice with concise, practical feedback. Return JSON only.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Create a lightweight prep brief before the full AI Shark Tank duel.",
              "Use only the user's stated facts or clearly label missing proof. Do not invent revenue, customers, margins, traction, valuation, or team details.",
              "Make this useful for idea-stage founders and scaled businesses. Judge readiness relative to the selected stage and focus.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              "Return JSON with this shape:",
              JSON.stringify({
                businessTitle: "short title",
                promptSummary: "one sentence business summary",
                readinessScore: 0,
                stageFit: "whether the selected stage fits the facts and what to watch",
                strongestSignal: "best proof or insight already in the prompt",
                missingFacts: ["specific missing investor detail"],
                pitchAngle: "best strategic pitch angle for this practice room",
                rewrittenPitch: "tight 45-60 second investor pitch to rehearse",
                askFraming: "how to frame the ask or next milestone",
                likelyFirstQuestions: ["hard investor question"],
                scaleLevers: ["specific way this business could scale from its current facts"],
                riskWatch: ["risk or objection investor will press"],
                nextMove: "one immediate practice action before running the duel",
              }),
              "",
              `Business prompt:\n${prompt}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return normalizeFounderPrep(raw, prompt, practiceContext);
}

async function createFounderAnswers({ founder, prompt, brief, strict = false }) {
  const style =
    founder === "nemotron"
      ? "You are Founder A. You are operationally rigorous, numerical, direct, and execution-focused."
      : "You are Founder B. You are strategically sharp, market-aware, narrative-driven, and growth-focused.";

  let raw;
  try {
    raw = await callJson({
      role: modelConfig[founder],
      temperature: 0.72,
      maxTokens: 3200,
      messages: [
        {
          role: "system",
          content: [
            style,
            "Pitch the exact business described by the user. You may choose a different strategy, but you must not invent contradictory facts.",
            "Never output placeholders, ellipses, templates, or generic coaching advice. Answer as the founder in the room.",
            "Do not preface answers with phrases like 'Here's the pitch', 'Here's the answer', or 'Sure'. Start directly with the pitch content.",
            strict ? "This is a retry because the previous output was too generic. Use the user's actual numbers and business details in every answer." : "",
            "Return JSON only.",
          ].filter(Boolean).join(" "),
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: [
                "Answer every investor question as if you are competing against another founder pitching the same business.",
                "Use the user's facts. If a number is missing, say what you would validate next instead of inventing it.",
                "",
                "Return JSON with this shape:",
                JSON.stringify({
                  openingPosition: "one sentence positioning",
                  answers: brief.questions.map((question, index) => ({
                    id: question.id,
                    answer: `answer to investor question ${index + 1}`,
                    boldMove: `specific scale move after question ${index + 1}`,
                  })),
                }),
                "",
                `Business prompt:\n${prompt}`,
                "",
                `Investor brief:\n${JSON.stringify(brief)}`,
              ].join("\n"),
            },
          ],
        },
      ],
    });
  } catch {
    return createFounderAnswersPlain({ founder, prompt, brief, style });
  }

  const answers = Array.isArray(raw.answers) ? raw.answers : [];
  const result = {
    openingPosition: sanitizeInput(raw.openingPosition, "We will turn this business into a focused, fundable wedge.").slice(0, 240),
    answers: brief.questions.map((question, index) => {
      const answer = answers.find((item) => item?.id === question.id) || answers[index] || {};
      const answerKey = `round${index + 1}Answer`;
      const moveKey = `round${index + 1}Move`;
      return {
        id: question.id,
        answer: sanitizeInput(
          answer.answer || raw[answerKey],
          "I would focus the pitch on the clearest customer pain, the current proof, and the next measurable milestone.",
        ).slice(0, 1000),
        boldMove: sanitizeInput(
          answer.boldMove || raw[moveKey],
          "Validate willingness to pay with a small, specific customer segment.",
        ).slice(0, 260),
      };
    }),
  };

  if (
    !strict &&
    (isWeakPitchText(result.openingPosition) ||
      result.answers.some((answer) => isWeakPitchText(answer.answer)))
  ) {
    return createFounderAnswers({ founder, prompt, brief, strict: true });
  }

  if (strict && result.answers.some((answer) => isWeakPitchText(answer.answer))) {
    return createFounderAnswersPlain({ founder, prompt, brief, style });
  }

  return result;
}

function extractPlainSection(text, label, fallback) {
  const pattern = new RegExp(`${label}:\\\\s*([\\\\s\\\\S]*?)(?=\\\\n(?:OPENING|ROUND \\\\d+ ANSWER|ROUND \\\\d+ MOVE):|$)`, "i");
  const match = text.match(pattern);
  return sanitizeInput(match?.[1], fallback);
}

async function createFounderAnswersPlain({ founder, prompt, brief, style }) {
  const text = await callText({
    role: modelConfig[founder],
    temperature: 0.62,
    maxTokens: 2600,
    messages: [
      {
        role: "system",
        content: [
          style,
          "Answer as the founder in a live investor room.",
          "Use actual details from the business prompt.",
          "Do not preface answers with phrases like 'Here's the pitch', 'Here's the answer', or 'Sure'. Start directly with the pitch content.",
          "Do not output JSON. Do not output placeholders. Do not give generic advice.",
        ].join(" "),
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Write exactly these labels, with real founder answers after each label:",
              "OPENING:",
              ...brief.questions.flatMap((_round, index) => [
                `ROUND ${index + 1} ANSWER:`,
                `ROUND ${index + 1} MOVE:`,
              ]),
              "",
              `Business prompt:\n${prompt}`,
              "",
              `Investor questions:\n${brief.questions
                .map((round, index) => `ROUND ${index + 1}: ${round.question}`)
                .join("\n")}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return {
    openingPosition: extractPlainSection(text, "OPENING", "We will pitch this business using its real traction, current bottleneck, and next funding milestone.").slice(0, 240),
    answers: brief.questions.map((question, index) => ({
      id: question.id,
      answer: extractPlainSection(
        text,
        `ROUND ${index + 1} ANSWER`,
        "This business already has concrete traction, and the next pitch should tie that traction to the clearest bottleneck and funding milestone.",
      ).slice(0, 1000),
      boldMove: extractPlainSection(
        text,
        `ROUND ${index + 1} MOVE`,
        "Validate the next growth step with a measurable experiment.",
      ).slice(0, 260),
    })),
  };
}

async function createFounderRoundAnswer({ founder, prompt, practiceContext, brief, round, index, strict = false }) {
  const isNemotron = founder === "nemotron";
  const style = isNemotron
    ? [
        "You are Founder A.",
        "You pitch a creative scaling plan through operations: standardized packages, hiring systems, throughput, margin control, automation, retention loops, and measurable milestones.",
        "You are numerical, direct, and execution-focused.",
      ].join(" ")
    : [
        "You are Founder B.",
        "You pitch a creative scaling plan through strategy: category positioning, partnerships, product/data layer, distribution loops, expansion segments, and defensibility.",
        "You are market-aware, narrative-driven, and growth-focused.",
      ].join(" ");

  let raw;
  try {
    raw = await callJson({
      role: modelConfig[founder],
      temperature: 0.68,
      maxTokens: 1100,
      messages: [
        {
          role: "system",
          content: [
            style,
            "Answer as the founder in a live investor room.",
            "Every answer must include a concrete scaling angle for this exact business.",
            "Adapt the answer to the founder's current stage and practice objective.",
            practiceContextPrompt(practiceContext),
            "Use the user's stated facts. Do not invent contradictory traction, revenue, customers, profit, or terms.",
            "Do not preface answers with phrases like 'Here's the pitch', 'Here's the answer', or 'Sure'. Start directly with the pitch content.",
            "Return JSON only.",
            strict ? "This is a retry. Be specific, answer the exact question, include the user's real numbers where relevant, and make the scale plan sharper." : "",
          ].filter(Boolean).join(" "),
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: [
                "Answer this one investor question for the same business.",
                "Do not merely repeat the prompt. Explain the next fundable move from the current stage, evidence, revenue, customers, margin, and ask if those details exist.",
                isNemotron
                  ? "Founder A should focus on operational scaling: hiring plan, delivery capacity, process, margin, automation, and milestones."
                  : "Founder B should focus on strategic scaling: wedge, partnerships, distribution, product/data layer, market expansion, and moat.",
                "The boldMove must be one specific scaling move that could happen next.",
                `Practice context:\n${practiceContextPrompt(practiceContext)}`,
                "Return JSON with this shape:",
                JSON.stringify({
                  openingPosition: "one sentence positioning, only needed for round 1",
                  answer: "direct founder answer",
                  boldMove: "one concrete next move",
                }),
                "",
                `Business prompt:\n${prompt}`,
                "",
                `Extracted facts:\n${brief.facts.map((fact) => `- ${fact}`).join("\n")}`,
                "",
                `Round ${index + 1}: ${round.title}`,
                `Investor question: ${round.question}`,
                `What this tests: ${round.focus}`,
              ].join("\n"),
            },
          ],
        },
      ],
    });
  } catch (error) {
    throw new Error(`${modelConfig[founder].label} could not answer round ${index + 1}: ${error.message}`);
  }

  const answerText = sanitizeInput(raw.answer);
  if (!answerText) {
    throw new Error(`${modelConfig[founder].label} returned an empty answer for round ${index + 1}.`);
  }

  const result = {
    openingPosition: sanitizeInput(raw.openingPosition, answerText).slice(0, 240),
    id: round.id,
    answer: answerText.slice(0, 1000),
    boldMove: sanitizeInput(raw.boldMove, "No next move provided.").slice(0, 260),
  };

  if (!strict && isWeakPitchText(result.answer)) {
    return createFounderRoundAnswer({ founder, prompt, practiceContext, brief, round, index, strict: true });
  }

  return result;
}

async function judgeSingleRound({ prompt, practiceContext, brief, round, nemotronAnswer, deepseekAnswer }) {
  const raw = await callJson({
    role: modelConfig.judge,
    temperature: 0.34,
    maxTokens: 900,
    messages: [
      {
        role: "system",
        content:
          "You are the investor judge. Score one round of a two-founder Shark Tank duel. Return JSON only.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Score this one round from 0-100.",
              "Choose winner as nemotron, deepseek, or tie. Penalize vague answers and invented facts.",
              "Score relative to the founder stage and practice objective, not as a generic mature-company pitch.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "Return JSON with this shape:",
              JSON.stringify({
                nemotronScore: 0,
                deepseekScore: 0,
                winner: "nemotron",
                judgeComment: "brief reason",
              }),
              "",
              `Original business prompt:\n${prompt}`,
              "",
              `Extracted facts:\n${brief.facts.map((fact) => `- ${fact}`).join("\n")}`,
              "",
              `Investor question: ${round.question}`,
              "",
              `${modelConfig.nemotron.label} answer:\n${JSON.stringify(nemotronAnswer)}`,
              "",
              `DeepSeek answer:\n${JSON.stringify(deepseekAnswer)}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  const nemotronScore = isWeakPitchText(nemotronAnswer?.answer) ? 15 : toScore(raw.nemotronScore, 68);
  const deepseekScore = isWeakPitchText(deepseekAnswer?.answer) ? 15 : toScore(raw.deepseekScore, 68);
  const winner =
    ["nemotron", "deepseek", "tie"].includes(raw.winner)
      ? raw.winner
      : nemotronScore === deepseekScore
        ? "tie"
        : nemotronScore > deepseekScore
          ? "nemotron"
          : "deepseek";

  return {
    ...round,
    nemotron: nemotronAnswer,
    deepseek: deepseekAnswer,
    scores: {
      nemotron: nemotronScore,
      deepseek: deepseekScore,
    },
    winner,
    judgeComment: sanitizeInput(
      raw.judgeComment,
      winner === "tie"
        ? "Both founders made a credible but incomplete case."
        : `${winnerName(winner)} gave the more investor-ready answer.`,
    ).slice(0, 280),
  };
}

async function createFinalReview({ prompt, practiceContext, brief, rounds, totals, winner }) {
  const raw = await callJson({
    role: modelConfig.judge,
    temperature: 0.32,
    maxTokens: 1400,
    messages: [
      {
        role: "system",
        content:
          "You are the investor judge. Write the final review after all scored rounds. Return JSON only.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Write a concise final review. Use the computed winner unless there is a scoring tie.",
              "Make this useful for founder practice, not just entertainment.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "Return JSON with this shape:",
              JSON.stringify({
                verdict: "final investor verdict",
                readinessScore: 0,
                skillScores: {
                  clarity: { score: 0, note: "pitch clarity note" },
                  proof: { score: 0, note: "traction or validation note" },
                  economics: { score: 0, note: "pricing, margin, and unit economics note" },
                  scale: { score: 0, note: "repeatable growth and operations note" },
                  moat: { score: 0, note: "competition and defensibility note" },
                  deal: { score: 0, note: "ask, terms, and milestone note" },
                },
                strongestMoment: "best answer or proof",
                weakestMoment: "biggest fix",
                rewrittenPitch: "tight 60-second pitch the founder should practice",
                investorHooks: ["strongest investor hook"],
                investorObjections: ["objection the founder must rehearse"],
                nextDataToCollect: ["specific proof or data to collect next"],
                recommendedAskFraming: "how to frame the ask and milestone",
                practiceDrills: [
                  {
                    name: "drill name",
                    goal: "what this improves",
                    prompt: "specific investor question or timed rehearsal prompt",
                  },
                ],
                nextPractice: ["practice item"],
              }),
              "",
              `Original business prompt:\n${prompt}`,
              "",
              `Investor brief:\n${JSON.stringify(brief)}`,
              "",
              `Computed totals:\n${JSON.stringify({ totals, winner })}`,
              "",
              `Scored rounds:\n${JSON.stringify(rounds)}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return {
    rounds,
    totals,
    winner,
    verdict: sanitizeInput(
      raw.verdict,
      winner === "tie"
        ? "The investor could not separate the two founders; both need sharper proof and clearer terms."
        : `${winnerName(winner)} made the stronger investor case across the full investor room.`,
    ).slice(0, 320),
    readinessScore: toScore(raw.readinessScore, Math.round((totals.nemotron + totals.deepseek) / 2)),
    skillScores: normalizeSkillScores(raw.skillScores),
    strongestMoment: sanitizeInput(raw.strongestMoment, rounds.find((round) => round.winner === winner)?.judgeComment || "The strongest answer connected the business facts to a concrete next milestone.").slice(0, 260),
    weakestMoment: sanitizeInput(raw.weakestMoment, "The weakest area was turning claims into investor-grade proof.").slice(0, 260),
    rewrittenPitch: sanitizeInput(raw.rewrittenPitch, "Practice a tighter pitch that names the customer, urgent problem, proof, business model, and next milestone.").slice(0, 900),
    investorHooks: Array.isArray(raw.investorHooks)
      ? raw.investorHooks.slice(0, 3).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    investorObjections: Array.isArray(raw.investorObjections)
      ? raw.investorObjections.slice(0, 4).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    nextDataToCollect: Array.isArray(raw.nextDataToCollect)
      ? raw.nextDataToCollect.slice(0, 4).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    recommendedAskFraming: sanitizeInput(raw.recommendedAskFraming, "Tie the ask to one measurable milestone and the evidence needed to de-risk the next round.").slice(0, 320),
    practiceDrills: normalizePracticeDrills(raw.practiceDrills),
    nextPractice: Array.isArray(raw.nextPractice)
      ? raw.nextPractice.slice(0, 4).map((item) => sanitizeInput(item).slice(0, 180))
      : [
          "Turn every claim into a metric, customer quote, or experiment.",
          "Make the investment ask map to one measurable milestone.",
          "Prepare sharper competition, moat, and risk answers.",
        ],
  };
}

async function judgeDuel({ prompt, brief, nemotron, deepseek }) {
  const raw = await callJson({
    role: modelConfig.judge,
    temperature: 0.42,
    maxTokens: 3600,
    messages: [
      {
        role: "system",
        content:
          "You are the investor judge. Score two founders pitching the same business. Be fair, specific, and concise. Return JSON only.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Judge this model-founder duel.",
              "Each score is 0-100. Choose one per-round winner: nemotron, deepseek, or tie.",
              "Choose one final winner: nemotron, deepseek, or tie.",
              "Penalize invented facts, vague answers, weak unit economics, and unclear customer focus.",
              "",
              "Return JSON with this shape:",
              JSON.stringify({
                rounds: brief.questions.map((round) => ({
                  id: round.id,
                  nemotronScore: 0,
                  deepseekScore: 0,
                  winner: "nemotron",
                  judgeComment: "why the winner won this round",
                })),
                totals: {
                  nemotron: 0,
                  deepseek: 0,
                },
                winner: "nemotron",
                verdict: "final investor verdict",
                strongestMoment: "best answer or phrase",
                weakestMoment: "biggest fix",
                nextPractice: ["practice item"],
              }),
              "",
              `Original business prompt:\n${prompt}`,
              "",
              `Investor brief:\n${JSON.stringify(brief)}`,
              "",
              `${modelConfig.nemotron.label}:\n${JSON.stringify(nemotron)}`,
              "",
              `DeepSeek Founder:\n${JSON.stringify(deepseek)}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  const judgedRounds = Array.isArray(raw.rounds) ? raw.rounds : [];
  const rounds = brief.questions.map((question, index) => {
    const judgeRound = judgedRounds.find((item) => item?.id === question.id) || judgedRounds[index] || {};
    const nemotronScore = isWeakPitchText(nemotron.answers[index]?.answer)
      ? 15
      : toScore(judgeRound.nemotronScore, 65);
    const deepseekScore = isWeakPitchText(deepseek.answers[index]?.answer)
      ? 15
      : toScore(judgeRound.deepseekScore, 65);
    const winner =
      ["nemotron", "deepseek", "tie"].includes(judgeRound.winner)
        ? judgeRound.winner
        : nemotronScore === deepseekScore
          ? "tie"
          : nemotronScore > deepseekScore
            ? "nemotron"
            : "deepseek";

    return {
      ...question,
      nemotron: nemotron.answers[index],
      deepseek: deepseek.answers[index],
      scores: {
        nemotron: nemotronScore,
        deepseek: deepseekScore,
      },
      winner,
      judgeComment: sanitizeInput(
        judgeRound.judgeComment,
        winner === "tie"
          ? "Both founders made a credible but incomplete case."
          : `${winner === "nemotron" ? modelConfig.nemotron.label.replace(" Founder", "") : "DeepSeek"} gave the more investor-ready answer.`,
      ).slice(0, 340),
    };
  });

  const computedTotals = rounds.reduce(
    (totals, round) => ({
      nemotron: totals.nemotron + round.scores.nemotron,
      deepseek: totals.deepseek + round.scores.deepseek,
    }),
    { nemotron: 0, deepseek: 0 },
  );

  const totals = {
    nemotron: Math.round(computedTotals.nemotron / rounds.length),
    deepseek: Math.round(computedTotals.deepseek / rounds.length),
  };

  const winner =
    ["nemotron", "deepseek", "tie"].includes(raw.winner)
      ? raw.winner
      : totals.nemotron === totals.deepseek
        ? "tie"
        : totals.nemotron > totals.deepseek
          ? "nemotron"
          : "deepseek";

  return {
    rounds,
    totals,
    winner,
    verdict: sanitizeInput(raw.verdict, "The winner made the clearer case, but both need stronger proof before a real check.").slice(0, 320),
    strongestMoment: sanitizeInput(raw.strongestMoment, "The best answer tied the business to a specific customer pain.").slice(0, 260),
    weakestMoment: sanitizeInput(raw.weakestMoment, "The weakest moment was missing proof or unit economics.").slice(0, 260),
    nextPractice: Array.isArray(raw.nextPractice)
      ? raw.nextPractice.slice(0, 4).map((item) => sanitizeInput(item).slice(0, 180))
      : [
          "Turn every claim into a metric, customer quote, or experiment.",
          "Prepare a sharper answer for competition and moat.",
          "Make the investment ask map to one measurable milestone.",
        ],
  };
}

async function createFinalNegotiation({ prompt, practiceContext, brief, nemotron, deepseek, judgement }) {
  const raw = await callJson({
    role: modelConfig.judge,
    temperature: 0.32,
    maxTokens: 1200,
    messages: [
      {
        role: "system",
        content:
          "You are the final investor judge. You have heard both founders. Now negotiate, decide whether to invest, and write final terms. Return JSON only.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Create the final negotiation scene after all questions are complete.",
              "Negotiate with both founders, but favor whoever made the stronger case.",
              "If the business is investable, make a realistic conditional offer. If not, say no deal and explain what must change.",
              "Do not invent new business facts. Base the decision on the duel transcript.",
              "Use the founder stage and practice objective when deciding what would be realistic.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              "Return JSON with this shape:",
              JSON.stringify({
                decision: "Deal, Conditional deal, or No deal",
                offer: "investment terms or no-deal terms",
                negotiationSummary: "short description of how the judge negotiated with both founders",
                reason: "why this final decision was made",
                winnerAdvice: "what the winning founder should do next",
                loserAdvice: "what the losing founder should fix",
              }),
              "",
              `Original business prompt:\n${prompt}`,
              "",
              `Investor brief:\n${JSON.stringify(brief)}`,
              "",
              `${modelConfig.nemotron.label} opening: ${nemotron.openingPosition}`,
              "",
              `DeepSeek Founder opening: ${deepseek.openingPosition}`,
              "",
              `Round judgement:\n${JSON.stringify(judgement)}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return {
    decision: sanitizeInput(raw.decision, "Conditional deal").slice(0, 80),
    offer: sanitizeInput(raw.offer, "Conditional offer pending stronger proof and clean unit economics.").slice(0, 260),
    negotiationSummary: sanitizeInput(
      raw.negotiationSummary,
      "The investor pressed both founders on proof, risk, and use of funds before choosing the more credible operator.",
    ).slice(0, 520),
    reason: sanitizeInput(raw.reason, "The final decision followed the stronger pitch, clearer numbers, and lower execution risk.").slice(0, 520),
    winnerAdvice: sanitizeInput(raw.winnerAdvice, "Turn the winning pitch into a measurable operating plan.").slice(0, 260),
    loserAdvice: sanitizeInput(raw.loserAdvice, "Replace generic answers with concrete evidence and a sharper deal case.").slice(0, 260),
  };
}

async function runPitchDuelSimulation({ prompt, practiceContext = normalizePracticeContext(), cacheKey, emit }) {
  await emit({ type: "status", status: "Mastra workflow started. Judge is extracting business facts and questions..." });
  const brief = await withChunkCache({
    prompt,
    practiceContext,
    step: "investor-brief",
    producer: () => createInvestorBrief({ prompt, practiceContext }),
  });
  await emit({
    type: "brief",
    status: "Investor questions are ready.",
    data: buildSimulationData({ prompt, practiceContext, brief, currentRoundIndex: 0 }),
  });

  const nemotron = { openingPosition: "", answers: [] };
  const deepseek = { openingPosition: "", answers: [] };
  const judgedRounds = [];

  for (const [index, round] of brief.questions.entries()) {
    await emit({
      type: "status",
      status: `Round ${index + 1}: both founder agents are answering in parallel...`,
    });

    const [nemotronRound, deepseekRound] = await Promise.all([
      withChunkCache({
        prompt,
        practiceContext,
        step: `founder-nemotron-round-${index + 1}`,
        extra: JSON.stringify(round),
        producer: () =>
          createFounderRoundAnswer({ founder: "nemotron", prompt, practiceContext, brief, round, index }),
      }),
      withChunkCache({
        prompt,
        practiceContext,
        step: `founder-deepseek-round-${index + 1}`,
        extra: JSON.stringify(round),
        producer: () =>
          createFounderRoundAnswer({ founder: "deepseek", prompt, practiceContext, brief, round, index }),
      }),
    ]);

    if (index === 0) {
      nemotron.openingPosition = nemotronRound.openingPosition || nemotronRound.answer.slice(0, 220);
      deepseek.openingPosition = deepseekRound.openingPosition || deepseekRound.answer.slice(0, 220);
    }
    nemotron.answers[index] = {
      id: round.id,
      answer: nemotronRound.answer,
      boldMove: nemotronRound.boldMove,
    };
    deepseek.answers[index] = {
      id: round.id,
      answer: deepseekRound.answer,
      boldMove: deepseekRound.boldMove,
    };
    await emit({
      type: "founder",
      status: `Round ${index + 1}: both answers are on screen.`,
      data: buildSimulationData({ prompt, practiceContext, brief, nemotron, deepseek, currentRoundIndex: index }),
    });

    await emit({
      type: "status",
      status: `Round ${index + 1}: investor judge is scoring...`,
    });
    const judgedRound = await withChunkCache({
      prompt,
      practiceContext,
      step: `judge-round-${index + 1}`,
      extra: JSON.stringify({ round, nemotron: nemotron.answers[index], deepseek: deepseek.answers[index] }),
      producer: () =>
        judgeSingleRound({
          prompt,
          practiceContext,
          brief,
          round,
          nemotronAnswer: nemotron.answers[index],
          deepseekAnswer: deepseek.answers[index],
        }),
    });
    judgedRounds[index] = judgedRound;

    const runningTotals = judgedRounds.reduce(
      (totals, item) => ({
        nemotron: totals.nemotron + item.scores.nemotron,
        deepseek: totals.deepseek + item.scores.deepseek,
      }),
      { nemotron: 0, deepseek: 0 },
    );
    const completedRounds = judgedRounds.length;
    const runningJudgement = {
      rounds: brief.questions.map((question, roundIndex) => judgedRounds[roundIndex] || {
        ...question,
        nemotron: nemotron.answers[roundIndex] || null,
        deepseek: deepseek.answers[roundIndex] || null,
        scores: null,
        winner: null,
        judgeComment: "",
      }),
      totals: {
        nemotron: Math.round(runningTotals.nemotron / completedRounds),
        deepseek: Math.round(runningTotals.deepseek / completedRounds),
      },
      winner: null,
      verdict: "",
      strongestMoment: "",
      weakestMoment: "",
      nextPractice: [],
    };

    await emit({
      type: "judgement",
      status: `Round ${index + 1} scored.`,
      data: buildSimulationData({
        prompt,
        practiceContext,
        brief,
        nemotron,
        deepseek,
        judgement: runningJudgement,
        currentRoundIndex: index,
      }),
    });
  }

  const computedTotals = judgedRounds.reduce(
    (totals, round) => ({
      nemotron: totals.nemotron + round.scores.nemotron,
      deepseek: totals.deepseek + round.scores.deepseek,
    }),
    { nemotron: 0, deepseek: 0 },
  );
  const totals = {
    nemotron: Math.round(computedTotals.nemotron / judgedRounds.length),
    deepseek: Math.round(computedTotals.deepseek / judgedRounds.length),
  };
  const winner =
    totals.nemotron === totals.deepseek
      ? "tie"
      : totals.nemotron > totals.deepseek
        ? "nemotron"
        : "deepseek";

  await emit({ type: "status", status: "Investor judge is writing the final review..." });
  const judgement = await withChunkCache({
    prompt,
    practiceContext,
    step: "final-review",
    extra: JSON.stringify({ judgedRounds, totals, winner }),
    producer: () => createFinalReview({ prompt, practiceContext, brief, rounds: judgedRounds, totals, winner }),
  });
  await emit({
    type: "judgement",
    status: "Final review is ready. Preparing report...",
    data: buildSimulationData({
      prompt,
      practiceContext,
      brief,
      nemotron,
      deepseek,
      judgement,
      currentRoundIndex: Math.max(0, brief.questions.length - 1),
    }),
  });

  await emit({ type: "status", status: "Investor judge is negotiating final terms..." });
  const negotiation = await withChunkCache({
    prompt,
    practiceContext,
    step: "final-negotiation",
    extra: JSON.stringify(judgement),
    producer: () => createFinalNegotiation({ prompt, practiceContext, brief, nemotron, deepseek, judgement }),
  });
  const reportData = buildSimulationData({ prompt, practiceContext, brief, nemotron, deepseek, judgement, negotiation });
  const report = saveReport(reportData, cacheKey);
  const finalData = {
    ...reportData,
    reportId: report.id,
    reportUrl: `/reports/${report.id}`,
    generatedAt: report.createdAt,
  };

  await emit({
    type: "done",
    status: "Report saved. You can open it from the top button.",
    cached: false,
    data: finalData,
  });

  return finalData;
}

function isPlaceholderBrief(brief) {
  return (
    isPlaceholderText(brief.businessTitle) ||
    isPlaceholderText(brief.promptSummary) ||
    !brief.facts?.length ||
    brief.facts.some(isPlaceholderText) ||
    !brief.rounds?.length ||
    brief.rounds.some((round) => isPlaceholderText(round.focus) || isPlaceholderText(round.panelQuestion))
  );
}

function normalizeRoomBrief(raw = {}, prompt) {
  return {
    businessTitle: sanitizeInput(raw.businessTitle, "Founder Shark Room").slice(0, 80),
    promptSummary: sanitizeInput(raw.promptSummary, prompt).slice(0, 260),
    facts: Array.isArray(raw.facts)
      ? raw.facts.slice(0, 10).map((fact) => sanitizeInput(fact).slice(0, 180))
      : [],
    promptDiagnostics: normalizePromptDiagnostics(raw.promptDiagnostics),
    rounds: [],
  };
}

function deriveBriefFromPrompt(prompt, practiceContext) {
  const cleanPrompt = sanitizeInput(prompt).slice(0, 1000);
  const titleMatch =
    cleanPrompt.match(/\b(?:I run|I am building|we run|we are building|we built|my company is|our company is)\s+([^,.:\n]+)/i) ||
    cleanPrompt.match(/\b([A-Z][A-Za-z0-9 -]{2,40}),\s+(?:an?|the)\b/);
  const businessTitle = sanitizeInput(titleMatch?.[1], "Founder Shark Room").slice(0, 80);
  const sentences = cleanPrompt
    .split(/(?<=[.!?])\s+|\n+/)
    .map((item) => sanitizeInput(item))
    .filter(Boolean);
  const facts = sentences
    .flatMap((sentence) => sentence.split(/,\s+(?=(?:and\s+)?(?:we|have|at|with|\$|\d))/i))
    .map((item) => sanitizeInput(item))
    .filter((item) => /\d|\$|%|revenue|margin|client|customer|clinic|pilot|raising|ask|mrr|churn/i.test(item))
    .slice(0, 10);

  return {
    businessTitle,
    promptSummary: sentences[0] || cleanPrompt,
    facts: facts.length ? facts : [cleanPrompt.slice(0, 180)],
    promptDiagnostics: normalizePromptDiagnostics({
      stageFit: `${practiceContext.stageLabel} is usable because the prompt includes concrete founder context.`,
      missingFacts: ["CAC or acquisition channel proof", "valuation or equity flexibility", "team ownership and operating capacity"],
      strongestSignal: facts[0] || "The founder included concrete traction details.",
      firstPracticeMove: "Tie the ask to one measurable milestone and one risk-control metric.",
    }),
    rounds: [],
  };
}

async function repairSharkRoomBrief({ prompt, practiceContext, rawOutput }) {
  const text = await callText({
    role: modelConfig.deepseek,
    temperature: 0.1,
    maxTokens: 1100,
    messages: [
      {
        role: "system",
        content:
          "Extract a real founder brief. Return only the requested labels. Use the founder's actual prompt, not schema examples or placeholders.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "The user is the founder. Extract concrete facts from the founder prompt.",
              "If numbers are present, preserve them exactly.",
              "Respond using exactly these labels:",
              "BUSINESS TITLE:",
              "PROMPT SUMMARY:",
              "FACTS:",
              "STAGE FIT:",
              "MISSING FACTS:",
              "STRONGEST SIGNAL:",
              "FIRST PRACTICE MOVE:",
              "",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              `Founder prompt:\n${prompt}`,
              "",
              `Malformed previous brief:\n${JSON.stringify(rawOutput)}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return normalizeRoomBrief(
    {
      businessTitle: extractLabeledValue(text, ["BUSINESS TITLE"]),
      promptSummary: extractLabeledValue(text, ["PROMPT SUMMARY"]),
      facts: parseListValue(extractLabeledValue(text, ["FACTS"])),
      promptDiagnostics: {
        stageFit: extractLabeledValue(text, ["STAGE FIT"]),
        missingFacts: parseListValue(extractLabeledValue(text, ["MISSING FACTS"])),
        strongestSignal: extractLabeledValue(text, ["STRONGEST SIGNAL"]),
        firstPracticeMove: extractLabeledValue(text, ["FIRST PRACTICE MOVE"]),
      },
    },
    prompt,
  );
}

function parseSharkQuestionText(text, sharkKey, count) {
  return Array.from({ length: count }, (_, index) => {
    const number = index + 1;
    return {
      focus: extractLabeledValue(text, [`FOCUS ${number}`]),
      question: extractLabeledValue(text, [`QUESTION ${number}`]),
      angle: extractLabeledValue(text, [`ANGLE ${number}`]),
    };
  }).map((question) => ({
    askingShark: sharkKey,
    askingSharkLabel: sharkLabel(sharkKey),
    focus: sanitizeInput(question.focus).slice(0, 100),
    question: sanitizeInput(question.question).slice(0, 520),
    angle: sanitizeInput(question.angle).slice(0, 180),
  }));
}

function normalizeRawSharkQuestionArray(rawQuestions = [], sharkKey, count) {
  const source = Array.isArray(rawQuestions) ? rawQuestions : [];
  return source.slice(0, count).map((item = {}) => ({
    askingShark: sharkKey,
    askingSharkLabel: sharkLabel(sharkKey),
    focus: sanitizeInput(item.focus).slice(0, 100),
    question: sanitizeInput(item.question || item.panelQuestion).slice(0, 520),
    angle: sanitizeInput(item.angle).slice(0, 180),
  }));
}

function isMalformedGeneratedQuestion(question = {}) {
  const values = [question.focus, question.question, question.angle].map((value) => sanitizeInput(value).toLowerCase());
  return values.some(
    (value) =>
      !value ||
      value.includes("so i need") ||
      value.includes("i need to output") ||
      value.includes("output three lines") ||
      value.includes("respond using") ||
      value.includes("exactly these labels") ||
      value.includes("final answer only") ||
      value.includes("do not include") ||
      /^angle\s+\d+\s*:?\s*$/i.test(value) ||
      /^focus\s+\d+\s*:?\s*$/i.test(value) ||
      /^question\s+\d+\s*:?\s*$/i.test(value),
  );
}

function isInvalidSharkQuestionSet(questions = [], count) {
  return (
    questions.length < count ||
    questions.some(
      (question) =>
        isPlaceholderText(question.focus) ||
        isPlaceholderText(question.question) ||
        isPlaceholderText(question.angle) ||
        sanitizeInput(question.question).length < 35 ||
        isMalformedGeneratedQuestion(question),
    )
  );
}

function deriveSharkQuestionSetFromPrompt({ sharkKey, overview, practiceContext, count }) {
  const facts = (overview.facts || []).filter(Boolean).slice(0, 4).join("; ");
  const context = facts || overview.promptSummary || "the founder's current traction";
  const templates = {
    nemotron: [
      {
        focus: "Operating proof",
        question: `Given ${context}, what operating milestone will prove you can scale without quality, margin, or retention breaking?`,
        angle: "Tests delivery systems, hiring discipline, throughput, margin, and retention.",
      },
      {
        focus: "Execution plan",
        question: `What will you personally own over the next 90 days, and which weekly metric tells me execution is working?`,
        angle: "Tests founder ownership, operating cadence, and measurable execution.",
      },
    ],
    deepseek: [
      {
        focus: "Growth wedge",
        question: `Given ${context}, what specific acquisition wedge gets the next customers repeatably instead of through founder hustle?`,
        angle: "Tests distribution, category wedge, channel repeatability, and market pull.",
      },
      {
        focus: "Scale loop",
        question: `What partnership, product loop, or data advantage makes this business scale faster after the next milestone?`,
        angle: "Tests growth loops, partnerships, defensibility, and expansion logic.",
      },
    ],
    judge: [
      {
        focus: "Deal logic",
        question: `Why is this ask the right amount, what milestone does it unlock, and what makes the terms fair for investors?`,
        angle: "Tests valuation, use of funds, risk, return, and deal discipline.",
      },
      {
        focus: "Risk and return",
        question: `What is the biggest reason I should pass today, and what proof would change that decision?`,
        angle: "Tests downside risk, missing proof, diligence, and conditions for investment.",
      },
    ],
  };
  const source = templates[sharkKey] || templates.judge;
  return source.slice(0, count).map((item) => ({
    askingShark: sharkKey,
    askingSharkLabel: sharkLabel(sharkKey),
    focus: `${practiceContext.objectiveLabel}: ${item.focus}`.slice(0, 100),
    question: item.question.slice(0, 520),
    angle: item.angle.slice(0, 180),
  }));
}

async function repairSharkQuestionSetJson({ sharkKey, prompt, practiceContext, overview, rawOutput, count }) {
  const raw = await callJson({
    role: modelConfig.deepseek,
    temperature: 0.08,
    maxTokens: 1400,
    messages: [
      {
        role: "system",
        content:
          "Create clean Shark Tank investor questions as strict JSON. Return only JSON. Do not include analysis, labels, markdown, placeholders, or copied instructions.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              `Write exactly ${count} question${count === 1 ? "" : "s"} for ${sharkLabel(sharkKey)}.`,
              sharkProfiles()[sharkKey].thesis,
              "Each question must be one direct investor question to the human founder.",
              "Use the founder's stated facts. Do not invent revenue, margins, customers, team, valuation, or traction.",
              "Return JSON in this shape only:",
              JSON.stringify({
                questions: [
                  {
                    focus: "short focus",
                    question: "one direct investor question",
                    angle: "what this shark is testing",
                  },
                ],
              }),
              "",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              `Business overview:\n${JSON.stringify({
                businessTitle: overview.businessTitle,
                promptSummary: overview.promptSummary,
                facts: overview.facts,
                promptDiagnostics: overview.promptDiagnostics,
              })}`,
              "",
              `Founder prompt:\n${prompt}`,
              "",
              `Malformed previous output:\n${rawOutput}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return normalizeRawSharkQuestionArray(raw.questions, sharkKey, count);
}

async function repairSharkReaction({ sharkKey, prompt, room, round, answer, rawOutput }) {
  const text = await callText({
    role: modelConfig.deepseek,
    temperature: 0.16,
    maxTokens: 1100,
    messages: [
      {
        role: "system",
        content:
          "Rewrite malformed shark reaction output into a final investor response. Use the raw model output and room context, but do not copy placeholders, instructions, schema text, draft notes, or thinking text. Do not use JSON.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Respond using exactly these labels:",
              "REACTION:",
              "SCORE:",
              "INTEREST:",
              "PRESSURE:",
              "DEAL SIGNAL:",
              "INVESTOR NOTE:",
              "",
              `Write as ${sharkLabel(sharkKey)}.`,
              sharkProfiles()[sharkKey].thesis,
              "Score and interest must be integers from 0 to 100.",
              "Use the founder's actual answer and business facts. Do not invent missing numbers.",
              "",
              `Raw model output:\n${typeof rawOutput === "string" ? rawOutput : JSON.stringify(rawOutput)}`,
              "",
              `Business prompt:\n${prompt}`,
              `Facts:\n${room.facts.map((fact) => `- ${fact}`).join("\n")}`,
              `Current focus: ${round.focus}`,
              `Asking shark: ${round.askingSharkLabel || "Shark panel"}`,
              `Question: ${round.panelQuestion}`,
              `Founder answer:\n${answer}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  return normalizeSharkReaction(
    {
      reaction: extractLabeledValue(text, ["REACTION"]),
      score: extractLabeledValue(text, ["SCORE"], "0"),
      interest: extractLabeledValue(text, ["INTEREST"], "0"),
      pressure: extractLabeledValue(text, ["PRESSURE"]),
      dealSignal: extractLabeledValue(text, ["DEAL SIGNAL", "DEAL_SIGNAL"]),
      investorNote: extractLabeledValue(text, ["INVESTOR NOTE", "INVESTOR_NOTE"]),
    },
    sharkKey,
  );
}

async function createSharkQuestionSet({ sharkKey, prompt, practiceContext, overview, strict = false }) {
  const count = practiceContext.questionsPerShark || 1;
  const text = await callText({
    role: modelConfig[sharkKey],
    temperature: strict ? 0.14 : 0.32,
    maxTokens: sharkKey === "judge" ? 1800 : 1300,
    messages: [
      {
        role: "system",
        content: [
          `You are ${sharkLabel(sharkKey)} preparing your own Shark Tank questions for the human founder.`,
          sharkProfiles()[sharkKey].thesis,
          "You are one of three investor sharks. Do not write questions for the other sharks.",
          "Final answer only. Do not include analysis, a thinking process, markdown, JSON, examples, or ellipses.",
          strict ? "This is a retry. Fill every requested label with specific questions grounded in the founder's facts." : "",
        ].filter(Boolean).join(" "),
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              `Write exactly ${count} starting question${count === 1 ? "" : "s"} from your shark perspective.`,
              "Each question must be answerable by the founder in one response.",
              "Use the founder's actual facts and numbers if present. Do not invent missing revenue, margins, customers, or team facts.",
              "Avoid repeating the other sharks' likely angles.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              `Business overview:\n${JSON.stringify({
                businessTitle: overview.businessTitle,
                promptSummary: overview.promptSummary,
                facts: overview.facts,
                promptDiagnostics: overview.promptDiagnostics,
              })}`,
              "",
              `Founder prompt:\n${prompt}`,
              "",
              "Respond using exactly these labels:",
              ...Array.from({ length: count }, (_, index) => {
                const number = index + 1;
                return [`FOCUS ${number}:`, `QUESTION ${number}:`, `ANGLE ${number}:`].join("\n");
              }),
            ].join("\n"),
          },
        ],
      },
    ],
  });

  const questions = parseSharkQuestionText(text, sharkKey, count);
  if (isInvalidSharkQuestionSet(questions, count)) {
    if (!strict) {
      return createSharkQuestionSet({ sharkKey, prompt, practiceContext, overview, strict: true });
    }
    const repairedText = await callText({
      role: modelConfig.deepseek,
      temperature: 0.16,
      maxTokens: 1200,
      messages: [
        {
          role: "system",
          content:
            "Rewrite malformed shark question output into final labeled questions. Use the raw model output and room context, but do not copy placeholders, instructions, draft notes, or thinking text. Do not use JSON.",
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: [
                `Write exactly ${count} question${count === 1 ? "" : "s"} as ${sharkLabel(sharkKey)}.`,
                sharkProfiles()[sharkKey].thesis,
                "Use the founder's actual facts. Do not invent missing numbers.",
                "",
                "Respond using exactly these labels:",
                ...Array.from({ length: count }, (_, index) => {
                  const number = index + 1;
                  return [`FOCUS ${number}:`, `QUESTION ${number}:`, `ANGLE ${number}:`].join("\n");
                }),
                "",
                `Raw model output:\n${text}`,
                "",
                `Business overview:\n${JSON.stringify({
                  businessTitle: overview.businessTitle,
                  promptSummary: overview.promptSummary,
                  facts: overview.facts,
                  promptDiagnostics: overview.promptDiagnostics,
                })}`,
                "",
                `Founder prompt:\n${prompt}`,
              ].join("\n"),
            },
          ],
        },
      ],
    });
    const repairedQuestions = parseSharkQuestionText(repairedText, sharkKey, count);
    if (!isInvalidSharkQuestionSet(repairedQuestions, count)) {
      return repairedQuestions;
    }
    const jsonRepairedQuestions = await repairSharkQuestionSetJson({
      sharkKey,
      prompt,
      practiceContext,
      overview,
      rawOutput: `${text}\n\n${repairedText}`,
      count,
    });
    if (!isInvalidSharkQuestionSet(jsonRepairedQuestions, count)) {
      return jsonRepairedQuestions;
    }
    return deriveSharkQuestionSetFromPrompt({ sharkKey, overview, practiceContext, count });
  }

  return questions;
}

async function createSharkRoomBrief({ prompt, practiceContext, strict = false }) {
  let raw;
  try {
    raw = await callJson({
      role: modelConfig.deepseek,
      temperature: strict ? 0.12 : 0.28,
      maxTokens: 1400,
      messages: [
      {
        role: "system",
        content:
          [
            "You are the Shark Tank room coordinator preparing only the founder brief.",
            "Extract real facts from the founder prompt so each investor shark can write its own questions.",
            "Do not copy example values from the requested JSON shape.",
            "Never return placeholders such as short title, one sentence business summary, or fact from user prompt.",
            strict ? "This is a retry. The previous answer copied schema placeholders. Use the founder's actual business details in every field." : "",
            "Return JSON only.",
          ].filter(Boolean).join(" "),
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "The user is the founder. The three model agents are investors, not founders.",
              "Extract only stated facts or clearly safe summaries. Do not invent revenue, customers, margins, team, valuation, or traction.",
              "Every string must be a real value for this business, not an example or placeholder.",
              "Do not create investor questions. Only create the brief fields.",
              "If the prompt includes numbers such as revenue, margin, clients, ask amount, or team details, include those exact numbers in the facts.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              "Return only a valid JSON object with these keys:",
              "- businessTitle: a short name for the actual business.",
              "- promptSummary: one sentence summarizing the actual business.",
              "- facts: an array of concrete facts from the founder prompt.",
              "- promptDiagnostics.stageFit: whether the selected stage fits the facts.",
              "- promptDiagnostics.missingFacts: an array of specific missing investor facts.",
              "- promptDiagnostics.strongestSignal: the strongest concrete proof in the prompt.",
              "- promptDiagnostics.firstPracticeMove: the first answer the founder should tighten.",
              "",
              `Founder prompt:\n${prompt}`,
            ].join("\n"),
          },
        ],
      },
      ],
    });
  } catch (error) {
    raw = await repairSharkRoomBrief({
      prompt,
      practiceContext,
      rawOutput: error instanceof Error ? error.message : "The model returned malformed JSON.",
    });
  }

  let overview = normalizeRoomBrief(raw, prompt);

  if (
    isPlaceholderText(overview.businessTitle) ||
    isPlaceholderText(overview.promptSummary) ||
    !overview.facts?.length ||
    overview.facts.some(isPlaceholderText)
  ) {
    if (!strict) {
      return createSharkRoomBrief({ prompt, practiceContext, strict: true });
    }
    overview = await repairSharkRoomBrief({ prompt, practiceContext, rawOutput: raw });
    if (
      isPlaceholderText(overview.businessTitle) ||
      isPlaceholderText(overview.promptSummary) ||
      !overview.facts?.length ||
      overview.facts.some(isPlaceholderText)
    ) {
      overview = deriveBriefFromPrompt(prompt, practiceContext);
    }
  }

  const questionPairs = await Promise.all(
    sharkKeys.map(async (sharkKey) => [
      sharkKey,
      await createSharkQuestionSet({ sharkKey, prompt, practiceContext, overview }),
    ]),
  );
  const questionSets = Object.fromEntries(questionPairs);
  const rounds = normalizeRoomRoundsFromSharkQuestions(questionSets, practiceContext);
  const brief = { ...overview, rounds };

  if (isPlaceholderBrief(brief)) {
    throw new Error("One or more sharks returned placeholder starting questions. Try again with more concrete business details.");
  }

  return brief;
}

async function createSharkReaction({ sharkKey, prompt, practiceContext, room, round, answer, strict = false }) {
  if (sharkKey === "judge") {
    const text = await callText({
      role: modelConfig.judge,
      temperature: strict ? 0.12 : 0.24,
      maxTokens: 1800,
      messages: [
        {
          role: "system",
          content: [
            `You are ${sharkLabel(sharkKey)} in an interactive AI Shark Tank room.`,
            sharkProfiles()[sharkKey].thesis,
            "Evaluate the human founder's live answer as a financial skeptic.",
            "Final answer only. Do not include analysis, a thinking process, a checklist, draft notes, JSON, markdown, or ellipses.",
            "Write concrete, specific investor language under each requested label.",
            strict ? "This is a retry because the previous answer was not usable. Fill every label with real content." : "",
          ].filter(Boolean).join(" "),
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: [
                "Respond using exactly these labels:",
                "REACTION:",
                "SCORE:",
                "INTEREST:",
                "PRESSURE:",
                "DEAL SIGNAL:",
                "INVESTOR NOTE:",
                "",
                `Practice context:\n${practiceContextPrompt(practiceContext)}`,
                "",
                `Business prompt:\n${prompt}`,
                "",
                `Room facts:\n${room.facts.map((fact) => `- ${fact}`).join("\n")}`,
                "",
                `Current focus: ${round.focus}`,
                `Panel question: ${round.panelQuestion}`,
                `Your angle: ${round.sharkAngles?.[sharkKey] || sharkProfiles()[sharkKey].thesis}`,
                "",
                `Founder answer:\n${answer}`,
              ].join("\n"),
            },
          ],
        },
      ],
    });
    const reaction = normalizeSharkReaction(
      {
        reaction: extractLabeledValue(text, ["REACTION"]),
        score: extractLabeledValue(text, ["SCORE"], "0"),
        interest: extractLabeledValue(text, ["INTEREST"], "0"),
        pressure: extractLabeledValue(text, ["PRESSURE"]),
        dealSignal: extractLabeledValue(text, ["DEAL SIGNAL", "DEAL_SIGNAL"]),
        investorNote: extractLabeledValue(text, ["INVESTOR NOTE", "INVESTOR_NOTE"]),
      },
      sharkKey,
    );
    if (isPlaceholderReaction(reaction)) {
      if (!strict) {
        return createSharkReaction({ sharkKey, prompt, practiceContext, room, round, answer, strict: true });
      }
      const repaired = await callJson({
        role: modelConfig.deepseek,
        temperature: 0.18,
        maxTokens: 900,
        messages: [
          {
            role: "system",
            content:
              "Structure a usable investor reaction for the Nemotron Lightning Shark. Use the founder answer and room context. Do not use placeholders, ellipses, or copied schema text. Return JSON only.",
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: [
                  "Return JSON with keys: reaction, score, interest, pressure, dealSignal, investorNote.",
                  "Write as the Nemotron Lightning Shark: lead deal-maker and financial skeptic.",
                  "",
                  `Raw Nemotron output:\n${text}`,
                  "",
                  `Business prompt:\n${prompt}`,
                  `Facts:\n${room.facts.map((fact) => `- ${fact}`).join("\n")}`,
                  `Panel question: ${round.panelQuestion}`,
                  `Founder answer:\n${answer}`,
                ].join("\n"),
              },
            ],
          },
        ],
      });
      const repairedReaction = normalizeSharkReaction(repaired, sharkKey);
      if (isPlaceholderReaction(repairedReaction)) {
        throw new Error(`${sharkLabel(sharkKey)} returned placeholder reaction text.`);
      }
      return repairedReaction;
    }
    return reaction;
  }

  let raw;
  try {
    raw = await callJson({
      role: modelConfig[sharkKey],
      temperature: strict ? 0.12 : sharkKey === "judge" ? 0.22 : 0.48,
      maxTokens: 1100,
      messages: [
      {
        role: "system",
        content: [
          `You are ${sharkLabel(sharkKey)} in an interactive AI Shark Tank room.`,
          sharkProfiles()[sharkKey].thesis,
          "You are evaluating the human founder's live answer, not pitching as a founder.",
          "Score harshly but practically from 0-100. Interest is your current likelihood of investing from 0-100.",
          "Do not invent facts. If proof is missing, call it out.",
          "Never output ellipses, placeholder text, or empty fields. Every field must contain actual investor language.",
          strict ? "This is a retry because the previous reaction was empty or placeholder text. Give specific investor feedback using the founder's actual answer." : "",
          "Return JSON only.",
        ].filter(Boolean).join(" "),
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "React to the founder's answer for this round.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              "Return only a valid JSON object with these keys:",
              "- reaction: a concise, specific investor reaction to this answer.",
              "- score: an integer from 0 to 100.",
              "- interest: an integer from 0 to 100 showing your current likelihood of investing.",
              "- pressure: one specific follow-up pressure point.",
              "- dealSignal: how this answer changes your willingness to invest.",
              "- investorNote: one practical note to help the founder improve.",
              "",
              `Business prompt:\n${prompt}`,
              "",
              `Room facts:\n${room.facts.map((fact) => `- ${fact}`).join("\n")}`,
              "",
              `Previous answered rounds:\n${JSON.stringify((room.rounds || []).filter((item) => item.userAnswer).map((item) => ({
                focus: item.focus,
                panelQuestion: item.panelQuestion,
                userAnswer: item.userAnswer,
                scores: item.scores,
                interest: item.interest,
              })))}`,
              "",
              `Current focus: ${round.focus}`,
              `Panel question: ${round.panelQuestion}`,
              `Your angle: ${round.sharkAngles?.[sharkKey] || sharkProfiles()[sharkKey].thesis}`,
              "",
              `Founder answer:\n${answer}`,
            ].join("\n"),
          },
        ],
      },
      ],
    });
  } catch (error) {
    const repairedReaction = await repairSharkReaction({
      sharkKey,
      prompt,
      room,
      round,
      answer,
      rawOutput: error instanceof Error ? error.message : "The model returned malformed JSON.",
    });
    if (isPlaceholderReaction(repairedReaction)) {
      throw new Error(`${sharkLabel(sharkKey)} returned malformed reaction text.`);
    }
    return repairedReaction;
  }

  const reaction = normalizeSharkReaction(raw, sharkKey);
  if (isPlaceholderReaction(reaction)) {
    if (!strict) {
      return createSharkReaction({ sharkKey, prompt, practiceContext, room, round, answer, strict: true });
    }
    const repairedReaction = await repairSharkReaction({
      sharkKey,
      prompt,
      room,
      round,
      answer,
      rawOutput: raw,
    });
    if (isPlaceholderReaction(repairedReaction)) {
      throw new Error(`${sharkLabel(sharkKey)} returned placeholder reaction text.`);
    }
    return repairedReaction;
  }

  return reaction;
}

async function repairFinalSharkOffer({ sharkKey, prompt, practiceContext, room, rawOutput }) {
  const text = await callText({
    role: modelConfig.deepseek,
    temperature: 0.12,
    maxTokens: 1100,
    messages: [
      {
        role: "system",
        content:
          "Write a final Shark Tank investment decision using only the requested labels. No JSON, markdown, analysis, placeholders, or copied schema text.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              `Write as ${sharkLabel(sharkKey)}.`,
              sharkProfiles()[sharkKey].thesis,
              "Choose exactly one decision: offer, pass, or join.",
              "If passing, leave amount and equity blank.",
              "Respond using exactly these labels:",
              "DECISION:",
              "AMOUNT:",
              "EQUITY:",
              "CONDITIONS:",
              "RATIONALE:",
              "IMPROVEMENT:",
              "CONFIDENCE:",
              "",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              `Business prompt:\n${prompt}`,
              "",
              `Room transcript:\n${JSON.stringify(room.rounds)}`,
              "",
              `Malformed previous output:\n${rawOutput}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });
  return normalizeOffer(
    {
      decision: extractLabeledValue(text, ["DECISION"]),
      amount: extractLabeledValue(text, ["AMOUNT"]),
      equity: extractLabeledValue(text, ["EQUITY"]),
      conditions: parseListValue(extractLabeledValue(text, ["CONDITIONS"])),
      rationale: extractLabeledValue(text, ["RATIONALE"]),
      improvementNote: extractLabeledValue(text, ["IMPROVEMENT"]),
      confidence: extractLabeledValue(text, ["CONFIDENCE"], "0"),
    },
    sharkKey,
  );
}

async function createFinalSharkOffer({ sharkKey, prompt, practiceContext, room }) {
  if (sharkKey === "judge") {
    const text = await callText({
      role: modelConfig.judge,
      temperature: 0.24,
      maxTokens: 1300,
      messages: [
        {
          role: "system",
          content: [
            `You are ${sharkLabel(sharkKey)} making your independent final Shark Tank decision.`,
            sharkProfiles()[sharkKey].thesis,
            "Choose offer, pass, or join. Use realistic terms and conditions.",
            "Final answer only. Do not include analysis, a thinking process, draft notes, JSON, markdown, or ellipses. Fill every label with concrete content.",
          ].join(" "),
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: [
                "Respond using exactly these labels:",
                "DECISION:",
                "AMOUNT:",
                "EQUITY:",
                "CONDITIONS:",
                "RATIONALE:",
                "IMPROVEMENT:",
                "CONFIDENCE:",
                "",
                `Practice context:\n${practiceContextPrompt(practiceContext)}`,
                "",
                `Business prompt:\n${prompt}`,
                "",
                `Room transcript:\n${JSON.stringify(room.rounds)}`,
              ].join("\n"),
            },
          ],
        },
      ],
    });
    return normalizeOffer(
      {
        decision: extractLabeledValue(text, ["DECISION"]),
        amount: extractLabeledValue(text, ["AMOUNT"]),
        equity: extractLabeledValue(text, ["EQUITY"]),
        conditions: parseListValue(extractLabeledValue(text, ["CONDITIONS"])),
        rationale: extractLabeledValue(text, ["RATIONALE"]),
        improvementNote: extractLabeledValue(text, ["IMPROVEMENT"]),
        confidence: extractLabeledValue(text, ["CONFIDENCE"], "0"),
      },
      sharkKey,
    );
  }

  let raw;
  try {
    raw = await callJson({
      role: modelConfig[sharkKey],
      temperature: sharkKey === "judge" ? 0.28 : 0.42,
      maxTokens: 1200,
      messages: [
      {
        role: "system",
        content: [
          `You are ${sharkLabel(sharkKey)} making your independent final Shark Tank decision.`,
          sharkProfiles()[sharkKey].thesis,
          "Choose offer, pass, or join. A join means you would join another shark's terms instead of leading.",
          "Use realistic terms and conditions. Do not invent new business facts.",
          "Return JSON only.",
        ].join(" "),
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Make your final investment decision after hearing every founder answer.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              "Return JSON with this shape:",
              JSON.stringify({
                decision: "offer",
                amount: "$150k",
                equity: "10%",
                conditions: ["condition"],
                rationale: "why you made this decision",
                improvementNote: "what founder should improve",
                confidence: 0,
              }),
              "",
              `Business prompt:\n${prompt}`,
              "",
              `Room transcript:\n${JSON.stringify(room.rounds)}`,
            ].join("\n"),
          },
        ],
      },
      ],
    });
  } catch (error) {
    return repairFinalSharkOffer({
      sharkKey,
      prompt,
      practiceContext,
      room,
      rawOutput: error instanceof Error ? error.message : "The model returned malformed JSON.",
    });
  }

  return normalizeOffer(raw, sharkKey);
}

async function createFinalDealReview({ prompt, practiceContext, room, offers }) {
  const raw = await callJson({
    role: modelConfig.deepseek,
    temperature: 0.26,
    maxTokens: 1500,
    messages: [
      {
        role: "system",
        content:
          "You are the Shark Tank room coordinator writing the final deal memo for a founder practice room. Summarize offers, passes, risks, and drills. Return JSON only.",
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Summarize the final deal phase. Outcome must be Deal, Conditional deal, or No deal.",
              "Best offer should reference one of the sharks if any offer or join exists.",
              "Keep this useful for the human founder to practice next.",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              "Return JSON with this shape:",
              JSON.stringify({
                outcome: "Conditional deal",
                bestOffer: { shark: "nemotron", label: "MiniMax Shark", terms: "$150k for 12%" },
                verdict: "final deal verdict",
                strongestAnswer: "best founder answer",
                weakestAnswer: "weakest founder answer",
                dealRisks: ["risk"],
                nextPractice: ["practice move"],
                practiceDrills: [
                  {
                    name: "drill name",
                    goal: "what this improves",
                    prompt: "practice question",
                  },
                ],
              }),
              "",
              `Business prompt:\n${prompt}`,
              "",
              `Rounds:\n${JSON.stringify(room.rounds)}`,
              "",
              `Independent shark decisions:\n${JSON.stringify(offers)}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  const acceptedOffers = offers.filter((offer) => offer.decision === "offer" || offer.decision === "join");
  const bestOffer = !acceptedOffers.length
    ? {
        shark: "",
        label: "No lead shark",
        terms: "No formal offer",
      }
    : raw.bestOffer && typeof raw.bestOffer === "object"
    ? {
        shark: sanitizeInput(raw.bestOffer.shark, acceptedOffers[0]?.shark || "").slice(0, 40),
        label: sanitizeInput(raw.bestOffer.label, acceptedOffers[0]?.label || "No lead shark").slice(0, 80),
        terms: sanitizeInput(
          raw.bestOffer.terms,
          acceptedOffers[0] ? `${acceptedOffers[0].amount} ${acceptedOffers[0].equity ? `for ${acceptedOffers[0].equity}` : ""}` : "No formal offer",
        ).slice(0, 180),
      }
    : {
        shark: acceptedOffers[0]?.shark || "",
        label: acceptedOffers[0]?.label || "No lead shark",
        terms: acceptedOffers[0] ? `${acceptedOffers[0].amount} ${acceptedOffers[0].equity ? `for ${acceptedOffers[0].equity}` : ""}` : "No formal offer",
      };
  const rawOutcome = sanitizeInput(raw.outcome, acceptedOffers.length ? "Conditional deal" : "No deal");
  const outcome = !acceptedOffers.length
    ? "No deal"
    : ["Deal", "Conditional deal", "No deal"].find((item) => item.toLowerCase() === rawOutcome.toLowerCase()) ||
      "Conditional deal";

  return {
    outcome,
    offers,
    bestOffer,
    verdict: sanitizeInput(raw.verdict, "The sharks made their decision based on the founder's proof, economics, growth plan, and deal risk.").slice(0, 520),
    strongestAnswer: sanitizeInput(raw.strongestAnswer, "The strongest answer connected a real fact to a fundable next milestone.").slice(0, 260),
    weakestAnswer: sanitizeInput(raw.weakestAnswer, "The weakest answer needs more proof, numbers, and risk control.").slice(0, 260),
    dealRisks: Array.isArray(raw.dealRisks)
      ? raw.dealRisks.slice(0, 5).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    nextPractice: Array.isArray(raw.nextPractice)
      ? raw.nextPractice.slice(0, 5).map((item) => sanitizeInput(item).slice(0, 180))
      : [],
    practiceDrills: normalizePracticeDrills(raw.practiceDrills),
    counterOffers: [],
  };
}

async function createCounterOfferResponse({ sharkKey, prompt, practiceContext, room, counter, strict = false }) {
  if (sharkKey === "judge") {
    const text = await callText({
      role: modelConfig.judge,
      temperature: strict ? 0.12 : 0.22,
      maxTokens: 2200,
      messages: [
        {
          role: "system",
          content: [
            `You are ${sharkLabel(sharkKey)} responding to the founder's counter-offer.`,
            sharkProfiles()[sharkKey].thesis,
            "Final answer only. Choose accept, revise, or walk. Do not include analysis, a thinking process, draft notes, JSON, markdown, or ellipses.",
            strict ? "This is a retry. MESSAGE must directly explain your decision on the founder's revised terms. FINAL ADVICE must teach one practical negotiation lesson." : "",
          ].join(" "),
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: [
                "Respond using exactly these labels:",
                "DECISION:",
                "REVISED AMOUNT:",
                "REVISED EQUITY:",
                "CONDITIONS:",
                "MESSAGE:",
                "FINAL ADVICE:",
                "",
                `Practice context:\n${practiceContextPrompt(practiceContext)}`,
                "",
                `Business prompt:\n${prompt}`,
                "",
                `Final deal before counter:\n${JSON.stringify(room.finalDeal)}`,
                "",
                `Founder counter-offer:\n${counter}`,
              ].join("\n"),
            },
          ],
        },
      ],
    });
    const response = normalizeCounterResponse(
      {
        decision: extractLabeledValue(text, ["DECISION"]),
        revisedAmount: extractLabeledValue(text, ["REVISED AMOUNT", "REVISED_AMOUNT"]),
        revisedEquity: extractLabeledValue(text, ["REVISED EQUITY", "REVISED_EQUITY"]),
        conditions: parseListValue(extractLabeledValue(text, ["CONDITIONS"])),
        message: extractLabeledValue(text, ["MESSAGE"]),
        finalAdvice: extractLabeledValue(text, ["FINAL ADVICE", "FINAL_ADVICE"]),
      },
      sharkKey,
    );
    if (isPlaceholderCounterResponse(response)) {
      if (!strict) {
        return createCounterOfferResponse({ sharkKey, prompt, practiceContext, room, counter, strict: true });
      }
      const repairedText = await callText({
        role: modelConfig.deepseek,
        temperature: 0.18,
        maxTokens: 1500,
        messages: [
          {
            role: "system",
            content:
              "Write the final counter-offer response for the Nemotron Lightning Shark. Use the raw Nemotron output and room context, but do not copy placeholders, instructions, draft notes, or thinking text. Do not use JSON.",
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: [
                  "Respond using exactly these labels:",
                  "DECISION:",
                  "REVISED AMOUNT:",
                  "REVISED EQUITY:",
                  "CONDITIONS:",
                  "MESSAGE:",
                  "FINAL ADVICE:",
                  "",
                  "Write as the Nemotron Lightning Shark: lead deal-maker and financial skeptic.",
                  "decision must be accept, revise, or walk.",
                  "",
                  `Raw Nemotron output:\n${text}`,
                  "",
                  `Business prompt:\n${prompt}`,
                  `Final deal before counter:\n${JSON.stringify(room.finalDeal)}`,
                  `Founder counter-offer:\n${counter}`,
                ].join("\n"),
              },
            ],
          },
        ],
      });
      const repairedResponse = normalizeCounterResponse(
        {
          decision: extractLabeledValue(repairedText, ["DECISION"]),
          revisedAmount: extractLabeledValue(repairedText, ["REVISED AMOUNT", "REVISED_AMOUNT"]),
          revisedEquity: extractLabeledValue(repairedText, ["REVISED EQUITY", "REVISED_EQUITY"]),
          conditions: parseListValue(extractLabeledValue(repairedText, ["CONDITIONS"])),
          message: extractLabeledValue(repairedText, ["MESSAGE"]),
          finalAdvice: extractLabeledValue(repairedText, ["FINAL ADVICE", "FINAL_ADVICE"]),
        },
        sharkKey,
      );
      if (isPlaceholderCounterResponse(repairedResponse)) {
        throw new Error(`${sharkLabel(sharkKey)} returned placeholder counter-offer text.`);
      }
      return repairedResponse;
    }
    return response;
  }

  const text = await callText({
    role: modelConfig[sharkKey],
    temperature: strict ? 0.12 : 0.28,
    maxTokens: 1200,
    messages: [
      {
        role: "system",
        content: [
          `You are ${sharkLabel(sharkKey)} responding to the founder's counter-offer.`,
          sharkProfiles()[sharkKey].thesis,
          "Final answer only. Choose accept, revise, or walk. Do not include analysis, a thinking process, draft notes, JSON, markdown, or ellipses.",
          strict ? "This is a retry. Fill MESSAGE and FINAL ADVICE with specific investor language tied to the counter-offer." : "",
        ].join(" "),
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: [
              "Respond using exactly these labels:",
              "DECISION:",
              "REVISED AMOUNT:",
              "REVISED EQUITY:",
              "CONDITIONS:",
              "MESSAGE:",
              "FINAL ADVICE:",
              "",
              "If you did not previously offer, you may still revise into an offer only if the counter materially solves your objections.",
              "",
              `Practice context:\n${practiceContextPrompt(practiceContext)}`,
              "",
              `Business prompt:\n${prompt}`,
              "",
              `Final deal before counter:\n${JSON.stringify(room.finalDeal)}`,
              "",
              `Founder counter-offer:\n${counter}`,
            ].join("\n"),
          },
        ],
      },
    ],
  });

  const response = normalizeCounterResponse(
    {
      decision: extractLabeledValue(text, ["DECISION"]),
      revisedAmount: extractLabeledValue(text, ["REVISED AMOUNT", "REVISED_AMOUNT"]),
      revisedEquity: extractLabeledValue(text, ["REVISED EQUITY", "REVISED_EQUITY"]),
      conditions: parseListValue(extractLabeledValue(text, ["CONDITIONS"])),
      message: extractLabeledValue(text, ["MESSAGE"]),
      finalAdvice: extractLabeledValue(text, ["FINAL ADVICE", "FINAL_ADVICE"]),
    },
    sharkKey,
  );
  if (isPlaceholderCounterResponse(response)) {
    if (!strict) {
      return createCounterOfferResponse({ sharkKey, prompt, practiceContext, room, counter, strict: true });
    }
    const repairedResponse = await repairCounterOfferResponse({
      sharkKey,
      prompt,
      practiceContext,
      room,
      counter,
      rawOutput: text,
    });
    if (isPlaceholderCounterResponse(repairedResponse)) {
      throw new Error(`${sharkLabel(sharkKey)} returned placeholder counter-offer text.`);
    }
    return repairedResponse;
  }

  return response;
}

function buildRoomReportData(room) {
  const finalDeal = room.finalDeal || {};
  const totals = roomTotals(room);
  return {
    ...room,
    kind: "user-shark-room",
    winner: dealOutcomeKey(finalDeal.outcome),
    verdict: finalDeal.verdict || "",
    totals,
    readinessScore: Math.round(
      Object.values(totals).filter((value) => value != null).reduce((sum, value) => sum + value, 0) /
        Math.max(1, Object.values(totals).filter((value) => value != null).length),
    ),
    strongestMoment: finalDeal.strongestAnswer || "",
    weakestMoment: finalDeal.weakestAnswer || "",
    nextPractice: finalDeal.nextPractice || [],
    practiceDrills: normalizePracticeDrills(finalDeal.practiceDrills),
  };
}

const pitchDuelStep = createStep({
  id: "run-pitch-duel",
  description: "Runs the Shark Tank duel against Nebius models and streams UI-ready events.",
  inputSchema: z.object({
    prompt: z.string().min(1),
    practiceContext: z.object({
      stage: z.string(),
      stageLabel: z.string(),
      stagePrompt: z.string(),
      objective: z.string(),
      objectiveLabel: z.string(),
      objectivePrompt: z.string(),
      length: z.string(),
      lengthLabel: z.string(),
      roundCount: z.number(),
      questionsPerShark: z.number().optional(),
    }),
    cacheKey: z.string().min(1),
  }),
  outputSchema: z.any(),
  execute: async ({ inputData, outputWriter }) =>
    runPitchDuelSimulation({
      prompt: inputData.prompt,
      practiceContext: inputData.practiceContext,
      cacheKey: inputData.cacheKey,
      emit: async (event) => {
        if (outputWriter) {
          await outputWriter(event);
        }
      },
    }),
});

const pitchDuelWorkflow = createWorkflow({
  id: "pitch-duel-workflow",
  inputSchema: z.object({
    prompt: z.string().min(1),
    practiceContext: z.object({
      stage: z.string(),
      stageLabel: z.string(),
      stagePrompt: z.string(),
      objective: z.string(),
      objectiveLabel: z.string(),
      objectivePrompt: z.string(),
      length: z.string(),
      lengthLabel: z.string(),
      roundCount: z.number(),
      questionsPerShark: z.number().optional(),
    }),
    cacheKey: z.string().min(1),
  }),
  outputSchema: z.any(),
})
  .then(pitchDuelStep)
  .commit();

const mastra = new Mastra({
  agents: {
    miniMaxFounderAgent,
    deepSeekFounderAgent,
    investorJudgeAgent,
  },
  workflows: { pitchDuelWorkflow },
  storage: new LibSQLStore({
    id: "ai-shark-tank-mastra-storage",
    url: `file:${mastraDbPath}`,
  }),
});

app.get("/api/health", (_request, response) => {
  response.json({
    ok: true,
    hasNebiusKey: Boolean(process.env.NEBIUS_API_KEY),
    callTimeoutMs: LLM_CALL_TIMEOUT_MS,
    models: modelConfig,
    agentFramework: {
      name: "Mastra",
      workflow: pitchDuelWorkflow.id,
      roomMode: "user-shark-room",
      agents: Object.values(mastra.listAgents()).map((agent) => ({
        id: agent.id,
        name: agent.name,
      })),
    },
  });
});

app.get("/api/reports", (request, response) => {
  const reports = listReports(request.query.limit);
  const drillAttempts = listDrillAttempts(request.query.limit);
  response.json({
    ok: true,
    data: reports,
    summary: summarizeReports(reports, drillAttempts),
  });
});

app.get("/api/reports/:id", (request, response) => {
  const report = getReport(String(request.params.id || ""));
  if (!report) {
    response.status(404).json({ ok: false, error: "Report not found." });
    return;
  }

  response.json({ ok: true, data: report });
});

app.get("/reports/:id", (request, response) => {
  const report = getReport(String(request.params.id || ""));
  if (!report) {
    response.status(404).send("<!doctype html><title>Report not found</title><h1>Report not found</h1>");
    return;
  }

  response.type("html").send(renderReportHtml(report));
});

app.post("/api/prep", async (request, response) => {
  const prompt = buildPromptFromBody(request.body);
  if (!prompt) {
    response.status(400).json({ ok: false, error: "Business prompt is required." });
    return;
  }

  if (!process.env.NEBIUS_API_KEY) {
    response.status(500).json({
      ok: false,
      error: "Missing NEBIUS_API_KEY. Add it to ai-shark-tank/.env and restart the server.",
    });
    return;
  }

  const practiceContext = normalizePracticeContext(request.body);

  try {
    const result = await withChunkCacheMeta({
      prompt,
      practiceContext,
      step: "founder-prep",
      extra: "prep-v1",
      producer: () => createFounderPrep({ prompt, practiceContext }),
    });
    response.json({
      ok: true,
      cached: result.cached,
      data: {
        ...result.data,
        cached: result.cached,
      },
    });
  } catch (error) {
    console.error(error);
    response.status(502).json({
      ok: false,
      error: error instanceof Error ? error.message : "Nebius founder prep failed.",
    });
  }
});

app.post("/api/drill-feedback", async (request, response) => {
  const reportId = sanitizeInput(request.body.reportId).slice(0, 80);
  const report = reportId ? getReport(reportId) : null;
  const prompt = buildPromptFromBody(request.body) || sanitizeInput(report?.prompt);
  const answer = sanitizeInput(request.body.answer);
  const drill = {
    name: sanitizeInput(request.body.drill?.name, "Practice Drill").slice(0, 80),
    goal: sanitizeInput(request.body.drill?.goal, "Improve one investor-critical answer.").slice(0, 180),
    prompt: sanitizeInput(request.body.drill?.prompt, "Answer the investor question clearly.").slice(0, 320),
  };

  if (!prompt) {
    response.status(400).json({ ok: false, error: "Business prompt is required." });
    return;
  }

  if (!answer) {
    response.status(400).json({ ok: false, error: "Write your practice answer first." });
    return;
  }

  if (!process.env.NEBIUS_API_KEY) {
    response.status(500).json({
      ok: false,
      error: "Missing NEBIUS_API_KEY. Add it to ai-shark-tank/.env and restart the server.",
    });
    return;
  }

  const practiceContext = report?.practiceContext || normalizePracticeContext(request.body);

  try {
    const result = await withChunkCacheMeta({
      prompt,
      practiceContext,
      step: "drill-feedback",
      extra: JSON.stringify({ reportId, drill, answer }),
      producer: () => createDrillFeedback({ prompt, practiceContext, report, drill, answer }),
    });
    const attempt = saveDrillAttempt({
      reportId,
      drill,
      answer,
      feedback: result.data,
    });
    const attemptSummary = {
      id: attempt.id,
      reportId: reportId || null,
      createdAt: attempt.createdAt,
      drillName: drill.name,
      drillPrompt: drill.prompt,
      score: toScore(result.data.score),
      verdict: sanitizeInput(result.data.verdict).slice(0, 180),
      nextPracticeMove: sanitizeInput(result.data.nextPracticeMove).slice(0, 180),
    };
    response.json({
      ok: true,
      cached: result.cached,
      data: {
        ...result.data,
        attemptId: attempt.id,
        attemptCreatedAt: attempt.createdAt,
        attempt: attemptSummary,
        cached: result.cached,
      },
    });
  } catch (error) {
    console.error(error);
    response.status(502).json({
      ok: false,
      error: error instanceof Error ? error.message : "Nebius drill feedback failed.",
    });
  }
});

app.post("/api/room/start", async (request, response) => {
  const prompt = buildPromptFromBody(request.body);
  if (!prompt) {
    response.status(400).json({ ok: false, error: "Business prompt is required." });
    return;
  }

  if (!process.env.NEBIUS_API_KEY) {
    response.status(500).json({
      ok: false,
      error: "Missing NEBIUS_API_KEY. Add it to ai-shark-tank/.env and restart the server.",
    });
    return;
  }

  const practiceContext = normalizePracticeContext(request.body);

  try {
    const brief = await withChunkCache({
      prompt,
      practiceContext,
      step: "user-room-brief",
      extra: "panel-rounds",
      producer: () => createSharkRoomBrief({ prompt, practiceContext }),
    });
    const id = randomUUID();
    const room = saveRoom({
      id,
      kind: "user-shark-room",
      status: "awaiting-answer",
      prompt,
      practiceContext,
      models: modelConfig,
      businessTitle: brief.businessTitle,
      promptSummary: brief.promptSummary,
      promptDiagnostics: brief.promptDiagnostics,
      facts: brief.facts,
      sharks: sharkProfiles(),
      rounds: brief.rounds,
      currentRoundIndex: 0,
      finalDeal: null,
    });

    response.json({ ok: true, data: room });
  } catch (error) {
    console.error(error);
    response.status(502).json({
      ok: false,
      error: error instanceof Error ? error.message : "Nebius room start failed.",
    });
  }
});

app.post("/api/room/:id/answer", async (request, response) => {
  const room = getRoom(String(request.params.id || ""));
  const answer = sanitizeInput(request.body.answer);
  if (!room) {
    response.status(404).json({ ok: false, error: "Room not found." });
    return;
  }
  if (room.status === "complete") {
    response.status(409).json({ ok: false, error: "This room is already complete. Start a new room or counter the final offers." });
    return;
  }
  if (!answer) {
    response.status(400).json({ ok: false, error: "Answer the sharks before advancing." });
    return;
  }
  if (!process.env.NEBIUS_API_KEY) {
    response.status(500).json({
      ok: false,
      error: "Missing NEBIUS_API_KEY. Add it to ai-shark-tank/.env and restart the server.",
    });
    return;
  }

  const index = Number(room.currentRoundIndex) || 0;
  const round = room.rounds?.[index];
  if (!round) {
    response.status(400).json({ ok: false, error: "No active round found for this room." });
    return;
  }

  try {
    const reactions = await Promise.all(
      sharkKeys.map((sharkKey) =>
        withChunkCache({
          prompt: room.prompt,
          practiceContext: room.practiceContext,
          step: `room-${room.id}-round-${index + 1}-${sharkKey}`,
          extra: JSON.stringify({ question: round.panelQuestion, answer }),
          producer: () =>
            createSharkReaction({
              sharkKey,
              prompt: room.prompt,
              practiceContext: room.practiceContext,
              room,
              round,
              answer,
            }),
        }),
      ),
    );

    const sharkReactions = Object.fromEntries(reactions.map((reaction) => [reaction.shark, reaction]));
    const scores = Object.fromEntries(reactions.map((reaction) => [reaction.shark, reaction.score]));
    const interest = Object.fromEntries(reactions.map((reaction) => [reaction.shark, reaction.interest]));
    const nextRounds = [...room.rounds];
    nextRounds[index] = {
      ...round,
      userAnswer: answer,
      sharkReactions,
      scores,
      interest,
      status: "scored",
    };

    let updatedRoom = {
      ...room,
      rounds: nextRounds,
      currentRoundIndex: Math.min(index + 1, nextRounds.length - 1),
      status: index + 1 >= nextRounds.length ? "dealing" : "awaiting-answer",
    };

    if (index + 1 >= nextRounds.length) {
      const offers = await Promise.all(
        sharkKeys.map((sharkKey) =>
          withChunkCache({
            prompt: room.prompt,
            practiceContext: room.practiceContext,
            step: `room-${room.id}-final-offer-${sharkKey}`,
            extra: JSON.stringify(nextRounds.map((item) => ({ q: item.panelQuestion, a: item.userAnswer, s: item.scores }))),
            producer: () =>
              createFinalSharkOffer({
                sharkKey,
                prompt: room.prompt,
                practiceContext: room.practiceContext,
                room: { ...updatedRoom, rounds: nextRounds },
              }),
          }),
        ),
      );
      const finalDeal = await withChunkCache({
        prompt: room.prompt,
        practiceContext: room.practiceContext,
        step: `room-${room.id}-final-deal`,
        extra: JSON.stringify(offers),
        producer: () =>
          createFinalDealReview({
            prompt: room.prompt,
            practiceContext: room.practiceContext,
            room: { ...updatedRoom, rounds: nextRounds },
            offers,
          }),
      });
      updatedRoom = {
        ...updatedRoom,
        finalDeal,
        status: "complete",
        currentRoundIndex: nextRounds.length - 1,
      };
      if (isReportableDealOutcome(finalDeal.outcome)) {
        const reportData = buildRoomReportData(updatedRoom);
        const report = saveReport(reportData, null);
        updatedRoom = {
          ...updatedRoom,
          winner: reportData.winner,
          totals: reportData.totals,
          readinessScore: reportData.readinessScore,
          practiceDrills: reportData.practiceDrills,
          reportId: report.id,
          reportUrl: `/reports/${report.id}`,
          generatedAt: report.createdAt,
        };
      }
    }

    updatedRoom = saveRoom(updatedRoom);
    response.json({ ok: true, data: updatedRoom });
  } catch (error) {
    console.error(error);
    response.status(502).json({
      ok: false,
      error: error instanceof Error ? error.message : "Nebius shark round failed.",
    });
  }
});

app.post("/api/room/:id/counter", async (request, response) => {
  const room = getRoom(String(request.params.id || ""));
  const counter = sanitizeInput(request.body.counter);
  if (!room) {
    response.status(404).json({ ok: false, error: "Room not found." });
    return;
  }
  if (room.status !== "complete" || !room.finalDeal) {
    response.status(409).json({ ok: false, error: "Counter-offers open after the sharks make final offers." });
    return;
  }
  if (Array.isArray(room.finalDeal.counterOffers) && room.finalDeal.counterOffers.length) {
    response.status(409).json({ ok: false, error: "Counter-offer already completed. Open the review to see the final report." });
    return;
  }
  if (!counter) {
    response.status(400).json({ ok: false, error: "Write your counter-offer first." });
    return;
  }
  if (!process.env.NEBIUS_API_KEY) {
    response.status(500).json({
      ok: false,
      error: "Missing NEBIUS_API_KEY. Add it to ai-shark-tank/.env and restart the server.",
    });
    return;
  }

  try {
    const counterResponses = await Promise.all(
      sharkKeys.map((sharkKey) =>
        createCounterOfferResponse({
          sharkKey,
          prompt: room.prompt,
          practiceContext: room.practiceContext,
          room,
          counter,
        }),
      ),
    );
    const finalDeal = {
      ...room.finalDeal,
      counterOffer: counter,
      counterOffers: counterResponses,
      outcome: counterResponses.some((item) => item.decision === "accept" || item.decision === "revise")
        ? "Conditional deal"
        : room.finalDeal.outcome,
    };
    const updatedRoom = saveRoom({ ...room, finalDeal });
    if (updatedRoom.reportId) {
      updateReportData(updatedRoom.reportId, buildRoomReportData(updatedRoom));
    }
    response.json({ ok: true, data: updatedRoom });
  } catch (error) {
    console.error(error);
    response.status(502).json({
      ok: false,
      error: error instanceof Error ? error.message : "Nebius counter-offer failed.",
    });
  }
});

app.post("/api/simulate/stream", async (request, response) => {
  const prompt = buildPromptFromBody(request.body);
  if (!prompt) {
    response.status(400).json({ ok: false, error: "Business prompt is required." });
    return;
  }
  const practiceContext = normalizePracticeContext(request.body);

  response.writeHead(200, {
    "Content-Type": "application/x-ndjson; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
  });

  const cacheKey = getCacheKey(prompt, practiceContext);
  const cachedReport = getCachedReport(cacheKey);
  if (cachedReport) {
    sendStream(response, {
      type: "done",
      status: "Loaded saved report from SQLite.",
      cached: true,
      data: cachedReport,
    });
    response.end();
    return;
  }

  if (!process.env.NEBIUS_API_KEY) {
    sendStream(response, {
      type: "error",
      error: "Missing NEBIUS_API_KEY. Add it to ai-shark-tank/.env and restart the server.",
    });
    response.end();
    return;
  }

  try {
    const workflow = mastra.getWorkflow("pitchDuelWorkflow");
    const run = await workflow.createRun();
    const result = await run.start({
      inputData: { prompt, practiceContext, cacheKey },
      outputWriter: async (event) => {
        sendStream(response, event);
      },
    });

    if (result.status !== "success") {
      throw new Error(result.error?.message || "Mastra pitch duel workflow failed.");
    }

    response.end();
  } catch (error) {
    console.error(error);
    sendStream(response, {
      type: "error",
      error: error instanceof Error ? error.message : "Nebius duel simulation failed.",
    });
    response.end();
  }
});

app.post("/api/simulate", async (request, response) => {
  const prompt = buildPromptFromBody(request.body);
  if (!prompt) {
    response.status(400).json({ ok: false, error: "Business prompt is required." });
    return;
  }
  const practiceContext = normalizePracticeContext(request.body);

  const cacheKey = getCacheKey(prompt, practiceContext);
  const cachedReport = getCachedReport(cacheKey);
  if (cachedReport) {
    response.json({ ok: true, cached: true, data: cachedReport });
    return;
  }

  if (!process.env.NEBIUS_API_KEY) {
    response.status(500).json({
      ok: false,
      error: "Missing NEBIUS_API_KEY. Add it to ai-shark-tank/.env and restart the server.",
    });
    return;
  }

  try {
    const reportData = await runPitchDuelSimulation({
      prompt,
      practiceContext,
      cacheKey,
      emit: async () => {},
    });
    response.json({
      ok: true,
      cached: false,
      data: reportData,
    });
  } catch (error) {
    console.error(error);
    response.status(502).json({
      ok: false,
      error: error instanceof Error ? error.message : "Nebius duel simulation failed.",
    });
  }
});

if (fs.existsSync(distPath)) {
  app.use(express.static(distPath));
  app.get("*", (request, response, next) => {
    if (request.path.startsWith("/api")) {
      next();
      return;
    }

    response.sendFile(path.join(distPath, "index.html"));
  });
}

app.listen(port, () => {
  console.log(`AI Shark Tank listening on http://localhost:${port}`);
  console.log(`${modelConfig.nemotron.label}: ${modelConfig.nemotron.model}`);
  console.log(`${modelConfig.deepseek.label}: ${modelConfig.deepseek.model}`);
  console.log(`${modelConfig.judge.label}: ${modelConfig.judge.model}`);
});
