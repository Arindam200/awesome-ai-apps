import { NextResponse } from "next/server";
import { restoreCaseStudyDoc } from "@/lib/db";

export const runtime = "nodejs";

export async function POST(request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const body = (await request.json().catch(() => ({}))) as {
    lastEditor?: string;
  };

  const doc = restoreCaseStudyDoc(runId, body.lastEditor?.trim() || "Signals reviewer");
  if (!doc) {
    return NextResponse.json({ error: "Case study run not found" }, { status: 404 });
  }

  return NextResponse.json({ doc });
}
