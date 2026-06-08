export type ActivityType =
  | "chat_message"
  | "ai_response"
  | "workflow_triggered"
  | "workflow_step"
  | "workflow_completed"
  | "workflow_failed"
  | "system_event"
  | "secure_access";

export interface ActivityRecord {
  id: string;
  type: ActivityType;
  actor: { name: string; kind: "human" | "ai" | "system" };
  action: string;
  detail: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

interface VeltSyncStatus {
  configured: boolean;
  okCount: number;
  failCount: number;
  lastOkAt: string | null;
  lastErrorAt: string | null;
  lastError: string | null;
  lastUrl: string | null;
  usingPublicKeyFallback: boolean;
}

type ActivityStore = {
  activities: ActivityRecord[];
  veltSyncStatus: VeltSyncStatus;
};

const defaultStore: ActivityStore = {
  activities: [],
  veltSyncStatus: {
  configured: false,
  okCount: 0,
  failCount: 0,
  lastOkAt: null,
  lastErrorAt: null,
  lastError: null,
  lastUrl: null,
  usingPublicKeyFallback: false,
  },
};

function getStore(): ActivityStore {
  const g = globalThis as typeof globalThis & { __flowsentinelActivityStore?: ActivityStore };
  if (!g.__flowsentinelActivityStore) {
    g.__flowsentinelActivityStore = defaultStore;
  }
  return g.__flowsentinelActivityStore;
}

interface VeltPushResult {
  ok: boolean;
  url: string | null;
  error: string | null;
}

const VELT_API_KEY =
  process.env.VELT_API_KEY?.trim() || process.env.NEXT_PUBLIC_VELT_API_KEY?.trim() || "";
const VELT_AUTH_TOKEN = process.env.VELT_AUTH_TOKEN?.trim() || "";
const VELT_ORGANIZATION_ID = process.env.VELT_ORGANIZATION_ID?.trim() || "";
const VELT_DOCUMENT_ID = process.env.VELT_DOCUMENT_ID?.trim() || "flowsentinel-dashboard";
const USING_PUBLIC_KEY_FALLBACK =
  !process.env.VELT_API_KEY?.trim() && !!process.env.NEXT_PUBLIC_VELT_API_KEY?.trim();

const VELT_ACTIVITY_URLS = [
  process.env.VELT_ACTIVITY_API_URL?.trim(),
  "https://api.velt.dev/v2/activities/add",
].filter(Boolean) as string[];

async function pushActivityToVelt(record: ActivityRecord): Promise<VeltPushResult> {
  const store = getStore();
  store.veltSyncStatus.configured = !!VELT_API_KEY && VELT_ACTIVITY_URLS.length > 0;
  store.veltSyncStatus.usingPublicKeyFallback = USING_PUBLIC_KEY_FALLBACK;
  if (!VELT_API_KEY || VELT_ACTIVITY_URLS.length === 0 || !VELT_ORGANIZATION_ID || !VELT_AUTH_TOKEN) {
    const missing: string[] = [];
    if (!VELT_API_KEY) missing.push("VELT_API_KEY");
    if (!VELT_AUTH_TOKEN) missing.push("VELT_AUTH_TOKEN");
    if (!VELT_ORGANIZATION_ID) missing.push("VELT_ORGANIZATION_ID");
    if (VELT_ACTIVITY_URLS.length === 0) missing.push("VELT_ACTIVITY_API_URL");
    return {
      ok: false,
      url: null,
      error: `Missing required Velt config: ${missing.join(", ")}`,
    };
  }

  // Velt REST v2 expects { data: { organizationId, documentId, activities: [...] } }.
  const payload = {
    data: {
      organizationId: VELT_ORGANIZATION_ID,
      documentId: VELT_DOCUMENT_ID,
      activities: [
        {
          id: record.id,
          featureType: "custom",
          actionType: record.type,
          targetEntityId: VELT_DOCUMENT_ID,
          displayMessageTemplate: record.detail,
          actionUser: {
            userId: record.actor.name.toLowerCase().replace(/\s+/g, "_"),
            name: record.actor.name,
            email: `${record.actor.name.toLowerCase().replace(/\s+/g, ".")}@flowsentinel.local`,
          },
          metadata: {
            ...(record.metadata ?? {}),
            source: "flowsentinel",
            actorKind: record.actor.kind,
            action: record.action,
            localRecordId: record.id,
            localTimestamp: record.timestamp,
          },
        },
      ],
    },
  };

  let firstError: string | null = null;
  let firstErrorUrl: string | null = null;

  for (const url of VELT_ACTIVITY_URLS) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-velt-api-key": VELT_API_KEY,
          "x-velt-auth-token": VELT_AUTH_TOKEN,
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        store.veltSyncStatus.okCount += 1;
        store.veltSyncStatus.lastOkAt = new Date().toISOString();
        store.veltSyncStatus.lastUrl = url;
        store.veltSyncStatus.lastError = null;
        return {
          ok: true,
          url,
          error: null,
        };
      }
      const text = await res.text();
      store.veltSyncStatus.failCount += 1;
      if (!firstError) {
        firstError = `HTTP ${res.status}: ${text.slice(0, 240)}`;
        firstErrorUrl = url;
      }
    } catch {
      store.veltSyncStatus.failCount += 1;
      if (!firstError) {
        firstError = "Network error while calling Velt activity endpoint";
        firstErrorUrl = url;
      }
      // Try fallback URL.
    }
  }

  store.veltSyncStatus.lastErrorAt = new Date().toISOString();
  store.veltSyncStatus.lastUrl = firstErrorUrl;
  store.veltSyncStatus.lastError = firstError;
  return {
    ok: false,
    url: firstErrorUrl,
    error: firstError,
  };
}

