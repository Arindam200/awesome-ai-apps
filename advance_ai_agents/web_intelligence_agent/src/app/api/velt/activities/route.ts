import { NextResponse } from "next/server";
import { getVeltActivitiesForRun, veltOrgDiagnostics } from "@/lib/velt";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const runId = searchParams.get("runId")?.trim();
  if (!runId) {
    return NextResponse.json({ error: "runId is required." }, { status: 400 });
  }

  const result = await getVeltActivitiesForRun(runId);
  return NextResponse.json({
    ...result,
    orgDiagnostics: veltOrgDiagnostics()
  });
}
