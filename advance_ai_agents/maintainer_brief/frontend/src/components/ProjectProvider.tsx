"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { Project, api } from "@/lib/api";

interface Ctx {
  projects: Project[];
  selected: Project | null;
  loaded: boolean;
  setSelectedId: (id: number) => void;
  refresh: () => Promise<Project[]>;
}

const ProjectCtx = createContext<Ctx | null>(null);
const LS_KEY = "mb.selectedProjectId";

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedIdState] = useState<number | null>(null);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    const ps = await api.projects();
    setProjects(ps);
    setLoaded(true);
    setSelectedIdState((cur) => {
      const stored = Number(
        typeof window !== "undefined" ? localStorage.getItem(LS_KEY) : "",
      );
      const valid = ps.find((p) => p.id === (cur ?? stored));
      return valid ? valid.id : (ps[0]?.id ?? null);
    });
    return ps;
  }, []);

  useEffect(() => {
    refresh().catch(() => setLoaded(true));
  }, [refresh]);

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
