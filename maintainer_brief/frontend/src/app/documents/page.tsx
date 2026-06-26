"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL, DocumentRow, api } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import RunNowButton from "@/components/RunNowButton";

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
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (body.status === "created") created++;
      else if (body.status === "duplicate") dupes++;
    }
    setMessage(
      `${created} uploaded${dupes ? `, ${dupes} already ingested` : ""}. Run the brief to extract.`,
    );
    setUploading(false);
    refresh();
  };

  if (!selected) return <p className="text-muted">Select or create a project first.</p>;

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">Documents</h1>
          <p className="mt-1 text-sm text-muted">
            Conference decks, reports, RFCs, advisories for <b>{selected.name}</b> —
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
        className={`mt-6 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragOver ? "border-accent bg-accent-soft" : "border-line bg-card hover:border-accent/60"
        }`}
      >
        <div className="text-3xl">📄</div>
        <p className="mt-2 text-sm font-medium">
          {uploading ? "Uploading…" : "Drop PDFs here, or click to choose"}
        </p>
        <p className="mt-1 text-xs text-muted">PDF, PPTX, DOCX, PNG, JPG, XLSX · up to 100 MB each</p>
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

      {message && <p className="mt-4 text-sm text-accent">{message}</p>}

      {docs.length === 0 ? (
        <p className="mt-10 text-center text-muted">No documents yet.</p>
      ) : (
        <div className="mt-6 space-y-2">
          {docs.map((d) => (
            <div
              key={d.id}
              className="flex items-center justify-between rounded-sm border border-line bg-card p-4"
            >
              <div>
                <h2 className="font-serif text-lg">{d.title ?? `Document ${d.id}`}</h2>
                <p className="mt-0.5 text-xs text-muted">
                  {d.doc_category ?? "unclassified"}
                  {d.page_count ? ` · ${d.page_count} pages` : ""} · {d.status}
                </p>
              </div>
              <span
                className={`rounded-sm px-3 py-1 text-xs font-bold ${
                  d.signal_count > 0 ? "bg-accent-soft text-accent" : "bg-line text-muted"
                }`}
              >
                {d.signal_count} signal{d.signal_count === 1 ? "" : "s"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
