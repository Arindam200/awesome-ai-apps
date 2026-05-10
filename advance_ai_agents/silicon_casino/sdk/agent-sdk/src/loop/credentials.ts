import { promises as fs } from "node:fs";
import path from "node:path";

export type AgentCredential = {
  api_base: string;
  agent_name: string;
  agent_id: string;
  api_key: string;
  updated_at: string;
};

type CredentialStore = {
  version: number;
  credential?: AgentCredential;
};

const STORE_VERSION = 2;

export function defaultCredentialPath(): string {
  return path.join(process.cwd(), "credentials.json");
}

export async function loadCredential(
  apiBase: string,
  _agentName: string | undefined,
  filePath: string = defaultCredentialPath()
): Promise<AgentCredential | null> {
  const store = await readStore(filePath);
  if (!store.credential) {
    return null;
  }
  if (store.credential.api_base !== apiBase) {
    return null;
  }
  return store.credential;
}

export async function saveCredential(
  record: Omit<AgentCredential, "updated_at">,
  filePath: string = defaultCredentialPath()
): Promise<void> {
  const store = await readStore(filePath);
  store.credential = {
    ...record,
    updated_at: new Date().toISOString()
  };
  await writeStore(store, filePath);
}

async function readStore(filePath: string): Promise<CredentialStore> {
  let raw = "";
  try {
    raw = await fs.readFile(filePath, "utf8");
  } catch (err) {
    if (isENOENT(err)) {
      return { version: STORE_VERSION };
    }
    throw err;
  }
  if (!raw.trim()) {
    return { version: STORE_VERSION };
  }
  let parsed: CredentialStore | undefined;
  try {
    parsed = JSON.parse(raw) as CredentialStore;
  } catch {
    return { version: STORE_VERSION };
  }
  if (!parsed || typeof parsed !== "object") {
    return { version: STORE_VERSION };
  }
  if (parsed.credential && typeof parsed.credential === "object") {
    return { version: STORE_VERSION, credential: parsed.credential };
  }
  return { version: STORE_VERSION };
}

async function writeStore(store: CredentialStore, filePath: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(store, null, 2)}\n`, { mode: 0o600 });
}

function isENOENT(err: unknown): err is NodeJS.ErrnoException {
  return Boolean(err && typeof err === "object" && (err as NodeJS.ErrnoException).code === "ENOENT");
}
