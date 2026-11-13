"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Icon } from "./Icon";
import { SketchPad } from "./SketchPad";

type ExampleCard = { id: string; file: string; name: string; licence?: string; author?: string };

export function Start({ examples }: { examples: ExampleCard[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [mode, setMode] = useState<"photo" | "draw">("photo");
  const [picked, setPicked] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  async function send(body: FormData | { example: string }) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        ...(body instanceof FormData ? { body } : { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } }),
      });
      const json = (await res.json()) as { id?: string; error?: string };
      if (!res.ok || !json.id) throw new Error(json.error || "Could not start the run.");
      router.push(`/run/${json.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
      setPicked(null);
    }
  }

  function upload(file: File | undefined, name?: string) {
    if (!file) return;
    if (!file.type.startsWith("image/")) return setError("Choose an image file: a photo or scan of the drawing.");
    const form = new FormData();
    form.set("image", file);
    form.set("name", name ?? file.name);
    void send(form);
  }

  return (
    <div className="stack" style={{ gap: 40 }}>
      <div className="card stack">
        <div className="spread">
          <h4>Your circuit</h4>
          <div className="tabs" role="tablist" style={{ borderBottom: 0 }}>
            <button className="tab" role="tab" aria-selected={mode === "photo"} onClick={() => setMode("photo")}>
              <Icon name="upload" /> Photo or scan
            </button>
            <button className="tab" role="tab" aria-selected={mode === "draw"} onClick={() => setMode("draw")}>
              <Icon name="pencil" /> Draw it here
            </button>
          </div>
        </div>

        {mode === "photo" ? (
          <div
            className={`drop${over ? " over" : ""}`}
            role="button"
            tabIndex={0}
            onClick={() => input.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(false);
              upload(e.dataTransfer.files[0]);
            }}
          >
            <Icon name="upload" size={28} />
            <div>{busy ? "Starting the run" : "Drop a photo of a hand-drawn circuit, or click to choose one"}</div>
            <div className="faint small">Notebook photos are fine. Mistakes are welcome: finding them is the point.</div>
            <input ref={input} type="file" accept="image/*" hidden onChange={(e) => upload(e.target.files?.[0])} />
          </div>
        ) : (
          <SketchPad busy={busy} onDone={(file) => upload(file, "Drawn in Inkwire")} />
        )}
        {error && <div className="error-box small">{error}</div>}
      </div>

      {examples.length > 0 && (
        <section className="stack">
          <div>
            <h3>Real sketches from the web</h3>
            <p className="muted small" style={{ margin: "4px 0 0" }}>Hand-drawn circuits under open licences. Pick one to run it.</p>
          </div>
          <div className="grid-3">
            {examples.map((ex) => (
              <button key={ex.id} className={`example${picked === ex.id ? " picked" : ""}`} disabled={busy} onClick={() => (setPicked(ex.id), send({ example: ex.id }))}>
                <img src={`/api/examples/${ex.file}`} alt={ex.name} />
                <span className="small">{picked === ex.id ? "Starting the run" : ex.name}</span>
                <span className="faint caption">{[ex.author, ex.licence].filter(Boolean).join(" · ")}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
