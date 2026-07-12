"use client";

import { useCallback, useEffect, useState } from "react";
import { UploadCloud, FileText } from "lucide-react";
import { API_URL, DocumentRow, api, authHeaders } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import RunNowButton from "@/components/RunNowButton";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { IconChip } from "@/components/ui/IconChip";

export default function DocumentsPage() {
  const { selected } = useProject();
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (selected) api.documents(selected.id).then(setDocs).catch(() => {});
  }, [selected]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const uploadFiles = async (files: FileList | File[]) => {
    if (!selected) return;
    setUploading(true);
    setMessage(null);
    let created = 0;
    let dupes = 0;
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/documents/upload?project_id=${selected.id}`, {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (body.status === "created") created++;
      else if (body.status === "duplicate") dupes++;
    }
    setMessage(`${created} uploaded${dupes ? `, ${dupes} already ingested` : ""}. Run the brief to extract.`);
    setUploading(false);
    refresh();
  };

  if (!selected)
    return (
      <p className="font-mono text-xs uppercase tracking-[0.16em] text-faint">
        Select or create a project first.
      </p>
    );

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">Documents</h1>
          <p className="mt-2 text-sm text-muted">
            Conference decks, reports, RFCs, advisories for <b className="text-ink">{selected.name}</b> —
            extracted into cited signals by Unsiloed.
          </p>
        </div>
        <RunNowButton projectId={selected.id} />
      </div>

      {/* drag-drop zone */}
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
        }}
        className={`mt-6 flex cursor-pointer flex-col items-center justify-center rounded-[8px] border-2 border-dashed px-6 py-12 text-center transition-colors ${
          dragOver ? "border-primary bg-primary-soft" : "border-line bg-surface hover:border-primary/50"
        }`}
      >
        <UploadCloud size={32} strokeWidth={1.75} className={dragOver ? "text-primary" : "text-faint"} />
        <p className="mt-3 text-sm font-medium text-ink">
          {uploading ? "Uploading…" : "Drop PDFs here, or click to choose"}
        </p>
        <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
          PDF · PPTX · DOCX · PNG · JPG · XLSX — up to 100 MB each
        </p>
        <input
          type="file"
          multiple
          accept=".pdf,.pptx,.ppt,.docx,.doc,.png,.jpg,.jpeg,.xlsx,.xls"
          className="hidden"
          disabled={uploading}
          onChange={(e) => {
            if (e.target.files?.length) uploadFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </label>

      {message && <p className="mt-4 text-sm text-primary">{message}</p>}

      {docs.length === 0 ? (
        <p className="mt-10 text-center font-mono text-xs uppercase tracking-[0.16em] text-faint">
          No documents yet.
        </p>
      ) : (
        <div className="mt-6 space-y-2">
          {docs.map((d) => (
            <Card key={d.id} className="flex items-center justify-between gap-4 p-4">
              <div className="flex items-center gap-3">
                <IconChip icon={FileText} tone="soft" size="sm" />
                <div>
                  <h2 className="font-display text-base font-semibold text-ink">
                    {d.title ?? `Document ${d.id}`}
                  </h2>
                  <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
                    {d.doc_category ?? "unclassified"}
                    {d.page_count ? ` · ${d.page_count} pages` : ""} · {d.status}
                  </p>
                </div>
              </div>
              <Badge tone={d.signal_count > 0 ? "blue" : "neutral"}>
                {d.signal_count} signal{d.signal_count === 1 ? "" : "s"}
              </Badge>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
