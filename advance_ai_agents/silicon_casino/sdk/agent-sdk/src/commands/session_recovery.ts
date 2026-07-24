import type { APAClientError } from "../http/client.js";

export type ResumableSession = {
  session_id: string;
  stream_url: string;
};

export function resolveStreamURL(apiBase: string, streamURL: string): string {
  const base = apiBase.replace(/\/api\/?$/, "");
  return streamURL.startsWith("http") ? streamURL : `${base}${streamURL}`;
}

export function recoverSessionFromConflict(err: unknown, apiBase: string): ResumableSession | null {
  const httpErr = err as APAClientError | null;
  if (!httpErr || httpErr.status !== 409 || httpErr.code !== "agent_already_in_session") {
    return null;
  }
  const body = (httpErr.body && typeof httpErr.body === "object"
    ? httpErr.body
    : null) as Record<string, unknown> | null;
  if (!body) {
    return null;
  }
  const sessionID = typeof body.session_id === "string" ? body.session_id : "";
  const streamURLRaw = typeof body.stream_url === "string" ? body.stream_url : "";
  if (!sessionID || !streamURLRaw) {
    return null;
  }
  return {
    session_id: sessionID,
    stream_url: resolveStreamURL(apiBase, streamURLRaw)
  };
}
