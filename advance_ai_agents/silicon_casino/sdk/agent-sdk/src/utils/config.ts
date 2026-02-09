export const DEFAULT_API_BASE = "http://localhost:8080/api";

export function normalizeApiBase(raw: string): string {
  const trimmed = raw.trim().replace(/\/+$/, "");
  if (trimmed.endsWith("/api")) {
    return trimmed;
  }
  return `${trimmed}/api`;
}

export function resolveApiBase(override?: string): string {
  return normalizeApiBase(override || process.env.API_BASE || DEFAULT_API_BASE);
}

export function requireArg(name: string, value?: string): string {
  if (value && value.trim() !== "") {
    return value;
  }
  throw new Error(`missing required argument: ${name}`);
}
