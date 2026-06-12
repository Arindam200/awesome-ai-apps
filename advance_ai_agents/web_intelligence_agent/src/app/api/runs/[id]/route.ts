import { NextResponse } from "next/server";
import { getRun } from "@/lib/db";

export const runtime = "nodejs";

export function GET(_request: Request, { params }: { params: { id: string } }) {
  const run = getRun(params.id);
  if (!run) {
    return NextResponse.json({ error: "Run not found" }, { status: 404 });
  }
  return NextResponse.json({ run });
}
