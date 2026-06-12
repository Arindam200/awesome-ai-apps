"use client";

import {
  VeltComments,
  VeltCommentsSidebar,
  VeltAutocomplete,
  VeltNotificationsTool,
  VeltPresence,
  VeltProvider,
  useVeltClient
} from "@veltdev/react";
import type { VeltAuthProvider } from "@veltdev/types";
import {
  FileDown,
  Edit3,
  Eye,
  FileText,
  Loader2,
  MessageSquareText,
  RotateCcw,
  Save,
  Trash2,
  Users,
  X
} from "lucide-react";
import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";
import { usePathname } from "next/navigation";
import { MarkdownArticle } from "@/components/MarkdownArticle";
import type { CaseStudyDocRecord, WorkflowRunRecord } from "@/lib/types";

const VELT_API_KEY =
  process.env.NEXT_PUBLIC_VELT_CLIENT_ID?.trim() || process.env.NEXT_PUBLIC_VELT_API_KEY?.trim() || "";
const VELT_ORG_ID =
  process.env.NEXT_PUBLIC_VELT_ORG_ID?.trim() || process.env.NEXT_PUBLIC_VELT_ORGANIZATION_ID?.trim() || "";

type LocalVeltUser = {
  userId: string;
  organizationId: string;
  name: string;
  email: string;
  color: string;
};

type LocalVeltContact = {
  userId: string;
  name: string;
  email: string;
  color: string;
  organizationId: string;
  groupId: string;
  visibility: "group";
  source: string;
  initial: string;
};

type VeltUserContextValue = {
  users: LocalVeltUser[];
  currentUser: LocalVeltUser | null;
  switchUser: (userId: string) => void;
};

const VeltUserContext = createContext<VeltUserContextValue>({
  users: [],
  currentUser: null,
  switchUser: () => {}
});

function hardcodedUsers(): LocalVeltUser[] {
  if (!VELT_ORG_ID) return [];
  return [
    {
      userId: "signals-analyst",
      organizationId: VELT_ORG_ID,
      name: "Analyst",
      email: "analyst@signals.local",
      color: "#1f7a68"
    },
    {
      userId: "signals-reviewer",
      organizationId: VELT_ORG_ID,
      name: "Reviewer",
      email: "reviewer@signals.local",
      color: "#3157d5"
    }
  ];
}

function initialUser(users: LocalVeltUser[]): LocalVeltUser | null {
  if (users.length === 0) return null;
  if (typeof window === "undefined") return users[0];
  const savedId = window.localStorage.getItem("signals_user_id");
  return users.find((user) => user.userId === savedId) ?? users[0];
}

function reviewerContacts(users: LocalVeltUser[]): LocalVeltContact[] {
  return users.map((user) => ({
    userId: user.userId,
    name: user.name,
    email: user.email,
    color: user.color,
    organizationId: user.organizationId,
    groupId: "signals-reviewers",
    visibility: "group",
    source: "signals-local-reviewers",
    initial: user.name.slice(0, 1).toUpperCase()
  }));
}

function reviewerAutocompleteItems(users: LocalVeltUser[]) {
  return users.map((user) => ({
    id: user.userId,
    name: user.name,
    description: user.email,
    groupId: "signals-reviewers"
  }));
}

function mentionTextIsAllowed(text: string, contacts: LocalVeltContact[]) {
  const normalized = text.toLowerCase();
  return contacts.some((contact) =>
    [contact.name, contact.email, contact.userId].some((value) => normalized.includes(value.toLowerCase()))
  );
}

async function logHumanActivity(input: {
  run: WorkflowRunRecord | null;
  actorName: string;
  actionType: string;
  message: string;
  metadata?: Record<string, unknown>;
}) {
  if (!input.run) return;
  await fetch("/api/activity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      runId: input.run.id,
      workflowId: input.run.workflowId,
      actorType: "user",
      actorName: input.actorName,
      actionType: input.actionType,
      message: input.message,
      metadata: input.metadata ?? {}
    })
  }).catch(() => undefined);
}

