import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import type { CallLog } from "@/lib/inkling/client";
import type { CircuitRead } from "@/lib/schema/circuit";
import type { CheckedIssue, Finding } from "@/lib/sim/checks";
import type { Mismatch } from "@/lib/sim/agreement";

// Runs are plain folders: run.json, the sketch, each round's HTML and screenshots.
export const DATA_DIR = path.resolve(/*turbopackIgnore: true*/ process.env.INKWIRE_DATA_DIR || path.join(process.cwd(), "data"));
const RUNS = path.join(DATA_DIR, "runs");

export type Status = "reading" | "checking" | "building" | "looking" | "done" | "failed";

export type ShotRecord = { label: string; file: string; errors: string[]; mismatches: Mismatch[] };
export type Round = { n: number; file: string; shots: ShotRecord[]; review?: { ok: boolean; problems: string[] } };

export type Source = { name: string; url?: string; licence?: string; author?: string };

export type Run = {
  id: string;
  createdAt: string;
  status: Status;
  // Which model and provider the run used, for the header and the run log.
  model?: string;
  provider?: string;
  progress: { stage: string; chars: number; thought?: number };
  sketch: { file: string; width: number; height: number; hash: string; source?: Source };
  read?: CircuitRead;
  via?: "tool" | "text";
  repaired?: boolean;
  check?: { issues: CheckedIssue[]; solverOnly: Finding[] };
  rounds: Round[];
  result?: { round: number; agrees: boolean; looksRight: boolean | null };
  calls: CallLog[];
  error?: string;
};

export function runDir(id: string) {
  if (!/^[a-z0-9-]+$/.test(id)) throw new Error("bad run id");
  return path.join(RUNS, id);
}

export function newId() {
  return `${new Date().toISOString().slice(0, 10)}-${crypto.randomBytes(4).toString("hex")}`;
}

export async function saveRun(run: Run) {
  const dir = runDir(run.id);
  await fs.mkdir(dir, { recursive: true });
  const tmp = path.join(dir, `run.json.${process.pid}.tmp`);
  await fs.writeFile(tmp, JSON.stringify(run, null, 2));
  await fs.rename(tmp, path.join(dir, "run.json"));
}

export async function loadRun(id: string): Promise<Run | null> {
  try {
    return JSON.parse(await fs.readFile(path.join(runDir(id), "run.json"), "utf8")) as Run;
  } catch {
    return null;
  }
}

export async function listRuns(): Promise<Run[]> {
  let ids: string[] = [];
  try {
    ids = await fs.readdir(RUNS);
  } catch {
    return [];
  }
  const runs = await Promise.all(ids.map(loadRun));
  return runs.filter((r): r is Run => r !== null).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function writeFile(id: string, name: string, data: Buffer | string) {
  await fs.writeFile(path.join(runDir(id), name), data);
}

export async function readRunFile(id: string, name: string): Promise<Buffer> {
  if (!/^[a-z0-9._-]+$/i.test(name) || name.startsWith(".")) throw new Error("bad file name");
  return fs.readFile(path.join(runDir(id), name));
}
