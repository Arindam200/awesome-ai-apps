import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";

import type {
  AppEvent,
  CodeActionResult,
  ProviderInfo,
  ServerJsonMessage,
  SummaryDepth,
  TimelineRole
} from "../shared/messages.js";
import { PcmPlayer, startMicrophoneStream, type AudioControls } from "./audio.js";
import "./styles.css";

type TimelineItem = {
  id: string;
  role: TimelineRole;
  text: string;
  at: number;
  pending?: boolean;
};

type StoredSession = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  target: string;
  depth: SummaryDepth;
  allowEdits: boolean;
  timeline: TimelineItem[];
  events: AppEvent[];
  result: CodeActionResult | null;
};

const HISTORY_KEY = "cursor_code_editor.sessions";
const MAX_SESSIONS = 12;
const INACTIVITY_CLOSE_MS = 5000;
const EDIT_ACCESS_GRACE_MS = 30000;
const PROVIDER_LINKS: Record<ProviderInfo["id"], string> = {
  deepgram: "https://developers.deepgram.com/docs/voice-agent",
  nebius: "https://docs.tokenfactory.nebius.com/",
  cursor: "https://cursor.com/docs/sdk/typescript"
};

function App() {
  const [status, setStatus] = useState("idle");
  const [workspace, setWorkspace] = useState("");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [missingEnv, setMissingEnv] = useState<string[]>([]);
  const [target, setTarget] = useState("workspace");
  const [depth, setDepth] = useState<SummaryDepth>("standard");
  const [allowEdits, setAllowEdits] = useState(false);
  const [level, setLevel] = useState(0);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [events, setEvents] = useState<AppEvent[]>([]);
  const [result, setResult] = useState<CodeActionResult | null>(null);
  const [sessions, setSessions] = useState<StoredSession[]>(loadSessions);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [showLog, setShowLog] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<AudioControls | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const hasUserTurnRef = useRef(false);
  const pauseTimerRef = useRef<number | null>(null);
  const resumeTimerRef = useRef<number | null>(null);
  const autoStopTimerRef = useRef<number | null>(null);
  const speakerDoneTimerRef = useRef<number | null>(null);
  const editAccessFollowupRef = useRef(false);
  const playerRef = useRef(new PcmPlayer());

  const connected = status !== "idle" && status !== "closed" && status !== "error";
  const canStart = missingEnv.length === 0 && !connected;

  useEffect(() => {
    void fetch("/api/health")
      .then((response) => response.json())
      .then((health) => {
        setMissingEnv(health.missingEnv || []);
        setWorkspace(health.workspace || "");
        setProviders(health.providers || []);
      })
      .catch(() => setStatus("health check failed"));
  }, []);

  const start = async () => {
    const id = crypto.randomUUID();
    const now = Date.now();
    const session: StoredSession = {
      id,
      title: "New voice chat",
      createdAt: now,
      updatedAt: now,
      target,
      depth,
      allowEdits,
      timeline: [],
      events: [],
      result: null
    };

    sessionIdRef.current = id;
    hasUserTurnRef.current = false;
    setCurrentSessionId(id);
    setTimeline([]);
    setEvents([]);
    setResult(null);
    setStatus("connecting");
    playerRef.current.reset();
    saveSessions([session, ...sessions].slice(0, MAX_SESSIONS));
    setSessions((items) => [session, ...items].slice(0, MAX_SESSIONS));

    const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/voice`);
    socket.binaryType = "arraybuffer";
    socketRef.current = socket;

    socket.onopen = async () => {
      socket.send(JSON.stringify({ type: "start", target, depth, allowEdits }));
      audioRef.current = await startMicrophoneStream(
        (chunk) => {
          if (socket.readyState === WebSocket.OPEN) socket.send(chunk);
        },
        setLevel,
        handleVoiceActivity
      );
    };

    socket.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        audioRef.current?.setPaused(true);
        void playerRef.current.play(event.data);
        return;
      }
      handleServerMessage(JSON.parse(event.data as string) as ServerJsonMessage);
    };

    socket.onerror = () => {
      addItem("error", "Voice socket failed.");
      setStatus("error");
    };

    socket.onclose = () => {
      clearVoiceTimers();
      setStatus("closed");
      audioRef.current?.stop();
      audioRef.current = null;
      setLevel(0);
    };
  };

  const stop = () => {
    clearVoiceTimers();
    socketRef.current?.send(JSON.stringify({ type: "stop" }));
    socketRef.current?.close();
    socketRef.current = null;
    audioRef.current?.stop();
    audioRef.current = null;
    playerRef.current.reset();
    setStatus("closed");
    setLevel(0);
  };

  const selectSession = (session: StoredSession) => {
    if (connected) return;
    sessionIdRef.current = session.id;
    setCurrentSessionId(session.id);
    setTimeline(session.timeline);
    setEvents(session.events);
    setResult(session.result);
    setTarget(session.target);
    setDepth(session.depth);
    setAllowEdits(session.allowEdits);
  };

  const sendSessionSettings = (next: Partial<Pick<StoredSession, "target" | "depth" | "allowEdits">> = {}) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(
      JSON.stringify({
        type: "update_settings",
        target: next.target ?? target,
        depth: next.depth ?? depth,
        allowEdits: next.allowEdits ?? allowEdits
      })
    );
  };

  const handleTargetChange = (nextTarget: string) => {
    setTarget(nextTarget);
  };

  const handleTargetBlur = () => {
    sendSessionSettings({ target });
  };

  const handleDepthChange = (nextDepth: SummaryDepth) => {
    setDepth(nextDepth);
    sendSessionSettings({ depth: nextDepth });
  };

  const handleEditAccessChange = (nextAllowEdits: boolean) => {
    setAllowEdits(nextAllowEdits);
    clearInactivityTimer();
    resumeMicSoon();
    sendSessionSettings({ allowEdits: nextAllowEdits });
  };

  const addItem = (role: TimelineRole, text: string, options: { pending?: boolean } = {}) => {
    const item = { id: crypto.randomUUID(), role, text: cleanDisplayText(text), at: Date.now(), pending: options.pending };
    setTimeline((items) => [...items, item].slice(-80));
    updateCurrentSession((session) => ({
      ...session,
      timeline: [...session.timeline, item].slice(-80),
      updatedAt: Date.now()
    }));

    if (role === "user") {
      void maybeTitleSession(item.text);
    }
  };

  const addEvent = (event: AppEvent) => {
    setEvents((items) => [...items, event].slice(-100));
    updateCurrentSession((session) => ({
      ...session,
      events: [...session.events, event].slice(-100),
      updatedAt: Date.now()
    }));
  };

  const handleServerMessage = (message: ServerJsonMessage) => {
    switch (message.type) {
      case "ready":
        setMissingEnv(message.missingEnv);
        setWorkspace(message.workspace);
        setProviders(message.providers);
        break;
      case "status":
        setStatus(message.status);
        if (message.status === "AgentThinking") {
          clearInactivityTimer();
          pauseMicSoon();
        }
        if (message.status === "AgentStartedSpeaking") {
          clearInactivityTimer();
          audioRef.current?.setPaused(true);
        }
        if (message.status === "UserStartedSpeaking") {
          clearInactivityTimer();
        }
        if (message.status === "AgentAudioDone") endVoiceAfterSpeaker();
        if (message.status === "ThinkUpdated") clearInactivityTimer();
        if (message.status === "edit access enabled") {
          editAccessFollowupRef.current = true;
          clearInactivityTimer();
          resumeMicSoon();
          scheduleInactivityStop(EDIT_ACCESS_GRACE_MS);
        }
        if (message.detail) addItem("system", message.detail);
        break;
      case "transcript":
        if (message.role === "user") {
          hasUserTurnRef.current = true;
          clearInactivityTimer();
        }
        addItem(message.role, message.text);
        break;
      case "function": {
        const statusMessage = friendlyFunctionMessage(message.name, message.status, message.detail, allowEdits);
        if (statusMessage) addItem(message.status === "error" ? "error" : "function", statusMessage, { pending: message.status === "requested" });
        break;
      }
      case "event":
        addEvent(message.event);
        break;
      case "result":
        setResult(message.result);
        updateCurrentSession((session) => ({ ...session, result: message.result, updatedAt: Date.now() }));
        addItem("assistant", message.result.spokenAnswer || `${message.result.title} is ready in the result panel.`);
        if (message.result.title.toLowerCase().includes("edit access")) {
          clearInactivityTimer();
          setStatus("waiting for edit access");
          resumeMicSoon();
          scheduleInactivityStop(EDIT_ACCESS_GRACE_MS);
        }
        break;
      case "error":
        setStatus("error");
        addItem("error", message.message);
        break;
      default:
        break;
    }
  };

  const maybeTitleSession = async (text: string) => {
    const id = sessionIdRef.current;
    const session = sessions.find((item) => item.id === id);
    if (!id || (session && session.title !== "New voice chat")) return;

    const fallback = text.split(/\s+/).slice(0, 6).join(" ");
    updateSession(id, (item) => ({ ...item, title: fallback || "Voice coding chat" }));

    try {
      const response = await fetch("/api/title", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text })
      });
      if (!response.ok) return;
      const data = (await response.json()) as { title?: string };
      if (data.title) updateSession(id, (item) => ({ ...item, title: data.title || item.title }));
    } catch {
      // The provisional title is good enough if Nebius title generation fails.
    }
  };

  const updateCurrentSession = (updater: (session: StoredSession) => StoredSession) => {
    const id = sessionIdRef.current;
    if (id) updateSession(id, updater);
  };

  const updateSession = (id: string, updater: (session: StoredSession) => StoredSession) => {
    setSessions((items) => {
      const next = items.map((item) => (item.id === id ? updater(item) : item)).slice(0, MAX_SESSIONS);
      saveSessions(next);
      return next;
    });
  };

  const pauseMicSoon = () => {
    if (pauseTimerRef.current) window.clearTimeout(pauseTimerRef.current);
    pauseTimerRef.current = window.setTimeout(() => {
      audioRef.current?.setPaused(true);
    }, 450);
  };

  const endVoiceAfterSpeaker = () => {
    audioRef.current?.setPaused(true);
    if (speakerDoneTimerRef.current) window.clearTimeout(speakerDoneTimerRef.current);
    const drainDelay = Math.min(8000, playerRef.current.bufferedMs() + 350);
    speakerDoneTimerRef.current = window.setTimeout(() => {
      setStatus("listening");
      resumeMicSoon();
      scheduleInactivityStop(editAccessFollowupRef.current ? EDIT_ACCESS_GRACE_MS : INACTIVITY_CLOSE_MS);
      editAccessFollowupRef.current = false;
      speakerDoneTimerRef.current = null;
    }, drainDelay);
  };

  const resumeMicSoon = () => {
    if (resumeTimerRef.current) window.clearTimeout(resumeTimerRef.current);
    resumeTimerRef.current = window.setTimeout(() => {
      audioRef.current?.setPaused(false);
    }, 650);
  };

  const clearVoiceTimers = () => {
    if (pauseTimerRef.current) window.clearTimeout(pauseTimerRef.current);
    if (resumeTimerRef.current) window.clearTimeout(resumeTimerRef.current);
    if (speakerDoneTimerRef.current) window.clearTimeout(speakerDoneTimerRef.current);
    clearInactivityTimer();
    pauseTimerRef.current = null;
    resumeTimerRef.current = null;
    speakerDoneTimerRef.current = null;
  };

  const scheduleInactivityStop = (delayMs = INACTIVITY_CLOSE_MS) => {
    clearInactivityTimer();
    autoStopTimerRef.current = window.setTimeout(() => {
      setStatus("finishing");
      stop();
    }, delayMs);
  };

  const handleVoiceActivity = () => {
    if (!autoStopTimerRef.current) return;
    scheduleInactivityStop();
  };

  const clearInactivityTimer = () => {
    if (autoStopTimerRef.current) window.clearTimeout(autoStopTimerRef.current);
    autoStopTimerRef.current = null;
  };

  const statusText = useMemo(() => {
    if (missingEnv.length) return `Missing ${missingEnv.join(", ")}`;
    return status;
  }, [missingEnv, status]);

  const resolvedTarget = useMemo(() => {
    if (!workspace) return "";
    if (!target || target === "workspace") return workspace;
    if (target.startsWith("/")) return target;
    return `${workspace.replace(/\/$/, "")}/${target}`;
  }, [target, workspace]);

  return (
    <main className="app">
      <section className="app-layout">
        <aside className="sidebar" aria-label="Workspace navigation">
          <div className="brand">
            <span className="brand-mark">VC</span>
            <span>
              <strong>VoxCode</strong>
              <small>Voice AI code workspace</small>
            </span>
          </div>

          <div className="sidebar-status">
            <span className={connected ? "dot live" : "dot"} />
            <span>{connected ? "Voice running" : "Ready"}</span>
          </div>

          <section className="sidebar-section">
            <div className="rail-heading">
              <span>Providers</span>
            </div>
            <div className="provider-stack" aria-label="Provider responsibilities">
              {providers.map((provider) => (
                <a
                  className={`provider ${provider.id}`}
                  href={PROVIDER_LINKS[provider.id]}
                  key={provider.id}
                  rel="noreferrer"
                  target="_blank"
                >
                  <span className="provider-logo">
                    <img src={`/logos/${provider.id}.svg`} alt={`${provider.name} logo`} />
                  </span>
                  <span className={`provider-badge ${provider.id}`}>{provider.name}</span>
                  <strong>{provider.models.join(" + ")}</strong>
                  <small>Docs</small>
                </a>
              ))}
            </div>
          </section>

          <section className="panel history">
            <div className="panel-heading">
              <h2>Chats</h2>
              <span>{sessions.length}</span>
            </div>
            {sessions.length === 0 ? (
              <div className="empty-state">
                <strong>No saved chats yet</strong>
                <p>Start voice once and your transcript, result, target, depth, and event log will stay here.</p>
              </div>
            ) : (
              <div className="history-list">
                {sessions.map((session) => (
                  <button
                    className={session.id === currentSessionId ? "history-item active" : "history-item"}
                    key={session.id}
                    onClick={() => selectSession(session)}
                    type="button"
                  >
                    <span>{session.title}</span>
                    <small>{new Date(session.updatedAt).toLocaleString()}</small>
                  </button>
                ))}
              </div>
            )}
          </section>
        </aside>

        <section className="main-workspace">
          <header className="workspace-header">
            <div>
              <p className="eyebrow">Workspace console</p>
              <h1>Make code edits or learn and chat about your codebase using Voice AI</h1>
            </div>
            <div className="flow-card" aria-label="VoxCode workflow">
              <span>Voice</span>
              <strong>Deepgram</strong>
              <span>Reasoning</span>
              <strong>Nebius Minimax</strong>
              <span>Code action</span>
              <strong>Cursor SDK</strong>
            </div>
          </header>

          <section className="controls">
            <div className="control-title">
              <span>Run setup</span>
              <strong>{allowEdits ? "Edits enabled" : "Read-only by default"}</strong>
            </div>
            <label className="target-field">
              Target
              <input
                value={target}
                onBlur={handleTargetBlur}
                onChange={(event) => handleTargetChange(event.target.value)}
                placeholder="workspace or src/app.ts"
              />
              <small className="field-hint">{resolvedTarget}</small>
            </label>
            <label>
              Depth
              <select value={depth} onChange={(event) => handleDepthChange(event.target.value as SummaryDepth)}>
                <option value="brief">Brief</option>
                <option value="standard">Standard</option>
                <option value="deep">Deep</option>
              </select>
            </label>
            <label className="toggle">
              <input type="checkbox" checked={allowEdits} onChange={(event) => handleEditAccessChange(event.target.checked)} />
              <span>Allow file edits</span>
            </label>
            <button onClick={connected ? stop : start} disabled={!connected && !canStart}>
              {status === "finishing" ? "Ending..." : connected ? "Stop voice" : "Start voice"}
            </button>
          </section>

          <section className={`statusbar ${connected ? "live" : ""}`}>
            <span className="pulse" style={{ transform: `scale(${1 + level})` }} />
            <span className="status-copy">
              <strong>{statusText}</strong>
              <small>{connected ? "Voice session active" : "Ready for a new voice session"}</small>
            </span>
            <span className="workspace">Workspace: {workspace}</span>
          </section>

          <section className="panel transcript">
            <div className="panel-heading">
              <h2>Conversation</h2>
              <span>{timeline.length}</span>
            </div>
            <div className="timeline">
              {timeline.length === 0 ? (
                <div className="empty-state command-menu">
                  <strong>Try saying</strong>
                  <p>“Summarize this workspace.”</p>
                  <p>“Give me a deep summary of the server folder.”</p>
                  <p>“What are Deepgram, Nebius, and Cursor doing here?”</p>
                </div>
              ) : (
                timeline.map((item) => (
                  <article className={`line ${item.role}${item.pending ? " pending" : ""}`} key={item.id}>
                    <span>{timelineLabel(item.role)}</span>
                    <p>{item.text}</p>
                  </article>
                ))
              )}
            </div>
          </section>
        </section>

        <aside className="inspector" aria-label="Result and activity">
          <ResultPanel result={result} />
          <section className={showLog ? "panel event-panel open" : "panel event-panel"}>
            <div className="panel-heading">
              <h2>Activity</h2>
              <button className="log-toggle" type="button" onClick={() => setShowLog((value) => !value)}>
                {showLog ? "Hide" : "Show"}
              </button>
            </div>
            {showLog ? <EventLog events={events} /> : null}
            {!showLog ? <p className="empty compact">Collapsed. Open to inspect Deepgram, Nebius, and Cursor activity.</p> : null}
          </section>
        </aside>
      </section>
    </main>
  );
}

function friendlyFunctionMessage(name: string, status: "requested" | "completed" | "error", detail?: string, allowEdits = false) {
  if (status === "completed") return "";
  if (status === "error") return detail ? `The agent hit an error: ${detail}` : "The agent hit an error.";

  if (name === "summarize_code") {
    return "Agent is reading the workspace with Cursor SDK. I’ll keep the full answer in the result panel.";
  }

  if (name === "edit_code") {
    if (!allowEdits) {
      return "Agent checked edit access for this session.";
    }
    return "Agent is preparing a file edit with Cursor SDK. I’ll show the changed files and summary when it finishes.";
  }

  return "Agent is working on that request.";
}

function timelineLabel(role: TimelineRole) {
  if (role === "function") return "agent";
  return role;
}

function cleanDisplayText(text: string) {
  return text
    .replace(/```[\s\S]*?```/g, "code block omitted")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}

function ResultPanel({ result }: { result: CodeActionResult | null }) {
  return (
    <div className="panel result">
      <div className="panel-heading">
        <h2>{result ? result.title : "Latest result"}</h2>
        {result ? <span>{result.action}</span> : null}
      </div>
      {!result ? (
        <div className="empty-state">
          <strong>No result yet</strong>
          <p>When Nebius routes a code function, Cursor output and the polished summary will appear here.</p>
        </div>
      ) : (
        <>
          {result.spokenAnswer ? <p className="spoken">{result.spokenAnswer}</p> : null}
          {result.directAnswer ? <InfoBlock title="Direct answer" text={result.directAnswer} /> : null}
          {result.purpose ? <InfoBlock title="Purpose" text={result.purpose} /> : null}
          {result.architecture ? <InfoBlock title="Architecture" text={result.architecture} /> : null}
          <p className="summary">{result.summary}</p>
          {result.polishedBy ? <p className="polished">Polished by Nebius {result.polishedBy}</p> : null}
          <List title="Key files" items={result.keyFiles} />
          {result.changes ? <List title="Changes" items={result.changes} /> : null}
          <List title="Risks" items={result.notableRisks} />
          <List title="Follow-ups" items={result.followUps} />
          {result.raw ? (
            <details className="raw">
              <summary>Raw Cursor result</summary>
              <pre>{result.raw}</pre>
            </details>
          ) : null}
        </>
      )}
    </div>
  );
}

function InfoBlock({ title, text }: { title: string; text: string }) {
  return (
    <section className="info-block">
      <h3>{title}</h3>
      <p>{text}</p>
    </section>
  );
}

function EventLog({ events }: { events: AppEvent[] }) {
  if (!events.length) return <p className="empty">Deepgram, Nebius, and Cursor activity will appear here.</p>;
  const visibleEvents = events.slice(-24).reverse();
  return (
    <div className="events">
      {visibleEvents.map((event, index) => (
        <article className={`event ${event.source} ${event.level || "info"}`} key={`${event.at}-${index}`}>
          <span>{new Date(event.at).toLocaleTimeString()} · {event.source}</span>
          <strong>{event.label}</strong>
          {event.detail ? <p>{event.detail}</p> : null}
        </article>
      ))}
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="mini">
      <h3>{title}</h3>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function loadSessions() {
  try {
    const parsed = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]") as StoredSession[];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_SESSIONS) : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: StoredSession[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)));
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
