import { notFound } from "next/navigation";
import { MarkdownArticle } from "@/components/MarkdownArticle";
import { getOrCreateCaseStudyDoc, getRun } from "@/lib/db";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function cleanSourceList(sources: string[]) {
  const seen = new Set<string>();
  return sources
    .filter((source) => source.startsWith("http"))
    .filter((source) => {
      if (seen.has(source)) return false;
      seen.add(source);
      return true;
    })
    .slice(0, 12);
}

export default async function PrintCaseStudyPage({
  params,
  searchParams
}: {
  params: Promise<{ runId: string }>;
  searchParams?: Promise<{ print?: string }>;
}) {
  const { runId: rawRunId } = await params;
  const runId = decodeURIComponent(rawRunId);
  const run = getRun(runId);
  const doc = getOrCreateCaseStudyDoc(runId);

  if (!run || !doc) {
    notFound();
  }

  const sources = cleanSourceList(run.structuredOutput?.sources ?? run.fetchResult?.sources ?? []);
  const shouldPrint = (await searchParams)?.print === "1";

  return (
    <main className="min-h-screen bg-[#f5f3ec] px-6 py-8 text-[#111827] print:bg-white sm:px-10">
      <script
        dangerouslySetInnerHTML={{
          __html: `
            window.addEventListener('DOMContentLoaded', function () {
              var button = document.getElementById('print-case-study-button');
              if (button) button.addEventListener('click', function () { window.print(); });
              ${shouldPrint ? "setTimeout(function(){ window.print(); }, 450);" : ""}
            });
          `
        }}
      />
      <style
        dangerouslySetInnerHTML={{
          __html: `
            @page { margin: 0.6in; }
            html { background: #f5f3ec; }
            @media print {
              html { background: #fff !important; }
              body { background: #fff !important; }
              main { padding: 0 !important; }
              .no-print { display: none !important; }
              a { color: #111827; text-decoration: none; }
              table, blockquote { break-inside: avoid; }
              h1, h2, h3 { break-after: avoid; }
              .print-page { box-shadow: none !important; border: 0 !important; max-width: none !important; padding: 0 !important; }
              .print-cover { break-after: avoid; }
            }
          `
        }}
      />
      <div className="no-print mx-auto mb-5 flex max-w-4xl items-center justify-between gap-3 rounded-lg border border-[#d8ddd6] bg-[#f7f8f5] px-4 py-3 text-sm">
        <span>Clean print view for this saved case-study document.</span>
        <button id="print-case-study-button" type="button" className="rounded-md bg-[#1f2933] px-3 py-2 text-xs font-semibold text-white">
          Print or Save PDF
        </button>
      </div>
      <article className="print-page mx-auto max-w-4xl rounded-xl border border-[#ddd8cd] bg-white px-8 py-9 shadow-sm sm:px-12">
        <header className="print-cover mb-9 border-b border-[#d8ddd6] pb-6">
          <div className="inline-flex rounded-full border border-[#d8ddd6] bg-[#f7f6f1] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#68736f]">
            Web Intelligence Agent Case Study
          </div>
          <h1 className="mt-5 text-[42px] font-semibold leading-[1.08] tracking-normal text-[#111827]">{doc.title}</h1>
          <p className="mt-4 max-w-3xl text-[15px] leading-7 text-[#4b5652]">Research goal: {run.userRequest}</p>
          <p className="mt-4 text-sm leading-6 text-[#68736f]">
            Nemotron Ultra on Nebius / Version {doc.version} / Last edited by {doc.lastEditor} /{" "}
            {new Date(doc.updatedAt).toLocaleString()}
          </p>
        </header>
        <MarkdownArticle markdown={doc.markdown} variant="print" />
        {sources.length > 0 ? (
          <section className="mt-10 border-t border-[#d8ddd6] pt-5">
            <h2 className="text-xl font-semibold text-[#111827]">Printable Source Links</h2>
            <ol className="mt-3 space-y-2 pl-5 text-sm leading-6 text-[#4b5652]">
              {sources.map((source) => (
                <li key={source} className="list-decimal break-all">
                  <a href={source}>{source}</a>
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </article>
    </main>
  );
}
