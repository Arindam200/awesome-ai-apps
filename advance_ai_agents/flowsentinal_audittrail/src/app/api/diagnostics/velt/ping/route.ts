import { NextResponse } from "next/server";
import { createActivityAndWaitForVelt, getVeltSyncStatus } from "@/lib/activity";

export async function POST() {
  const result = await createActivityAndWaitForVelt(
    "system_event",
    { name: "Diagnostics", kind: "system" },
    "Velt sync ping",
    "Manual diagnostic event to verify Velt ingestion",
    { diagnostic: true }
  );

  return NextResponse.json({
    ok: result.velt.ok,
    message: result.velt.ok
      ? "Diagnostic event sent to Velt successfully."
      : "Diagnostic event failed to sync to Velt.",
    velt_push: result.velt,
    velt_sync: getVeltSyncStatus(),
  });
}
