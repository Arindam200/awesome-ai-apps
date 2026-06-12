import { NextResponse } from "next/server";
import { listRuns } from "@/lib/db";
import { startWebSignalWorkflow } from "@/lib/workflow";

export const runtime = "nodejs";

export function GET() {
  return NextResponse.json({ runs: listRuns() });
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    request?: string;
    optionalUrl?: string;
  };

  try {
    const result = startWebSignalWorkflow({
      request: body.request ?? "",
      optionalUrl: body.optionalUrl ?? ""
    });
    return NextResponse.json({ run: result }, { status: 202 });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not start workflow." },
      { status: 400 }
    );
  }
}
