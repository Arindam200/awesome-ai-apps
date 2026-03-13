import type { AgentCredential } from "../loop/credentials.js";

export function buildCredentialFromRegisterResult(
  result: unknown,
  apiBase: string,
  fallbackName: string
): Omit<AgentCredential, "updated_at"> | null {
  const obj = (result && typeof result === "object" ? result : null) as Record<string, unknown> | null;
  if (!obj) {
    return null;
  }
  const agent = (obj.agent && typeof obj.agent === "object" ? obj.agent : null) as Record<string, unknown> | null;
  if (!agent) {
    return null;
  }
  const agentID = typeof agent.agent_id === "string" ? agent.agent_id : "";
  const apiKey = typeof agent.api_key === "string" ? agent.api_key : "";
  const agentName = typeof agent.name === "string" && agent.name.trim() ? agent.name : fallbackName;
  if (!agentID || !apiKey || !agentName) {
    return null;
  }
  return {
    api_base: apiBase,
    agent_name: agentName,
    agent_id: agentID,
    api_key: apiKey
  };
}