export function createActivity(
  type: ActivityType,
  actor: ActivityRecord["actor"],
  action: string,
  detail: string,
  metadata?: Record<string, unknown>
): ActivityRecord {
  const store = getStore();
  const record: ActivityRecord = {
    id: `act_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    type,
    actor,
    action,
    detail,
    timestamp: new Date().toISOString(),
    metadata,
  };

  store.activities.unshift(record);
  if (store.activities.length > 200) store.activities = store.activities.slice(0, 200);
  void pushActivityToVelt(record);

  return record;
}

export async function createActivityAndWaitForVelt(
  type: ActivityType,
  actor: ActivityRecord["actor"],
  action: string,
  detail: string,
  metadata?: Record<string, unknown>
): Promise<{ activity: ActivityRecord; velt: VeltPushResult }> {
  const store = getStore();
  const activity: ActivityRecord = {
    id: `act_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    type,
    actor,
    action,
    detail,
    timestamp: new Date().toISOString(),
    metadata,
  };
  store.activities.unshift(activity);
  if (store.activities.length > 200) store.activities = store.activities.slice(0, 200);
  const velt = await pushActivityToVelt(activity);
  return { activity, velt };
}

export function getActivities(limit = 50): ActivityRecord[] {
  return getStore().activities.slice(0, limit);
}

export function getActivitiesByType(type: ActivityType, limit = 50): ActivityRecord[] {
  return getStore().activities.filter((a) => a.type === type).slice(0, limit);
}

export function getActivityStats() {
  const activities = getStore().activities;
  const total = activities.length;
  const byType: Record<string, number> = {};
  const byActor: Record<string, number> = {};

  for (const a of activities) {
    byType[a.type] = (byType[a.type] ?? 0) + 1;
    byActor[a.actor.kind] = (byActor[a.actor.kind] ?? 0) + 1;
  }

  return { total, byType, byActor };
}

export function getVeltSyncStatus() {
  const store = getStore();
  const hasServerKey = !!process.env.VELT_API_KEY?.trim();
  const hasPublicKey = !!process.env.NEXT_PUBLIC_VELT_API_KEY?.trim();
  const hasAuthToken = !!process.env.VELT_AUTH_TOKEN?.trim();
  const hasOrganizationId = !!process.env.VELT_ORGANIZATION_ID?.trim();
  const hasAnyKey = hasServerKey || hasPublicKey;
  const hasEndpoint = VELT_ACTIVITY_URLS.length > 0;

  return {
    ...store.veltSyncStatus,
    configured: hasAnyKey && hasEndpoint && hasAuthToken && hasOrganizationId,
    usingPublicKeyFallback: !hasServerKey && hasPublicKey,
    env: {
      hasServerKey,
      hasPublicKey,
      hasAuthToken,
      hasOrganizationId,
      hasEndpoint,
      organizationId: VELT_ORGANIZATION_ID || null,
      documentId: VELT_DOCUMENT_ID || null,
    },
  };
}
