"use client";

import { useMemo, useState } from "react";
import { api, Citation, PageInfo } from "@/lib/api";

/**
 * Renders a document page PNG with translucent highlight rectangles overlaid
 * at the Unsiloed citation positions.
 *
 * Calibrated against the live API (2026-06-12): citations are stored verbatim
 * as {bbox: [x0, y0, x1, y1], page, page_width, page_height} — corner
 * coordinates in Unsiloed's own normalized page frame. We scale to
 * percentages using the citation's page_width/page_height (NOT our PDF's
 * native dims — Unsiloed normalizes pages, e.g. letter → A4 595x842).
 * Legacy array/object bbox shapes are still parsed as a fallback.
 */

type Rect = { x: number; y: number; w: number; h: number; refW: number; refH: number };

function parseCitation(c: Citation, page: PageInfo): Rect | null {
  const raw = c.bbox as unknown;

  // Live Unsiloed shape: {bbox: [x0,y0,x1,y1], page_width, page_height}
  if (raw && typeof raw === "object" && !Array.isArray(raw) && "bbox" in raw) {
    const o = raw as { bbox: number[]; page_width?: number; page_height?: number };
    if (Array.isArray(o.bbox) && o.bbox.length >= 4) {
      const [x0, y0, x1, y1] = o.bbox;
      return {
        x: x0,
        y: y0,
        w: x1 - x0,
        h: y1 - y0,
        refW: o.page_width ?? page.width_pt,
        refH: o.page_height ?? page.height_pt,
      };
    }
  }
  // Fallbacks: bare [x, y, w, h] array or {left, top, width, height} in pt space
  if (Array.isArray(raw)) {
    const flat = (Array.isArray(raw[0]) ? raw[0] : raw) as number[];
    if (flat.length < 4) return null;
    return { x: flat[0], y: flat[1], w: flat[2], h: flat[3], refW: page.width_pt, refH: page.height_pt };
  }
  if (raw && typeof raw === "object" && "left" in (raw as object)) {
    const o = raw as Record<string, number>;
    return { x: o.left, y: o.top, w: o.width, h: o.height, refW: page.width_pt, refH: page.height_pt };
  }
  return null;
}

export default function CitationViewer({
  documentId,
  page,
  citations,
  activeCitationId,
}: {
  documentId: number;
  page: PageInfo;
  citations: Citation[];
  activeCitationId?: number;
}) {
  const [zoomed, setZoomed] = useState(false);

  const rects = useMemo(
    () =>
      citations
        .map((c) => ({ citation: c, rect: parseCitation(c, page) }))
        .filter((r): r is { citation: Citation; rect: Rect } => r.rect !== null),
    [citations, page],
  );

  return (
    <div>
      <div
        className={`relative overflow-hidden rounded-[6px] border border-line bg-white shadow-sm transition-all ${zoomed ? "cursor-zoom-out" : "cursor-zoom-in"}`}
        style={zoomed ? { transform: "scale(1.4)", transformOrigin: "top center" } : undefined}
        onClick={() => setZoomed(!zoomed)}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={api.pageImageUrl(documentId, page.page_no)}
          alt={`Page ${page.page_no}`}
          className="block w-full"
        />
        {rects.map(({ citation, rect }) => (
          <div
            key={citation.id}
            className={`citation-rect absolute border-2 border-primary bg-primary/20 ${
              activeCitationId === citation.id ? "z-10" : ""
            }`}
            style={{
              left: `${(rect.x / rect.refW) * 100}%`,
              top: `${(rect.y / rect.refH) * 100}%`,
              width: `${(rect.w / rect.refW) * 100}%`,
              height: `${(rect.h / rect.refH) * 100}%`,
            }}
            title={citation.snippet ?? citation.field_name ?? ""}
          >
            {citation.field_name && (
              <span className="absolute -top-5 left-0 whitespace-nowrap rounded-sm bg-primary px-1.5 py-0.5 text-[10px] font-bold text-white">
                {citation.field_name}
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
        Page {page.page_no} · {rects.length} citation{rects.length === 1 ? "" : "s"} · click to{" "}
        {zoomed ? "reset" : "zoom"} · extracted by Unsiloed
      </div>
    </div>
  );
}
