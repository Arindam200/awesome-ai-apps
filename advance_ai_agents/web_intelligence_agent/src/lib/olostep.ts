import { requireEnv } from "./env";
import type { FetchResult, OlostepOperation, WorkflowPlan } from "./types";

function baseUrl(): string {
  return (process.env.OLOSTEP_API_BASE_URL?.trim() || "https://api.olostep.com/v1").replace(/\/$/, "");
}

function timeoutSignal(ms: number): AbortSignal {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

function normalizeUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    const url = new URL(trimmed.startsWith("http") ? trimmed : `https://${trimmed}`);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return url.toString();
  } catch {
    return null;
  }
}

function collectUrls(value: unknown, limit = 20): string[] {
  const urls = new Set<string>();

  const visit = (item: unknown) => {
    if (urls.size >= limit) return;
    if (typeof item === "string") {
      const direct = normalizeUrl(item);
      if (direct) urls.add(direct);
      const matches = item.match(/https?:\/\/[^\s"'<>),]+/g) ?? [];
      for (const match of matches) {
        const url = normalizeUrl(match);
        if (url) urls.add(url);
      }
      return;
    }
    if (Array.isArray(item)) {
      item.forEach(visit);
      return;
    }
    if (item && typeof item === "object") {
      Object.values(item as Record<string, unknown>).forEach(visit);
    }
  };

  visit(value);
  return Array.from(urls).slice(0, limit);
}

async function callOlostep(operation: OlostepOperation, path: string, body: Record<string, unknown>) {
  const apiKey = requireEnv("OLOSTEP_API_KEY");
  const response = await fetch(`${baseUrl()}${path}`, {
    method: "POST",
    signal: timeoutSignal(75000),
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Olostep ${operation} endpoint ${path} failed (${response.status}): ${text.slice(0, 400)}`);
  }

  return response.json();
}

export async function olostepSearchTool(input: { query: string }): Promise<FetchResult> {
  const raw = await callOlostep("search", "/searches", { query: input.query });
  return {
    operation: "search",
    data: Array.isArray(raw?.result?.links) ? raw.result.links : Array.isArray(raw?.results) ? raw.results : raw,
    sources: collectUrls(raw),
    raw
  };
}

export async function olostepScrapeTool(input: {
  url: string;
  extractionPrompt?: string;
  outputSchema?: Record<string, unknown>;
}): Promise<FetchResult> {
  const raw = await callOlostep("scrape", "/scrapes", {
    url_to_scrape: input.url,
    formats: ["markdown", "text"],
    extraction_prompt: input.extractionPrompt,
    wait_before_scraping: 2000,
    remove_css_selectors: "default",
    remove_images: true,
    links_on_page: true
  });

  return {
    operation: "scrape",
    data: raw?.result ?? raw,
    sources: collectUrls([input.url, raw]),
    raw
  };
}

export async function olostepMultiScrapeTool(input: {
  urls: string[];
  extractionPrompt?: string;
  outputSchema?: Record<string, unknown>;
}): Promise<FetchResult> {
  const urls = Array.from(new Set(input.urls)).slice(0, 3);
  const pages = await Promise.all(
    urls.map((url) =>
      olostepScrapeTool({
        url,
        extractionPrompt: input.extractionPrompt,
        outputSchema: input.outputSchema
      })
    )
  );

  return {
    operation: "scrape",
    data: {
      pages: pages.map((page, index) => ({
        url: urls[index],
        data: page.data,
        sources: page.sources
      }))
    },
    pages,
    sources: Array.from(new Set(pages.flatMap((page) => page.sources))),
    raw: {
      urls,
      pages: pages.map((page) => page.raw)
    }
  };
}

export async function olostepAnswersTool(input: {
  question: string;
  jsonShape?: Record<string, unknown>;
}): Promise<FetchResult> {
  const raw = await callOlostep("answers", "/answers", {
    task: input.question,
    json_format: input.jsonShape
  });
  return {
    operation: "answers",
    data: raw?.answer ?? raw,
    sources: collectUrls(raw),
    raw
  };
}

export async function olostepMapTool(input: { url: string }): Promise<FetchResult> {
  const raw = await callOlostep("map", "/maps", { url: input.url });
  const urls = Array.isArray(raw?.urls) ? raw.urls.map(String) : collectUrls(raw, 50);
  return {
    operation: "map",
    urls,
    sources: collectUrls([input.url, raw]),
    raw
  };
}

export async function olostepCrawlTool(input: { url: string; limit?: number }): Promise<FetchResult> {
  const limit = Math.max(1, Math.min(input.limit ?? 5, 5));
  const raw = await callOlostep("crawl", "/crawls", {
    start_url: input.url,
    max_pages: limit
  });
  return {
    operation: "crawl",
    pages: Array.isArray(raw?.pages) ? raw.pages.slice(0, limit) : [],
    sources: collectUrls([input.url, raw], 50),
    raw
  };
}

export async function fetchWithPlan(plan: WorkflowPlan): Promise<FetchResult> {
  const operation: OlostepOperation = plan.selectedOlostepOperation;
  const url = plan.targetUrls[0];

  if (operation === "scrape") {
    if (plan.targetUrls.length > 1) {
      return olostepMultiScrapeTool({
        urls: plan.targetUrls,
        extractionPrompt: plan.searchQuery,
        outputSchema: plan.outputSchema
      });
    }
    return olostepScrapeTool({
      url,
      extractionPrompt: plan.searchQuery
    });
  }
  if (operation === "answers") {
    return olostepAnswersTool({ question: plan.searchQuery, jsonShape: plan.outputSchema });
  }
  if (operation === "map") {
    return olostepMapTool({ url });
  }
  if (operation === "crawl") {
    return olostepCrawlTool({ url, limit: 5 });
  }
  return olostepSearchTool({ query: plan.searchQuery });
}

export function validUrlOrBlank(raw: string): string {
  return normalizeUrl(raw) ?? "";
}

export function validUrls(raw: string, limit = 3): string[] {
  const urls = new Set<string>();
  const parts = raw
    .split(/[\n,\s]+/)
    .map((part) => part.trim())
    .filter(Boolean);

  for (const part of parts) {
    const url = normalizeUrl(part);
    if (url) urls.add(url);
    if (urls.size >= limit) break;
  }

  return Array.from(urls);
}
