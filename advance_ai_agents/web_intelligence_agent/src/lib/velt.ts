import { envValue } from "./env";

export type VeltUserInput = {
  userId: string;
  organizationId: string;
  email?: string;
  name?: string;
};

function veltApiUrl(path: string) {
  const base = envValue("VELT_API_BASE_URL") || "https://api.velt.dev/v2";
  return `${base.replace(/\/$/, "")}${path}`;
}

function mask(value: string) {
  if (!value) return "";
  if (value.length <= 8) return `${value.slice(0, 2)}...`;
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

export function veltDocumentIdForRun(runId: string) {
  return `signals-case-study:${runId}`;
}

export function veltServerConfig() {
  const apiKey = envValue("VELT_API_KEY", "NEXT_PUBLIC_VELT_API_KEY", "NEXT_PUBLIC_VELT_CLIENT_ID");
  const authToken = envValue("VELT_AUTH_TOKEN");
  const organizationId = envValue("VELT_ORGANIZATION_ID", "NEXT_PUBLIC_VELT_ORG_ID", "NEXT_PUBLIC_VELT_ORGANIZATION_ID");

  return {
    apiKey,
    authToken,
    organizationId,
    configured: Boolean(apiKey && authToken && organizationId)
  };
}

export function veltOrgDiagnostics() {
  const ids = {
    VELT_ORGANIZATION_ID: envValue("VELT_ORGANIZATION_ID"),
    NEXT_PUBLIC_VELT_ORG_ID: envValue("NEXT_PUBLIC_VELT_ORG_ID"),
    NEXT_PUBLIC_VELT_ORGANIZATION_ID: envValue("NEXT_PUBLIC_VELT_ORGANIZATION_ID")
  };
  const present = Object.values(ids).filter(Boolean);
  const unique = Array.from(new Set(present));
  const organizationId = veltServerConfig().organizationId;

  return {
    organizationId,
    maskedOrganizationId: mask(organizationId),
    mismatch: unique.length > 1,
    configuredKeys: Object.fromEntries(Object.entries(ids).map(([key, value]) => [key, Boolean(value)])),
    maskedValues: Object.fromEntries(Object.entries(ids).map(([key, value]) => [key, value ? mask(value) : "missing"]))
  };
}

export async function createVeltUserToken(user: VeltUserInput): Promise<string> {
  const config = veltServerConfig();
  if (!config.configured) {
    throw new Error("Velt server auth is not configured.");
  }

  const response = await fetch(veltApiUrl("/auth/token/get"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-velt-api-key": config.apiKey,
      "x-velt-auth-token": config.authToken
    },
    body: JSON.stringify({
      data: {
        userId: user.userId,
        apiKey: config.apiKey,
        authToken: config.authToken,
        userProperties: {
          isAdmin: false,
          organizationId: user.organizationId,
          email: user.email,
          name: user.name
        }
      }
    })
  });

  const json = (await response.json().catch(() => null)) as { result?: { data?: { token?: string } }; error?: { message?: string } } | null;
  const token = json?.result?.data?.token;
  if (!response.ok || !token) {
    throw new Error(json?.error?.message ?? `Velt token request failed with ${response.status}.`);
  }

  return token;
}

export async function checkVeltRestAuth(): Promise<{ ok: boolean; message: string }> {
  const config = veltServerConfig();
  if (!config.configured) {
    return { ok: false, message: "Velt REST auth env is incomplete." };
  }

  try {
    await createVeltUserToken({
      userId: "signals_setup_check",
      organizationId: config.organizationId,
      email: "signals.setup@signals.local",
      name: "Signals setup check"
    });
    return { ok: true, message: "Velt REST auth accepted." };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Velt REST auth check failed."
    };
  }
}

export async function getVeltActivitiesForRun(runId: string): Promise<{
  ok: boolean;
  status: number;
  message: string;
  documentId: string;
  organizationId: string;
  count: number;
  activities: unknown[];
}> {
  const config = veltServerConfig();
  const documentId = veltDocumentIdForRun(runId);
  if (!config.configured) {
    return {
      ok: false,
      status: 503,
      message: "Velt REST auth env is incomplete.",
      documentId,
      organizationId: config.organizationId,
      count: 0,
      activities: []
    };
  }

  try {
    const response = await fetch(veltApiUrl("/activities/get"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-velt-api-key": config.apiKey,
        "x-velt-auth-token": config.authToken
      },
      body: JSON.stringify({
        data: {
          organizationId: config.organizationId,
          documentId,
          pageSize: 100,
          order: "desc"
        }
      })
    });
    const json = (await response.json().catch(() => null)) as {
      data?: unknown[] | { activities?: unknown[] };
      result?: { data?: unknown[] | { activities?: unknown[] } };
      error?: { message?: string };
    } | null;
    const payload = json?.result?.data ?? json?.data;
    const activities = Array.isArray(payload) ? payload : Array.isArray(payload?.activities) ? payload.activities : [];

    return {
      ok: response.ok,
      status: response.status,
      message: response.ok ? `Velt returned ${activities.length} activities.` : json?.error?.message ?? `Velt activities get failed with ${response.status}.`,
      documentId,
      organizationId: config.organizationId,
      count: activities.length,
      activities
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      message: error instanceof Error ? error.message : "Velt activities get failed.",
      documentId,
      organizationId: config.organizationId,
      count: 0,
      activities: []
    };
  }
}
