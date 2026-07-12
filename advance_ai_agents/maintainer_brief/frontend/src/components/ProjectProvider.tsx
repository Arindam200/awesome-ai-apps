"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { Project, api, getToken } from "@/lib/api";

interface Ctx {
  projects: Project[];
  selected: Project | null;
  loaded: boolean;
  setSelectedId: (id: number) => void;
  refresh: () => Promise<Project[]>;
}

const ProjectCtx = createContext<Ctx | null>(null);
const LS_KEY = "mb.selectedProjectId";
const CACHE_KEY = "mb.projects";

function cachedProjects(): Project[] | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as Project[]) : null;
  } catch {
    return null;
  }
}

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedIdState] = useState<number | null>(null);
  const [loaded, setLoaded] = useState(false);

  const applyProjects = useCallback((ps: Project[]) => {
    setProjects(ps);
    setLoaded(true);
    setSelectedIdState((cur) => {
      const stored = Number(
        typeof window !== "undefined" ? localStorage.getItem(LS_KEY) : "",
      );
      const valid = ps.find((p) => p.id === (cur ?? stored));
      return valid ? valid.id : (ps[0]?.id ?? null);
    });
  }, []);

  const refresh = useCallback(async () => {
    const ps = await api.projects();
    applyProjects(ps);
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(ps));
    } catch {
      /* quota — skip cache */
    }
    return ps;
  }, [applyProjects]);

  useEffect(() => {
    // No session (public preview / sign-in screen) → nothing to fetch.
    if (!getToken()) {
      setLoaded(true);
      return;
    }
    // Render-then-revalidate: hydrate instantly from the cached list, then
    // refresh from the network (which also fixes any staleness).
    const cached = cachedProjects();
    if (cached?.length) applyProjects(cached);
    refresh().catch(() => setLoaded(true));
  }, [refresh, applyProjects]);

  const setSelectedId = useCallback((id: number) => {
    setSelectedIdState(id);
    if (typeof window !== "undefined") localStorage.setItem(LS_KEY, String(id));
  }, []);

  const selected = projects.find((p) => p.id === selectedId) ?? null;

  return (
    <ProjectCtx.Provider value={{ projects, selected, loaded, setSelectedId, refresh }}>
      {children}
    </ProjectCtx.Provider>
  );
}

export function useProject(): Ctx {
  const ctx = useContext(ProjectCtx);
  if (!ctx) throw new Error("useProject must be used within ProjectProvider");
  return ctx;
}
