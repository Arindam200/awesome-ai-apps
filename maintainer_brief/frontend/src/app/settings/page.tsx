"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import ChipsInput from "@/components/ChipsInput";

interface NewsletterCfg {
  recipients?: string[];
  cadence?: "weekly" | "daily";
  subject_prefix?: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const { selected, refresh, setSelectedId } = useProject();
  const [name, setName] = useState("");
  const [repos, setRepos] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [competitors, setCompetitors] = useState<string[]>([]);
  const [subreddits, setSubreddits] = useState<string[]>([]);
  const [hn, setHn] = useState<string[]>([]);
  const [recipients, setRecipients] = useState<string[]>([]);
  const [cadence, setCadence] = useState<"weekly" | "daily">("weekly");
  const [subjectPrefix, setSubjectPrefix] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!selected) return;
    const c = selected.config as Record<string, unknown>;
    const github = (c.github as { repos?: string[] }) ?? {};
    const community = (c.community as { subreddits?: string[]; hn_queries?: string[] }) ?? {};
    const newsletter = (c.newsletter as NewsletterCfg) ?? {};
    setName(selected.name);
    setRepos(github.repos ?? []);
    setKeywords((c.keywords as string[]) ?? []);
    setCompetitors(((c.competitors as { name: string }[]) ?? []).map((x) => x.name));
    setSubreddits(community.subreddits ?? []);
    setHn(community.hn_queries ?? []);
    setRecipients(newsletter.recipients ?? []);
    setCadence(newsletter.cadence ?? "weekly");
    setSubjectPrefix(newsletter.subject_prefix ?? `${selected.name} Brief`);
  }, [selected]);

  if (!selected) return <p className="text-muted">Select or create a project first.</p>;

  const save = async () => {
    setSaving(true);
    setSaved(false);
    const existingCompetitors = (selected.config.competitors as { name: string; keywords: string[] }[]) ?? [];
    await api.updateProject(selected.id, {
      name,
      config: {
        github: { repos },
        keywords,
        competitors: competitors.map(
          (n) => existingCompetitors.find((c) => c.name === n) ?? { name: n, keywords: [n.toLowerCase()] },
        ),
        community: { subreddits, hn_queries: hn },
        newsletter: { recipients, cadence, subject_prefix: subjectPrefix },
      },
    });
    await refresh();
    setSaving(false);
    setSaved(true);
  };

  const remove = async () => {
    if (!confirm(`Delete "${selected.name}" and all its data? This can't be undone.`)) return;
    await api.deleteProject(selected.id);
    const remaining = await refresh();
    if (remaining[0]) setSelectedId(remaining[0].id);
    router.push(remaining.length ? "/" : "/new");
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-serif text-3xl">Settings</h1>
      <p className="mt-1 text-sm text-muted">Configure how <b>{selected.name}</b>&apos;s brief is built and delivered.</p>

      <div className="mt-6 space-y-6">
        <Field label="Project name">
          <input value={name} onChange={(e) => setName(e.target.value)}
            className="w-full rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
        </Field>
        <Field label="GitHub repos"><ChipsInput values={repos} onChange={setRepos} placeholder="org/name" /></Field>
        <Field label="Keywords"><ChipsInput values={keywords} onChange={setKeywords} placeholder="add a keyword" /></Field>
        <Field label="Competitors"><ChipsInput values={competitors} onChange={setCompetitors} placeholder="competitor name" /></Field>
        <Field label="Subreddits"><ChipsInput values={subreddits} onChange={setSubreddits} placeholder="subreddit" /></Field>
        <Field label="Hacker News queries"><ChipsInput values={hn} onChange={setHn} placeholder="query" /></Field>
        <Field label="Recipients"><ChipsInput values={recipients} onChange={setRecipients} placeholder="email" type="email" /></Field>
        <Field label="Subject prefix">
          <input value={subjectPrefix} onChange={(e) => setSubjectPrefix(e.target.value)}
            className="w-full rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
        </Field>
        <Field label="Cadence">
          <div className="flex gap-2">
            {(["weekly", "daily"] as const).map((c) => (
              <button key={c} onClick={() => setCadence(c)}
                className={`rounded-sm border px-4 py-1.5 text-sm capitalize ${
                  cadence === c ? "border-accent bg-accent text-white" : "border-line hover:bg-paper"
                }`}>{c}</button>
            ))}
          </div>
        </Field>

        <div className="flex items-center gap-3 border-t border-line pt-5">
          <button onClick={save} disabled={saving}
            className="rounded-sm bg-accent px-5 py-2.5 text-sm font-bold text-white hover:opacity-90 disabled:opacity-50">
            {saving ? "Saving…" : "Save changes"}
          </button>
          {saved && <span className="text-sm text-accent">Saved ✓</span>}
          <button onClick={remove}
            className="ml-auto rounded-sm border border-line px-4 py-2 text-sm text-muted hover:border-accent hover:text-accent">
            Delete project
          </button>
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
