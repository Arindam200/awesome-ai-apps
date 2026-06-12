import type { WorkflowPlan } from "./types";

export function generateWorkflowCode(plan: WorkflowPlan): string {
  const scrapeBody =
    plan.targetUrls.length > 1
      ? {
          urls: plan.targetUrls.slice(0, 3),
          extraction_prompt: plan.searchQuery,
          formats: ["markdown", "text"]
        }
      : {
          url_to_scrape: plan.targetUrls[0] ?? "",
          extraction_prompt: plan.searchQuery,
          formats: ["markdown", "text"]
        };

  const endpointByOperation = {
    search: "/searches",
    scrape: "/scrapes",
    answers: "/answers",
    map: "/maps",
    crawl: "/crawls"
  } as const;

  const bodyByOperation = {
    search: { query: plan.searchQuery },
    scrape: scrapeBody,
    answers: { task: plan.searchQuery, json_format: plan.outputSchema },
    map: { url: plan.targetUrls[0] ?? "" },
    crawl: { start_url: plan.targetUrls[0] ?? "", max_pages: 5 }
  } as const;

  return `type WorkflowResult = {
  structuredData: unknown;
  sources: string[];
  metadata: Record<string, unknown>;
};

const outputSchema = ${JSON.stringify(plan.outputSchema, null, 2)};
const requestBody = ${JSON.stringify(bodyByOperation[plan.selectedOlostepOperation], null, 2)};

export async function runWebSignalWorkflow(): Promise<WorkflowResult> {
  const apiKey = process.env.OLOSTEP_API_KEY;
  if (!apiKey) {
    throw new Error("OLOSTEP_API_KEY is required");
  }

  const baseUrl = process.env.OLOSTEP_API_BASE_URL ?? "https://api.olostep.com/v1";
  const operation = "${plan.selectedOlostepOperation}";
  const endpoint = "${endpointByOperation[plan.selectedOlostepOperation]}";
  const urls = Array.isArray((requestBody as { urls?: string[] }).urls) ? (requestBody as { urls: string[] }).urls : [];

  async function callOlostep(body: unknown) {
    const response = await fetch(\`\${baseUrl.replace(/\\/$/, "")}\${endpoint}\`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: \`Bearer \${apiKey}\`
    },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      throw new Error(\`Olostep \${operation} endpoint \${endpoint} failed: \${response.status} \${await response.text()}\`);
    }

    return response.json();
  }

  const raw = urls.length > 0
    ? {
        pages: await Promise.all(
          urls.map((url) =>
            callOlostep({
              ...requestBody,
              urls: undefined,
              url_to_scrape: url
            })
          )
        )
      }
    : await callOlostep(requestBody);
  const sources = Array.from(
    new Set(JSON.stringify(raw).match(/https?:\\/\\/[^\\s"'<>),]+/g) ?? [])
  );

  return {
    structuredData: raw,
    sources,
    metadata: {
      operation,
      outputSchema,
      sourceCount: sources.length
    }
  };
}`;
}
