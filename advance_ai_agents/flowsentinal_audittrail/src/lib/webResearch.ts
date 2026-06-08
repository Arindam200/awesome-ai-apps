export interface WebSource {
  title: string;
  url: string;
  publishedAt?: string;
  snippet?: string;
}

interface WebResearchResult {
  context: string;
  sources: WebSource[];
}

function withTimeout(ms: number): AbortSignal {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

const FETCH_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  Accept: "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
};

function stripTags(input: string): string {
  return input
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function getTagValue(block: string, tag: string): string {
  const m = block.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "i"));
  return m?.[1]?.trim() ?? "";
}

function parseRssItems(xml: string): WebSource[] {
  const itemBlocks = xml.match(/<item[\s\S]*?<\/item>/gi) ?? [];
  return itemBlocks
    .map((block) => {
      const title = stripTags(getTagValue(block, "title"));
      const url = stripTags(getTagValue(block, "link"));
      const pubDate = stripTags(getTagValue(block, "pubDate"));
      const description = stripTags(getTagValue(block, "description"));
      return {
        title,
        url,
        publishedAt: pubDate || undefined,
        snippet: description || undefined,
      };
    })
    .filter((item) => item.title && item.url);
}

function parseYear(query: string): number | null {
  const m = query.match(/\b(20\d{2})\b/);
  if (!m) return null;
  const year = Number(m[1]);
  return Number.isFinite(year) ? year : null;
}

function containsAny(query: string, words: string[]): boolean {
  const lower = query.toLowerCase();
  return words.some((w) => lower.includes(w));
}

export function shouldUseWebResearch(query: string): boolean {
  return containsAny(query, [
    "latest",
    "current",
    "today",
    "yesterday",
    "last week",
    "last month",
    "last quarter",
    "this week",
    "this month",
    "this year",
    "2025",
    "2026",
    "news",
    "updates",
    "announcement",
    "announced",
    "changelog",
    "launch",
    "launches",
    "released",
    "release",
    "competitor",
  ]);
}

async function fetchAnthropicNews(query: string): Promise<WebSource[]> {
  const signal = withTimeout(10000);
  const urls = [
    "https://www.anthropic.com/blog/rss.xml",
    "https://www.anthropic.com/news/rss.xml",
  ];
  let all: WebSource[] = [];
  for (const url of urls) {
    try {
      const res = await fetch(url, { signal, headers: FETCH_HEADERS });
      if (!res.ok) continue;
      const xml = await res.text();
      const parsed = parseRssItems(xml);
      if (parsed.length) {
        all = parsed;
        break;
      }
    } catch {
      // try next feed
    }
  }
  // Fallback: many hosts block bot-style RSS fetches with 403.
  if (!all.length) {
    const viaNews = await fetchGoogleNews(`site:anthropic.com ${query}`);
    if (viaNews.length) return viaNews.slice(0, 20);
    throw new Error("Anthropic RSS fetch failed");
  }
  const year = parseYear(query);
  if (!year) return all.slice(0, 12);
  const filtered = all.filter((i) => (i.publishedAt ?? "").includes(String(year)));
  return (filtered.length ? filtered : all).slice(0, 20);
}

async function fetchOpenAINews(query: string): Promise<WebSource[]> {
  const signal = withTimeout(10000);
  const res = await fetch("https://openai.com/news/rss.xml", { signal, headers: FETCH_HEADERS });
  if (!res.ok) throw new Error(`OpenAI RSS fetch failed: ${res.status}`);
  const xml = await res.text();
  const all = parseRssItems(xml);
  const year = parseYear(query);
  if (!year) return all.slice(0, 12);
  return all.filter((i) => (i.publishedAt ?? "").includes(String(year))).slice(0, 20);
}

function toGoogleNewsQuery(query: string): string {
  return encodeURIComponent(query);
}

async function fetchGoogleNews(query: string): Promise<WebSource[]> {
  const signal = withTimeout(10000);
  const q = toGoogleNewsQuery(query);
  const url = `https://news.google.com/rss/search?q=${q}&hl=en-IN&gl=IN&ceid=IN:en`;
  const res = await fetch(url, { signal, headers: FETCH_HEADERS });
  if (!res.ok) throw new Error(`Google News RSS fetch failed: ${res.status}`);
  const xml = await res.text();
  const all = parseRssItems(xml);
  const year = parseYear(query);
  const filtered = year
    ? all.filter((i) => (i.publishedAt ?? "").includes(String(year)))
    : all;
  return filtered.slice(0, 20);
}

export async function researchWeb(query: string): Promise<WebResearchResult | null> {
  const lower = query.toLowerCase();
  let sources: WebSource[] = [];

  try {
    if (lower.includes("anthropic")) {
      sources = await fetchAnthropicNews(query);
    } else if (lower.includes("openai")) {
      sources = await fetchOpenAINews(query);
    } else {
      sources = await fetchGoogleNews(query);
    }
  } catch {
    return null;
  }

  if (!sources.length) return null;

  const context = sources
    .slice(0, 10)
    .map((s, idx) => {
      const date = s.publishedAt ? ` | Date: ${s.publishedAt}` : "";
      const snip = s.snippet ? ` | Summary: ${s.snippet}` : "";
      return `${idx + 1}. ${s.title}${date}${snip} | URL: ${s.url}`;
    })
    .join("\n");

  return { context, sources: sources.slice(0, 10) };
}
