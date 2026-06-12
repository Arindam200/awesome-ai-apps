import { envValue } from "./env";
import type { ActorType } from "./types";
import { veltDocumentIdForRun } from "./velt";

export type ActivityLogResult = {
  ok: boolean;
  status: number;
  message: string;
  documentId: string;
};

export async function logActivity(input: {
  workflowId: string;
  runId: string;
  actorType: ActorType;
  actorName: string;
  actionType: string;
  message: string;
  metadata?: Record<string, unknown>;
}): Promise<ActivityLogResult> {
  return pushActivityToVelt({
    ...input,
    id: `activity_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`,
    createdAt: new Date().toISOString(),
    metadata: input.metadata ?? {}
  });
}

async function pushActivityToVelt(event: {
  id: string;
  workflowId: string;
  runId: string;
  actorType: ActorType;
  actorName: string;
  actionType: string;
  message: string;
  metadata: Record<string, unknown>;
  createdAt: string;
}): Promise<ActivityLogResult> {
  const apiKey = envValue("VELT_API_KEY");
  const authToken = envValue("VELT_AUTH_TOKEN");
  const organizationId = envValue("VELT_ORGANIZATION_ID", "NEXT_PUBLIC_VELT_ORG_ID", "NEXT_PUBLIC_VELT_ORGANIZATION_ID");
  const documentId = veltDocumentIdForRun(event.runId);
  const url = envValue("VELT_ACTIVITY_API_URL") || "https://api.velt.dev/v2/activities/add";

  if (!apiKey || !authToken || !organizationId) {
    return {
      ok: false,
      status: 503,
      message: "Velt activity REST env is incomplete.",
      documentId
    };
  }

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-velt-api-key": apiKey,
        "x-velt-auth-token": authToken
      },
      body: JSON.stringify({
        data: {
          organizationId,
          documentId,
          activities: [
            {
              id: event.id,
              featureType: "custom",
              actionType: event.actionType,
              targetEntityId: event.runId,
              displayMessageTemplate: "{{actionUser.name}} {{message}}",
              displayMessageTemplateData: {
                message: event.message,
                actorType: event.actorType,
                workflowId: event.workflowId,
                runId: event.runId,
                ...event.metadata
              },
              actionUser: {
                userId: event.actorName.toLowerCase().replace(/\W+/g, "_"),
                name: event.actorName,
                email: `${event.actorName.toLowerCase().replace(/\W+/g, ".")}@signals.local`
              },
              metadata: {
                ...event.metadata,
                source: "signals",
                actorType: event.actorType,
                workflowId: event.workflowId,
                runId: event.runId,
                veltDocumentId: documentId,
                localTimestamp: event.createdAt
              }
            }
          ]
        }
      })
    });
    if (!response.ok) {
      const text = await response.text();
      const message = `Velt activity ingest failed (${response.status}): ${text.slice(0, 240)}`;
      console.warn(message);
      return {
        ok: false,
        status: response.status,
        message,
        documentId
      };
    }
    return {
      ok: true,
      status: response.status,
      message: "Velt activity ingested.",
      documentId
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      message: error instanceof Error ? error.message : "Velt activity ingest failed.",
      documentId
    };
  }
}
