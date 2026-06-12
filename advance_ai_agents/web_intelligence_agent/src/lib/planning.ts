import { validUrls } from "./olostep";
import type { OlostepOperation, StageName, TaskType, WorkflowPlan } from "./types";

const STAGES: StageName[] = ["Ask", "Collect", "Reason", "Verify", "Code"];

function includesAny(value: string, words: string[]) {
  return words.some((word) => value.includes(word));
}

export function inferSchema(request: string): Record<string, unknown> {
  const lower = request.toLowerCase();

  if (includesAny(lower, ["pricing", "price", "plan", "limits"])) {
    return {
      items: [
        {
          planName: "string",
          monthlyPrice: "string",
          limits: ["string"],
          keyFeatures: ["string"],
          sourceUrl: "string"
        }
      ]
    };
  }

  if (includesAny(lower, ["changelog", "release", "breaking", "api", "sdk"])) {
    return {
      updates: [
        {
          title: "string",
          releaseDate: "string",
          newApis: ["string"],
          breakingChanges: ["string"],
          sourceUrl: "string"
        }
      ]
    };
  }

  if (includesAny(lower, ["launch", "funding", "hiring", "partnership", "announcement"])) {
    return {
      announcements: [
        {
          productName: "string",
          launchDate: "string",
          category: "string",
          summary: "string",
          sourceUrl: "string"
        }
      ]
    };
  }

  if (includesAny(lower, ["observability", "open-source", "github", "license"])) {
    return {
      projects: [
        {
          projectName: "string",
          githubUrl: "string",
          license: "string",
          description: "string",
          sourceUrl: "string"
        }
      ]
    };
  }

  return {
    items: [
      {
        title: "string",
        summary: "string",
        date: "string",
        sourceUrl: "string"
      }
    ]
  };
}

export function planWorkflow(request: string, optionalUrl: string): WorkflowPlan {
  const lower = request.toLowerCase();
  const targetUrls = validUrls(optionalUrl, 3);
  const targetUrl = targetUrls[0] ?? "";
  let operation: OlostepOperation = "search";
  let taskType: TaskType = "web_research";

  if (targetUrl) {
    if (targetUrls.length > 1) {
      operation = "scrape";
      taskType = "multi_page_scan";
    } else if (includesAny(lower, ["discover", "map", "links", "urls", "sitemap"])) {
      operation = "map";
      taskType = "site_discovery";
    } else if (includesAny(lower, ["crawl", "several pages", "multiple pages", "scan the site", "across the site"])) {
      operation = "crawl";
      taskType = "multi_page_scan";
    } else {
      operation = "scrape";
      taskType = includesAny(lower, ["monitor", "detect if", "changed", "watch"]) ? "page_monitor" : "known_url_extract";
    }
  } else if (includesAny(lower, ["answer", "question", "what ", "which ", "who ", "when ", "why ", "how "])) {
    operation = "answers";
  }

  const workflowName =
    request
      .replace(/[^\w\s-]/g, "")
      .split(/\s+/)
      .slice(0, 7)
      .join(" ")
      .trim() || "Web signal workflow";

  return {
    workflowName,
    taskType,
    selectedOlostepOperation: operation,
    searchQuery: request,
    targetUrls,
    outputSchema: inferSchema(request),
    assumptions: [
      targetUrls.length > 1
        ? "The provided URLs are treated as a small fixed source set."
        : targetUrl
          ? "The provided URL is the primary source."
          : "A broad web discovery operation is acceptable.",
      "Only source-backed data from Olostep should be structured.",
      "Optional URL input is capped at three URLs for the localhost MVP.",
      "Crawl operations are capped at five pages for the localhost MVP."
    ],
    steps: STAGES
  };
}