function extractTitle(markdown: string, fallback: string): string {
  return markdown.match(/^#\s+(.+)$/m)?.[1]?.trim() || fallback;
}

function VeltRunDocument({ run }: { run: WorkflowRunRecord | null }) {
  const { client } = useVeltClient();

  useEffect(() => {
    if (!client) return;

    const documentId = run?.id ? `signals-case-study:${run.id}` : "signals-board";
    const documentName = run?.workflowName || "Signals Board";
    client.setDocuments?.([
      {
        id: documentId,
        metadata: {
          documentName,
          runId: run?.id,
          workflowId: run?.workflowId,
          status: run?.status,
          source: "signals"
        }
      }
    ]);
  }, [client, run?.id, run?.workflowId, run?.workflowName, run?.status]);

  return null;
}

function VeltRuntimeConfigurator({ users }: { users: LocalVeltUser[] }) {
  const { client } = useVeltClient();

  useEffect(() => {
    if (!client || users.length === 0) return;
    const contactElement = client.getContactElement?.() as
      | {
          updateContactList?: (contacts: unknown[], config?: { merge: boolean }) => void;
          updateContactListScopeForOrganizationUsers?: (scope: unknown[]) => void;
          disablePaginatedContactList?: () => void;
          disableAtHere?: () => void;
        }
      | undefined;
    const commentElement = client.getCommentElement?.() as
      | {
          updateContactList?: (contacts: unknown[], config?: { merge: boolean }) => void;
          updateContactListScopeForOrganizationUsers?: (scope: unknown[]) => void;
          disablePaginatedContactList?: () => void;
          enableUserMentions?: () => void;
          disableAtHere?: () => void;
          customAutocompleteSearch?: (handler: (query: string) => Promise<unknown[]>) => void;
        }
      | undefined;
    const autocompleteElement = client.getAutocompleteElement?.() as
      | {
          create?: (data: unknown) => void;
        }
      | undefined;
    const rootClient = client as unknown as {
      updateContactList?: (contacts: unknown[], config?: { merge: boolean }) => void;
    };
    const contacts = reviewerContacts(users);
    const autocompleteItems = reviewerAutocompleteItems(users);

    const search = async (query: string) => {
      const needle = query.trim().toLowerCase();
      if (!needle) return contacts;
      return contacts.filter((contact) =>
        [contact.name, contact.email, contact.userId].some((value) => value.toLowerCase().includes(needle))
      );
    };

    const applyReviewerContacts = () => {
      rootClient.updateContactList?.(contacts, { merge: false });
      contactElement?.disablePaginatedContactList?.();
      contactElement?.updateContactListScopeForOrganizationUsers?.(["document"]);
      contactElement?.updateContactList?.(contacts, { merge: false });
      contactElement?.disableAtHere?.();
      commentElement?.disablePaginatedContactList?.();
      commentElement?.updateContactListScopeForOrganizationUsers?.(["document"]);
      commentElement?.updateContactList?.(contacts, { merge: false });
      commentElement?.enableUserMentions?.();
      commentElement?.disableAtHere?.();
      commentElement?.customAutocompleteSearch?.(search);
      autocompleteElement?.create?.({
        hotkey: "@",
        description: "Mention Analyst or Reviewer",
        type: "contact",
        data: autocompleteItems,
        groups: [{ id: "signals-reviewers", name: "Reviewers" }]
      });
    };

    applyReviewerContacts();
    const timers = [250, 1000, 2500].map((delay) => window.setTimeout(applyReviewerContacts, delay));

    const hideLeakedContacts = () => {
      const selectors = [
        "velt-autocomplete-option",
        "velt-contact-list-item",
        "[role='option']",
        "[class*='autocomplete'] [class*='option']",
        "[class*='Autocomplete'] [class*='Option']"
      ];
      document.querySelectorAll<HTMLElement>(selectors.join(",")).forEach((node) => {
        const text = node.innerText || node.textContent || "";
        if (!text.trim()) return;
        if (mentionTextIsAllowed(text, contacts)) {
          node.style.removeProperty("display");
          node.removeAttribute("aria-hidden");
          return;
        }
        if (/operator|signalforge|@|user_/i.test(text)) {
          node.style.setProperty("display", "none", "important");
          node.setAttribute("aria-hidden", "true");
        }
      });
    };

    const observer = new MutationObserver(hideLeakedContacts);
    observer.observe(document.body, { childList: true, subtree: true });
    hideLeakedContacts();

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
      observer.disconnect();
    };
  }, [client, users]);

  return createElement(VeltAutocomplete as unknown as (props: Record<string, unknown>) => ReactNode, {
    hotkey: "@",
    contacts: reviewerContacts(users),
    listData: reviewerAutocompleteItems(users),
    customGroups: [{ id: "signals-reviewers", name: "Reviewers" }],
    showMentionGroupsFirst: false
  });
}

type VeltActivityItem = {
  id: string;
  actionType: string;
  actorName: string;
  actorType: "user" | "agent" | "tool" | "unknown";
  category: "Human" | "Agent";
  message: string;
  stage?: string;
  operation?: string;
  toolName?: string;
  timestamp: number;
  lastTimestamp?: number;
  count?: number;
};

