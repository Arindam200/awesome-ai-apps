"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import ChipsInput from "@/components/ChipsInput";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { SectionLabel } from "@/components/ui/SectionLabel";

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

  if (!selected)
    return (
      <p className="font-mono text-xs uppercase tracking-[0.16em] text-faint">
        Select or create a project first.
      </p>
    );

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
      <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">Settings</h1>
      <p className="mt-2 text-sm text-muted">
        Configure how <b className="text-ink">{selected.name}</b>&apos;s brief is built and delivered.
      </p>

      <SectionLabel label="Sources" className="mt-8" />
      <div className="mt-5 space-y-6">
        <Field label="Project name">
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="GitHub repos"><ChipsInput values={repos} onChange={setRepos} placeholder="org/name" /></Field>
        <Field label="Keywords"><ChipsInput values={keywords} onChange={setKeywords} placeholder="add a keyword" /></Field>
        <Field label="Competitors"><ChipsInput values={competitors} onChange={setCompetitors} placeholder="competitor name" /></Field>
        <Field label="Subreddits"><ChipsInput values={subreddits} onChange={setSubreddits} placeholder="subreddit" /></Field>
        <Field label="Hacker News queries"><ChipsInput values={hn} onChange={setHn} placeholder="query" /></Field>
      </div>

      <SectionLabel label="Delivery" className="mt-10" />
      <div className="mt-5 space-y-6">
        <Field label="Recipients"><ChipsInput values={recipients} onChange={setRecipients} placeholder="email" type="email" /></Field>
        <Field label="Subject prefix">
          <Input value={subjectPrefix} onChange={(e) => setSubjectPrefix(e.target.value)} />
        </Field>
        <Field label="Cadence">
          <SegmentedControl
            value={cadence}
            onChange={setCadence}
            options={[
              { value: "weekly", label: "Weekly" },
              { value: "daily", label: "Daily" },
            ]}
          />
        </Field>
      </div>

      <div className="mt-8 flex items-center gap-3 border-t border-line pt-5">
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
        {saved && <span className="text-sm text-success">Saved ✓</span>}
      </div>

      {/* danger zone */}
      <div className="mt-10 rounded-[6px] border border-danger/25 bg-danger-soft/50 p-4">
        <SectionLabel label="Danger zone" />
        <div className="mt-3 flex items-center justify-between gap-4">
          <p className="text-sm text-muted">
            Delete this project and all of its signals, briefs, and documents.
          </p>
          <Button variant="danger" onClick={remove}>
            <Trash2 size={14} />
            Delete
          </Button>
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
