import { NextResponse } from "next/server";
import { loadRun } from "@/lib/runs";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const run = /^[a-z0-9-]+$/.test(id) ? await loadRun(id) : null;
  if (!run) return NextResponse.json({ error: "Not found." }, { status: 404 });
  return NextResponse.json(run, { headers: { "Cache-Control": "no-store" } });
}
