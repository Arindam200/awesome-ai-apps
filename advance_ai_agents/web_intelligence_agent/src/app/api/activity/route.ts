import { NextResponse } from "next/server";
import { logActivity } from "@/lib/activity";
import { getRun } from "@/lib/db";
import type { ActorType } from "@/lib/types";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    runId?: string;
    workflowId?: string;
    actorType?: ActorType;
    actorName?: string;
    actionType?: string;
    message?: string;
    metadata?: Record<string, unknown>;
  };

  const run = body.runId ? getRun(body.runId) : null;
  const workflowId = body.workflowId || run?.workflowId;
  if (!body.runId || !workflowId || !body.actionType || !body.message) {
    return NextResponse.json({ error: "runId, workflowId, actionType, and message are required." }, { status: 400 });
  }

  const result = await logActivity({
    workflowId,
    runId: body.runId,
    actorType: body.actorType ?? "user",
    actorName: body.actorName?.trim() || "Signals reviewer",
    actionType: body.actionType,
    message: body.message,
    metadata: body.metadata ?? {}
  });

  return NextResponse.json(result);
}
