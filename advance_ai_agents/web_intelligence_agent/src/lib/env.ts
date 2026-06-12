import type { SetupStatus } from "./types";

export function envValue(...names: string[]): string {
  for (const name of names) {
    const value = process.env[name]?.trim();
    if (value) return value;
  }
  return "";
}

export function getSetupStatus(): SetupStatus {
  const required = ["OLOSTEP_API_KEY", "NEBIUS_API_KEY"];
  const optional = [
    "OLOSTEP_API_BASE_URL",
    "NEBIUS_BASE_URL",
    "NEBIUS_MODEL",
    "NEXT_PUBLIC_VELT_CLIENT_ID",
    "NEXT_PUBLIC_VELT_ORG_ID",
    "NEXT_PUBLIC_VELT_API_KEY",
    "NEXT_PUBLIC_VELT_ORGANIZATION_ID",
    "NEXT_PUBLIC_VELT_DOCUMENT_ID",
    "VELT_API_KEY",
    "VELT_AUTH_TOKEN",
    "VELT_ORGANIZATION_ID",
    "VELT_DOCUMENT_ID"
  ];
  const configured: Record<string, boolean> = {};

  for (const key of [...required, ...optional]) {
    configured[key] = Boolean(process.env[key]?.trim());
  }

  configured.VELT_ACTIVITY_LOGS = Boolean(
    envValue("NEXT_PUBLIC_VELT_CLIENT_ID", "NEXT_PUBLIC_VELT_API_KEY") &&
      envValue("NEXT_PUBLIC_VELT_ORG_ID", "NEXT_PUBLIC_VELT_ORGANIZATION_ID", "VELT_ORGANIZATION_ID")
  );
  configured.VELT_REST_ACTIVITY_INGEST = Boolean(
    envValue("VELT_API_KEY") &&
      envValue("VELT_AUTH_TOKEN") &&
      envValue("VELT_ORGANIZATION_ID", "NEXT_PUBLIC_VELT_ORG_ID", "NEXT_PUBLIC_VELT_ORGANIZATION_ID")
  );

  return {
    configured,
    missing: required.filter((key) => !configured[key])
  };
}

export function requireEnv(name: string): string {
  const value = envValue(name);
  if (!value) {
    throw new Error(`${name} is missing. Add it to advance_ai_agents/web_intelligence_agent/.env and restart the app.`);
  }
  return value;
}

export function databaseFileName(): string {
  const databaseUrl = process.env.DATABASE_URL?.trim() || "file:./signalforge.db";
  return databaseUrl.startsWith("file:") ? databaseUrl.slice("file:".length) : databaseUrl;
}
