import { NextResponse } from "next/server";
import { archiveCaseStudyDoc, getCaseStudyDoc, getOrCreateCaseStudyDoc, saveCaseStudyDoc } from "@/lib/db";

export const runtime = "nodejs";

export async function GET(_request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const archived = getCaseStudyDoc(runId, { includeDeleted: true });
  if (archived?.deletedAt) {
    return NextResponse.json({ doc: null, deleted: true, deletedAt: archived.deletedAt });
  }

  const doc = getOrCreateCaseStudyDoc(runId);
  if (!doc) {
    return NextResponse.json({ error: "Case study run not found" }, { status: 404 });
  }

  return NextResponse.json({ doc });
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const doc = archiveCaseStudyDoc(runId);
  if (!doc) {
    return NextResponse.json({ error: "Case study document not found" }, { status: 404 });
  }

  return NextResponse.json({ doc, deleted: true });
}

export async function PATCH(request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const body = (await request.json().catch(() => ({}))) as {
    markdown?: string;
    title?: string;
    lastEditor?: string;
  };

  if (!body.markdown?.trim()) {
    return NextResponse.json({ error: "Case study markdown is required." }, { status: 400 });
  }

  const doc = saveCaseStudyDoc({
    runId,
    markdown: body.markdown,
    title: body.title,
    lastEditor: body.lastEditor?.trim() || "Signals reviewer"
  });

  if (!doc) {
    return NextResponse.json({ error: "Case study run not found" }, { status: 404 });
  }

  return NextResponse.json({ doc });
}
