"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Mail, FlaskConical, CheckCircle2 } from "lucide-react";
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
import { Button, ButtonLink } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Toggle } from "@/components/ui/Toggle";
import { Frame } from "@/components/ui/Frame";
import { Skeleton } from "@/components/ui/Skeleton";

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
  const [previewVersion, setPreviewVersion] = useState(0);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadPreview = useCallback(async (briefId: number) => {
    const data = await api.briefHtml(briefId);
    setHtml(data.html);
    setPreviewVersion((v) => v + 1); // force the iframe to remount on new HTML
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
        // Paint instantly with the pipeline-rendered HTML, then refresh with the
        // toggle-accurate live render in the background.
        if (b.html) {
          setHtml(b.html);
          setPreviewVersion((v) => v + 1);
        }
        void loadPreview(b.id);
      })
      .catch(() => setNoBrief(true));
  }, [selected, loadPreview]);

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
      const res = await api.sendBrief(brief.id, { recipients, subject, from_name: fromName, test });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(null);
    }
  };

  if (!selected)
    return (
      <p className="font-mono text-xs uppercase tracking-[0.16em] text-faint">
        Select or create a project first.
      </p>
    );

  if (noBrief) {
    return (
      <div className="mx-auto mt-16 max-w-md text-center">
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">
          Nothing to send yet
        </h1>
        <p className="mt-3 text-sm text-muted">
          Generate a brief for <b className="text-ink">{selected.name}</b> first, then come
          back to customize and send it.
        </p>
        <div className="mt-6">
          <ButtonLink href="/" arrow>
            Go run the brief
          </ButtonLink>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">
        Compose &amp; Send
      </h1>
      <p className="mt-2 text-sm text-muted">
        Customize the newsletter for <b className="text-ink">{selected.name}</b>, preview the
        exact email, then send.
      </p>

      <div className="mt-7 grid gap-8 lg:grid-cols-[360px_1fr]">
        {/* controls */}
        <div className="space-y-6">
          <Field label="Recipients">
            <ChipsInput values={recipients} onChange={setRecipients} placeholder="add an email" type="email" />
          </Field>

          <Field label="Subject">
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
          </Field>

          <Field label="From name">
            <Input value={fromName} onChange={(e) => setFromName(e.target.value)} />
          </Field>

          <div>
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
              Sections
            </span>
            <div className="mt-3 space-y-2.5">
              {SECTION_KEYS.map((k) => (
                <div key={k} className="flex items-center justify-between gap-2">
                  <span className={`text-sm ${sections[k] === false ? "text-faint line-through" : "text-ink"}`}>
                    {SECTION_LABELS[k]}
                  </span>
                  <Toggle checked={sections[k] !== false} onChange={() => toggleSection(k)} />
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2 border-t border-line pt-5">
            <Button
              variant="secondary"
              className="w-full"
              onClick={() => doSend(true)}
              disabled={sending !== null || recipients.length === 0}
            >
              <FlaskConical size={14} className="text-primary" />
              {sending === "test" ? "Sending test…" : "Send test to first recipient"}
            </Button>
            <Button
              className="w-full"
              onClick={() => doSend(false)}
              disabled={sending !== null || recipients.length === 0}
            >
              <Mail size={14} />
              {sending === "all"
                ? "Sending…"
                : `Send to ${recipients.length} recipient${recipients.length === 1 ? "" : "s"}`}
            </Button>
            {result && (
              <p className="flex items-center gap-1.5 text-xs text-success">
                <CheckCircle2 size={13} />
                {result.test ? "Test sent" : "Sent"} to {result.sent_to.join(", ")}
                {result.resend_id ? ` · id ${result.resend_id.slice(0, 8)}…` : ""}
              </p>
            )}
            {error && <p className="text-xs text-danger">{error}</p>}
          </div>
        </div>

        {/* live preview */}
        <div>
          <Frame label="Live preview" dots>
            {html ? (
              <iframe
                key={previewVersion}
                srcDoc={html}
                title="email preview"
                className="h-[70vh] w-full bg-white"
                sandbox=""
              />
            ) : (
              <div className="h-[70vh] space-y-4 bg-white p-8">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-8 w-2/3" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="mt-8 h-3 w-40" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            )}
          </Frame>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-faint">{label}</div>
      {children}
    </div>
  );
}