function readableAction(actionType: string) {
  return actionType
    .split("_")
    .filter(Boolean)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function inferredAuditFields(actionType: string, actorName: string) {
  const actionMap: Record<string, { stage?: string; operation?: string; toolName?: string; actorType?: "user" | "agent" | "tool" }> = {
    request_submitted: { stage: "Ask", operation: "Submit request", actorType: "user" },
    workflow_planned: { stage: "Collect", operation: "Workflow planned", actorType: "agent" },
    tool_selected: { stage: "Collect", operation: "Tool selected", actorType: "agent" },
    evidence_collected: { stage: "Collect", operation: "Evidence collected", toolName: actorName, actorType: "tool" },
    nebius_reasoning_started: { stage: "Reason", operation: "Reasoning started", actorType: "agent" },
    structured_evidence: { stage: "Reason", operation: "Structured evidence", actorType: "agent" },
    source_check_started: { stage: "Verify", operation: "Source check started", actorType: "agent" },
    source_check_completed: { stage: "Verify", operation: "Source check completed", actorType: "agent" },
    case_study_generation_started: { stage: "Code", operation: "Case study generation", actorType: "agent" },
    case_study_created: { stage: "Code", operation: "Case study created", actorType: "agent" },
    run_saved: { stage: "Code", operation: "Run saved", toolName: actorName, actorType: "tool" },
    case_study_opened: { stage: "Review", operation: "Document opened", actorType: "user" },
    case_study_edit_started: { stage: "Review", operation: "Edit started", actorType: "user" },
    case_study_saved: { stage: "Review", operation: "Document saved", actorType: "user" },
    case_study_deleted: { stage: "Review", operation: "Case study deleted", actorType: "user" },
    case_study_restored: { stage: "Review", operation: "Case study restored", actorType: "user" },
    velt_user_switched: { stage: "Review", operation: "Reviewer switched", actorType: "user" }
  };
  return actionMap[actionType] ?? {};
}

function activityItems(value: unknown): VeltActivityItem[] {
  if (!Array.isArray(value)) return [];
  const sorted = value
    .map((item): VeltActivityItem | null => {
      if (!item || typeof item !== "object") return null;
      const record = item as {
        id?: unknown;
        actionType?: unknown;
        actionUser?: { name?: unknown };
        displayMessageTemplateData?: {
          message?: unknown;
          actorType?: unknown;
          agentName?: unknown;
          toolName?: unknown;
          stage?: unknown;
          operation?: unknown;
        };
        metadata?: {
          actorType?: unknown;
          agentName?: unknown;
          toolName?: unknown;
          stage?: unknown;
          operation?: unknown;
        };
        timestamp?: unknown;
      };
      const actionType = String(record.actionType ?? "activity");
      const actorFromVelt = String(record.actionUser?.name ?? "Signals");
      const inferred = inferredAuditFields(actionType, actorFromVelt);
      const actorTypeValue = String(record.displayMessageTemplateData?.actorType ?? record.metadata?.actorType ?? inferred.actorType ?? "unknown");
      const actorType = actorTypeValue === "user" || actorTypeValue === "agent" || actorTypeValue === "tool" ? actorTypeValue : "unknown";
      const actorName = String(
        record.displayMessageTemplateData?.toolName ??
          record.metadata?.toolName ??
          record.displayMessageTemplateData?.agentName ??
          record.metadata?.agentName ??
          inferred.toolName ??
          record.actionUser?.name ??
          "Signals"
      );
      const category = actorType === "user" || ["Analyst", "Reviewer", "Local operator"].includes(actorName) ? "Human" : "Agent";
      return {
        id: String(record.id ?? `${record.actionType ?? "activity"}-${record.timestamp ?? Math.random()}`),
        actionType,
        actorName,
        actorType,
        category,
        message: String(record.displayMessageTemplateData?.message ?? "recorded an activity."),
        stage: record.displayMessageTemplateData?.stage ? String(record.displayMessageTemplateData.stage) : record.metadata?.stage ? String(record.metadata.stage) : inferred.stage,
        operation: record.displayMessageTemplateData?.operation
          ? String(record.displayMessageTemplateData.operation)
          : record.metadata?.operation
            ? String(record.metadata.operation)
            : inferred.operation,
        toolName: record.displayMessageTemplateData?.toolName
          ? String(record.displayMessageTemplateData.toolName)
          : record.metadata?.toolName
            ? String(record.metadata.toolName)
            : inferred.toolName,
        timestamp: typeof record.timestamp === "number" ? record.timestamp : 0
      };
    })
    .filter((item): item is VeltActivityItem => Boolean(item))
    .sort((a, b) => a.timestamp - b.timestamp);

  const compact: VeltActivityItem[] = [];
  for (const item of sorted) {
    const previous = compact[compact.length - 1];
    if (
      previous &&
      previous.actorName === item.actorName &&
      previous.actionType === item.actionType &&
      previous.category === item.category &&
      previous.stage === item.stage &&
      previous.operation === item.operation &&
      previous.message === item.message &&
      item.timestamp - (previous.lastTimestamp ?? previous.timestamp) < 90_000
    ) {
      previous.count = (previous.count ?? 1) + 1;
      previous.lastTimestamp = item.timestamp;
      continue;
    }
    compact.push({ ...item, count: 1, lastTimestamp: item.timestamp });
  }

  return compact;
}

function ActivityTimeline({ items }: { items: VeltActivityItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-[18px] border border-dashed border-line bg-white/70 p-4 text-sm text-muted">
        No Velt audit events found for this workflow run yet.
      </div>
    );
  }

  return (
    <div className="thin-scroll max-h-[360px] overflow-auto rounded-[20px] border border-line bg-white">
      <ol className="divide-y divide-line">
        {items.slice(0, 50).map((item, index) => (
          <li key={item.id} className="grid gap-3 px-4 py-3 sm:grid-cols-[42px_minmax(0,1fr)_150px]">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-panel2 text-xs font-semibold text-text">
              {index + 1}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-text">
                <span
                  className={`rounded-md px-2 py-0.5 text-xs ${
                    item.category === "Human" ? "bg-teal/10 text-teal" : "bg-blue/10 text-blue"
                  }`}
                >
                  {item.category}
                </span>
                <span>{item.actorName}</span>
                <span className="rounded-md bg-blue/10 px-2 py-0.5 text-xs text-blue">{readableAction(item.actionType)}</span>
                {item.stage ? <span className="rounded-md bg-panel2 px-2 py-0.5 text-xs text-dim">{item.stage}</span> : null}
                {item.operation ? <span className="rounded-md bg-panel2 px-2 py-0.5 text-xs text-dim">{item.operation}</span> : null}
                {item.count && item.count > 1 ? <span className="rounded-md bg-amber/20 px-2 py-0.5 text-xs text-amber">x{item.count}</span> : null}
              </div>
              <p className="mt-1 text-sm leading-6 text-muted">{item.message}</p>
            </div>
            <time className="text-xs text-dim sm:text-right">
              {item.timestamp ? new Date(item.timestamp).toLocaleString() : "Time unavailable"}
              {item.count && item.count > 1 && item.lastTimestamp ? (
                <span className="block">to {new Date(item.lastTimestamp).toLocaleTimeString()}</span>
              ) : null}
            </time>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function VeltWorkspace({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const users = useMemo(() => hardcodedUsers(), []);
  const [user, setUser] = useState<LocalVeltUser | null>(users[0] ?? null);

  useEffect(() => {
    setUser(initialUser(users));
  }, [users]);

  const switchUser = (userId: string) => {
    const nextUser = users.find((candidate) => candidate.userId === userId);
    if (!nextUser) return;
    window.localStorage.setItem("signals_user_id", nextUser.userId);
    setUser(nextUser);
  };

  const authProvider = useMemo<VeltAuthProvider | undefined>(() => {
    if (!user) return undefined;

    return {
      user,
      retryConfig: { retryCount: 2, retryDelay: 1000 },
      generateToken: async () => {
        const response = await fetch("/api/velt/token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          body: JSON.stringify(user)
        });
        const data = (await response.json().catch(() => ({}))) as { token?: string; error?: string };
        if (!response.ok || !data.token) {
          throw new Error(data.error ?? "Velt token endpoint did not return a token.");
        }
        return data.token;
      },
      onError: (error) => {
        console.warn("Velt auth provider error", error);
      }
    };
  }, [user]);

  const contextValue = useMemo(
    () => ({
      users,
      currentUser: user,
      switchUser
    }),
    [user, users]
  );

  if (pathname?.startsWith("/print/")) {
    return <VeltUserContext.Provider value={contextValue}>{children}</VeltUserContext.Provider>;
  }

  if (!VELT_API_KEY || !VELT_ORG_ID || !authProvider) {
    return <VeltUserContext.Provider value={contextValue}>{children}</VeltUserContext.Provider>;
  }

  return (
    <VeltUserContext.Provider value={contextValue}>
      <VeltProvider apiKey={VELT_API_KEY} authProvider={authProvider}>
        <VeltRuntimeConfigurator users={users} />
        {children}
      </VeltProvider>
    </VeltUserContext.Provider>
  );
}

export function VeltActivityLogSurface({
  configured,
  authOk,
  authMessage,
  run,
  runs
}: {
  configured: boolean;
  authOk?: boolean;
  authMessage?: string;
  run?: WorkflowRunRecord | null;
  runs: WorkflowRunRecord[];
}) {
  const [selectedRunId, setSelectedRunId] = useState(run?.id ?? "");
  const [category, setCategory] = useState<"All" | "Human" | "Agent">("All");
  const [diagnostic, setDiagnostic] = useState<{
    ok: boolean;
    status: number;
    message: string;
    documentId: string;
    count: number;
    activities?: unknown[];
    orgDiagnostics?: {
      maskedOrganizationId: string;
      mismatch: boolean;
      maskedValues: Record<string, string>;
    };
  } | null>(null);

  const selectedRun = useMemo(() => {
    if (selectedRunId) {
      const match = runs.find((item) => item.id === selectedRunId);
      if (match) return match;
    }
    return run ?? runs.find((item) => item.status === "completed") ?? runs[0] ?? null;
  }, [run, runs, selectedRunId]);
  const timelineItems = activityItems(diagnostic?.activities ?? []);
  const filteredItems = category === "All" ? timelineItems : timelineItems.filter((item) => item.category === category);

  useEffect(() => {
    if (run?.id) {
      setSelectedRunId(run.id);
    } else if (!selectedRunId && runs.length > 0) {
      setSelectedRunId((runs.find((item) => item.status === "completed") ?? runs[0]).id);
    }
  }, [run?.id, runs, selectedRunId]);

  useEffect(() => {
    if (!configured || !selectedRun?.id) {
      setDiagnostic(null);
      return;
    }
    void fetch(`/api/velt/activities?runId=${encodeURIComponent(selectedRun.id)}`, { cache: "no-store" })
      .then((response) => response.json())
      .then((data) => setDiagnostic(data))
      .catch((error) =>
        setDiagnostic({
          ok: false,
          status: 0,
          message: error instanceof Error ? error.message : "Could not read Velt activities.",
          documentId: `signals-case-study:${selectedRun.id}`,
          count: 0,
          activities: []
        })
      );
  }, [configured, selectedRun?.id]);

  if (!configured || !VELT_API_KEY || !VELT_ORG_ID) {
    return (
      <div className="rounded-[20px] border border-dashed border-line bg-white/70 p-4 text-sm text-muted">
        Audit Trail is waiting for public Velt env values.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <VeltRunDocument run={selectedRun ?? null} />
      <div className={`rounded-[18px] border p-3 text-sm ${authOk ? "border-mint/40 bg-mint/10 text-muted" : "border-amber/50 bg-amber/15 text-muted"}`}>
        {authOk ? "Audit trail for both Human and Agents fetched via Velt." : authMessage || "Velt auth could not be verified."}
      </div>
      <div className={`rounded-[18px] border p-3 text-sm ${diagnostic?.ok ? "border-mint/40 bg-white/80 text-muted" : "border-amber/50 bg-amber/15 text-muted"}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-semibold text-text">Workflow audit scope</div>
            <div className="mt-1">
              {selectedRun ? diagnostic?.message || "Checking Velt activity readback..." : "Select or run a workflow to scope the audit trail."}
            </div>
          </div>
          <select
            value={selectedRun?.id ?? ""}
            onChange={(event) => setSelectedRunId(event.target.value)}
            className="min-h-9 max-w-full rounded-md border border-line bg-white px-3 text-xs font-semibold text-text outline-none"
          >
            {runs.length === 0 ? <option value="">No workflow runs</option> : null}
            {runs.map((item) => (
              <option key={item.id} value={item.id}>
                {item.workflowName} / {new Date(item.createdAt).toLocaleString()}
              </option>
            ))}
          </select>
        </div>
        {diagnostic ? (
          <div className="mt-2 grid gap-2 text-xs sm:grid-cols-3">
            <span className="truncate rounded-md bg-panel2 px-2 py-1">Doc: {diagnostic.documentId}</span>
            <span className="rounded-md bg-panel2 px-2 py-1">Count: {diagnostic.count}</span>
            <span className="rounded-md bg-panel2 px-2 py-1">Org: {diagnostic.orgDiagnostics?.maskedOrganizationId ?? "n/a"}</span>
          </div>
        ) : null}
        {diagnostic?.orgDiagnostics?.mismatch ? (
          <div className="mt-2 rounded-md border border-red/30 bg-red/10 px-2 py-1 text-xs text-red">
            Velt org id env values do not match: {Object.entries(diagnostic.orgDiagnostics.maskedValues).map(([key, value]) => `${key}=${value}`).join(", ")}
          </div>
        ) : null}
      </div>
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs font-semibold uppercase text-dim">Workflow activity timeline</div>
          <div className="inline-flex rounded-md border border-line bg-white p-1">
            {(["All", "Human", "Agent"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setCategory(item)}
                className={`h-8 rounded px-3 text-xs font-semibold transition ${
                  category === item ? "bg-text text-white" : "text-muted hover:bg-panel2 hover:text-text"
                }`}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
        <ActivityTimeline items={filteredItems} />
      </div>
    </div>
  );
}

function CaseStudyRunList({
  runs,
  docs,
  activeRunId,
  onOpenRun,
  onDeleteRun
}: {
  runs: WorkflowRunRecord[];
  docs: CaseStudyDocRecord[];
  activeRunId?: string;
  onOpenRun: (id: string) => void;
  onDeleteRun: (id: string) => void;
}) {
  const runById = new Map(runs.map((run) => [run.id, run]));

  if (docs.length === 0) {
    return (
      <div className="rounded-[16px] border border-dashed border-line bg-white/70 p-3 text-sm leading-6 text-muted">
        No case-study documents yet. Completed workflow runs can be restored into documents.
      </div>
    );
  }

  return (
    <div className="thin-scroll max-h-[640px] space-y-2 overflow-auto pr-1">
      {docs.map((doc) => {
        const item = runById.get(doc.runId);
        return (
          <div
            key={doc.runId}
            className={`rounded-md border p-3 transition ${
              activeRunId === doc.runId ? "border-blue/60 bg-blue/10" : "border-line bg-white/70 hover:border-blue/40"
            }`}
          >
            <button onClick={() => onOpenRun(doc.runId)} className="w-full text-left">
              <div className="flex min-w-0 items-center justify-between gap-3">
                <span className="truncate text-sm font-semibold text-text">{doc.title}</span>
                <span className={item?.status === "failed" ? "text-red" : item?.status === "completed" ? "text-mint" : "text-blue"}>
                  {item?.status ?? "saved"}
                </span>
              </div>
              <div className="mt-2 line-clamp-2 text-xs leading-5 text-muted">{item?.userRequest ?? "Saved Signals case study"}</div>
              <div className="mt-2 font-mono text-[11px] text-dim">Updated {new Date(doc.updatedAt).toLocaleString()}</div>
            </button>
            <button
              type="button"
              onClick={() => onDeleteRun(doc.runId)}
              className="mt-3 inline-flex h-8 items-center gap-2 rounded-md border border-line bg-white px-2.5 text-xs font-semibold text-muted transition hover:border-red/40 hover:text-red"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </div>
        );
      })}
    </div>
  );
}

function CaseStudyEditor({
  run,
  onDeleted,
  onRestored
}: {
  run: WorkflowRunRecord | null;
  onDeleted: (runId: string) => void;
  onRestored: (doc: CaseStudyDocRecord) => void;
}) {
  const { currentUser } = useContext(VeltUserContext);
  const [doc, setDoc] = useState<CaseStudyDocRecord | null>(null);
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<"review" | "edit">("review");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [deletedAt, setDeletedAt] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [editLoggedFor, setEditLoggedFor] = useState("");

  useEffect(() => {
    if (!run || (run.status === "running" && !run.signalBrief)) {
      setDoc(null);
      setDraft("");
      return;
    }

    setLoading(true);
    setError("");
    void fetch(`/api/case-studies/${run.id}`, { cache: "no-store" })
      .then(async (response) => {
        const data = (await response.json()) as { doc?: CaseStudyDocRecord | null; deleted?: boolean; deletedAt?: string; error?: string };
        if (data.deleted) {
          setDoc(null);
          setDraft("");
          setDeletedAt(data.deletedAt ?? null);
          return;
        }
        if (!response.ok || !data.doc) throw new Error(data.error ?? "Could not open case study.");
        setDoc(data.doc);
        setDraft(data.doc.markdown);
        setDeletedAt(null);
        setMode("review");
        setEditLoggedFor("");
        await logHumanActivity({
          run,
          actorName: currentUser?.name ?? "Signals reviewer",
          actionType: "case_study_opened",
          message: "opened the case-study document.",
          metadata: { version: data.doc.version, title: data.doc.title }
        });
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not open case study."))
      .finally(() => setLoading(false));
  }, [currentUser?.name, run?.id, run?.status]);

  async function deleteDoc() {
    if (!run || !doc) return;
    const confirmed = window.confirm("Delete this case-study document? The workflow history and immutable Velt audit trail will remain.");
    if (!confirmed) return;

    setDeleting(true);
    setError("");
    try {
      const response = await fetch(`/api/case-studies/${run.id}`, { method: "DELETE" });
      const data = (await response.json().catch(() => ({}))) as { doc?: CaseStudyDocRecord; error?: string };
      if (!response.ok) throw new Error(data.error ?? "Could not delete case study.");
      await logHumanActivity({
        run,
        actorName: currentUser?.name ?? "Signals reviewer",
        actionType: "case_study_deleted",
        message: "deleted the case-study document.",
        metadata: { title: doc.title, version: doc.version }
      });
      setDeletedAt(data.doc?.deletedAt ?? new Date().toISOString());
      setDoc(null);
      setDraft("");
      onDeleted(run.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete case study.");
    } finally {
      setDeleting(false);
    }
  }

  async function restoreDoc() {
    if (!run) return;
    setRestoring(true);
    setError("");
    try {
      const response = await fetch(`/api/case-studies/${run.id}/restore`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lastEditor: currentUser?.name ?? "Signals reviewer" })
      });
      const data = (await response.json()) as { doc?: CaseStudyDocRecord; error?: string };
      if (!response.ok || !data.doc) throw new Error(data.error ?? "Could not restore case study.");
      setDoc(data.doc);
      setDraft(data.doc.markdown);
      setDeletedAt(null);
      setMode("review");
      await logHumanActivity({
        run,
        actorName: currentUser?.name ?? "Signals reviewer",
        actionType: "case_study_restored",
        message: "restored the case-study document from saved run data.",
        metadata: { title: data.doc.title, version: data.doc.version }
      });
      onRestored(data.doc);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not restore case study.");
    } finally {
      setRestoring(false);
    }
  }

  async function saveDoc() {
    if (!run || !doc) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/case-studies/${run.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          markdown: draft,
          title: extractTitle(draft, doc.title),
          lastEditor: currentUser?.name ?? "Signals reviewer"
        })
      });
      const data = (await response.json()) as { doc?: CaseStudyDocRecord; error?: string };
      if (!response.ok || !data.doc) throw new Error(data.error ?? "Could not save case study.");
      setDoc(data.doc);
      setDraft(data.doc.markdown);
      setMode("review");
      setEditLoggedFor("");
      await logHumanActivity({
        run,
        actorName: currentUser?.name ?? "Signals reviewer",
        actionType: "case_study_saved",
        message: "saved edits to the case-study document.",
        metadata: { version: data.doc.version, title: data.doc.title }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save case study.");
    } finally {
      setSaving(false);
    }
  }

  function updateDraft(value: string) {
    setDraft(value);
    if (run && doc && editLoggedFor !== `${run.id}:${doc.version}`) {
      setEditLoggedFor(`${run.id}:${doc.version}`);
      void logHumanActivity({
        run,
        actorName: currentUser?.name ?? "Signals reviewer",
        actionType: "case_study_edit_started",
        message: "started editing the case-study document.",
        metadata: { version: doc.version, title: doc.title }
      });
    }
  }

  function exportPdf() {
    if (!run || !doc) return;
    window.open(`/print/case-studies/${encodeURIComponent(run.id)}?print=1`, "_blank", "noopener,noreferrer");
  }

  if (!run) {
    return (
      <div className="rounded-[18px] border border-dashed border-line bg-white/70 p-4 text-sm text-muted">
        Open a run from the Case Studies list to review its editable document.
      </div>
    );
  }

  if (run.status === "running" && !run.signalBrief) {
    return (
      <div className="rounded-[18px] border border-dashed border-line bg-white/70 p-4 text-sm text-muted">
        This run is still being written. Open the case study after the workflow completes.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-[420px] items-center justify-center rounded-[20px] border border-line bg-white">
        <Loader2 className="h-5 w-5 animate-spin text-blue" />
      </div>
    );
  }

  if (deletedAt) {
    return (
      <div className="rounded-[20px] border border-dashed border-line bg-white/80 p-5 text-sm text-muted">
        <div className="text-base font-semibold text-text">This case study was deleted.</div>
        <p className="mt-2 leading-6">
          The workflow run remains in History and the immutable Velt Audit Trail remains available for review.
        </p>
        <p className="mt-1 text-xs text-dim">Deleted {new Date(deletedAt).toLocaleString()}</p>
        {error ? <div className="mt-3 rounded-[16px] border border-red/40 bg-red/10 p-3 text-sm text-red">{error}</div> : null}
        <button
          type="button"
          onClick={() => void restoreDoc()}
          disabled={restoring}
          className="mt-4 inline-flex h-9 items-center gap-2 rounded-md bg-blue px-3 text-xs font-semibold text-white transition hover:bg-teal disabled:cursor-not-allowed disabled:opacity-60"
        >
          {restoring ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
          Restore from run data
        </button>
      </div>
    );
  }

  const scrollContainerId = `signals-case-study-scroll-${run.id}`;
  const articleId = `signals-case-study-doc-${run.id}`;
  const renderedArticle = (
    <div id={scrollContainerId} className="thin-scroll h-full max-h-[760px] overflow-auto rounded-[20px] border border-line bg-white shadow-panel">
      <article id={articleId} className="mx-auto max-w-3xl px-5 py-7 sm:px-8">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
          <div className="text-xs font-semibold uppercase text-dim">Signals Case Study</div>
          <div className="flex items-center gap-2 text-xs text-dim">
            <span>Nemotron Ultra on Nebius</span>
            <span>/</span>
            <span>{new Date(run.createdAt).toLocaleString()}</span>
          </div>
        </div>
        <MarkdownArticle markdown={draft} />
      </article>
      <VeltComments
        textMode={true}
        streamMode={false}
        dialogOnHover={false}
        dialogOnTargetElementClick={false}
        floatingCommentDialog={true}
        sidebarButtonOnCommentDialog={false}
        userMentions={true}
        customAutocompleteSearch={true}
        paginatedContactList={false}
        atHereEnabled={false}
        shadowDom={false}
        commentPlaceholder="Comment on the selected case-study text"
        onCommentAdd={() => {
          void logHumanActivity({
            run,
            actorName: currentUser?.name ?? "Signals reviewer",
            actionType: "case_study_comment_added",
            message: "added a Velt text comment to the case-study document.",
            metadata: { title: doc?.title, version: doc?.version }
          });
        }}
      />
    </div>
  );

  return (
    <div className="min-w-0 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[18px] border border-line bg-white/80 p-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-text">
            <FileText className="h-4 w-4 text-teal" />
            <span className="truncate">{doc?.title ?? run.workflowName}</span>
          </div>
          <div className="mt-1 text-xs text-dim">
            Version {doc?.version ?? 1} / Last edited by {doc?.lastEditor ?? "Not available"}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={exportPdf}
            disabled={!doc || draft.trim().length === 0}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-line bg-white px-3 text-xs font-semibold text-muted transition hover:border-blue/50 hover:text-text disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FileDown className="h-3.5 w-3.5" />
            Export PDF
          </button>
          <button
            onClick={() => setMode(mode === "review" ? "edit" : "review")}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-line bg-white px-3 text-xs font-semibold text-muted transition hover:border-blue/50 hover:text-text"
          >
            {mode === "review" ? <Edit3 className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            {mode === "review" ? "Edit" : "Review"}
          </button>
          <button
            onClick={() => void saveDoc()}
            disabled={saving || !doc || draft.trim().length === 0}
            className="inline-flex h-9 items-center gap-2 rounded-md bg-blue px-3 text-xs font-semibold text-white transition hover:bg-teal disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save
          </button>
          <button
            onClick={() => void deleteDoc()}
            disabled={deleting || !doc}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-line bg-white px-3 text-xs font-semibold text-muted transition hover:border-red/40 hover:text-red disabled:cursor-not-allowed disabled:opacity-60"
          >
            {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            Delete
          </button>
        </div>
      </div>

      {error ? <div className="rounded-[16px] border border-red/40 bg-red/10 p-3 text-sm text-red">{error}</div> : null}

      {mode === "edit" ? (
        <div className="grid min-w-0 gap-3 2xl:grid-cols-[minmax(320px,0.92fr)_minmax(0,1.08fr)]">
          <div className="min-w-0 rounded-[20px] border border-line bg-white shadow-panel">
            <div className="flex h-11 items-center justify-between border-b border-line px-4">
              <span className="text-sm font-semibold text-text">Markdown editor</span>
              <span className="text-xs text-dim">Preview remains commentable</span>
            </div>
            <textarea
              value={draft}
              onChange={(event) => updateDraft(event.target.value)}
              className="thin-scroll min-h-[700px] w-full resize-y border-0 bg-white p-5 font-mono text-sm leading-6 text-text outline-none"
              spellCheck={false}
            />
          </div>
          <div className="min-w-0">{renderedArticle}</div>
        </div>
      ) : (
        renderedArticle
      )}
    </div>
  );
}

function VeltUserSwitcher({ run }: { run: WorkflowRunRecord | null }) {
  const { users, currentUser, switchUser } = useContext(VeltUserContext);
  if (users.length === 0 || !currentUser) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-dim">
        <Users className="h-3.5 w-3.5" />
        Reviewer
      </div>
      <div className="inline-flex rounded-md border border-line bg-white p-1">
        {users.map((user) => (
          <button
            key={user.userId}
            onClick={() => {
              switchUser(user.userId);
              void logHumanActivity({
                run,
                actorName: user.name,
                actionType: "reviewer_switched",
                message: `switched the review identity to ${user.name}.`,
                metadata: { userId: user.userId }
              });
            }}
            className={`inline-flex h-8 items-center gap-2 rounded px-2.5 text-xs font-semibold transition ${
              currentUser.userId === user.userId ? "bg-text text-white" : "text-muted hover:bg-panel2 hover:text-text"
            }`}
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: user.color }} />
            {user.name}
          </button>
        ))}
      </div>
    </div>
  );
}

export function VeltCollaborationSurface({
  configured,
  run,
  runs,
  onOpenRun
}: {
  configured: boolean;
  run: WorkflowRunRecord | null;
  runs: WorkflowRunRecord[];
  onOpenRun: (id: string) => void;
}) {
  const { currentUser } = useContext(VeltUserContext);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [docs, setDocs] = useState<CaseStudyDocRecord[]>([]);

  const refreshDocs = () => {
    void fetch("/api/case-studies", { cache: "no-store" })
      .then((response) => response.json())
      .then((data: { docs?: CaseStudyDocRecord[] }) => setDocs(data.docs ?? []))
      .catch(() => setDocs([]));
  };

  useEffect(() => {
    refreshDocs();
  }, [runs.length, run?.id]);

  async function deleteRunDoc(runId: string) {
    const targetRun = runs.find((item) => item.id === runId) ?? null;
    const targetDoc = docs.find((item) => item.runId === runId);
    const confirmed = window.confirm("Delete this case-study document? The workflow history and immutable Velt audit trail will remain.");
    if (!confirmed) return;

    const response = await fetch(`/api/case-studies/${runId}`, { method: "DELETE" });
    if (!response.ok) return;
    if (targetRun) {
      await logHumanActivity({
        run: targetRun,
        actorName: currentUser?.name ?? "Signals reviewer",
        actionType: "case_study_deleted",
        message: "deleted the case-study document.",
        metadata: { title: targetDoc?.title }
      });
    }
    setDocs((current) => current.filter((doc) => doc.runId !== runId));
    if (run?.id === runId) {
      const next = docs.find((doc) => doc.runId !== runId);
      if (next) onOpenRun(next.runId);
    }
  }

  if (!configured || !VELT_API_KEY || !VELT_ORG_ID) {
    return (
      <div className="rounded-[20px] border border-dashed border-line bg-white/70 p-4 text-sm text-muted">
        Velt Comments are waiting for public Velt env values.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <VeltRunDocument run={run} />
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[18px] border border-line bg-white/75 p-3 text-sm text-muted">
        <div className="flex min-w-0 flex-col gap-1">
          <span>Select text in review mode to add Velt comments. Edit mode saves Markdown to SQLite.</span>
          <span className="text-xs text-dim">Comments, presence, and activity stay in Velt; the document text stays local.</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <VeltUserSwitcher run={run} />
          <div className="inline-flex min-h-9 items-center gap-2 rounded-md border border-line bg-panel2 px-3 text-xs font-semibold text-text">
            <VeltPresence maxUsers={2} self={true} shadowDom={false} />
          </div>
          <div className="inline-flex h-9 items-center justify-center rounded-md border border-line bg-panel2 px-2 text-text">
            <VeltNotificationsTool
              shadowDom={false}
              panelShadowDom={false}
              panelOpenMode="sidebar"
              selfNotifications={true}
              tabConfig={{
                forYou: { name: "For you", enable: true },
                documents: { name: "Docs", enable: true },
                all: { name: "All", enable: true },
                people: { name: "People", enable: false }
              }}
            />
          </div>
          <button
            type="button"
            onClick={() => setCommentsOpen((open) => !open)}
            className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold transition ${
              commentsOpen ? "border-blue/50 bg-blue/10 text-blue" : "border-line bg-panel2 text-text hover:border-blue/40"
            }`}
          >
            <MessageSquareText className="h-3.5 w-3.5" />
            Comments
          </button>
        </div>
      </div>

      <div className="grid min-w-0 gap-3 xl:grid-cols-[260px_minmax(0,1fr)]">
        <CaseStudyRunList runs={runs} docs={docs} activeRunId={run?.id} onOpenRun={onOpenRun} onDeleteRun={(id) => void deleteRunDoc(id)} />
        <CaseStudyEditor
          run={run}
          onDeleted={() => refreshDocs()}
          onRestored={(doc) => setDocs((current) => [doc, ...current.filter((item) => item.runId !== doc.runId)])}
        />
      </div>

      <div
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-[420px] flex-col border-l border-line bg-white shadow-2xl transition-transform duration-200 ${
          commentsOpen ? "translate-x-0" : "translate-x-full"
        }`}
        aria-hidden={!commentsOpen}
      >
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line px-4 text-sm font-semibold text-text">
          <MessageSquareText className="h-4 w-4 text-teal" />
          Review comments
          <button onClick={() => setCommentsOpen(false)} className="ml-auto rounded-md p-1 text-muted hover:bg-panel2 hover:text-text">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">
          {commentsOpen ? (
            <VeltCommentsSidebar
              embedMode={true}
              shadowDom={false}
              commentPlaceholder="Comment on this case study"
              groupConfig={{ enable: false }}
            />
          ) : null}
        </div>
      </div>
      {commentsOpen ? <button className="fixed inset-0 z-40 cursor-default bg-black/10" onClick={() => setCommentsOpen(false)} aria-label="Close comments" /> : null}
    </div>
  );
}
