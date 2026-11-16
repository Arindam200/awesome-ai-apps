import { NextResponse } from "next/server";
import { exampleImage, listExamples } from "@/lib/examples";
import { startRun } from "@/lib/pipeline";
import { listRuns, loadRun, readRunFile } from "@/lib/runs";

export const runtime = "nodejs";

const MAX_BYTES = 15 * 1024 * 1024;

export async function GET() {
  return NextResponse.json(await listRuns());
}

export async function POST(req: Request) {
  try {
    const type = req.headers.get("content-type") ?? "";
    if (type.includes("application/json")) {
      const { example, again } = (await req.json()) as { example?: string; again?: string };
      if (again) {
        // Run the same sketch again, from the original example image when there is one.
        const prev = /^[a-z0-9-]+$/.test(again) ? await loadRun(again) : null;
        if (!prev) return NextResponse.json({ error: "Unknown run." }, { status: 404 });
        const match = (await listExamples()).find((e) => e.name === prev.sketch.source?.name);
        const image = match ? await exampleImage(match.file) : await readRunFile(prev.id, prev.sketch.file);
        return NextResponse.json({ id: await startRun(image, prev.sketch.source) });
      }
      const ex = (await listExamples()).find((e) => e.id === example);
      if (!ex) return NextResponse.json({ error: "Unknown example." }, { status: 404 });
      const { id: _id, file, ...source } = ex;
      return NextResponse.json({ id: await startRun(await exampleImage(file), source) });
    }
    const form = await req.formData();
    const file = form.get("image");
    if (!(file instanceof File)) return NextResponse.json({ error: "Attach an image." }, { status: 400 });
    if (file.size > MAX_BYTES) return NextResponse.json({ error: "Images up to 15 MB." }, { status: 413 });
    const name = String(form.get("name") || file.name || "Uploaded sketch").slice(0, 120);
    return NextResponse.json({ id: await startRun(Buffer.from(await file.arrayBuffer()), { name }) });
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 400 });
  }
}
