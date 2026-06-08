import { NextResponse } from "next/server";
import { getVeltSyncStatus } from "@/lib/activity";

export async function GET() {
  const status = getVeltSyncStatus();
  return NextResponse.json({
    velt_sync: status,
    hints: [
      "Prefer VELT_API_KEY (server key) over NEXT_PUBLIC_VELT_API_KEY for backend ingestion.",
      "Velt REST v2 ingestion requires x-velt-auth-token and organizationId; set VELT_AUTH_TOKEN and VELT_ORGANIZATION_ID.",
      "If your workspace uses a custom activity endpoint/schema, set VELT_ACTIVITY_API_URL accordingly.",
      "In local dev, counters are in-memory and can reset after hot reload/server restart.",
    ],
  });
}
