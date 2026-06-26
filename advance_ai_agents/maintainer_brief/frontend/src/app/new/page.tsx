"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Search, Star, CheckCircle2, ChevronRight, ChevronDown } from "lucide-react";
import { GALLERY, GalleryPreset, GithubRepoMeta, api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import ChipsInput from "@/components/ChipsInput";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { SegmentedControl } from "@/components/ui/SegmentedControl";

interface Draft {
  name: string;
  repos: string[];
  keywords: string[];
  competitors: { name: string; keywords: string[] }[];
  subreddits: string[];
  hn_queries: string[];
  recipient: string;
  cadence: "weekly" | "daily";
}

const EMPTY: Draft = {
  name: "", repos: [], keywords: [], competitors: [], subreddits: [],
  hn_queries: [], recipient: "", cadence: "weekly",
};

export default function NewProjectPage() {
  const router = useRouter();
  const { refresh, setSelectedId } = useProject();
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [started, setStarted] = useState(false);
  const [repoInput, setRepoInput] = useState("");
  const [repo, setRepo] = useState<GithubRepoMeta | null>(null);
  const [validating, setValidating] = useState(false);
  const [repoError, setRepoError] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const usePreset = (p: GalleryPreset) => {
    setDraft({
      ...EMPTY, name: p.name, repos: p.repos, keywords: p.keywords,
      competitors: p.competitors, subreddits: p.subreddits, hn_queries: p.hn_queries,
    });
    setRepo(null);
    setStarted(true);
  };

  const validateRepo = async () => {
    const r = repoInput.trim().replace(/^https?:\/\/github\.com\//, "").replace(/\/$/, "");
    if (!r) return;
    setValidating(true);
    setRepoError(null);
    try {
      const meta = await api.validateGithubRepo(r);
      setRepo(meta);
      setDraft((d) => ({
        ...d,
        name: d.name || meta.name.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        repos: d.repos.includes(meta.full_name) ? d.repos : [...d.repos, meta.full_name],
        keywords: d.keywords.length ? d.keywords : meta.suggested_keywords,
      }));
      setStarted(true);
    } catch {
      setRepoError("Couldn't find that repo. Use the org/name form, e.g. meshery/meshery.");
    } finally {
      setValidating(false);
    }
  };

  const create = async () => {
    setError(null);
    if (!draft.name.trim()) return setError("Give your brief a name.");
    if (!draft.repos.length) return setError("Add at least one GitHub repo.");
    setSaving(true);
    try {
      const config = {
        github: { repos: draft.repos },
        keywords: draft.keywords,
        competitors: draft.competitors,
        community: { subreddits: draft.subreddits, hn_queries: draft.hn_queries },
        newsletter: {
          recipients: draft.recipient ? [draft.recipient.trim()] : [],
          cadence: draft.cadence,
          subject_prefix: `${draft.name} Brief`,
        },
        documents: { urls: [] },
      };
      const project = await api.createProject(draft.name.trim(), config);
      await refresh();
      setSelectedId(project.id);
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">New brief</h1>
      <p className="mt-2 text-sm text-muted">
        Pick a project to monitor. We&apos;ll watch its GitHub activity, community
        chatter, and any documents you upload.
      </p>

      {!started && (
        <>
          <SectionLabel label="Popular projects" index={1} total={2} className="mt-9" />
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {GALLERY.map((p) => (
              <button key={p.name} onClick={() => usePreset(p)} className="text-left">
                <Card hover className="flex h-full items-start gap-3 p-4">
                  <span className="text-2xl leading-none">{p.emoji}</span>
                  <span>
                    <span className="block font-display text-base font-semibold text-ink">{p.name}</span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-muted">{p.blurb}</span>
                  </span>
                  <ChevronRight size={16} className="ml-auto mt-1 shrink-0 text-faint" />
                </Card>
              </button>
            ))}
          </div>

          <SectionLabel label="Or add your own repo" index={2} total={2} className="mt-10" />
          <div className="mt-4 flex gap-2">
            <div className="relative flex-1">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
              <Input
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && validateRepo()}
                placeholder="org/name  (e.g. langchain-ai/langchain)"
                className="pl-9"
              />
            </div>
            <Button variant="secondary" onClick={validateRepo} disabled={validating}>
              {validating ? "Checking…" : "Find repo"}
            </Button>
          </div>
          {repoError && <p className="mt-2 text-sm text-danger">{repoError}</p>}
        </>
      )}

      {started && (
        <div className="mt-8 space-y-6">
          {repo && (
            <Card className="flex items-center gap-3 p-4">
              {repo.owner_avatar && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={repo.owner_avatar} alt="" className="h-10 w-10 rounded-[6px]" />
              )}
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 font-medium text-ink">
                  {repo.full_name}
                  <CheckCircle2 size={14} className="text-success" />
                </div>
                <div className="flex items-center gap-1.5 truncate text-xs text-muted">
                  <Star size={11} className="text-gold" fill="currentColor" />
                  {repo.stargazers_count.toLocaleString()} · {repo.language ?? "—"} ·{" "}
                  {repo.description}
                </div>
              </div>
            </Card>
          )}

          <Field label="Brief name">
            <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </Field>

          <Field label="GitHub repos" hint="org/name — add more for multi-repo projects">
            <ChipsInput values={draft.repos} onChange={(v) => setDraft({ ...draft, repos: v })} placeholder="org/name" />
          </Field>

          <Field label="Keywords" hint="used to match community chatter">
            <ChipsInput values={draft.keywords} onChange={(v) => setDraft({ ...draft, keywords: v })} placeholder="add a keyword" />
          </Field>

          <Field label="Your email" hint="where the brief is delivered">
            <Input
              type="email"
              value={draft.recipient}
              onChange={(e) => setDraft({ ...draft, recipient: e.target.value })}
              placeholder="you@example.com"
            />
          </Field>

          <Field label="Cadence">
            <SegmentedControl
              value={draft.cadence}
              onChange={(c) => setDraft({ ...draft, cadence: c })}
              options={[
                { value: "weekly", label: "Weekly" },
                { value: "daily", label: "Daily" },
              ]}
            />
          </Field>

          <button
            onClick={() => setAdvanced((a) => !a)}
            className="flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.14em] text-muted transition-colors hover:text-primary"
          >
            {advanced ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            Advanced (competitors, communities)
          </button>
          {advanced && (
            <div className="space-y-6 rounded-[6px] border border-line bg-surface-2/50 p-4">
              <Field label="Competitor names" hint="tracked in Competitor Watch">
                <ChipsInput
                  values={draft.competitors.map((c) => c.name)}
                  onChange={(names) =>
                    setDraft({
                      ...draft,
                      competitors: names.map(
                        (n) => draft.competitors.find((c) => c.name === n) ?? { name: n, keywords: [n.toLowerCase()] },
                      ),
                    })
                  }
                  placeholder="e.g. Backstage"
                />
              </Field>
              <Field label="Subreddits">
                <ChipsInput values={draft.subreddits} onChange={(v) => setDraft({ ...draft, subreddits: v })} placeholder="e.g. kubernetes" />
              </Field>
              <Field label="Hacker News queries">
                <ChipsInput values={draft.hn_queries} onChange={(v) => setDraft({ ...draft, hn_queries: v })} placeholder="e.g. service mesh" />
              </Field>
            </div>
          )}

          {error && <p className="text-sm text-danger">{error}</p>}

          <div className="flex gap-3">
            <Button onClick={create} disabled={saving} arrow={!saving}>
              {saving ? "Creating…" : "Create brief"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setStarted(false);
                setDraft(EMPTY);
                setRepo(null);
              }}
            >
              Back
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline gap-2">
        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-faint">{label}</span>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </div>
      {children}
    </div>
  );
}
