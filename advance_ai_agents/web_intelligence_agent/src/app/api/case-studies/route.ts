import { NextResponse } from "next/server";
import { listCaseStudyDocs, listRuns } from "@/lib/db";

export const runtime = "nodejs";

export function GET() {
  const docs = listCaseStudyDocs();
  return NextResponse.json({ docs, runs: listRuns(24) });
}
