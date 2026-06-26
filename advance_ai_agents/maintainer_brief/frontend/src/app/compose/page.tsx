"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Brief,
  SECTION_KEYS,
  SECTION_LABELS,
  SectionKey,
  SendResult,
  api,
} from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import ChipsInput from "@/components/ChipsInput";

export default function ComposePage() {
  const { selected, refresh } = useProject();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [noBrief, setNoBrief] = useState(false);
  const [html, setHtml] = useState("");
  const [subject, setSubject] = useState("");
  const [fromName, setFromName] = useState("Maintainer Brief");
  const [recipients, setRecipients] = useState<string[]>([]);
  const [sections, setSections] = useState<Record<SectionKey, boolean>>(
    {} as Record<SectionKey, boolean>,
  );
  const [sending, setSending] = useState<"test" | "all" | null>(null);
  const [result, setResult] = useState<SendResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadPreview = useCallback(async (briefId: number) => {
    const data = await api.briefHtml(briefId);
    setHtml(data.html);
    setSubject((s) => s || data.subject);
    setSections(data.sections);
    setRecipients((r) => (r.length ? r : data.default_recipients));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setNoBrief(false);
    api
      .latestBrief(selected.id)
      .then((b) => {
        setBrief(b);
        return loadPreview(b.id);
      })
      .catch(() => setNoBrief(true));
  }, [selected, loadPreview]);

  // toggle a section → persist on the project, then re-render preview
  const toggleSection = async (key: SectionKey) => {
    if (!selected || !brief) return;
    const next = { ...sections, [key]: !sections[key] };
    setSections(next);
    await api.updateProject(selected.id, { config: { newsletter: { sections: next } } });
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => loadPreview(brief.id).then(() => refresh()), 250);
  };

  const doSend = async (test: boolean) => {
    if (!brief) return;
    setSending(test ? "test" : "all");
    setError(null);
    setResult(null);
    try {
      const res = await api.sendBrief(brief.id, {
        recipients,
        subject,
        from_name: fromName,
        test,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(null);
    }
  };

  if (!selected) return <p className="text-muted">Select or create a project first.</p>;

  if (noBrief) {
    return (
      <div className="mx-auto mt-16 max-w-md text-center">
        <h1 className="font-serif text-3xl">Nothing to send yet</h1>
        <p className="mt-3 text-sm text-muted">
          Generate a brief for <b>{selected.name}</b> first, then come back to
          customize and send it.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block rounded-sm bg-accent px-4 py-2 text-sm font-bold text-white"
        >
          Go run the brief →
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-serif text-3xl">Compose &amp; Send</h1>
      <p className="mt-1 text-sm text-muted">
        Customize the newsletter for <b>{selected.name}</b>, preview the exact
        email, then send.
      </p>

      <div className="mt-6 grid gap-8 lg:grid-cols-[360px_1fr]">
        {/* controls */}
        <div className="space-y-6">
          <Field label="Recipients">
            <ChipsInput values={recipients} onChange={setRecipients} placeholder="add an email" type="email" />
          </Field>

          <Field label="Subject">
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </Field>

          <Field label="From name">
            <input
              value={fromName}
              onChange={(e) => setFromName(e.target.value)}
              className="w-full rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </Field>

          <div>
            <span className="text-sm font-medium">Sections</span>
            <div className="mt-2 space-y-1.5">
              {SECTION_KEYS.map((k) => (
                <label key={k} className="flex cursor-pointer items-center justify-between gap-2 text-sm">
                  <span className={sections[k] === false ? "text-muted line-through" : ""}>
                    {SECTION_LABELS[k]}
                  </span>
                  <button
                    type="button"
                    onClick={() => toggleSection(k)}
                    className={`relative h-5 w-9 rounded-full transition-colors ${
                      sections[k] === false ? "bg-line" : "bg-accent"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                        sections[k] === false ? "left-0.5" : "left-4"
                      }`}
                    />
                  </button>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-2 border-t border-line pt-4">
            <button
              onClick={() => doSend(true)}
              disabled={sending !== null || recipients.length === 0}
              className="w-full rounded-sm border border-line px-4 py-2 text-sm font-bold hover:bg-paper disabled:opacity-50"
            >
              {sending === "test" ? "Sending test…" : "Send test to first recipient"}
            </button>
            <button
              onClick={() => doSend(false)}
              disabled={sending !== null || recipients.length === 0}
              className="w-full rounded-sm bg-accent px-4 py-2 text-sm font-bold text-white hover:opacity-90 disabled:opacity-50"
            >
              {sending === "all"
                ? "Sending…"
                : `Send to ${recipients.length} recipient${recipients.length === 1 ? "" : "s"}`}
            </button>
            {result && (
              <p className="text-xs text-accent">
                {result.test ? "Test sent" : "Sent"} to {result.sent_to.join(", ")}
                {result.resend_id ? ` · id ${result.resend_id.slice(0, 8)}…` : ""}
              </p>
            )}
            {error && <p className="text-xs text-accent">{error}</p>}
          </div>
        </div>

        {/* live preview */}
        <div>
          <div className="mb-2 flex items-center justify-between text-xs text-muted">
            <span>Live preview</span>
            <span className="truncate">{subject}</span>
          </div>
          <div className="overflow-hidden rounded-sm border border-line bg-white shadow-sm">
            <iframe
              srcDoc={html}
              title="email preview"
              className="h-[70vh] w-full"
              sandbox=""
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      <div className="mt-1.5">{children}</div>
    </label>
  );
}
