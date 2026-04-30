import React from "react";
import * as pdfjsLib from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.mjs?url";
import { assetUrl } from "./api";
import type { SourceCitation } from "./types";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const pdfCache = new Map<string, Promise<ArrayBuffer>>();

type HighlightBox = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type PdfTextItem = {
  str: string;
  transform: number[];
  width: number;
  height: number;
};

export function PdfChunkPreview({ source }: { source: SourceCitation }) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const [highlights, setHighlights] = React.useState<HighlightBox[]>([]);
  const [status, setStatus] = React.useState("Loading highlighted PDF page...");

  React.useEffect(() => {
    let cancelled = false;
    const pdfUrl = assetUrl(source.pdf_url);
    const pageNumber = source.page_start ?? 1;
    if (!pdfUrl) return;

    async function renderPage() {
      const canvas = canvasRef.current;
      if (!canvas) return;
      setStatus("Loading highlighted PDF page...");
      setHighlights([]);
      let loadingTask: pdfjsLib.PDFDocumentLoadingTask | null = null;
      try {
        const pdfData = await fetchPdf(pdfUrl);
        if (cancelled) return;
        loadingTask = pdfjsLib.getDocument({ data: pdfData });
        const pdf = await loadingTask.promise;
        const page = await pdf.getPage(pageNumber);
        if (cancelled) return;

        const baseViewport = page.getViewport({ scale: 1 });
        const availableWidth = Math.max((containerRef.current?.clientWidth ?? 520) - 2, 320);
        const scale = Math.min(1.7, Math.max(0.72, availableWidth / baseViewport.width));
        const viewport = page.getViewport({ scale });
        const context = canvas.getContext("2d");
        if (!context) return;

        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * ratio);
        canvas.height = Math.floor(viewport.height * ratio);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;

        await page.render({
          canvas,
          canvasContext: context,
          viewport,
          transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
        }).promise;

        const textContent = await page.getTextContent();
        if (cancelled) return;
        const items = textContent.items.filter((item) => "str" in item) as PdfTextItem[];
        const boxes = locateChunkOnPage(items, source.text, viewport);
        setHighlights(boxes);
        setStatus(
          boxes.length > 0
            ? `Highlighted ${boxes.length} text ${boxes.length === 1 ? "span" : "spans"} on page ${pageNumber}.`
            : "Could not place an exact PDF overlay for this chunk. Use the evidence block below for the retrieved text.",
        );
      } catch (error) {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : "Could not render PDF page.");
        }
      } finally {
        loadingTask?.destroy();
      }
    }

    renderPage();
    return () => {
      cancelled = true;
    };
  }, [source.chunk_id, source.pdf_url, source.page_start, source.text]);

  return (
    <div className="pdf-highlight-viewer" ref={containerRef}>
      <div className="pdf-page-layer">
        <canvas ref={canvasRef} />
        {highlights.map((box, index) => (
          <span
            className="pdf-highlight-box"
            key={`${box.left}-${box.top}-${index}`}
            style={{
              left: `${box.left}px`,
              top: `${box.top}px`,
              width: `${box.width}px`,
              height: `${box.height}px`,
            }}
          />
        ))}
      </div>
      <div className="pdf-highlight-status">{status}</div>
    </div>
  );
}

function fetchPdf(url: string): Promise<ArrayBuffer> {
  const cached = pdfCache.get(url);
  if (cached) return cached.then((buffer) => buffer.slice(0));

  const request = fetch(url)
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`PDF request failed with ${response.status}`);
      }
      return response.arrayBuffer();
    })
    .catch((error) => {
      pdfCache.delete(url);
      throw error;
    });
  pdfCache.set(url, request);
  return request.then((buffer) => buffer.slice(0));
}

function locateChunkOnPage(
  items: PdfTextItem[],
  chunkText: string,
  viewport: pdfjsLib.PageViewport,
): HighlightBox[] {
  const pageIndex = buildSearchIndex(items.map((item) => item.str));
  const match = findBestMatch(pageIndex.text, chunkText);
  if (!match) return [];

  const itemIndexes = new Set(
    pageIndex.charToItem.slice(match.start, match.end).filter((index) => index >= 0),
  );
  return [...itemIndexes]
    .sort((a, b) => a - b)
    .map((itemIndex) => itemToHighlightBox(items[itemIndex], viewport))
    .filter((box) => box.width > 1 && box.height > 1)
    .slice(0, 80);
}

function buildSearchIndex(values: string[]) {
  let text = "";
  const charToItem: number[] = [];

  values.forEach((value, itemIndex) => {
    const normalized = normalizeForSearch(value);
    if (!normalized) return;
    if (text && !text.endsWith(" ")) {
      text += " ";
      charToItem.push(itemIndex);
    }
    for (const char of normalized) {
      text += char;
      charToItem.push(itemIndex);
    }
  });

  return { text, charToItem };
}

function findBestMatch(pageText: string, chunkText: string): { start: number; end: number } | null {
  for (const candidate of chunkCandidates(chunkText)) {
    const normalized = normalizeForSearch(candidate);
    if (normalized.length < 18) continue;
    const exact = pageText.indexOf(normalized);
    if (exact >= 0) return { start: exact, end: exact + normalized.length };

    const words = normalized.split(" ").filter(Boolean);
    for (let size = Math.min(words.length, 12); size >= 5; size -= 1) {
      const phrase = words.slice(0, size).join(" ");
      const partial = pageText.indexOf(phrase);
      if (partial >= 0) return { start: partial, end: partial + phrase.length };
    }
  }
  return null;
}

function chunkCandidates(text: string): string[] {
  const lines = text
    .split(/\n+/)
    .map((line) => line.replace(/[|*_`#>-]/g, " ").replace(/\s+/g, " ").trim())
    .filter((line) => line.length > 18 && !/^[-\s]+$/.test(line));
  return unique([
    lines.slice(0, 4).join(" ").slice(0, 220),
    ...lines.slice(0, 12).map((line) => line.slice(0, 180)),
    text.replace(/\s+/g, " ").trim().slice(0, 220),
  ]);
}

function itemToHighlightBox(item: PdfTextItem, viewport: pdfjsLib.PageViewport): HighlightBox {
  const transform = pdfjsLib.Util.transform(viewport.transform, item.transform);
  const left = transform[4];
  const fontHeight = Math.hypot(transform[2], transform[3]) || item.height * viewport.scale;
  const top = transform[5] - fontHeight;
  return {
    left,
    top,
    width: Math.max(item.width * viewport.scale, fontHeight * 0.45),
    height: Math.max(fontHeight * 1.12, 8),
  };
}

function normalizeForSearch(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}
