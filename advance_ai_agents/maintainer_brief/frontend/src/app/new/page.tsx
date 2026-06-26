"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { GALLERY, GalleryPreset, GithubRepoMeta, api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import ChipsInput from "@/components/ChipsInput";

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
  const [started, setStarted] = useState(false); // hide gallery once a preset/repo chosen
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
      <h1 className="font-serif text-4xl">New brief</h1>
      <p className="mt-1 text-sm text-muted">
        Pick a project to monitor. We&apos;ll watch its GitHub activity, community
        chatter, and any documents you upload.
      </p>

      {!started && (
        <>
          <h2 className="mt-8 text-xs font-bold uppercase tracking-[1.5px] text-accent">
            Popular projects
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {GALLERY.map((p) => (
              <button
                key={p.name}
                onClick={() => usePreset(p)}
                className="group flex items-start gap-3 rounded-sm border border-line bg-card p-4 text-left transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-sm"
              >
                <span className="text-2xl">{p.emoji}</span>
                <span>
                  <span className="block font-serif text-lg">{p.name}</span>
                  <span className="mt-0.5 block text-xs text-muted">{p.blurb}</span>
                </span>
              </button>
            ))}
          </div>

          <h2 className="mt-10 text-xs font-bold uppercase tracking-[1.5px] text-accent">
            Or add your own repo
          </h2>
          <div className="mt-3 flex gap-2">
            <input
              value={repoInput}
              onChange={(e) => setRepoInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && validateRepo()}
              placeholder="org/name  (e.g. langchain-ai/langchain)"
              className="flex-1 rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
            />
            <button
              onClick={validateRepo}
              disabled={validating}
              className="rounded-sm border border-line px-4 py-2 text-sm font-bold hover:bg-paper disabled:opacity-50"
            >
              {validating ? "Checking…" : "Find repo"}
            </button>
          </div>
          {repoError && <p className="mt-2 text-sm text-accent">{repoError}</p>}
        </>
      )}

      {started && (
        <div className="mt-8 space-y-6">
          {repo && (
            <div className="flex items-center gap-3 rounded-sm border border-line bg-card p-4">
              {repo.owner_avatar && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={repo.owner_avatar} alt="" className="h-10 w-10 rounded-sm" />
              )}
              <div>
                <div className="font-medium">{repo.full_name}</div>
                <div className="text-xs text-muted">
                  ★ {repo.stargazers_count.toLocaleString()} · {repo.language ?? "—"} ·{" "}
                  {repo.description}
                </div>
              </div>
            </div>
          )}

          <Field label="Brief name">
            <input
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              className="w-full rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </Field>

          <Field label="GitHub repos" hint="org/name — add more for multi-repo projects">
            <ChipsInput values={draft.repos} onChange={(v) => setDraft({ ...draft, repos: v })} placeholder="org/name" />
          </Field>

          <Field label="Keywords" hint="used to match community chatter">
            <ChipsInput values={draft.keywords} onChange={(v) => setDraft({ ...draft, keywords: v })} placeholder="add a keyword" />
          </Field>

          <Field label="Your email" hint="where the brief is delivered">
            <input
              type="email"
              value={draft.recipient}
              onChange={(e) => setDraft({ ...draft, recipient: e.target.value })}
              placeholder="you@example.com"
              className="w-full rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </Field>

          <Field label="Cadence">
            <div className="flex gap-2">
              {(["weekly", "daily"] as const).map((c) => (
                <button
                  key={c}
                  onClick={() => setDraft({ ...draft, cadence: c })}
                  className={`rounded-sm border px-4 py-1.5 text-sm capitalize ${
                    draft.cadence === c ? "border-accent bg-accent text-white" : "border-line hover:bg-paper"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </Field>

          <button
            onClick={() => setAdvanced((a) => !a)}
            className="text-xs font-bold text-muted hover:text-accent"
          >
            {advanced ? "▾" : "▸"} Advanced (competitors, communities)
          </button>
          {advanced && (
            <div className="space-y-6 rounded-sm border border-line bg-paper/40 p-4">
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

          {error && <p className="text-sm text-accent">{error}</p>}

          <div className="flex gap-3">
            <button
              onClick={create}
              disabled={saving}
              className="rounded-sm bg-accent px-5 py-2.5 text-sm font-bold text-white hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Creating…" : "Create brief"}
            </button>
            <button
              onClick={() => {
                setStarted(false);
                setDraft(EMPTY);
                setRepo(null);
              }}
              className="rounded-sm border border-line px-5 py-2.5 text-sm hover:bg-paper"
            >
              Back
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      {hint && <span className="ml-2 text-xs text-muted">{hint}</span>}
      <div className="mt-1.5">{children}</div>
    </label>
  );
}
