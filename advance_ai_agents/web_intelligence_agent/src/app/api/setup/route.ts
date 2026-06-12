import { NextResponse } from "next/server";
import { getSetupStatus } from "@/lib/env";
import { registeredAgentSummaries, webSignalWorkflow } from "@/lib/mastra";
import { nebiusModelId } from "@/lib/nebius";
import { checkVeltRestAuth, veltOrgDiagnostics } from "@/lib/velt";

export const runtime = "nodejs";

export async function GET() {
  const setup = getSetupStatus();
  const veltRestHealth = setup.configured.VELT_REST_ACTIVITY_INGEST
    ? await checkVeltRestAuth()
    : { ok: false, message: "Velt REST auth env is incomplete." };

  return NextResponse.json({
    ...setup,
    runtime: {
      mastraAgentActive: registeredAgentSummaries.length > 0,
      mastraWorkflow: webSignalWorkflow.id,
      registeredAgents: registeredAgentSummaries,
      registeredTools: ["olostepSearchTool", "olostepScrapeTool", "olostepAnswersTool", "olostepMapTool", "olostepCrawlTool"],
      model: nebiusModelId(),
      sqlite: true,
      veltAuditConfigured: Boolean(setup.configured.VELT_REST_ACTIVITY_INGEST),
      veltRestAuthOk: veltRestHealth.ok,
      veltRestAuthMessage: veltRestHealth.message,
      veltOrgDiagnostics: veltOrgDiagnostics()
    }
  });
}
