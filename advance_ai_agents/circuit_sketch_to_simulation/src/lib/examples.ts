import fs from "node:fs/promises";
import path from "node:path";
import type { Source } from "@/lib/runs";

// Real hand-drawn circuits from the web, each with its source and licence.
const DIR = path.join(process.cwd(), "fixtures", "sketches");

export type Example = Source & { id: string; file: string };

export async function listExamples(): Promise<Example[]> {
  try {
    return JSON.parse(await fs.readFile(path.join(DIR, "index.json"), "utf8")) as Example[];
  } catch {
    return [];
  }
}

export async function exampleImage(file: string): Promise<Buffer> {
  if (!/^[a-z0-9._-]+$/i.test(file) || file.startsWith(".")) throw new Error("bad file name");
  return fs.readFile(path.join(DIR, file));
}
