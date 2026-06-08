import { NextRequest, NextResponse } from "next/server";
import { getActivities, getActivityStats, createActivity, type ActivityType } from "@/lib/activity";

export async function GET(req: NextRequest) {
  const limit = parseInt(req.nextUrl.searchParams.get("limit") ?? "50", 10);
  const type = req.nextUrl.searchParams.get("type") as ActivityType | null;

  const activities = type
    ? getActivities(limit).filter((a) => a.type === type)
    : getActivities(limit);

  const stats = getActivityStats();

  return NextResponse.json({ activities, stats });
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { type, actor, action, detail, metadata } = body;

    if (!type || !actor || !action || !detail) {
      return NextResponse.json(
        { error: "type, actor, action, and detail are required" },
        { status: 400 }
      );
    }

    const record = createActivity(type, actor, action, detail, metadata);
    return NextResponse.json({ activity: record });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
